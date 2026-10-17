import { useState, type FormEvent } from "react";

const exampleQuestions = [
  "Can satellite imagery help detect river pollution?",
  "What limits the reliability of AI-generated medical summaries?",
  "How are low-cost sensors used to monitor urban air quality?",
];

export default function App() {
  const [question, setQuestion] = useState("");
  const [notice, setNotice] = useState("");
  const [runId, setRunId] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim()) {
      setNotice("Enter a research question to continue.");
      return;
    }
    setIsSubmitting(true);
    setNotice("");
    setRunId("");
    try {
      const response = await fetch("/api/research-runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question.trim() }),
      });
      if (!response.ok) {
        setNotice(response.status === 422
          ? "Please enter a valid question of up to 1,000 characters."
          : "Could not save the request. Check that the API is running.");
        return;
      }
      const result = (await response.json()) as { run_id: string; status: string };
      setRunId(result.run_id);
      setNotice("Request saved as queued. Research processing is not connected yet.");
    } catch {
      setNotice("Could not reach the API. Start the backend and try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="page-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="ResearchPilot home">
          <span className="brand-mark">R</span>
          <span>ResearchPilot<span className="brand-ai"> AI</span></span>
        </a>
        <span className="status-pill"><span className="status-dot" /> Research workspace</span>
      </header>
      <section className="hero">
        <p className="eyebrow">EVIDENCE-FIRST RESEARCH</p>
        <h1>Go from a question<br />to a clearer research direction.</h1>
        <p className="hero-copy">Explore sources, compare reported findings, and identify candidate research gaps with evidence you can inspect.</p>
        <form className="question-card" onSubmit={handleSubmit}>
          <label htmlFor="research-question">What are you investigating?</label>
          <textarea
            id="research-question"
            value={question}
            onChange={(event) => { setQuestion(event.target.value); setNotice(""); setRunId(""); }}
            maxLength={1000}
            placeholder="Enter a focused scientific or technical research question…"
            rows={4}
            disabled={isSubmitting}
          />
          <div className="form-footer">
            <span className="character-count">{question.length}/1000</span>
            <button type="submit" disabled={isSubmitting}>{isSubmitting ? "Saving…" : "Start research"} <span aria-hidden="true">→</span></button>
          </div>
          {notice && <p className="notice" role="status">{notice}</p>}
          {runId && <p className="notice">Run ID: <code>{runId}</code></p>}
        </form>
        <div className="examples">
          <p>NEED A STARTING POINT?</p>
          <div className="example-list">
            {exampleQuestions.map((example) => (
              <button className="example-chip" key={example} type="button" onClick={() => { setQuestion(example); setNotice(""); setRunId(""); }}>
                {example}<span aria-hidden="true">↗</span>
              </button>
            ))}
          </div>
        </div>
      </section>
      <section className="principles" aria-label="ResearchPilot principles">
        <article><span className="principle-number">01</span><h2>Traceable evidence</h2><p>Claims should lead back to sources and supporting excerpts.</p></article>
        <article><span className="principle-number">02</span><h2>Compare, don’t flatten</h2><p>Different methods or populations may explain different results.</p></article>
        <article><span className="principle-number">03</span><h2>Honest uncertainty</h2><p>A limited search is not proof that a topic is unexplored.</p></article>
      </section>
      <footer className="footer"><span>ResearchPilot AI</span><span>Early-stage literature exploration · Evidence over assumptions</span></footer>
    </main>
  );
}
