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
// Every capture's coordinates are fuzzed to a ~11 km grid by the backend before they are
// stored, so the pins here are already the publishable locations — there is nothing to
// filter or blur on this side. Several captures from the same area land on exactly the
// same point, which is the intended behaviour, not a rendering bug.

import { rarityMeta } from "../rarity";
import type { Capture } from "../api/collection";

/** A capture rendered as a map pin. Captures without coordinates are filtered out. */
export interface MapPin {
  id: string;
  lng: number;
  lat: number;
  /** Drives the pin colour. null when rarity could not be determined. */
  rarity: string | null;
}

/** Captures that have a location, as pins. Captures with no coordinates are dropped —
 *  a pin at 0,0 would be a lie, and the Collection screen still shows them. */
export function capturesToPins(captures: Capture[]): MapPin[] {
  return captures
    .filter((c): c is Capture & { lat: number; lng: number } => c.lat !== null && c.lng !== null)
    .map((c) => ({ id: c.id, lat: c.lat, lng: c.lng, rarity: c.rarity_tier }));
}

// Free demo tiles hosted by MapLibre — no API key, no usage fees.
export const STYLE_URL = "https://demotiles.maplibre.org/style.json";
export const MAPLIBRE_VERSION = "4.7.1";
export const MAPLIBRE_JS = `https://unpkg.com/maplibre-gl@${MAPLIBRE_VERSION}/dist/maplibre-gl.js`;
export const MAPLIBRE_CSS = `https://unpkg.com/maplibre-gl@${MAPLIBRE_VERSION}/dist/maplibre-gl.css`;

// Fallback view when there is nothing to show: continental US, since the app targets
// US-based players. With pins we fit to them instead — a capture the player cannot see
// may as well not be on the map, and captures abroad would sit off-screen entirely.
export const CENTER: [number, number] = [-98.5, 39.8]; // [lng, lat]
export const ZOOM = 3;

/** Padding and zoom cap for fitting the view to pins. maxZoom stops a single capture
 *  from zooming to street level, which loses all sense of where it is. */
export const FIT_OPTIONS = { padding: 48, maxZoom: 9, animate: false };

/** Bounding box of the pins as [[west, south], [east, north]], or null if there are
 *  none. A single pin gives a zero-size box, which fitBounds handles via maxZoom. */
export function computeBounds(pins: MapPin[]): [[number, number], [number, number]] | null {
  if (pins.length === 0) return null;
  const lngs = pins.map((p) => p.lng);
  const lats = pins.map((p) => p.lat);
  return [
    [Math.min(...lngs), Math.min(...lats)],
    [Math.max(...lngs), Math.max(...lats)],
  ];
}

/**
 * What the map should frame: one capture if the Collection screen asked for it,
 * otherwise everything.
 *
 * An unknown or unmappable `focusId` falls back to all pins rather than returning null.
 * Arriving from a card whose capture has since gone should still show a usable map, not
 * an empty default view of Kansas.
 */
export function boundsFor(
  pins: MapPin[],
  focusId?: string | null,
): [[number, number], [number, number]] | null {
  const focused = focusId ? pins.filter((p) => p.id === focusId) : [];
  return computeBounds(focused.length ? focused : pins);
}

/** GeoJSON for the capture pins layer. */
export function buildGeoJson(pins: MapPin[] = []) {
  return {
    type: "FeatureCollection",
    features: pins.map((p) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [p.lng, p.lat] },
      properties: { id: p.id, color: rarityMeta(p.rarity).color },
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

/** Invisible larger circle, drawn over the visible pin purely to be tapped. A 7 px
 *  radius is about 14 px across — fine for a mouse, far below the ~44 px a fingertip
 *  needs. Taps are tested against this layer, so the pin can stay small. */
export const PIN_HIT_LAYER = {
  id: "capture-pins-hit",
  type: "circle",
  source: "captures",
  paint: {
    "circle-radius": 22,
    "circle-color": "#000000",
    "circle-opacity": 0,
  },
};

/**
 * JSON for embedding inside a `<script>` block.
 *
 * JSON.stringify alone is NOT enough here. It does not escape `<`, so a string
 * containing `</script>` closes the tag early and everything after it is parsed as HTML
 * — the classic breakout, and it lands inside a WebView we hand our own bridge to.
 *
 * Today nothing reaches this that a player controls: pin properties carry a
 * server-generated UUID and a colour from a fixed table. That changes the moment species
 * names are denormalised onto pins, and vision output is model-generated text from a
 * photograph. Escaping now costs one replace and removes the trap rather than leaving it
 * armed for whoever adds that field.
 *
 * `<` is valid inside a JSON string and parses back to `<`, so the data arrives
 * unchanged.
 */
function safeJson(value: unknown): string {
  return JSON.stringify(value).replace(/</g, "\\u003c");
}

/** Self-contained map document, used by the native WebView.
 *
 * `focusId` is baked into the document rather than pushed over the bridge afterwards:
 * the HTML is already rebuilt when the pins change, so framing one capture is the same
 * mechanism, and it avoids a second messaging path for something that happens once. */
export function buildMapHtml(pins: MapPin[] = [], focusId?: string | null): string {
  const data = safeJson(buildGeoJson(pins));
  const layer = safeJson(PIN_LAYER);
  const hitLayer = safeJson(PIN_HIT_LAYER);
  const bounds = safeJson(boundsFor(pins, focusId));
  const fit = safeJson(FIT_OPTIONS);

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
  function post(msg) { if (window.ReactNativeWebView) { window.ReactNativeWebView.postMessage(JSON.stringify(msg)); } }
  try {
    if (!window.maplibregl) { post({ type: 'error' }); } else {
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
        map.addLayer(${hitLayer});
        var bounds = ${bounds};
        if (bounds) { map.fitBounds(bounds, ${fit}); }
        post({ type: 'ready' });
      });

      // Taps are tested against the invisible hit layer, not the visible pin.
      map.on('click', '${PIN_HIT_LAYER.id}', function (e) {
        if (e.features && e.features.length) {
          post({ type: 'select', id: e.features[0].properties.id });
        }
      });
      // A tap on empty map dismisses the card. This fires for pin taps too, but
      // MapLibre runs the layer handler first, so the selection survives.
      map.on('click', function (e) {
        var hits = map.queryRenderedFeatures(e.point, { layers: ['${PIN_HIT_LAYER.id}'] });
        if (!hits.length) { post({ type: 'deselect' }); }
      });
      map.on('mouseenter', '${PIN_HIT_LAYER.id}', function () { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', '${PIN_HIT_LAYER.id}', function () { map.getCanvas().style.cursor = ''; });

      map.on('error', function () { post({ type: 'error' }); });
    }
  } catch (e) { post({ type: 'error' }); }
</script>
</body>
</html>`;
}

