import { useCallback, useEffect, useState, type FormEvent } from "react";

type Claim = { id: string; claim_text: string; claim_type: string; evidence_excerpt?: string | null; confidence_label: string; is_inference: boolean };
type Source = { id: string; title: string; canonical_url: string; publisher?: string | null; publication_year?: number | null; authors: string[]; venue?: string | null; retrieval_status: string; failure_code?: string | null; excerpt?: string | null; claims: Claim[] };
type Run = { run_id: string; question: string; status: string; stage: string; progress: number; source_count: number; usable_source_count: number; warning_summary?: string | null };
type Report = { question: string; status: string; stage: string; progress: number; structured_sections: Record<string, unknown>; claims: Claim[]; sources: Source[]; validation_warnings: string[]; warning_summary?: string | null };
type Node = { id: string; type: "claim" | "source"; label: string; confidence?: string | null; source_url?: string | null; excerpt?: string | null; metadata: Record<string, unknown> };
type Edge = { source: string; target: string; type: "supports" | "contradicts" | "qualifies" | "derived_from"; rationale: string; confidence: string };
type Graph = { nodes: Node[]; edges: Edge[]; warning_summary?: string | null };
const examples = ["Can satellite imagery help detect river pollution?", "What limits the reliability of AI-generated medical summaries?", "How are low-cost sensors used to monitor urban air quality?"];
const terminal = (s = "") => ["completed", "succeeded", "partial", "failed", "error"].includes(s.toLowerCase());
const pretty = (s: string) => s.replaceAll("_", " ");

