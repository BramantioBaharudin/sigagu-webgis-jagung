import os
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path, override=True)

from services import auth_service as auth  # noqa: E402
from services import data_service as data  # noqa: E402
from services.import_service import parse_file  # noqa: E402

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # batas upload 5 MB
app.config["TEMPLATES_AUTO_RELOAD"] = True

YEARS = data.YEARS
LATEST_YEAR = YEARS[-1]
db = data.get_db()


# =====================================================================
# Helper template
# =====================================================================
@app.template_filter("angka")
def format_angka(value, decimals=2):
    """Format angka gaya Indonesia: 12.345,67"""
    if value is None:
        return "–"
    teks = f"{float(value):,.{decimals}f}"
    return teks.replace(",", "_").replace(".", ",").replace("_", ".")


@app.context_processor
def inject_globals():
    pending = 0
    if session.get("role") == "admin":
        pending = auth.count_pending(db)
    return {
        "current_user": {
            "nama": session.get("nama"),
            "username": session.get("username"),
            "role": session.get("role"),
        },
        "pending_operator": pending,
        "db_ready": db is not None,
        "status_label": auth.STATUS_LABEL,
        "min_k": data.MIN_K,
        "max_k": data.MAX_K,
        "default_k": data.DEFAULT_K,
        "warna_klaster": data.warna_klaster,
        "palet_k": data.WARNA_PER_K,
    }


def selected_year_arg() -> int:
    tahun = request.args.get("tahun", LATEST_YEAR, type=int)
    return tahun if tahun in YEARS else LATEST_YEAR


def require_db(redirect_endpoint, **kwargs):
    if not db:
        flash("Database Supabase belum dikonfigurasi. Periksa file .env.", "danger")
        return redirect(url_for(redirect_endpoint, **kwargs))
    return None


# =====================================================================
# Autentikasi role
# =====================================================================
def login_required(role):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user_id = session.get("user_id")
            if not user_id:
                flash("Silakan login terlebih dahulu.", "warning")
                return redirect(url_for("login"))

            user = auth.get_user(db, user_id) if db else None
            if not user or user["status"] != "disetujui":
                session.clear()
                flash("Sesi berakhir atau akun tidak lagi aktif. Silakan login kembali.", "warning")
                return redirect(url_for("login"))

            if user["role"] != role:
                return redirect(url_for(f"{user['role']}_dashboard"))
            return fn(*args, **kwargs)

        return wrapper

    return decorator


# =====================================================================
# 1. Halaman publik
# =====================================================================
@app.get("/")
def index():
    tahun = selected_year_arg()
    kecamatan = data.get_kecamatan(db)
    records = data.load_records(db)
    year_rows = data.records_for_year(records, tahun)

    selected_id = request.args.get("kecamatan", type=int)
    valid_ids = {int(k["id"]) for k in kecamatan}
    if selected_id not in valid_ids:
        selected_id = max(year_rows, key=lambda r: r["produksi"])["kecamatan_id"] if year_rows else None

    selected = next((r for r in year_rows if r["kecamatan_id"] == selected_id), None)
    history = data.history_for_kecamatan(records, selected_id) if selected_id else []
    selected_name = next(
        (k["nama_kecamatan"] for k in kecamatan if int(k["id"]) == selected_id), "–"
    )

    map_config = data.get_map_config(db, data.year_k(year_rows))
    profiles = data.cluster_profiles(year_rows)
    legenda = data.legend_items(map_config, profiles, data.get_keterangan(db, tahun))
    summary = data.yearly_summary(records).get(tahun, {})

    return render_template(
        "index.html",
        years=sorted(YEARS, reverse=True),
        selected_year=tahun,
        kecamatan=kecamatan,
        selected_id=selected_id,
        selected_name=selected_name,
        selected=selected,
        history=history,
        legenda=legenda,
        summary=summary,
        map_config=map_config,
    )


@app.get("/peta")
@app.get("/data")
def legacy_redirect():
    return redirect(url_for("index", tahun=selected_year_arg()))


