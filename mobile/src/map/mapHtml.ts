// Owner: Person B — Rarity Engine & Collection
//
// The map document, shared by the native and web Map screens.
//
// We render MapLibre GL JS in a browser context rather than using
// @maplibre/maplibre-react-native: that native module is not bundled in Expo Go, and
// the team's workflow is `expo start` + Expo Go. Expo Router eagerly loads every route
// file, so importing it crashes the app on startup for everyone. This approach also
// keeps us off Google Maps (which react-native-maps would use on Android).
//
// Two hosts render this same HTML:
//   app/(tabs)/map.tsx      — native: react-native-webview (ships inside Expo Go)
//   app/(tabs)/map.web.tsx  — web:    an <iframe> (react-native-webview has no web build)
//
// Week 2: pins. Pass a GeoJSON FeatureCollection into `buildMapHtml` and it renders as
// circles. Captures whose coordinates were fuzzed or withheld for sensitive species
// (IUCN VU/EN/CR) have no coordinates, so they simply never become features.

/** A capture rendered as a map pin. Captures without coordinates are filtered out upstream. */
export interface MapPin {
  id: string;
  lng: number;
  lat: number;
  /** Drives the pin colour; matches the backend's rarity tiers. */
  rarity: "common" | "uncommon" | "rare" | "legendary";
}

// Free demo tiles hosted by MapLibre — no API key, no usage fees.
const STYLE_URL = "https://demotiles.maplibre.org/style.json";
const MAPLIBRE_JS = "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js";
const MAPLIBRE_CSS = "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css";

const RARITY_COLORS: Record<MapPin["rarity"], string> = {
  legendary: "#f59e0b",
  rare: "#0ea5e9",
  uncommon: "#10b981",
  common: "#64748b",
};

// Default view: continental US, since the app targets US-based players.
const CENTER: [number, number] = [-98.5, 39.8]; // [lng, lat]
const ZOOM = 3;

/** Builds the self-contained map document. */
export function buildMapHtml(pins: MapPin[] = []): string {
  // JSON.stringify keeps injected data escaped — no raw interpolation into JS source.
  const data = JSON.stringify({
    type: "FeatureCollection",
    features: pins.map((p) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [p.lng, p.lat] },
      properties: { id: p.id, color: RARITY_COLORS[p.rarity] },
    })),
  });

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
  // react-native-webview listens on ReactNativeWebView; the web <iframe> host listens
  // for postMessage. Sending both keeps this document host-agnostic.
  function post(msg) {
    if (window.ReactNativeWebView) { window.ReactNativeWebView.postMessage(msg); }
    else if (window.parent) { window.parent.postMessage(msg, '*'); }
  }
  try {
    var map = new maplibregl.Map({
      container: 'map',
      style: '${STYLE_URL}',
      center: [${CENTER[0]}, ${CENTER[1]}],
      zoom: ${ZOOM}
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    map.on('load', function () {
      map.addSource('captures', { type: 'geojson', data: ${data} });
      map.addLayer({
        id: 'capture-pins',
        type: 'circle',
        source: 'captures',
        paint: {
          'circle-radius': 7,
          'circle-color': ['get', 'color'],
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff'
        }
      });
      post('ready');
    });
    map.on('error', function () { post('error'); });
  } catch (e) { post('error'); }
</script>
</body>
</html>`;
}

/** Week 1: no pins yet. */
export const MAP_HTML = buildMapHtml();