export default function App() {
  const [question, setQuestion] = useState("");
  const [yearMin, setYearMin] = useState("");
  const [yearMax, setYearMax] = useState("");
  const [notice, setNotice] = useState("");
  const [runId, setRunId] = useState("");
  const [run, setRun] = useState<Run | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [graph, setGraph] = useState<Graph | null>(null);
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<"report" | "sources" | "graph">("report");
  const [selected, setSelected] = useState("");

  const refresh = useCallback(async (id: string) => {
    const responses = await Promise.all([
      fetch("/api/research-runs/" + id), fetch("/api/research-runs/" + id + "/report"), fetch("/api/research-runs/" + id + "/graph"),
    ]);
    if (responses[0].ok) setRun(await responses[0].json() as Run);
    if (responses[1].ok) setReport(await responses[1].json() as Report);
    if (responses[2].ok) setGraph(await responses[2].json() as Graph);
  }, []);

  useEffect(() => {
    if (!runId || terminal(run?.status)) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const response = await fetch("/api/research-runs/" + runId);
        if (!response.ok || cancelled) return;
        const next = await response.json() as Run;
        setRun(next);
        if (terminal(next.status)) await refresh(runId);
      } catch { /* Retry on the next poll after transient network errors. */ }
    };
    void poll();
    const timer = window.setInterval(() => { if (!terminal(run?.status)) void poll(); }, 2500);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [runId, run?.status, refresh]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim()) { setNotice("Enter a research question to continue."); return; }
    if (yearMin && yearMax && Number(yearMin) > Number(yearMax)) { setNotice("The start year must not be later than the end year."); return; }
    setBusy(true); setNotice(""); setRunId(""); setRun(null); setReport(null); setGraph(null);
    try {
      const body: { question: string; year_min?: number; year_max?: number } = { question: question.trim() };
      if (yearMin) body.year_min = Number(yearMin);
      if (yearMax) body.year_max = Number(yearMax);
      const response = await fetch("/api/research-runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (!response.ok) { setNotice(response.status === 422 ? "Check your question and year range. Years must be between 1900 and 2100." : "Could not start research. Check that the API is running."); return; }
      const result = await response.json() as { run_id: string };
      setRunId(result.run_id); setTab("report");
    } catch { setNotice("Could not reach the API. Start the backend and try again."); }
    finally { setBusy(false); }
  }

  const sections = report?.structured_sections ?? {};
  const comparisons = Array.isArray(sections.cross_source_comparisons) ? sections.cross_source_comparisons as Record<string, unknown>[] : [];
  const gaps = Array.isArray(sections.candidate_research_gaps) ? sections.candidate_research_gaps as Record<string, unknown>[] : [];
  const limitations = Array.isArray(sections.limitations) ? sections.limitations : [];
  const sources = report?.sources ?? [];
  const nodes = graph?.nodes ?? [];
  const edges = graph?.edges ?? [];
  const selectedNode = nodes.find(n => n.id === selected);

  return <main className="page-shell">
    <header className="topbar"><a className="brand" href="/" aria-label="ResearchPilot home"><span className="brand-mark">R</span><span>ResearchPilot<span className="brand-ai"> AI</span></span></a><span className="status-pill"><span className="status-dot" /> Evidence-first research</span></header>
    <section className="hero">
      <p className="eyebrow">EVIDENCE-FIRST RESEARCH</p><h1>Go from a question<br />to a clearer research direction.</h1>
      <p className="hero-copy">Explore sources, compare reported findings, and identify candidate research gaps with evidence you can inspect.</p>
      <form className="question-card" onSubmit={submit}>
        <label htmlFor="research-question">What are you investigating?</label>
        <textarea id="research-question" value={question} onChange={e => { setQuestion(e.target.value); setNotice(""); }} maxLength={1000} placeholder="Enter a focused scientific or technical research question…" rows={4} disabled={busy} />
        <div className="year-filters"><label htmlFor="year-min">Published from <input id="year-min" type="number" min="1900" max="2100" placeholder="Any year" value={yearMin} onChange={e => setYearMin(e.target.value)} /></label><label htmlFor="year-max">Published to <input id="year-max" type="number" min="1900" max="2100" placeholder="Any year" value={yearMax} onChange={e => setYearMax(e.target.value)} /></label></div>
        <div className="form-footer"><span className="character-count">{question.length}/1000</span><button type="submit" disabled={busy}>{busy ? "Starting…" : "Start research"} <span aria-hidden="true">→</span></button></div>
        {notice && <p className="notice" role="status">{notice}</p>}
      </form>
      {!runId && <div className="examples"><p>NEED A STARTING POINT?</p><div className="example-list">{examples.map(item => <button className="example-chip" key={item} type="button" onClick={() => { setQuestion(item); setNotice(""); }}>{item}<span aria-hidden="true">↗</span></button>)}</div></div>}
    </section>
    {runId && <section className="results-section" aria-live="polite">
      <div className="results-heading"><div><p className="eyebrow">RESEARCH WORKSPACE</p><h2>Your research run</h2><p className="muted run-question">{run?.question ?? question}</p></div><button className="secondary-button" type="button" onClick={() => void refresh(runId)}>Refresh results</button></div>
      <div className="progress-card"><div className="progress-top"><span className="status-label"><span className={"status-dot " + (run?.status === "partial" ? "warning-dot" : "")} />{pretty(run?.status ?? "queued")}</span><span>{run?.progress ?? 0}%</span></div><div className="progress-track"><span style={{ width: Math.max(0, Math.min(100, run?.progress ?? 0)) + "%" }} /></div><div className="progress-bottom"><span>{pretty(run?.stage ?? "waiting to start")}</span><span>{run?.usable_source_count ?? 0} usable / {run?.source_count ?? 0} sources</span></div>{run?.warning_summary && <p className="warning-message">{run.warning_summary}</p>}{run && terminal(run.status) && <p className="muted completion-note">Processing has stopped. Results may be partial; review the evidence and limitations below.</p>}</div>
      <nav className="result-tabs" aria-label="Research result views"><button className={tab === "report" ? "active" : ""} onClick={() => setTab("report")} type="button">Report <span>{report?.claims.length ?? 0}</span></button><button className={tab === "sources" ? "active" : ""} onClick={() => setTab("sources")} type="button">Sources <span>{sources.length}</span></button><button className={tab === "graph" ? "active" : ""} onClick={() => setTab("graph")} type="button">Evidence graph <span>{nodes.length}</span></button></nav>
      {tab === "report" && <div className="result-content"><div className="section-heading"><div><p className="eyebrow">SYNTHESIS</p><h3>Evidence report</h3></div><span className="subtle-tag">Draft · source-linked</span></div>
        {!report || (!report.claims.length && !comparisons.length && !gaps.length) ? <div className="empty-state"><h4>{run && terminal(run.status) ? "No report evidence available yet" : "Building your evidence report"}</h4><p>Claims and comparisons appear after retrieval and analysis. A missing result is not evidence that no prior research exists.</p></div> : <>
          <section className="report-block"><h4>Extracted claims <span className="count">{report.claims.length}</span></h4>{!report.claims.length ? <p className="muted">No validated claims were extracted.</p> : <div className="claim-list">{report.claims.map(claim => { const source = sources.find(s => s.claims.some(c => c.id === claim.id)); return <article className="claim-card" key={claim.id}><div className="claim-meta"><span className="type-tag">{pretty(claim.claim_type)}</span><span className={"confidence confidence-" + claim.confidence_label}>{pretty(claim.confidence_label)} confidence</span>{claim.is_inference && <span className="type-tag">Inference</span>}</div><p>{claim.claim_text}</p>{claim.evidence_excerpt && <blockquote>{claim.evidence_excerpt}</blockquote>}{source && <a href={source.canonical_url} target="_blank" rel="noreferrer" className="source-link">Source: {source.title} ↗</a>}</article>; })}</div>}</section>
          <section className="report-block"><h4>Cross-source comparison <span className="count">{comparisons.length}</span></h4>{!comparisons.length ? <p className="muted">No cross-source relationships were validated.</p> : <div className="comparison-list">{comparisons.map((item, i) => <article className="comparison-card" key={String(item.id ?? i)}><span className={"relation-tag relation-" + String(item.relationship ?? item.type ?? "qualifies")}>{pretty(String(item.relationship ?? item.type ?? "comparison"))}</span><p>{String(item.rationale ?? item.description ?? "No rationale supplied.")}</p>{Boolean(item.confidence_label ?? item.confidence) && <span className="muted small-text">Confidence: {String(item.confidence_label ?? item.confidence)}</span>}</article>)}</div>}</section>
          <section className="report-block"><h4>Candidate research gaps <span className="count">{gaps.length}</span></h4><p className="caution-copy">Candidate leads only — not verified claims of novelty.</p>{!gaps.length ? <p className="muted">No candidate gaps were generated from this evidence set.</p> : <div className="gap-grid">{gaps.map((gap, i) => <article className="gap-card" key={String(gap.id ?? i)}><div className="gap-top"><span className="type-tag">Candidate gap</span><span className="evidence-level">{pretty(String(gap.evidence_level ?? "insufficient"))} evidence</span></div><h5>{String(gap.title ?? "Research opportunity")}</h5><p>{String(gap.description ?? gap.rationale ?? "Review supporting sources before drawing a conclusion.")}</p>{Boolean(gap.rationale && gap.description) && <p className="muted small-text">{String(gap.rationale)}</p>}<span className="novelty-note">Novelty not confirmed</span></article>)}</div>}</section>
          <section className="report-block"><h4>Limitations</h4><ul className="limitations-list">{(limitations.length ? limitations : ["Coverage is limited to sources returned and successfully retrieved.", "Automated comparisons and candidate gaps require human verification."]).map((item, i) => <li key={i}>{typeof item === "string" ? item : JSON.stringify(item)}</li>)}</ul>{report.validation_warnings.map((warning, i) => <p className="warning-message" key={i}>{warning}</p>)}</section>
        </>}
      </div>}
      {tab === "sources" && <div className="result-content"><div className="section-heading"><div><p className="eyebrow">RETRIEVAL LOG</p><h3>Discovered sources</h3></div><span className="subtle-tag">{sources.length} records</span></div>{!sources.length ? <div className="empty-state"><h4>No source records yet</h4><p>Source records appear as discovery completes.</p></div> : <div className="source-list">{sources.map(source => <article className="source-card" key={source.id}><div className="source-card-top"><span className={"retrieval-tag " + (source.retrieval_status === "retrieved" ? "retrieved" : "not-retrieved")}>{pretty(source.retrieval_status)}</span>{source.publication_year && <span className="muted small-text">{source.publication_year}</span>}</div><h4><a href={source.canonical_url} target="_blank" rel="noreferrer">{source.title || source.canonical_url} ↗</a></h4><p className="source-metadata">{[source.publisher, source.venue, source.authors?.slice(0, 3).join(", ")].filter(Boolean).join(" · ") || "Publication metadata unavailable"}</p>{source.excerpt && <blockquote>{source.excerpt}</blockquote>}{source.claims.length > 0 && <div className="source-claims"><strong>{source.claims.length} linked claims</strong>{source.claims.map(claim => <p key={claim.id}>{claim.claim_text}</p>)}</div>}{source.failure_code && <p className="muted small-text">Retrieval note: {pretty(source.failure_code)}</p>}</article>)}</div>}</div>}
      {tab === "graph" && <div className="result-content"><div className="section-heading"><div><p className="eyebrow">EVIDENCE MAP</p><h3>Sources and claim relationships</h3></div><span className="subtle-tag">{nodes.length} nodes · {edges.length} edges</span></div><div className="graph-legend"><span><i className="legend-source" /> Source</span><span><i className="legend-claim" /> Claim</span><span><i className="legend-line" /> Relationship</span></div>{!nodes.length ? <div className="empty-state"><h4>Evidence graph is waiting for data</h4><p>Nodes represent sources and extracted claims; edges represent evidence links or cross-source relationships.</p></div> : <><div className="graph-scroll"><div className="graph-columns"><div><h4>Sources</h4>{nodes.filter(n => n.type === "source").map(n => <button key={n.id} type="button" className={"graph-card source-node " + (selected === n.id ? "selected" : "")} onClick={() => setSelected(n.id)}>{n.label}</button>)}</div><div><h4>Relationships</h4>{edges.map((e, i) => <div className="edge-card" key={i}><span className={"relation-tag relation-" + e.type}>{pretty(e.type)}</span><p className="edge-endpoints">{nodes.find(n => n.id === e.source)?.label ?? e.source} → {nodes.find(n => n.id === e.target)?.label ?? e.target}</p><p>{e.rationale}</p><small>{e.confidence} confidence</small></div>)}</div><div><h4>Claims</h4>{nodes.filter(n => n.type === "claim").map(n => <button key={n.id} type="button" className={"graph-card claim-node " + (selected === n.id ? "selected" : "")} onClick={() => setSelected(n.id)}>{n.label}</button>)}</div></div></div>{selectedNode && <article className="node-detail"><div className="section-heading"><h4>{selectedNode.type === "source" ? "Source details" : "Claim details"}</h4><button className="text-button" type="button" onClick={() => setSelected("")}>Clear selection</button></div><h5>{selectedNode.label}</h5>{selectedNode.excerpt && <blockquote>{selectedNode.excerpt}</blockquote>}{selectedNode.source_url && <a className="source-link" href={selectedNode.source_url} target="_blank" rel="noreferrer">Open source ↗</a>}<p className="muted small-text">{Object.entries(selectedNode.metadata).filter(([, v]) => v !== null && v !== undefined).map(([k, v]) => pretty(k) + ": " + String(v)).join(" · ")}</p>{edges.filter(e => e.source === selectedNode.id || e.target === selectedNode.id).map((e, i) => <p key={i}><span className={"relation-tag relation-" + e.type}>{pretty(e.type)}</span> {e.rationale}</p>)}</article>}</>}</div>}
    </section>}
    <section className="principles" aria-label="ResearchPilot principles"><article><span className="principle-number">01</span><h2>Traceable evidence</h2><p>Claims should lead back to sources and supporting excerpts.</p></article><article><span className="principle-number">02</span><h2>Compare, don’t flatten</h2><p>Different methods or populations may explain different results.</p></article><article><span className="principle-number">03</span><h2>Honest uncertainty</h2><p>A limited search is not proof that a topic is unexplored.</p></article></section>
    <footer className="footer"><span>ResearchPilot AI</span><span>Early-stage literature exploration · Evidence over assumptions</span></footer>
  </main>;
}
