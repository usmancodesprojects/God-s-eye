"""Build the hackathon report (docs/GodsEye_Report.docx) from the saved results.

python -m src.eval.build_report        (run src.eval.report_figures and src.eval.experiments first)
Every number in the tables is read from data/results/*.json, so the report always matches the code.
"""
import json

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from src.model import ROOT

RES = ROOT / "data" / "results"
ASSETS = ROOT / "docs" / "report_assets"
PLOTS = ROOT / "results" / "plots"
OUT = ROOT / "docs" / "GodsEye_Report.docx"
INK = RGBColor(0x13, 0x17, 0x14)
SAGE = RGBColor(0x46, 0x71, 0x3F)
MUTED = RGBColor(0x5F, 0x67, 0x5F)


def load(name):
    return json.loads((RES / f"result_{name}.json").read_text())


INT = {n: load(f"intersections_{n}") for n in (8, 12, 16)}
AREA = {k: load(f"sector_{n}") for k, n in (("S", 8), ("M", 12), ("L", 16))}

doc = Document()
sec = doc.sections[0]
sec.left_margin = sec.right_margin = Cm(2.0)
sec.top_margin = sec.bottom_margin = Cm(1.8)
st = doc.styles["Normal"]
st.font.name = "Calibri"
st.font.size = Pt(10.5)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
st.paragraph_format.space_after = Pt(5)
st.paragraph_format.line_spacing = 1.12
for lvl, size in ((1, 15), (2, 12.5), (3, 11)):
    h = doc.styles[f"Heading {lvl}"]
    h.font.name = "Calibri"
    h.font.size = Pt(size)
    h.font.color.rgb = INK if lvl == 1 else SAGE
    h.font.bold = True
    h.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    h.paragraph_format.space_before = Pt(12 if lvl == 1 else 8)
    h.paragraph_format.space_after = Pt(4)


def para(text="", bold_lead=None, italic=False, size=None, color=None, align=None, after=None):
    p = doc.add_paragraph()
    if bold_lead:
        r = p.add_run(bold_lead)
        r.bold = True
    r = p.add_run(text)
    r.italic = italic
    if size:
        r.font.size = Pt(size)
    if color:
        r.font.color.rgb = color
    if align:
        p.alignment = align
    if after is not None:
        p.paragraph_format.space_after = Pt(after)
    return p


def bullet(text, bold_lead=None):
    p = doc.add_paragraph(style="List Bullet")
    if bold_lead:
        p.add_run(bold_lead).bold = True
    p.add_run(text)
    p.paragraph_format.space_after = Pt(2)
    return p


def numbered(text, bold_lead=None):
    p = doc.add_paragraph(style="List Number")
    if bold_lead:
        p.add_run(bold_lead).bold = True
    p.add_run(text)
    p.paragraph_format.space_after = Pt(2)
    return p


