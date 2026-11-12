import { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import { Maximize2, Layers3, LocateFixed } from 'lucide-react';
import { bboxFeature, closeRing, coveredZones, fc, feature, selectedCameras } from '../data.js';
import { frustumLayer } from './FrustumLayer.js';
import DataMap from './DataMap.jsx';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';

maplibregl.setWorkerUrl(workerUrl);

export default function CityMap({ data, method, focused, onFocus, bbox, captureRef }) {
  const container = useRef(null), mapRef = useRef(null), markers = useRef([]), latest = useRef();
  const [ready, setReady] = useState(false), [error, setError] = useState(''), [buildings, setBuildings] = useState(true), [cones, setCones] = useState(true), [fallback,setFallback] = useState(false);
  latest.current = { data, method, focused, onFocus, bbox };
  useEffect(() => {
    let map;
    try {
      map = new maplibregl.Map({ container: container.current, style: 'https://tiles.openfreemap.org/styles/liberty', center: data.sector.center, zoom: 16.5, pitch: 60, bearing: -28, maxPitch: 80, attributionControl: true });
    } catch { setError('WebGL is unavailable. Showing a 2D data view; enable browser hardware acceleration for the 3D city map.'); setFallback(true); return; }
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
    map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-left');
    captureRef.current = () => { const b = map.getBounds(); return [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].map(n => +n.toFixed(7)); };
    map.on('error', () => setError('Some map assets could not load. Check your connection to OpenFreeMap, then reload the map.'));
    map.on('load', () => {
      const style = map.getStyle();
      const base = style.layers.find(l => l['source-layer'] === 'building');
      if (base) {
        // Building source is discovered from the provider's style, not assumed.
        map.addLayer({ id: 'city-buildings', source: base.source, 'source-layer': 'building', type: 'fill-extrusion', minzoom: 14,
          paint: { 'fill-extrusion-color': '#c8d1d7', 'fill-extrusion-height': ['max', 0, ['to-number', ['get', 'render_height'], 0]], 'fill-extrusion-base': ['max', 0, ['to-number', ['get', 'render_min_height'], 0]], 'fill-extrusion-opacity': 0.72 } });
      } else setError('The basemap has no building source layer; 3D buildings are unavailable.');
      for (const id of ['sector', 'request', 'candidates', 'wedges', 'zones']) map.addSource(id, { type: 'geojson', data: fc([]) });
      map.addLayer({ id: 'sector-line', type: 'line', source: 'sector', paint: { 'line-color': '#55627a', 'line-width': 1.5, 'line-dasharray': [3, 3] } });
      map.addLayer({ id: 'request-line', type: 'line', source: 'request', paint: { 'line-color': '#9255d7', 'line-width': 2, 'line-dasharray': [2, 2] } });
      map.addLayer({ id: 'fov-fill', type: 'fill', source: 'wedges', paint: { 'fill-color': ['get', 'color'], 'fill-opacity': 0.22 } });
      map.addLayer({ id: 'fov-line', type: 'line', source: 'wedges', paint: { 'line-color': ['get', 'color'], 'line-width': 1.3, 'line-opacity': 0.85 } });
      map.addLayer({ id: 'candidate-dots', type: 'circle', source: 'candidates', paint: { 'circle-radius': 3.5, 'circle-color': '#7a8490', 'circle-stroke-color': '#fff', 'circle-stroke-width': 1 } });
      map.addLayer({ id: 'zone-circles', type: 'circle', source: 'zones', paint: {
        'circle-radius': ['case', ['get', 'priority'], 10, 6], 'circle-color': ['case', ['get', 'isCovered'], '#23865d', '#e05252'],
        'circle-stroke-color': '#fff', 'circle-stroke-width': ['case', ['get', 'priority'], 3, 2], 'circle-opacity': 0.95,
      } });
      map.on('click', 'zone-circles', e => {
        const p = e.features[0].properties;
        const node = document.createElement('div'); node.textContent = `${p.name || `Zone ${p.id}`} · ${p.isCovered ? 'Covered' : 'Uncovered'}${p.priority ? ' · Priority' : ''}`;
        new maplibregl.Popup().setLngLat(e.lngLat).setDOMContent(node).addTo(map);
      });
      map.on('click', 'candidate-dots', e => latest.current.onFocus(Number(e.features[0].properties.id)));
      for (const layer of ['zone-circles', 'candidate-dots']) {
        map.on('mouseenter', layer, () => { map.getCanvas().style.cursor = 'pointer'; });
        map.on('mouseleave', layer, () => { map.getCanvas().style.cursor = ''; });
      }
      setError(''); setReady(true);
    });
    return () => { captureRef.current = null; markers.current.forEach(m => m.remove()); map.remove(); mapRef.current = null; };
  }, []);
  useEffect(() => {
    if (!ready || !mapRef.current) return;
    const map = mapRef.current, selected = selectedCameras(data, method);
    map.getSource('sector').setData(bboxFeature(data.sector.bbox));
    map.getSource('request').setData(JSON.stringify(bbox) === JSON.stringify(data.sector.bbox) ? fc([]) : bboxFeature(bbox));
    map.getSource('candidates').setData(fc(data.candidates.map(c => feature('Point', [c.lon,c.lat], { id: c.id }))));
    map.getSource('zones').setData(fc(coveredZones(data, method).map(z => feature('Point', [z.lon,z.lat], z))));
    map.getSource('wedges').setData(fc(selected.map(c => feature('Polygon', [closeRing(c.fov_polygon)], { id: c.id, color: c.color }))));
    markers.current.forEach(m => m.remove());
    markers.current = selected.map(c => {
      const el = document.createElement('button'); el.className = 'camera-pin'; el.style.setProperty('--pin', c.color);
      el.textContent = `C${c.id}`; el.title = `Camera ${c.id} · ${c.height_m}m · pan ${c.azimuth_deg}° · tilt ${c.tilt_deg}°`; el.setAttribute('aria-label', el.title);
      el.addEventListener('click', () => onFocus(c.id));
      return new maplibregl.Marker({ element: el, anchor: 'bottom', offset: [0,-8] }).setLngLat([c.lon,c.lat]).addTo(map);
    });
    if (map.getLayer('camera-frustums')) map.removeLayer('camera-frustums');
    if (cones) map.addLayer(frustumLayer(selected, data.sector.center));
  }, [ready, data, method, bbox, cones, onFocus]);
  useEffect(() => {
    if (!ready) return;
    const map = mapRef.current;
    if (map?.getLayer('city-buildings')) map.setLayoutProperty('city-buildings', 'visibility', buildings ? 'visible' : 'none');
  }, [ready, buildings]);
  useEffect(() => {
    if (ready) mapRef.current?.flyTo({ center: data.sector.center, zoom: 16.5, pitch: 60, bearing: -28, duration: 1000 });
  }, [ready, data]);
  useEffect(() => {
    const c = data.candidates.find(c => c.id === focused);
    if (ready && c) mapRef.current?.flyTo({ center: [c.lon,c.lat], zoom: 18, pitch: 60, bearing: c.azimuth_deg, duration: 1000 });
  }, [focused, ready, data]);
  const reset = () => mapRef.current?.flyTo({ center: data.sector.center, zoom: 16.5, pitch: 60, bearing: -28, duration: 900 });
  return <div className="map-shell">
    <div ref={container} className="map-canvas" aria-label="Interactive 3D camera placement map"/>
    {fallback&&<DataMap data={data} method={method} focused={focused} onFocus={onFocus} bbox={bbox}/>}
    {!ready && !error && <div className="map-loading"><span className="spinner"/> Loading Manhattan…</div>}
    {error && <div role="alert" className="map-error">{error}</div>}
    <div className="map-heading"><span className="live-dot"/><strong>BRYANT PARK SECTOR</strong><span>40.7536° N / 73.9840° W</span></div>
    <div className="map-tools"><button disabled={!ready} onClick={reset}><LocateFixed size={15}/> Reset view</button><button disabled={!ready} aria-pressed={buildings} onClick={() => setBuildings(!buildings)}><Layers3 size={15}/> Buildings {buildings ? 'on' : 'off'}</button><button disabled={!ready} aria-pressed={cones} onClick={() => setCones(!cones)}>3D rays {cones ? 'on' : 'off'}</button><button aria-label="Toggle fullscreen map" onClick={() => { const el=container.current.parentElement; if(document.fullscreenElement) document.exitFullscreen?.(); else el.requestFullscreen?.(); }}><Maximize2 size={15}/></button></div>
    <div className="map-legend"><span><i className="dot covered"/> Covered zone</span><span><i className="dot uncovered"/> Uncovered</span><span><i className="dot priority"/> Priority</span><span><i className="dot candidate"/> Candidate</span><span><i className="legend-wedge"/> Field of view</span></div>
    <div className="map-caption">{fallback?'2D fallback · Click a camera to inspect':'Drag to explore · Right-drag to tilt & rotate · Click a camera to inspect'}</div>
  </div>;
}