# =====================================================================
# 2. Login, registrasi, logout, ganti password
# =====================================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for(f"{session.get('role')}_dashboard"))

    if request.method == "POST":
        user, error = auth.authenticate(
            db,
            request.form.get("username", ""),
            request.form.get("password", ""),
        )
        if error:
            flash(error, "danger")
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["nama"] = user["nama_lengkap"]
            session["role"] = user["role"]
            flash(f"Selamat datang, {user['nama_lengkap']}.", "success")
            return redirect(url_for(f"{user['role']}_dashboard"))

    return render_template("auth/login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        error = auth.register_operator(
            db,
            request.form.get("nama_lengkap", ""),
            request.form.get("username", ""),
            request.form.get("password", ""),
            request.form.get("konfirmasi", ""),
        )
        if error:
            flash(error, "danger")
            return render_template("auth/register.html", form=request.form)

        flash("Pendaftaran berhasil. Akun Anda akan aktif setelah divalidasi Admin.", "success")
        return redirect(url_for("login"))

    return render_template("auth/register.html", form={})


@app.get("/logout")
def logout():
    session.clear()
    flash("Anda telah keluar.", "success")
    return redirect(url_for("login"))


@app.route("/akun/password", methods=["GET", "POST"])
def ganti_password():
    role = session.get("role")
    if role not in ("admin", "operator"):
        return redirect(url_for("login"))

    @login_required(role)
    def handler():
        if request.method == "POST":
            try:
                auth.change_own_password(
                    db,
                    session["user_id"],
                    request.form.get("password_lama", ""),
                    request.form.get("password_baru", ""),
                    request.form.get("konfirmasi", ""),
                )
                flash("Password berhasil diganti.", "success")
                return redirect(url_for(f"{role}_dashboard"))
            except ValueError as exc:
                flash(str(exc), "danger")
        return render_template("auth/ganti_password.html", layout=f"{role}/layout_{role}.html")

    return handler()


# =====================================================================
# 3. Halaman bersama Admin & Operator
# =====================================================================
def render_dashboard(role):
    records = data.load_records(db)
    summary = data.yearly_summary(records)
    diproses = [t for t in YEARS if summary[t]["diproses"]]
    tahun_terakhir = diproses[-1] if diproses else None
    return render_template(
        f"{role}/dashboard.html",
        total_data=len(records),
        jumlah_kecamatan=len({r["kecamatan_id"] for r in records}),
        years=YEARS,
        summary=summary,
        k_max=max([summary[t]["k"] or 0 for t in YEARS] + [data.DEFAULT_K]),
        tahun_terakhir=tahun_terakhir,
        tahun_diproses=len(diproses),
    )


def render_data_pertanian(role):
    tahun = selected_year_arg()
    records = data.load_records(db)
    return render_template(
        f"{role}/data_pertanian.html",
        years=sorted(YEARS, reverse=True),
        selected_year=tahun,
        rows=data.records_for_year(records, tahun),
        kecamatan=data.get_kecamatan(db),
    )


def render_clustering(role):
    tahun = selected_year_arg()
    records = data.load_records(db)
    year_rows = data.records_for_year(records, tahun)
    map_config = data.get_map_config(db, data.year_k(year_rows))
    profiles = data.cluster_profiles(year_rows)
    summary_all = data.yearly_summary(records)
    return render_template(
        f"{role}/clustering.html",
        years=sorted(YEARS, reverse=True),
        years_asc=YEARS,
        selected_year=tahun,
        rows=sorted(year_rows, key=lambda r: (r["klaster"] or 99, -r["produksi"])),
        summary=summary_all.get(tahun, {}),
        summary_all=summary_all,
        map_config=map_config,
        legenda=data.legend_items(map_config, profiles, data.get_keterangan(db, tahun)),
    )


def render_pemetaan(role):
    tahun = selected_year_arg()
    records = data.load_records(db)
    year_rows = data.records_for_year(records, tahun)
    map_config = data.get_map_config(db, data.year_k(year_rows))
    profiles = data.cluster_profiles(year_rows)
    return render_template(
        f"{role}/pemetaan.html",
        years=sorted(YEARS, reverse=True),
        selected_year=tahun,
        map_config=map_config,
        legenda=data.legend_items(map_config, profiles, data.get_keterangan(db, tahun)),
    )