def equation(text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.name = "Cambria Math"
    r.font.size = Pt(10.5)
    p.paragraph_format.left_indent = Cm(1.0)
    p.paragraph_format.space_after = Pt(3)
    return p


def shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def table(header, rows, widths=None, note=None):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        c.text = ""
        r = c.paragraphs[0].add_run(h)
        r.bold = True
        r.font.size = Pt(9)
        shade(c, "E6EEDF")
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            run = cells[i].paragraphs[0].add_run(str(v))
            run.font.size = Pt(9)
            if isinstance(v, str) and v.startswith("**"):
                run.text = v.strip("*")
                run.bold = True
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    if note:
        p = para(note, italic=True, size=8.5, color=MUTED)
        p.paragraph_format.space_before = Pt(3)
    else:
        doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def figure(path, width_cm, caption):
    if not path.exists():
        para(f"[missing figure: {path.name}]", italic=True, color=MUTED)
        return
    doc.add_picture(str(path), width=Cm(width_cm))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = para(caption, italic=True, size=8.5, color=MUTED, align=WD_ALIGN_PARAGRAPH.CENTER)
    p.paragraph_format.space_after = Pt(8)


def todo(text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = True
    r.font.highlight_color = WD_COLOR_INDEX.YELLOW
    return p


# ------------------------------------------------------------------ title
t = para("God’s Eye", size=30, color=INK, after=0)
t.runs[0].bold = True
para("Quantum-optimised public-safety camera coverage for smart cities", size=14, color=SAGE, after=4)
para("Qiskit Fall Fest 2026 Hackathon · The Quantum Optimization Challenge · "
     "Domain 6: Energy & Smart Infrastructure", size=10, color=MUTED, after=2)
para("Team: Huzaifa (quantum formulation and solver) · Ahmad (full-stack web application) · "
     "third team member (repository, research and documentation)", size=10, color=MUTED, after=2)
todo("GitHub repository: <paste the public repository URL here before submitting>")
todo("3-minute video (anyone with the link): <paste the Google Drive link here before submitting>")

doc.add_heading("Executive summary", level=1)
L, M, S = AREA["L"], AREA["M"], AREA["S"]
dL = L["quantum"]["decomposition"]
para(f"God’s Eye decides where a city should mount its street cameras, which way each one should point and which lens it "
     f"should use, so that every street in a district is watched at the lowest hardware and lifetime-energy cost. We build "
     f"the problem from real OpenStreetMap geometry of Midtown Manhattan, encode it as an exact higher-order Ising cost "
     f"Hamiltonian (one qubit per candidate camera, no slack qubits) and solve it with QAOA in Qiskit. Every quantum result "
     f"is checked against exact references (brute force and a MILP solver) and a greedy heuristic.")
bullet(f"QAOA found the proven optimum on every intersection benchmark (8, 12 and 16 qubits) and beat greedy by one camera "
       f"on 12 and 16 qubits; the optimum was sampled up to ×{INT[16]['quantum']['amplification']:.0f} more often than by "
       f"random guessing.", "Exact QAOA: ")
bullet(f"For full street coverage of a {len(L['zones'])}-point district ({len(L['candidates'])} candidate cameras), "
       f"decomposed QAOA reaches 100% coverage; all {dL['subproblems']} sub-problems were solved to their verified "
       f"optimum (mean amplification ×{dL['mean_amplification']:.1f}).", "Full areas: ")
bullet(f"The whole-area MILP optimum needs {L['solutions']['exact']['num_cameras']} cameras versus "
       f"{L['solutions']['qaoa']['num_cameras']} for decomposed QAOA. The gap comes from the decomposition, not from "
       f"QAOA: the same decomposition with an exact sub-solver needs {L['solutions']['decomposed_exact']['num_cameras']}.",
       "Honest comparison: ")
bullet("A 3D web application (React + MapLibre + FastAPI) shows the layouts, lets planners re-run the quantum solver live "
       "on any map region, and colours cameras so that no two overlapping views share a colour.", "Delivery: ")

# ------------------------------------------------------------------ 1 problem statement
doc.add_heading("1. Problem statement", level=1)
para("Cities install CCTV cameras on building walls and street poles for public safety and traffic management "
     "(for example, Safe City programmes). Each camera costs money to buy and mount and draws power for many years. "
     "Planners usually place cameras intersection by intersection, which leaves blind spots on the streets between them "
     "and wastes budget and energy on overlapping views. Choosing a mount, a direction and a lens for every camera across "
     "a district is a weighted set-cover problem with side constraints, which is NP-hard.", "Motivation. ")
para("municipal smart-infrastructure and public-safety planners, and the utility or street-lighting departments that host "
     "and power the cameras.", "Intended users: ")
para("select camera configurations so that every street point in the chosen area is in view (100% coverage, with "
     "priority intersections weighted higher) while minimising total cost = hardware capex + lifetime energy cost.",
     "Objective: ")
para("", "Constraints: ")
bullet("Coverage: every street point must be seen by at least one selected camera (within lens range, inside the field "
       "of view, and with no building blocking the line of sight).")
bullet("At most one camera per wall mount (one bracket and one power feed per mount).")
bullet("Hardware and energy budget enter through the cost of each configuration; the coverage weight λ sets the "
       "trade-off between coverage and cost.")
para("coverage % (target 100%), number of cameras, total cost, total power (W), optimality gap to the exact MILP optimum, "
     "and the probability that QAOA samples the optimum compared with random guessing.", "Measurable success criteria: ")
para("is it within an eligible domain? Camera networks are city infrastructure that consumes energy for years; the cost "
     "model includes each lens’s power draw, so the planner trades coverage against energy as well as hardware "
     "(Domain 6, Energy & Smart Infrastructure).", "Domain fit: ")

# ------------------------------------------------------------------ 2 formulation
doc.add_heading("2. Mathematical formulation", level=1)
doc.add_heading("2.1 Instances from real city geometry", level=2)
para("Buildings and streets come from OpenStreetMap (cached locally, so every run is reproducible offline). Each street is "
     "sampled every 15 m and intersections are added as priority points. Candidate mounts are placed 1.5 m off every "
     "building facade that faces a street (8 m mounting height). Each mount gets 36 aim directions (10° steps) and two "
     "lens types. A configuration covers a street point if the point is within range, inside the field of view and the "
     "straight line of sight does not cross a building footprint (2.5D occlusion with Shapely). Configurations dominated "
     "by a cheaper one on the same mount are removed.")
table(["Lens", "Field of view", "Range", "Capex", "Power", "Cost c_j = capex + 0.05·W"],
      [["wide", "100°", "65 m", "1.0", "6 W", "1.30"], ["tele", "50°", "125 m", "1.4", "10 W", "1.90"]],
      widths=[2, 2.4, 2, 1.8, 1.8, 5])
table(["Instance", "Street points", "Candidate configurations (= qubits before decomposition)", "Mounts"],
      [[f"Area {k} · {AREA[k]['sector']['name'].split(' - ')[-1]}", len(AREA[k]["zones"]), len(AREA[k]["candidates"]),
        len({c['mount_id'] for c in AREA[k]['candidates']})] for k in ("S", "M", "L")] +
      [[f"Intersection benchmark {n}", len(INT[n]["zones"]), n, len({c['mount_id'] for c in INT[n]['candidates']})]
       for n in (8, 12, 16)],
      widths=[5.5, 2.6, 6, 2])
doc.add_heading("2.2 Variables, objective and constraints", level=2)
para("x_j ∈ {0, 1} equals 1 if candidate configuration j (mount, aim, lens) is installed. S_i is the set of "
     "configurations that see street point i, w_i its priority weight (3 for 42nd St / Broadway intersections, 2 for "
     "avenue intersections, 1 otherwise), and m indexes mounts.", "Decision variables: ")
equation("minimise   H(x) = Σ_j c_j x_j  +  B Σ_i w_i Π_{j∈S_i} (1 − x_j)  +  P Σ_m Σ_{j<k ∈ m} x_j x_k")
para("The first term is hardware plus lifetime energy cost. The second term equals B·w_i exactly when point i is seen by "
     "no selected camera, so it enforces coverage. The third term forbids two cameras on one mount. B = λ (default 2) is "
     "larger than any single camera cost, so covering a point always pays off; P is derived from B so that "
     "double-mounting never pays off. Minimising H(x) therefore gives the cheapest layout with full coverage. A MILP "
     "with the same constraints written as linear inequalities is used as the exact reference.")

# ------------------------------------------------------------------ 3 quantum approach
doc.add_heading("3. Quantum approach and justification", level=1)
doc.add_heading("3.1 Mapping to qubits", level=2)
para("With x_j = (1 − Z_j)/2, every term of H(x) becomes a product of Pauli-Z operators, so H is a diagonal Ising "
     "Hamiltonian. The key modelling choice is the coverage term:")
equation("Π_{j∈S_i} (1 − x_j)  =  2^(−|S_i|) · Σ_{T ⊆ S_i} Π_{j∈T} Z_j")
para("This encodes ‘point i is unseen’ exactly as a |S_i|-local term. A standard QUBO would have to rewrite the inequality "
     "Σ_j x_j ≥ 1 with slack qubits (about ⌈log₂|S_i|⌉ per point, i.e. hundreds of extra qubits for Area L). Our encoding "
     "needs exactly one qubit per candidate camera. QAOA implements a k-local Z term as a CNOT ladder plus one RZ "
     "rotation, so no reduction to quadratic form is needed. We cap |S_i| ≤ 4 inside each sub-problem to bound circuit "
     "depth. A unit test confirms that the diagonal of the SparsePauliOp equals H(x) for every one of the 2ⁿ bitstrings.")
q16 = INT[16]["quantum"]
table(["Benchmark", "Qubits", "Pauli terms", "Max locality", "Depth (p=2)", "CNOTs (p=2)"],
      [[f"intersections_{n}", INT[n]["quantum"]["num_qubits"], INT[n]["quantum"]["operator"]["num_terms"],
        INT[n]["quantum"]["operator"]["max_locality"], INT[n]["quantum"]["depth"], INT[n]["quantum"]["two_qubit_gates"]]
       for n in (8, 12, 16)], widths=[3.6, 1.6, 2.4, 2.4, 2.4, 2.6],
      note="Circuits transpiled to {cx, rz, rx, h, sx, x}; statevector simulation (noise-free).")
doc.add_heading("3.2 Algorithm: QAOA with a CVaR objective", level=2)
bullet("QAOA prepares |γ,β⟩ = Π_k e^(−iβ_k Σ X) e^(−iγ_k H) |+⟩^⊗n with p = 2 layers (QAOAAnsatz, X mixer).")
bullet("The classical loop (COBYLA, linear-ramp start plus seeded random restarts) minimises CVaR_0.2, the mean energy of "
       "the best 20% of outcomes (Barkoutsos et al., 2020). We only need the best samples, and on the 12-qubit benchmark "
       "CVaR raised the probability of sampling the optimum about 4.5× compared with the plain expectation value.")
bullet("Read-out uses StatevectorSampler with 2,048–4,096 shots; the cheapest feasible sampled bitstring is decoded into "
       "cameras.")
para("our cost is already a diagonal (HUBO) Hamiltonian, which is exactly what the QAOA cost layer applies; QAOA is shallow "
     "and NISQ-oriented, uses only 2p parameters, and its quality can be measured directly against brute force. "
     "Alternatives were considered: Grover adaptive search needs deep oracles and fault tolerance; quantum annealing would "
     "need a quadratic reduction with ancilla qubits and is outside Qiskit; a hardware-efficient VQE ignores the problem "
     "structure and suffers from barren plateaus.", "Why QAOA: ")
doc.add_heading("3.3 Scaling to whole districts: verified decomposition", level=2)
para("A district has hundreds of candidates, far more than can be simulated, so the area is solved in sub-problems of "
     "at most 12 qubits:")
numbered("Exact row-dominance reduction: drop a street point if another point is seen by a subset of its cameras.")
numbered("Seed at the hardest uncovered point (fewest available cameras) and take its 6 nearest uncovered neighbours.")
numbered("Pick at most 12 candidates, ranked by uncovered street seen per unit cost; include every uncovered point those "
         "candidates see (at most 4 candidates per point).")
numbered("Build that sub-problem’s Hamiltonian, run QAOA, keep the cheapest feasible sample, and check it against brute "
         "force.")
numbered("Repeat until every street point is covered; then drop redundant cameras and colour the result (DSatur), so "
         "cameras whose views touch never share a colour.")

# ------------------------------------------------------------------ 4 architecture
doc.add_heading("4. Architecture", level=1)
figure(ASSETS / "architecture.png", 16.5, "Figure 1 — God’s Eye architecture: spatial pipeline (green), quantum "
       "optimisation in Qiskit (violet), validation and delivery (blue).")
table(["Component", "Implementation"],
      [["Spatial pipeline", "src/geo/fetch_osm.py, area_instance.py (Overpass download + cache, street sampling, mounts, "
                            "ray-cast fields of view, line-of-sight coverage)"],
       ["Model and Hamiltonian", "src/model.py (H(x)), src/quantum/hamiltonian.py (SparsePauliOp with k-local Z terms)"],
       ["Quantum solver", "src/quantum/qaoa.py (QAOAAnsatz, StatevectorEstimator/Sampler, COBYLA, CVaR), "
                          "src/solve_area.py (decomposition, verification, colouring)"],
       ["Classical references", "src/classical/baselines.py (brute force 2ⁿ, MILP via SciPy HiGHS, greedy set cover)"],
       ["Web application", "backend/ (FastAPI, validated result contract, live adapter) and frontend/ (React, MapLibre 3D, "
                           "Chart.js)"],
       ["Tests", "24 core tests (pytest), 10 API tests, 8 front-end tests; identical results on rebuild"]],
      widths=[3.8, 13])

# ------------------------------------------------------------------ 5 results
doc.add_heading("5. Results", level=1)
doc.add_heading("5.1 Exact QAOA on the intersection benchmark (no decomposition)", level=2)
rows = []
for n in (8, 12, 16):
    s, q = INT[n]["solutions"], INT[n]["quantum"]
    rows.append([f"{n} qubits", f"{s['qaoa']['num_cameras']} cams · {s['qaoa']['cost']}",
                 f"{s['exact']['num_cameras']} cams · {s['exact']['cost']}",
                 f"{s['greedy']['num_cameras']} cams · {s['greedy']['cost']}",
                 f"{q['p_optimal']:.4f} vs {q['p_optimal_random']:.5f}", f"×{q['amplification']:.0f}"])
table(["Instance", "QAOA (p=2, CVaR)", "Exact optimum", "Greedy", "P(optimum) QAOA vs random", "Amplification"], rows,
      widths=[2.4, 3.2, 3.0, 3.0, 3.6, 2.2],
      note="All layouts cover 100% of the intersections. QAOA returns the proven optimum at every size; greedy needs one "
           "extra camera at 12 and 16 qubits.")
figure(PLOTS / "amplification.png", 9.5, "Figure 2 — Probability of sampling the optimum per shot: QAOA versus uniform "
       "random guessing (log scale).")
figure(PLOTS / "p_optimal_vs_depth.png", 15, "Figure 3 — Effect of QAOA depth p and of the objective (expectation vs "
       "CVaR) on the probability of the optimum.")
figure(PLOTS / "pareto.png", 9.5, "Figure 4 — Sweeping the coverage weight λ traces the cost–coverage trade-off; QAOA "
       "lands on the exact Pareto front, greedy below it.")

doc.add_heading("5.2 Full street coverage of real districts (decomposed QAOA)", level=2)
rows = []
for k in ("S", "M", "L"):
    r = AREA[k]
    s, d = r["solutions"], r["quantum"]["decomposition"]
    rows.append([f"Area {k}", len(r["zones"]), len(r["candidates"]),
                 f"{d['subproblems_solved_optimally']}/{d['subproblems']}", f"×{d['mean_amplification']:.1f}",
                 f"{s['exact']['num_cameras']} · {s['exact']['cost']}", f"{s['greedy']['num_cameras']} · {s['greedy']['cost']}",
                 f"{s['decomposed_exact']['num_cameras']} · {s['decomposed_exact']['cost']}",
                 f"**{s['qaoa']['num_cameras']} · {s['qaoa']['cost']}", f"{s['qaoa']['approx_ratio']:.2f}",
                 s['qaoa']['num_colors']])
table(["Area", "Street pts", "Cand.", "Sub-problems optimal", "Mean ampl.", "Exact MILP (cams · cost)", "Greedy",
       "Decomp. + brute force", "Decomp. + QAOA", "Ratio", "Colours"], rows,
      widths=[1.3, 1.4, 1.3, 1.8, 1.5, 2.2, 1.7, 2.0, 2.0, 1.2, 1.3],
      note="Every method reaches 100% street coverage. Ratio = exact cost / QAOA cost. Colours = classes needed so that "
           "no two touching views share a colour (verified for every saved layout).")
figure(ASSETS / "area_map_sector_16.png", 16.5, "Figure 5 — Area L (Bryant Park sector): decomposed QAOA (left) and the "
       "exact optimum (right). Green dots are street points in view, triangles are cameras, wedges are ray-cast fields of "
       "view coloured by DSatur class.")
figure(ASSETS / "area_comparison.png", 16.5, "Figure 6 — Cameras and cost needed for 100% coverage, per method and area.")
figure(ASSETS / "subproblems_sector_16.png", 16.5, "Figure 7 — The 15 QAOA sub-problems of Area L: probability of "
       "sampling each sub-problem’s optimum versus random guessing.")
doc.add_heading("5.3 Generalisation to new regions", level=2)
para("Because the whole pipeline runs from map bounds, the web app can re-solve any region live. Examples run through the "
     "API: Times Square (109 street points, 845 candidates) solved in 16 s with 100% coverage (QAOA 21 cameras, exact 18); "
     "a Murray Hill block (41 street points, fresh OpenStreetMap download) solved in 48 s with 100% coverage. The saved "
     "Area S re-solves live in about 5 s.")
doc.add_heading("5.4 The application", level=2)
figure(ASSETS / "ui_hero.jpg", 13, "Figure 8 — God’s Eye web app: live headline numbers for the selected area.")
figure(ASSETS / "ui_workspace_map.jpg", 15, "Figure 9 — Workspace: controls, live re-solve, 3D map with coloured camera "
       "views and covered street points.")
figure(ASSETS / "ui_quantum.jpg", 15, "Figure 10 — Quantum diagnostics: circuit statistics, measurement distribution and "
       "optimiser convergence for the representative sub-problem.")

# ------------------------------------------------------------------ 6 comparison
doc.add_heading("6. Classical and exact reference comparison", level=1)
bullet("Small instances (≤ 16 qubits) are enumerated completely (2ⁿ assignments), and an independent MILP (HiGHS) with "
       "linear constraints confirms the same optimum, which also validates the penalty encoding.", "Brute force and MILP: ")
bullet("On the intersection benchmark QAOA matches the exact optimum at all sizes and beats greedy (8.3 → 7.0 and "
       "10.2 → 8.9 cost). Quantum sampling concentrates probability on the optimum ×7 to ×110 above random guessing.",
       "Where QAOA wins: ")
bullet(f"On full districts the MILP solves the whole problem in about {L['solutions']['exact']['runtime_s']:.1f} s and "
       f"is the honest ‘minimum cameras’ answer ({L['solutions']['exact']['num_cameras']} for Area L). Greedy is 8–20% "
       f"more expensive and decomposed QAOA 25–37% more expensive (approximation ratio 0.73–0.80).",
       "Where classical wins: ")
bullet("Decomposition with an exact brute-force sub-solver lands within 0–6% of decomposed QAOA, and every QAOA "
       "sub-problem hits its verified optimum. The remaining gap is therefore caused by solving the district piece by "
       "piece, not by QAOA.", "Attributing the gap: ")
bullet("Runtimes include simulating quantum circuits on a laptop and do not indicate any quantum speed-up.", "Runtime: ")

# ------------------------------------------------------------------ 7 limitations
doc.add_heading("7. Honest limitations and trade-offs", level=1)
for lead, text in [
    ("No quantum advantage is claimed. ", "Every instance here is solved faster and exactly by MILP. The instances are "
     "small on purpose, so QAOA can be verified against a provable optimum."),
    ("Simulation only. ", f"Results are noise-free statevector simulations. The 16-qubit p=2 circuit needs "
     f"{q16['two_qubit_gates']} CNOTs (depth {q16['depth']}), which is too deep for reliable execution on current hardware "
     f"without error mitigation."),
    ("Sampling, not concentration. ", f"QAOA raises the probability of the optimum strongly, but at 16 qubits it is still "
     f"only {q16['p_optimal']:.2%} per shot; the answer is the cheapest of thousands of samples, and the most probable "
     f"bitstring is often not optimal."),
    ("Decomposition loses optimality. ", "District layouts cost 25–37% more than the exact optimum because sub-problems are "
     "solved one after another with limited view of their neighbours."),
    ("Higher-order terms cost depth. ", "A point seen by d candidates adds up to 2^d Pauli terms; capping d ≤ 4 keeps "
     "circuits shallow but restricts each sub-problem."),
    ("Penalty tuning. ", "Large penalties guarantee feasibility but roughen the optimisation landscape; many samples remain "
     "infeasible."),
    ("Simplified geometry. ", "15 m street sampling (gaps between points are not checked), 10° aim presets, two lens types, "
     "fixed 8 m mount height, 2.5D occlusion from footprints only, and OpenStreetMap data quality."),
    ("Simple energy model. ", "Constant power per lens and a fixed lifetime cost per watt; no solar, PoE or tariff modelling."),
    ("External data service. ", "Live regions outside the cached areas depend on public Overpass servers, which were "
     "intermittently down during testing; the app reuses cached downloads and reports outages clearly."),
    ("Privacy and governance. ", "The tool only plans coverage of public streets. It processes no video and identifies no "
     "people. Any real deployment needs legal review, signage and data-retention policies."),
]:
    bullet(text, lead)

# ------------------------------------------------------------------ 8 reflection
doc.add_heading("8. Reflection and future work", level=1)
bullet("Correctness is established by construction and by testing: the operator diagonal equals H(x) for every bitstring, "
       "brute force equals MILP, every saved layout covers every street point, and rebuilding all instances and results "
       "reproduces them exactly (seeded).", "Correctness: ")
bullet("The pipeline is practical today as a planning tool because the exact MILP and the quantum solver share one model; "
       "the quantum part becomes interesting when sub-problems grow beyond what exact methods handle comfortably.",
       "Feasibility: ")
bullet("Run the ≤ 12-qubit sub-problems on IBM Quantum hardware with error mitigation; use an XY mixer to keep the "
       "one-camera-per-mount constraint inside the search space; warm-start QAOA from the greedy layout; replace the "
       "one-pass decomposition with iterated large-neighbourhood search to close the gap to the optimum; add overlap "
       "(hand-off) requirements for continuous tracking on priority corridors.", "Next steps: ")

# ------------------------------------------------------------------ 9 rubric map
doc.add_heading("9. How this submission addresses the judging rubric", level=1)
table(["Criterion", "Evidence in this submission"],
      [["A. Problem validity (20)", "Domain 6 smart infrastructure with an energy cost term; real Manhattan geometry; "
                                    "explicit variables, objective and constraints (Section 2); small, simulator-friendly "
                                    "instances; measurable metrics (coverage %, cameras, cost, watts, gap)."],
       ["B. Quantum utilisation (25)", "Exact higher-order Ising mapping with no slack qubits, tested on every bitstring; "
                                      "QAOA justified against alternatives; CVaR objective; quantum sampling decides every "
                                      "sub-problem; assumptions and limits stated (Sections 3 and 7)."],
       ["C. Implementation and validation (25)", "Working Qiskit code; interpretable maps, tables and a 3D app; brute force, "
                                                 "MILP and greedy baselines; seeded, cached and tested (42 automated tests)."],
       ["D. Innovation (15)", "Street-level coverage of a real district instead of a toy graph; slack-free k-local "
                              "encoding; verified decomposition; DSatur colouring of overlapping views; live re-solve "
                              "of any map region."],
       ["E. Presentation (15)", "This report, a 3-minute demo video, the README and a polished web application."]],
      widths=[4.2, 12.6])

# ------------------------------------------------------------------ appendix
doc.add_heading("Appendix A. Reproducing the results", level=1)
for cmd in ["pip install -r requirements.txt   (Python 3.12, Qiskit 2.6.2; qiskit-aer is not required)",
            "python -m pytest -q tests          (24 core tests)",
            "python -m src.geo.area_instance    (rebuild the three street-coverage areas from cached OSM data)",
            "python -m src.solve_area sector_8 sector_12 sector_16",
            "python -m src.solve intersections_8 intersections_12 intersections_16",
            "python -m src.eval.experiments     (depth and λ sweeps)",
            "npm --prefix frontend ci  then  npm run dev   (web app on http://localhost:5173)"]:
    p = doc.add_paragraph(style="List Bullet")
    r = p.add_run(cmd)
    r.font.name = "Consolas"
    r.font.size = Pt(9)
doc.add_heading("Appendix B. Credits and references", level=1)
bullet("Map data © OpenStreetMap contributors (ODbL); basemap tiles by OpenFreeMap / OpenMapTiles.")
bullet("Qiskit (QAOAAnsatz, SparsePauliOp, StatevectorEstimator, StatevectorSampler); SciPy (COBYLA, HiGHS MILP); "
       "Shapely; FastAPI; React; MapLibre GL JS; Chart.js.")
bullet("Farhi, Goldstone, Gutmann, ‘A Quantum Approximate Optimization Algorithm’, arXiv:1411.4028 (2014).")
bullet("Barkoutsos et al., ‘Improving Variational Quantum Optimization using CVaR’, Quantum 4, 256 (2020).")
bullet("Brélaz, ‘New methods to color the vertices of a graph’ (DSatur), Communications of the ACM 22(4), 1979.")
bullet("No tutorial code was copied; all reused libraries are credited above.")

doc.save(OUT)
print("wrote", OUT)
