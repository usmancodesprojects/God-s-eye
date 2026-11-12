import { coveredZones, selectedCameras, closeRing, bboxFeature } from '../data.js';

// No basemap or invented streets: a coordinate-accurate data view for browsers
// without WebGL. The primary renderer remains MapLibre with 3D buildings.
export default function DataMap({ data, method, focused, onFocus, bbox }) {
  const cameras=selectedCameras(data,method), zones=coveredZones(data,method);
  const points=[data.sector.center,...bboxFeature(data.sector.bbox).features[0].geometry.coordinates[0],...data.candidates.map(c=>[c.lon,c.lat]),...data.zones.map(z=>[z.lon,z.lat]),...cameras.flatMap(c=>c.fov_polygon)];
  const lonScale=Math.cos(data.sector.center[1]*Math.PI/180), xs=points.map(p=>p[0]*lonScale), ys=points.map(p=>p[1]);
  const minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
  const scale=Math.min(760/Math.max(maxX-minX,.0001),330/Math.max(maxY-minY,.0001));
  const project=p=>[450+(p[0]*lonScale-(minX+maxX)/2)*scale,270-(p[1]-(minY+maxY)/2)*scale];
  return <div className="data-map"><svg viewBox="0 0 900 490" role="img" aria-label="2D fallback showing supplied camera coordinates, coverage zones and FOV polygons">
    <defs><pattern id="coordinate-grid" width="35" height="35" patternUnits="userSpaceOnUse"><path d="M35 0H0V35" fill="none" stroke="#d8e1df" strokeWidth=".7"/></pattern></defs>
    <rect width="900" height="490" fill="#eaf0ed"/><rect width="900" height="490" fill="url(#coordinate-grid)"/>
    <text x="845" y="130" fill="#75877b" fontSize="12" textAnchor="middle">N</text><path d="M845 145V180M839 153L845 143 851 153" fill="none" stroke="#75877b" strokeWidth="1.5"/>
    {[data.sector.bbox,...(JSON.stringify(bbox)!==JSON.stringify(data.sector.bbox)&&bboxFeature(bbox).features.length?[bbox]:[])].map((b,i)=><polygon key={`bounds-${i}`} points={bboxFeature(b).features[0].geometry.coordinates[0].map(p=>project(p).join(',')).join(' ')} fill="none" stroke={i?'#9255d7':'#8b9c9c'} strokeWidth="1.5" strokeDasharray="5 5"/>)}
    {cameras.map(c=><polygon key={c.id} points={closeRing(c.fov_polygon).map(p=>project(p).join(',')).join(' ')} fill={c.color} fillOpacity=".21" stroke={c.color} strokeWidth="1.4"/>)}
    {data.candidates.map(c=>{const [x,y]=project([c.lon,c.lat]);return <circle key={c.id} cx={x} cy={y} r="3.2" fill="#85919b"/>;})}
    {zones.map(z=>{const [x,y]=project([z.lon,z.lat]);return <g key={z.id}><circle cx={x} cy={y} r={z.priority?8:5.5} fill={z.isCovered?'#23865d':'#e05252'} stroke="white" strokeWidth="2"/><title>{z.name||`Zone ${z.id}`}: {z.isCovered?'covered':'uncovered'}</title></g>;})}
    {cameras.map(c=>{const[x,y]=project([c.lon,c.lat]);return <g key={c.id} role="button" tabIndex="0" aria-label={`Camera ${c.id}`} onClick={()=>onFocus(c.id)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onFocus(c.id);}}} style={{cursor:'pointer'}}><title>Camera {c.id}: {c.height_m}m height, pan {c.azimuth_deg}°, tilt {c.tilt_deg}°</title>{focused===c.id&&<circle cx={x} cy={y-11} r="23" fill="none" stroke="#53677b" strokeDasharray="3 3"/>}<path d={`M${x-13} ${y-27}h26v22h-9l-4 6-4-6h-9z`} fill={c.color} stroke="white" strokeWidth="2"/><text x={x} y={y-12} textAnchor="middle" fill="#263c32" fontSize="10" fontWeight="700">C{c.id}</text></g>;})}
    <text x="450" y="460" textAnchor="middle" fill="#7e8f85" fontSize="10">Geographic data view · supplied coordinates and footprints · no basemap</text>
  </svg></div>;
}
