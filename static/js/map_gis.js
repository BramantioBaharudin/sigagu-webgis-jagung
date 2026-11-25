/**
 * static/js/map_gis.js
 * Memuat file GeoJSON asli 33 Kecamatan Kabupaten Malang (GADM v4.1) menggunakan Leaflet.js,
 * mewarnai poligon berdasarkan klaster K-Medoids dari Supabase, dan memicu callback
 * saat poligon kecamatan diklik. Evaluasi hanya menampilkan Silhouette Coefficient.
 */

const mapInstances = {};
const geojsonLayers = {};

async function initSigaguMap(mapElementId, tahun, onKecamatanClick) {
  const el = document.getElementById(mapElementId);
  if (!el || !window.L) return;

  if (!mapInstances[mapElementId]) {
    const map = L.map(mapElementId).setView([-8.15, 112.65], 10);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap &middot; GADM v4.1 &middot; Dinas TPHP Kab. Malang",
    }).addTo(map);
    mapInstances[mapElementId] = map;
  }

  const mapInstance = mapInstances[mapElementId];

  try {
    const [geoRes, apiRes] = await Promise.all([
      fetch("/static/geojson/kecamatan.geojson"),
      fetch(`/api/map-data/${tahun}`),
    ]);

    if (!geoRes.ok) {
      throw new Error("File GeoJSON tidak ditemukan");
    }

    const geojsonData = await geoRes.json();
    const payload = apiRes.ok ? await apiRes.json() : { data: {}, map_config: {} };
    const dataById = payload.data || {};
    const cfg = payload.map_config || {
      c1_color: "#15803d",
      c2_color: "#a3e635",
      c3_color: "#ea580c",
      c1_label: "Klaster 1",
      c2_label: "Klaster 2",
      c3_label: "Klaster 3",
    };

    if (geojsonLayers[mapElementId]) {
      mapInstance.removeLayer(geojsonLayers[mapElementId]);
    }

    function getRecord(props) {
      const id = String(props.kecamatan_id ?? props.id ?? "");
      if (dataById[id]) return dataById[id];
      const name = String(props.nama_kecamatan || props.WADMKC || props.NAMOBJ || "").toLowerCase();
      return Object.values(dataById).find((r) => String(r.kecamatan || "").toLowerCase() === name) || null;
    }

    function getClusterColor(klaster) {
      return (klaster && cfg[`c${klaster}_color`]) || "#cbd5e1";
    }

    function getClusterLabel(klaster) {
      if (!klaster) return "Belum diproses";
      return cfg[`c${klaster}_label`] || `Klaster ${klaster}`;
    }
    const layer = L.geoJSON(geojsonData, {
      style: function (feature) {
        const rec = getRecord(feature.properties || {});
        const klaster = rec ? rec.klaster : null;
        return {
          fillColor: getClusterColor(klaster),
          weight: 1.5,
          opacity: 1,
          color: "#ffffff",
          fillOpacity: 0.65,
        };
      },
      onEachFeature: function (feature, fLayer) {
        const props = feature.properties || {};
        const kecId = props.kecamatan_id ?? props.id;
        const kecName = props.nama_kecamatan || props.WADMKC || props.NAMOBJ || "Kecamatan";
        const rec = getRecord(props);

        if (rec) {
          const medoidBadge = rec.is_medoid ? " ⭐ (Medoid)" : "";
          const silText =
            rec.silhouette !== null && rec.silhouette !== undefined
              ? Number(rec.silhouette).toFixed(4)
              : "–";
          fLayer.bindTooltip(
            `<div style="font-size:12px;line-height:1.45">` +
              `<strong>Kec. ${kecName} (${tahun})${medoidBadge}</strong><br/>` +
              `<span style="font-weight:700">${getClusterLabel(rec.klaster)}</span><br/>` +
              `Produksi: <strong>${Number(rec.produksi).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} Ton</strong><br/>` +
              `Luas Panen: ${Number(rec.luas_panen).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} Ha · Produktivitas: ${Number(rec.produktivitas).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} Kw/Ha<br/>` +
              `Silhouette Coefficient: <strong>${silText}</strong>` +
            `</div>`,
            { sticky: true }
          );
        } else {
          fLayer.bindTooltip(`<strong>Kec. ${kecName}</strong><br/>Data belum tersedia`);
        }

        fLayer.on("mouseover", function () {
          fLayer.setStyle({ weight: 2.5, fillOpacity: 0.95 });
        });

        fLayer.on("mouseout", function () {
          layer.resetStyle(fLayer);
        });

        fLayer.on("click", function () {
          if (typeof onKecamatanClick === "function") {
            onKecamatanClick(kecId, kecName, rec);
          }
        });
      },
    }).addTo(mapInstance);

    geojsonLayers[mapElementId] = layer;

    if (layer.getBounds().isValid()) {
      mapInstance.fitBounds(layer.getBounds(), { padding: [15, 15] });
    }
  } catch (err) {
    console.error("Gagal memuat peta GIS:", err);
  }
}