def handle_run_clustering(endpoint):
    tahun = selected_year_arg()
    blocked = require_db(endpoint, tahun=tahun)
    if blocked:
        return blocked

    try:
        k = data.validasi_k(request.form.get("k"))
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for(endpoint, tahun=tahun))

    target = request.form.get("target", str(tahun))
    targets = YEARS if target == "semua" else [int(target)]
    berhasil, gagal = [], []
    for t in targets:
        try:
            data.run_clustering(db, t, k)
            berhasil.append(str(t))
        except Exception as exc:
            app.logger.exception("Clustering tahun %s gagal", t)
            gagal.append(f"{t} ({exc})")

    if berhasil:
        flash(f"Clustering (k = {k}) berhasil untuk tahun: {', '.join(berhasil)}.", "success")
    if gagal:
        flash(f"Clustering gagal untuk tahun: {'; '.join(gagal)}.", "danger")

    if target != "semua":
        tahun = int(target)
    return redirect(url_for(endpoint, tahun=tahun))


# =====================================================================
# 4. Admin
# =====================================================================
@app.get("/admin")
def admin_root():
    return redirect(url_for("admin_dashboard"))


@app.get("/admin/dashboard")
@login_required("admin")
def admin_dashboard():
    return render_dashboard("admin")


@app.route("/admin/data-pertanian", methods=["GET", "POST"])
@login_required("admin")
def admin_data_pertanian():
    if request.method == "GET":
        return render_data_pertanian("admin")

    tahun = selected_year_arg()
    blocked = require_db("admin_data_pertanian", tahun=tahun)
    if blocked:
        return blocked

    action = request.form.get("action")
    try:
        if action == "simpan":
            payload = data.parse_data_form(request.form)
            data.upsert_data(db, payload)
            tahun = payload["tahun"]
            flash("Data berhasil disimpan. Jalankan ulang clustering tahun tersebut agar peta ikut diperbarui.", "success")
        elif action == "hapus":
            kid = int(request.form["kecamatan_id"])
            tahun = int(request.form["tahun"])
            data.delete_data(db, kid, tahun)
            flash("Data berhasil dihapus beserta hasil clustering kecamatan tersebut.", "success")
        elif action == "import":
            upload = request.files.get("file_dataset")
            if not upload or not upload.filename:
                raise ValueError("Pilih file CSV atau XLSX terlebih dahulu.")
            payload, errors = parse_file(upload, data.get_kecamatan(db), YEARS)
            if errors:
                contoh = "; ".join(errors[:5])
                lainnya = f" (+{len(errors) - 5} lainnya)" if len(errors) > 5 else ""
                raise ValueError(f"Import dibatalkan. {contoh}{lainnya}")
            data.upsert_data(db, payload)
            flash(f"Berhasil mengimpor {len(payload)} baris data.", "success")
        else:
            abort(400)
    except (KeyError, ValueError) as exc:
        flash(str(exc) or "Isian tidak valid.", "danger")
    except Exception:
        app.logger.exception("Operasi data pertanian gagal")
        flash("Operasi gagal. Periksa log server dan constraint database.", "danger")

    return redirect(url_for("admin_data_pertanian", tahun=tahun))


@app.route("/admin/clustering", methods=["GET", "POST"])
@login_required("admin")
def admin_clustering():
    if request.method == "POST":
        return handle_run_clustering("admin_clustering")
    return render_clustering("admin")


@app.route("/admin/pemetaan", methods=["GET", "POST"])
@login_required("admin")
def admin_pemetaan():
    if request.method == "GET":
        return render_pemetaan("admin")

    tahun = selected_year_arg()
    blocked = require_db("admin_pemetaan", tahun=tahun)
    if blocked:
        return blocked

    try:
        if request.form.get("action") == "warna":
            k_tahun = data.year_k(data.records_for_year(data.load_records(db), tahun))
            data.save_map_config(db, request.form, k_tahun)
            flash("Warna dan label legenda berhasil disimpan.", "success")
        elif request.form.get("action") == "keterangan":
            data.save_keterangan(db, tahun, request.form)
            flash(f"Penjelasan klaster tahun {tahun} berhasil disimpan.", "success")
        else:
            abort(400)
    except Exception:
        app.logger.exception("Gagal menyimpan pengaturan peta")
        flash("Gagal menyimpan. Pastikan schema_tambahan.sql sudah dijalankan di Supabase.", "danger")

    return redirect(url_for("admin_pemetaan", tahun=tahun))


