import type { StyleSpecification } from 'maplibre-gl';

// Light "morning haze" basemap in the design tokens, Protomaps basemap v4 schema. No symbol layers,
// so no glyph server is needed; place names come from our own HTML markers.
export function basemapStyle(pmtilesUrl: string | null): StyleSpecification {
  const layers: StyleSpecification['layers'] = [{ id: 'bg', type: 'background', paint: { 'background-color': '#F3F2EE' } }];
  const style: StyleSpecification = { version: 8, sources: {}, layers };
  if (!pmtilesUrl) return style;
  style.sources.base = { type: 'vector', url: `pmtiles://${pmtilesUrl}`, attribution: '© OpenStreetMap contributors · Protomaps' };
  layers.push(
    { id: 'earth', type: 'fill', source: 'base', 'source-layer': 'earth', paint: { 'fill-color': '#F3F2EE' } },
    { id: 'landcover', type: 'fill', source: 'base', 'source-layer': 'landcover', paint: { 'fill-color': '#E3E9DF', 'fill-opacity': 0.7 } },
    { id: 'landuse', type: 'fill', source: 'base', 'source-layer': 'landuse', paint: { 'fill-color': '#ECEBE5' } },
    { id: 'water', type: 'fill', source: 'base', 'source-layer': 'water', paint: { 'fill-color': '#D3E3EB' } },
    { id: 'water-line', type: 'line', source: 'base', 'source-layer': 'water', paint: { 'line-color': '#B8CFDB', 'line-width': 0.6 } },
    { id: 'buildings', type: 'fill', source: 'base', 'source-layer': 'buildings', minzoom: 14, paint: { 'fill-color': '#E4E2DA', 'fill-outline-color': '#D6D3CA' } },
    { id: 'roads-minor', type: 'line', source: 'base', 'source-layer': 'roads', filter: ['in', ['get', 'kind'], ['literal', ['minor_road', 'other', 'path']]], minzoom: 13, paint: { 'line-color': '#E2DFD6', 'line-width': 0.6 } },
    { id: 'roads-major', type: 'line', source: 'base', 'source-layer': 'roads', filter: ['in', ['get', 'kind'], ['literal', ['major_road', 'highway', 'medium_road']]], paint: { 'line-color': '#D2CEC3', 'line-width': ['interpolate', ['linear'], ['zoom'], 9, 0.5, 15, 1.6] } },
    { id: 'rail', type: 'line', source: 'base', 'source-layer': 'roads', filter: ['==', ['get', 'kind'], 'rail'], paint: { 'line-color': '#C4C8C4', 'line-width': 0.8, 'line-dasharray': [3, 2] } },
    { id: 'boundaries', type: 'line', source: 'base', 'source-layer': 'boundaries', paint: { 'line-color': '#C9C4D2', 'line-width': 0.8, 'line-dasharray': [4, 3] } },
  );
  return style;
}
