export const METHODS = ['qaoa', 'exact', 'greedy'];
export const COLORS = { qaoa: '#b5f06b', exact: '#76baff', greedy: '#ecbb70' };
export const PALETTE = ['#91d84f', '#2aafa1', '#9180e5', '#ebaa4f', '#3a9de1', '#d779ad', '#c7bb48'];
export const fmt = (n, digits = 2) => Number.isFinite(n) ? n.toLocaleString('en-US', { maximumFractionDigits: digits }) : '—';
export const probability = n => Number.isFinite(n) ? `${(n * 100).toFixed(4).replace(/0+$/, '').replace(/\.$/, '')}%` : '—';
export function validateResult(d) {
  const fail = message => { throw new Error(`Invalid solver result: ${message}`); };
  const finite = x => typeof x === 'number' && Number.isFinite(x);
  const coord = c => Array.isArray(c) && c.length === 2 && c.every(finite) && Math.abs(c[0]) <= 180 && Math.abs(c[1]) <= 90;
  if (!d || !coord(d.sector?.center) || !validBBox(d.sector?.bbox)) fail('sector coordinates are missing or invalid');
  if (!Array.isArray(d.zones) || !Array.isArray(d.candidates)) fail('zones/candidates must be arrays');
  const ids = new Set(d.candidates.map(c => c.id));
  if (ids.size !== d.candidates.length || d.candidates.some(c => !Number.isInteger(c.id))) fail('candidate IDs must be unique integers');
  for (const c of d.candidates) {
    if (!coord([c.lon, c.lat])) fail(`camera ${c.id}: invalid coordinates`);
    for (const k of ['height_m', 'azimuth_deg', 'tilt_deg', 'fov_deg', 'range_m', 'cost', 'power_w']) if (!finite(c[k])) fail(`camera ${c.id}: invalid ${k}`);
    if (!Array.isArray(c.fov_polygon) || c.fov_polygon.length < 3 || !c.fov_polygon.every(coord)) fail(`camera ${c.id}: invalid FOV polygon`);
  }
  const zoneIds = new Set(d.zones.map(z => z.id));
  if (zoneIds.size !== d.zones.length) fail('duplicate zone IDs');
  for (const z of d.zones) if (!coord([z.lon, z.lat]) || !Array.isArray(z.covered_by) || z.covered_by.some(id => !ids.has(id))) fail(`zone ${z.id}: invalid coverage references`);
  for (const method of METHODS) {
    const s = d.solutions?.[method];
    if (!s || !Array.isArray(s.selected) || new Set(s.selected).size !== s.selected.length || s.selected.some(id => !ids.has(id))) fail(`${method}: invalid selected IDs`);
    if (s.num_cameras !== s.selected.length) fail(`${method}: camera count does not match selection`);
    for (const key of ['coverage_pct', 'cost', 'power_w', 'runtime_s']) if (!finite(s[key]) || s[key] < 0) fail(`${method}: invalid ${key}`);
  }
  if (!d.quantum || !Array.isArray(d.quantum.top_bitstrings) || !Array.isArray(d.quantum.convergence) || !d.quantum.convergence.every(finite)) fail('quantum chart data is missing');
  for (const b of d.quantum.top_bitstrings) if (!/^[01]+$/.test(b.bits) || !finite(b.prob) || b.prob < 0 || b.prob > 1 || typeof b.feasible !== 'boolean') fail('invalid bitstring probability');
  return d;
}
export function selectedCameras(d, method) {
  const byId = new Map(d.candidates.map(c => [c.id, c]));
  return d.solutions[method].selected.map((id, i) => ({ ...byId.get(id), color: PALETTE[i % PALETTE.length] }));
}
export function coveredZones(d, method) {
  const selected = new Set(d.solutions[method].selected);
  return d.zones.map(z => ({ ...z, isCovered: z.covered_by.some(id => selected.has(id)) }));
}
export function closeRing(points) {
  if (!points.length) return [];
  const ring = points.map(p => [...p]);
  if (ring[0][0] !== ring.at(-1)[0] || ring[0][1] !== ring.at(-1)[1]) ring.push([...ring[0]]);
  return ring;
}
export function validBBox(b) {
  return Array.isArray(b) && b.length === 4 && b.every(n => typeof n === 'number' && Number.isFinite(n)) && b[0] >= -180 && b[2] <= 180 && b[1] >= -85 && b[3] <= 85 && b[0] < b[2] && b[1] < b[3];
}
export const fc = features => ({ type: 'FeatureCollection', features });
export const feature = (type, coordinates, properties = {}) => ({ type: 'Feature', geometry: { type, coordinates }, properties });
export function bboxFeature(bbox) {
  if (!validBBox(bbox)) return fc([]);
  const [w, s, e, n] = bbox;
  return fc([feature('Polygon', [[[w,s],[e,s],[e,n],[w,n],[w,s]]])]);
}
export function downloadJSON(data) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
  const a = document.createElement('a'); a.href = url; a.download = `${data.instance || 'camera'}_result.json`; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
