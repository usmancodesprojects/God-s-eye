import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowDownToLine, Eye, ArrowUpRight, Atom, Check, ChevronRight, Map, Navigation2, Play, ScanLine, Settings2, Video, Wallet, X, Zap } from 'lucide-react';
import CityMap from './components/CityMap.jsx';
import QuantumPanel from './components/QuantumPanel.jsx';
import Comparison from './components/Comparison.jsx';
import Hero from './components/Hero.jsx';
import { health, loadResult, runOptimization } from './api.js';
import { AREA_LABELS, COLORS, METHODS, coveredZones, downloadJSON, fmt, selectedCameras, validBBox } from './data.js';

const METHOD_NAMES = { qaoa: 'QAOA', exact: 'Exact', greedy: 'Greedy' };
const METHOD_TEXT = { qaoa: 'Quantum Approximate Optimization Algorithm', exact: 'Exact classical solution', greedy: 'Greedy classical baseline' };
const scrollToWorkspace = () => {
  const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  document.getElementById('workspace')?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
};

export default function App() {
  const [data,setData] = useState(null), [instance,setInstance] = useState('sector_12'), [method,setMethod] = useState('qaoa'), [tab,setTab] = useState('placement');
  const [busy,setBusy] = useState('saved'), [error,setError] = useState(''), [source,setSource] = useState('Saved result'), [api,setApi] = useState(null);
  const [bbox,setBBox] = useState([]), [p,setP] = useState(2), [penalty,setPenalty] = useState(2), [focused,setFocused] = useState(null), [allCameras,setAllCameras] = useState(false);
  const captureRef = useRef(null), requestRef = useRef(null), serial = useRef(0);
  const focus = useCallback(id => { setFocused(id); setTab('placement'); }, []);
  function accept(d,origin) {
    setData(d); setBBox(d.sector.bbox); setP(d.quantum.p); setPenalty(d.quantum.penalties?.B_coverage ?? d.params?.B ?? 2);
    setFocused(null); setSource(origin);
  }
  useEffect(() => {
    const control = new AbortController(), id=++serial.current;
    requestRef.current=control; setBusy('saved'); setError('');
    loadResult(instance,control.signal).then(d=>{if(id===serial.current) accept(d,'Saved result');}).catch(e=>{if(e.name!=='AbortError'&&id===serial.current)setError(e.message);}).finally(()=>{if(id===serial.current)setBusy('');});
    return ()=>control.abort();
  }, [instance]);
  useEffect(()=>{
    const c=new AbortController(); health(c.signal).then(setApi).catch(()=>setApi({mode:'unreachable'}));
    return ()=>{c.abort();requestRef.current?.abort();};
  },[]);
  async function runLive() {
    if (!validBBox(bbox) || !Number.isInteger(Number(p)) || +p<1 || +p>3 || !(+penalty>0) || +penalty>1000000) { setError('Use valid increasing map bounds, integer p from 1–3, and a positive penalty up to 1,000,000.'); return; }
    requestRef.current?.abort(); const c=new AbortController(), id=++serial.current;requestRef.current=c;
    setBusy('live');setError('');
    try {
      const d=await runOptimization({instance,p:+p,lambda:+penalty,bbox},c.signal);
      if(id===serial.current) {accept(d,'Live solver');setApi({mode:'live',solver_configured:true});}
    } catch(e) {if(e.name!=='AbortError'&&id===serial.current)setError(e.message);}
    finally {if(id===serial.current)setBusy('');}
  }
  const selected=data?selectedCameras(data,method):[], zones=data?coveredZones(data,method):[], solution=data?.solutions[method];
  const camera=data?.candidates.find(c=>c.id===focused), displayed=allCameras?data?.candidates:selected;
  const pendingRegion=data&&JSON.stringify(bbox)!==JSON.stringify(data.sector.bbox);
  const apiText = api?.solver_configured ? 'Solver connected' : api?.mode==='unreachable' ? 'API offline · saved results available' : 'Saved results ready · live adapter required';

  return <div className="app">
    <a className="skip-link" href="#workspace">Skip to workspace</a>
    <header className="nav">
      <a className="brand" href="#top" aria-label="God’s Eye home"><span className="brand-mark"><Eye size={18}/></span><span className="brand-name">God’s <span className="accent">Eye</span></span></a>
      <nav className="nav-links" aria-label="Sections">
        <a href="#top">Overview</a>
        <a href="#workspace" onClick={()=>setTab('placement')}>Workspace</a>
        <a href="#workspace" onClick={()=>setTab('quantum')}>Quantum</a>
        <a href="#workspace" onClick={()=>{setTab('placement'); setTimeout(()=>document.getElementById('comparison')?.scrollIntoView({block:'start'}),60);}}>Benchmark</a>
      </nav>
      <div className="nav-right">
        <span className="status-chip"><span className={`status-dot ${api?.solver_configured?'online':''}`}/>{api?.solver_configured?'Solver online':api?.mode==='unreachable'?'API offline':'Saved results'}</span>
        <a className="btn btn-dark btn-sm" href="#workspace" onClick={()=>setTab('placement')}>Open workspace <ArrowUpRight size={15}/></a>
      </div>
    </header>

    <main>
      <Hero data={data} method={method} instance={instance} onExplore={()=>setTab('placement')} onQuantum={()=>{setTab('quantum'); scrollToWorkspace();}}/>

      <section className="workspace" id="workspace" aria-labelledby="workspace-title">
        <div className="section-head">
          <div>
            <div className="breadcrumb">Workspace <ChevronRight size={13}/> New York City <ChevronRight size={13}/> Midtown</div>
            <h2 id="workspace-title"><span className="thin">Plan coverage for</span> a city block<span className="accent">.</span></h2>
            <p>Pick an area, compare the quantum and classical layouts, then run the solver live on any region.</p>
          </div>
          <button className="btn btn-ghost export-btn" disabled={!data||!!busy} onClick={()=>downloadJSON(data)}><ArrowDownToLine size={16}/> Export result</button>
        </div>

        <div className="workspace-bar">
          <div className="tabs" role="tablist" aria-label="Workspace views">
            <button id="placement-tab" role="tab" aria-selected={tab==='placement'} aria-controls="placement-panel" onClick={()=>setTab('placement')}><Map size={16}/> Placement</button>
            <button id="quantum-tab" role="tab" aria-selected={tab==='quantum'} aria-controls="quantum-panel" onClick={()=>setTab('quantum')}><Atom size={16}/> Quantum diagnostics</button>
          </div>
          <div className="dataset-label"><span className="tiny-square"/>{data?.instance||instance}<span className="sep">/</span>{source}</div>
        </div>

        {error&&<div className="alert" role="alert"><strong>Request could not complete.</strong> {error} {data&&'The last successful result remains displayed.'}<button onClick={()=>setError('')} aria-label="Dismiss error"><X size={16}/></button></div>}

        {!data ? <div className="empty-state">{busy?<><span className="spinner"/> Loading the supplied result files…</>:<><h3>Result unavailable</h3><p>Check the error above, then reload.</p><button className="btn btn-ghost" onClick={()=>location.reload()}>Reload</button></>}</div> :
        <div className="workspace-grid">
          <aside className="control-column">
            <section className="panel controls" aria-labelledby="setup-title">
              <div className="card-heading"><h3 id="setup-title"><Settings2 size={17}/> Experiment setup</h3><span className="step-label">01</span></div>
              <label className="field">Area
                <select value={instance} disabled={!!busy} onChange={e=>setInstance(e.target.value)}>{[8,12,16].map(n=><option key={n} value={`sector_${n}`}>{AREA_LABELS[`sector_${n}`]}</option>)}</select>
              </label>
              <div className="instance-meta"><span>{data.zones.length} street points</span><span>{data.candidates.length} candidates</span></div>
              <hr/>
              <span className="field">Solution method</span>
              <div className="method-toggle" role="group" aria-label="Solution method">{METHODS.map(m=><button key={m} aria-pressed={method===m} className={method===m?'chosen':''} onClick={()=>{setMethod(m);setFocused(null);}}>{METHOD_NAMES[m]}</button>)}</div>
              <div className="method-description"><i style={{background:COLORS[method]}}/>{METHOD_TEXT[method]}</div>
              <div className="input-pair">
                <label className="field">QAOA layers (p)<input type="number" min="1" max="3" step="1" value={p} disabled={!!busy} onChange={e=>setP(e.target.value)}/></label>
                <label className="field">Penalty (λ)<input type="number" min="0.001" max="1000000" step="any" value={penalty} disabled={!!busy} onChange={e=>setPenalty(e.target.value)}/></label>
              </div>
              <details className="region-controls">
                <summary>Map region <span>{pendingRegion?'Edited':'Sector bounds'}</span></summary>
                <p>Bounds apply to the next live request. Saved results keep their original sector.</p>
                <div className="bbox-inputs">{['West longitude','South latitude','East longitude','North latitude'].map((name,i)=><label key={name}>{name}<input type="number" step="0.00001" value={bbox[i]??''} disabled={!!busy} onChange={e=>setBBox(b=>b.map((v,j)=>i===j?(e.target.value===''?'':+e.target.value):v))}/></label>)}</div>
                <div className="region-buttons"><button disabled={!!busy||tab!=='placement'} onClick={()=>{const b=captureRef.current?.();if(b)setBBox(b);}}>Use map view</button><button disabled={!!busy} onClick={()=>setBBox(data.sector.bbox)}>Reset</button></div>
              </details>
              <button className="run-button" disabled={!!busy} onClick={runLive}>{busy?<span className="spinner"/>:<Play size={15} fill="currentColor"/>}<span>{busy==='live'?'Optimizing…':busy?'Loading result…':'Run live'}</span>{!busy&&<ArrowUpRight size={17}/>}</button>
              <p className="api-status"><span className={`status-dot ${api?.solver_configured?'online':''}`}/>{apiText}</p>
              {busy==='live'&&<p className="small-note" role="status">The solver may take up to a minute on large areas. Keep this page open.</p>}
            </section>
            <section className="sector-card">
              <span className="eyebrow">Study area</span>
              <h3>{data.sector.name.startsWith('Custom') ? 'Custom region' : <>Midtown<br/>Manhattan</>}</h3>
              <p>{data.sector.name.startsWith('Custom') ? data.sector.name : 'Bryant Park and the surrounding street grid'}</p>
              <div className="sector-bottom"><Navigation2 size={15}/><span>OpenStreetMap · OpenFreeMap<br/><small>No map API key required</small></span></div>
            </section>
            <p className="scope-note">Mounts, line of sight and coverage come from the solver. The 3D buildings on the map are geographic context only.</p>
          </aside>

          <div className="content-column">{tab==='placement'?<section id="placement-panel" role="tabpanel" aria-labelledby="placement-tab">
            <div className="metric-grid">{[[Video,'Selected cameras',solution.num_cameras,`${data.candidates.length} possible placements`],[ScanLine,'Street coverage',`${fmt(solution.coverage_pct,1)}%`,`${zones.filter(z=>z.isCovered).length} of ${zones.length} street points`],[Wallet,'Total cost',fmt(solution.cost),'Hardware + lifetime energy'],[Zap,'Total power',`${fmt(solution.power_w,0)} W`,'Combined selected power']].map(([Icon,label,value,sub],i)=><div className="panel metric reveal" style={{'--i':i}} key={label}><div><span>{label}</span><Icon size={17}/></div><strong>{value}</strong><small>{sub}</small></div>)}</div>
            <div className="map-topline"><div><span className="eyebrow">Spatial overview</span><h2>Coverage in context</h2></div><span className="pill"><span className="status-dot online"/>{METHOD_NAMES[method]} solution</span></div>
            <CityMap data={data} method={method} focused={focused} onFocus={focus} bbox={bbox} captureRef={captureRef}/>
            {pendingRegion&&<div className="info-note compact">Purple boundary: the region for the next live run. The solution shown belongs to the dashed grey sector.</div>}
            {camera&&<div className="camera-inspector panel">
              <div><span className="eyebrow">Camera inspector</span><h3>C{camera.id} <span>Mount {camera.mount_id} · {camera.lens||'Camera'}</span></h3></div>
              <div className="orientation-dial" aria-label={`Pan ${camera.azimuth_deg} degrees from north`}><Navigation2 size={16} style={{transform:`rotate(${camera.azimuth_deg}deg)`}}/><small>N</small></div>
              <div>Height<strong>{camera.height_m} m</strong></div>
              <div>Pan / tilt<strong>{camera.azimuth_deg}° / {camera.tilt_deg}°</strong></div>
              <div>FOV / range<strong>{camera.fov_deg}° / {camera.range_m} m</strong></div>
              <button aria-label="Close camera inspector" onClick={()=>setFocused(null)}><X size={18}/></button>
            </div>}
            <section className="panel camera-table">
              <div className="card-heading"><div><h3>Camera placements <span className="count">{displayed.length}</span></h3><p>Click a camera to fly to its mount and orientation.</p></div><label className="checkbox"><input type="checkbox" checked={allCameras} onChange={e=>setAllCameras(e.target.checked)}/>All candidates</label></div>
              <div className="table-scroll"><table><thead><tr>{['Camera','Latitude / Longitude','Height','Pan','Tilt','FOV','Range','Cost','Power'].map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{displayed.map(c=><tr key={c.id} className={focused===c.id?'focused-row':''} onClick={()=>focus(c.id)}><td><button className="camera-id" onClick={e=>{e.stopPropagation();focus(c.id);}}><i style={{background:selected.find(s=>s.id===c.id)?.color||'#b9bfb6'}}/>C{c.id}<ArrowUpRight size={12}/></button></td><td className="coordinates">{c.lat.toFixed(6)}<br/>{c.lon.toFixed(6)}</td><td>{fmt(c.height_m)} m</td><td>{fmt(c.azimuth_deg)}°</td><td>{fmt(c.tilt_deg)}°</td><td>{fmt(c.fov_deg)}°</td><td>{fmt(c.range_m)} m</td><td>{fmt(c.cost)}</td><td>{fmt(c.power_w)} W</td></tr>)}</tbody></table></div>
              <div className="table-footer"><span><Check size={14}/> {solution.num_cameras} selected cameras</span><span>Pan: clockwise from north · Tilt: downward from horizontal</span></div>
            </section>
            <Comparison data={data} method={method} onMethod={setMethod}/>
          </section>:<section id="quantum-panel" role="tabpanel" aria-labelledby="quantum-tab"><QuantumPanel data={data}/></section>}</div>
        </div>}
      </section>
    </main>

    <footer className="site-footer">
      <span className="brand small"><span className="brand-mark"><Eye size={14}/></span><span className="brand-name">God’s <span className="accent">Eye</span></span></span>
      <span>Quantum camera coverage · Qiskit Fall Fest 2026</span>
      <span>Full-stack demo / Ahmad · Quantum solver / Huzaifa</span>
    </footer>
  </div>;
}