@app.route("/admin/validasi-operator", methods=["GET", "POST"])
@login_required("admin")
def admin_validasi_operator():
    filter_status = request.args.get("status", "semua")

    if request.method == "POST":
        blocked = require_db("admin_validasi_operator", status=filter_status)
        if blocked:
            return blocked

        action = request.form.get("action")
        user_id = request.form.get("user_id", type=int)
        pesan = {
            "setujui": ("disetujui", "Operator disetujui dan sudah dapat login."),
            "tolak": ("ditolak", "Pendaftaran operator ditolak."),
            "nonaktifkan": ("nonaktif", "Operator dinonaktifkan."),
            "aktifkan": ("disetujui", "Operator diaktifkan kembali."),
        }
        try:
            if action in pesan:
                status, teks = pesan[action]
                auth.set_operator_status(db, user_id, status)
                flash(teks, "success")
            elif action == "hapus":
                auth.delete_operator(db, user_id)
                flash("Akun operator dihapus.", "success")
            elif action == "reset":
                auth.reset_password(
                    db,
                    user_id,
                    request.form.get("password_baru", ""),
                    request.form.get("konfirmasi", ""),
                )
                flash("Password operator berhasil direset.", "success")
            else:
                abort(400)
        except ValueError as exc:
            flash(str(exc), "danger")
        except Exception:
            app.logger.exception("Validasi operator gagal")
            flash("Operasi gagal. Periksa log server.", "danger")

        return redirect(url_for("admin_validasi_operator", status=filter_status))

    operators, error = auth.list_operators(db)
    counts = {s: sum(1 for o in operators if o["status"] == s) for s in auth.STATUS_LABEL}
    if filter_status in auth.STATUS_LABEL:
        operators = [o for o in operators if o["status"] == filter_status]
    else:
        filter_status = "semua"

    return render_template(
        "admin/validasi_operator.html",
        operators=operators,
        counts=counts,
        filter_status=filter_status,
        error=error,
    )


# =====================================================================
# 5. Operator
# =====================================================================
@app.get("/operator")
def operator_root():
    return redirect(url_for("operator_dashboard"))


@app.get("/operator/dashboard")
@login_required("operator")
def operator_dashboard():
    return render_dashboard("operator")


@app.route("/operator/data-pertanian", methods=["GET", "POST"])
@login_required("operator")
def operator_data_pertanian():
    """Operator hanya dapat melihat dan mengubah data yang sudah ada."""
    if request.method == "GET":
        return render_data_pertanian("operator")

    tahun = selected_year_arg()
    blocked = require_db("operator_data_pertanian", tahun=tahun)
    if blocked:
        return blocked

    try:
        payload = data.parse_data_form(request.form)
        data.update_data(db, payload)
        tahun = payload["tahun"]
        flash("Data berhasil diperbarui. Jalankan ulang clustering tahun tersebut agar peta ikut diperbarui.", "success")
    except (KeyError, ValueError) as exc:
        flash(str(exc) or "Isian tidak valid.", "danger")
    except Exception:
        app.logger.exception("Operator gagal mengubah data")
        flash("Data gagal diperbarui. Periksa log server.", "danger")

    return redirect(url_for("operator_data_pertanian", tahun=tahun))


@app.route("/operator/clustering", methods=["GET", "POST"])
@login_required("operator")
def operator_clustering():
    if request.method == "POST":
        return handle_run_clustering("operator_clustering")
    return render_clustering("operator")


@app.get("/operator/pemetaan")
@login_required("operator")
def operator_pemetaan():
    return render_pemetaan("operator")


# =====================================================================
# 6. API untuk peta & grafik
# =====================================================================
@app.get("/api/map-data/<int:tahun>")
def api_map_data(tahun):
    if tahun not in YEARS:
        return jsonify({"error": "Tahun tidak valid"}), 400
    records = data.load_records(db)
    rows = data.records_for_year(records, tahun)
    return jsonify({
        "tahun": tahun,
        "map_config": data.get_map_config(db, data.year_k(rows)),
        "data": {str(r["kecamatan_id"]): r for r in rows},
    })


@app.get("/api/kecamatan/<int:kecamatan_id>/riwayat")
def api_riwayat(kecamatan_id):
    records = data.load_records(db)
    return jsonify({
        "kecamatan_id": kecamatan_id,
        "riwayat": data.history_for_kecamatan(records, kecamatan_id),
    })


@app.get("/health")
def health():
    return jsonify({"status": "ok", "supabase_configured": db is not None})


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "true").lower() == "true")
