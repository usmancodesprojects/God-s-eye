import { ArrowUpRight, Atom, Check, Video } from 'lucide-react';
import { AREA_LABELS, fmt, selectedCameras } from '../data.js';

// Presentational hero: concentric orbit rings with the selected cameras travelling on them,
// and a result card underneath. All numbers come from the loaded result file.
const RINGS = [
  { d: 'var(--ring-1)', t: '70s', reverse: false, angles: [24, 148, 262] },
  { d: 'var(--ring-2)', t: '95s', reverse: true, angles: [58, 196, 318] },
  { d: 'var(--ring-3)', t: '130s', reverse: false, angles: [102, 230, 345] },
];

function Node({ angle, camera, chip, tone }) {
  return <span className="node" style={{ '--a': `${angle}deg` }}>
    <span className="node-center"><span className="node-spin">
      <span className="cam-badge" style={{ '--pin': camera?.color || 'var(--sage-600)' }}><Video size={15} strokeWidth={2}/></span>
      {chip && <span className={`chip ${tone || ''}`}>{chip}</span>}
    </span></span>
  </span>;
}

export default function Hero({ data, method, instance, onExplore, onQuantum }) {
  const s = data?.solutions?.[method];
  const q = data?.quantum;
  const dec = q?.decomposition;
  const cams = data ? selectedCameras(data, method) : [];
  const zones = data?.zones?.length;
  const chips = [
    s && { text: <><Check size={12}/> {fmt(s.coverage_pct, 1)}% covered</>, tone: 'sage' },
    cams[0] && { text: `C${cams[0].id} · pan ${fmt(cams[0].azimuth_deg, 0)}°` },
    q && { text: `p = ${q.p} · ${q.num_qubits} qubits`, tone: 'ink' },
    dec && { text: <><Check size={12}/> {dec.subproblems_solved_optimally}/{dec.subproblems} optimal</>, tone: 'sage' },
    s && { text: `${s.num_cameras} cameras · ${fmt(s.power_w, 0)} W` },
  ].filter(Boolean);
  let k = 0;
  return <section className="hero" id="top" aria-labelledby="hero-title">
    <div className="orbit" aria-hidden="true">
      <div className="orbit-glow"/>
      {RINGS.map((r, ri) => <div key={ri} className={`ring ${r.reverse ? 'reverse' : ''}`} style={{ '--d': r.d, '--t': r.t }}>
        {r.angles.map((a, ai) => {
          const cam = cams[(ri * 3 + ai) % Math.max(cams.length, 1)];
          const chip = (ai === 0 || (ri === 1 && ai === 2)) ? chips[k++ % Math.max(chips.length, 1)] : null;
          return <Node key={ai} angle={a} camera={cam} chip={chip?.text} tone={chip?.tone}/>;
        })}
      </div>)}
    </div>

    <div className="hero-copy">
      <span className="eyebrow-chip reveal" style={{ '--i': 0 }}><span className="live-dot"/>Qiskit Fall Fest 2026 · Smart infrastructure</span>
      <h1 id="hero-title" className="reveal" style={{ '--i': 1 }}>
        <span className="thin">{zones ? `${fmt(zones, 0)} street points,` : 'Every street,'}</span>
        <span className="strong">{s ? `${fmt(s.coverage_pct, 1)}% in view.` : 'in view.'}</span>
      </h1>
      <p className="reveal" style={{ '--i': 2 }}>
        God’s Eye decides where a city mounts each camera, which way it points and which lens it uses, so every street is
        watched at the lowest hardware and energy cost. Solved with QAOA in Qiskit and checked against an exact optimum.
      </p>
      <div className="hero-actions reveal" style={{ '--i': 3 }}>
        <a className="btn btn-dark" href="#workspace" onClick={onExplore}>Explore the workspace <ArrowUpRight size={16}/></a>
        <button className="btn btn-ghost" type="button" onClick={onQuantum}><Atom size={16}/> See the quantum result</button>
      </div>
    </div>

    <article className="proof-card reveal" style={{ '--i': 4 }} aria-live="polite">
      <div className="proof-avatar"><Atom size={22}/></div>
      {data ? <>
        <h2>{dec
          ? `QAOA solved ${dec.subproblems_solved_optimally} of ${dec.subproblems} sub-problems to the proven optimum.`
          : 'QAOA matched the exact optimum on this instance.'}</h2>
        <p>{dec
          ? `Every sub-problem of up to ${dec.max_qubits} qubits is checked against brute force, and the whole layout against an exact MILP. On average the optimum was sampled ${fmt(dec.mean_amplification, 1)}× more often than by random guessing.`
          : `The optimum was sampled ${fmt(q?.amplification, 1)}× more often than by random guessing.`}</p>
        <div className="proof-sign">
          <strong>{AREA_LABELS[instance] && data.sector.name.startsWith('Custom') ? data.sector.name : (AREA_LABELS[instance] || data.sector.name)}</strong>
          <span>{fmt(zones, 0)} street points · {fmt(data.candidates.length, 0)} candidate cameras · {s.num_cameras} selected</span>
        </div>
      </> : <div className="proof-skeleton"><span/><span/><span/></div>}
    </article>
  </section>;
}
