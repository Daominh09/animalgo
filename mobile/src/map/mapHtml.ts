// Owner: Person B — Rarity Engine & Collection
//
// Shared map configuration, plus the HTML document used on native.
//
// We render MapLibre GL JS rather than using @maplibre/maplibre-react-native: that
// native module is not bundled in Expo Go, and the team's workflow is `expo start` +
// Expo Go. Expo Router eagerly loads every route file, so importing it crashes the app
// on startup for everyone. This also keeps us off Google Maps (which react-native-maps
// would use on Android).
//
// The two platforms host MapLibre differently:
//   app/(tabs)/map.tsx      — native: buildMapHtml() inside react-native-webview
//   app/(tabs)/map.web.tsx  — web:    MapLibre mounted directly into the page
//
// Web deliberately does NOT use an <iframe srcDoc>: that gives the document an opaque
// origin, and MapLibre spawns a Web Worker from a blob URL, which browsers block in
// that context — the map fails to initialise and renders blank.
//
// Week 2: pass pins to buildGeoJson/buildMapHtml and they render as rarity-coloured
// circles on both platforms. Captures whose coordinates were fuzzed or withheld for
// sensitive species (IUCN VU/EN/CR) have no coordinates, so they never become features.

/** A capture rendered as a map pin. Captures without coordinates are filtered out upstream. */
export interface MapPin {
  id: string;
  lng: number;
  lat: number;
  /** Drives the pin colour; matches the backend's rarity tiers. */
  rarity: "common" | "uncommon" | "rare" | "legendary";
}

// Free demo tiles hosted by MapLibre — no API key, no usage fees.
export const STYLE_URL = "https://demotiles.maplibre.org/style.json";
export const MAPLIBRE_VERSION = "4.7.1";
export const MAPLIBRE_JS = `https://unpkg.com/maplibre-gl@${MAPLIBRE_VERSION}/dist/maplibre-gl.js`;
export const MAPLIBRE_CSS = `https://unpkg.com/maplibre-gl@${MAPLIBRE_VERSION}/dist/maplibre-gl.css`;

export const RARITY_COLORS: Record<MapPin["rarity"], string> = {
  legendary: "#f59e0b",
  rare: "#0ea5e9",
  uncommon: "#10b981",
  common: "#64748b",
};

// Default view: continental US, since the app targets US-based players.
export const CENTER: [number, number] = [-98.5, 39.8]; // [lng, lat]
export const ZOOM = 3;

/** GeoJSON for the capture pins layer. */
export function buildGeoJson(pins: MapPin[] = []) {
  return {
    type: "FeatureCollection",
    features: pins.map((p) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [p.lng, p.lat] },
      properties: { id: p.id, color: RARITY_COLORS[p.rarity] },
    })),
  };
}

/** The circle layer definition, shared by both platforms. */
export const PIN_LAYER = {
  id: "capture-pins",
  type: "circle",
  source: "captures",
  paint: {
    "circle-radius": 7,
    "circle-color": ["get", "color"],
    "circle-stroke-width": 2,
    "circle-stroke-color": "#ffffff",
  },
};

/** Self-contained map document, used by the native WebView. */
export function buildMapHtml(pins: MapPin[] = []): string {
  // JSON.stringify keeps injected data escaped — no raw interpolation into JS source.
  const data = JSON.stringify(buildGeoJson(pins));
  const layer = JSON.stringify(PIN_LAYER);

  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" />
<link href="${MAPLIBRE_CSS}" rel="stylesheet" />
<script src="${MAPLIBRE_JS}"></script>
<style>html,body,#map{margin:0;padding:0;height:100%;width:100%}body{background:#eef2f7}</style>
</head>
<body>
<div id="map"></div>
<script>
  function post(msg) { if (window.ReactNativeWebView) { window.ReactNativeWebView.postMessage(msg); } }
  try {
    if (!window.maplibregl) { post('error'); } else {
      var map = new maplibregl.Map({
        container: 'map',
        style: '${STYLE_URL}',
        center: [${CENTER[0]}, ${CENTER[1]}],
        zoom: ${ZOOM}
      });
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
      map.on('load', function () {
        map.addSource('captures', { type: 'geojson', data: ${data} });
        map.addLayer(${layer});
        post('ready');
      });
      map.on('error', function () { post('error'); });
    }
  } catch (e) { post('error'); }
</script>
</body>
</html>`;
}

/** Week 1: no pins yet. */
export const MAP_HTML = buildMapHtml();
