import { useState, type FormEvent } from "react";

const exampleQuestions = [
  "Can satellite imagery help detect river pollution?",
  "What limits the reliability of AI-generated medical summaries?",
  "How are low-cost sensors used to monitor urban air quality?",
];

type CreatedRun = { run_id: string; status: string };

export default function App() {
  const [question, setQuestion] = useState("");
  const [notice, setNotice] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [createdRun, setCreatedRun] = useState<CreatedRun | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) {
      setNotice("Enter a research question to continue.");
      return;
    }

    setIsSubmitting(true);
    setNotice("");
    setCreatedRun(null);
    try {
      const response = await fetch("/api/research-runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: trimmedQuestion }),
      });
      if (!response.ok) {
        if (response.status === 422) {
          setNotice("Please enter a non-empty question of up to 1,000 characters.");
        } else {
          setNotice("Could not create a research run. Check that the API is running and try again.");
        }
        return;
      }
      const run = (await response.json()) as CreatedRun;
      setCreatedRun(run);
      setNotice("Your request has been saved. Research processing is not connected yet.");
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
        <p className="hero-copy">
          Explore sources, compare reported findings, and identify candidate research gaps
          with evidence you can inspect.
        </p>

        <form className="question-card" onSubmit={handleSubmit}>
          <label htmlFor="research-question">What are you investigating?</label>
          <textarea
            id="research-question"
            value={question}
            onChange={(event) => {
              setQuestion(event.target.value);
              setNotice("");
              setCreatedRun(null);
            }}
            maxLength={1000}
            placeholder="Enter a focused scientific or technical research question…"
            rows={4}
            disabled={isSubmitting}
          />
          <div className="form-footer">
            <span className="character-count">{question.length}/1000</span>
            <button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Saving…" : "Start research"} <span aria-hidden="true">→</span>
            </button>
          </div>
          {notice && <p className="notice" role="status">{notice}</p>}
          {createdRun && (
            <div className="run-result" role="status">
              <strong>Request saved · {createdRun.status}</strong>
              <span>Run ID: <code>{createdRun.run_id}</code></span>
            </div>
          )}
        </form>

        <div className="examples">
          <p>NEED A STARTING POINT?</p>
          <div className="example-list">
            {exampleQuestions.map((example) => (
              <button
                className="example-chip"
                key={example}
                type="button"
                onClick={() => {
                  setQuestion(example);
                  setNotice("");
                  setCreatedRun(null);
                }}
              >
                {example}<span aria-hidden="true">↗</span>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="principles" aria-label="ResearchPilot principles">
        <article>
          <span className="principle-number">01</span>
          <h2>Traceable evidence</h2>
          <p>Claims should lead back to sources and supporting excerpts.</p>
        </article>
        <article>
          <span className="principle-number">02</span>
          <h2>Compare, don’t flatten</h2>
          <p>Different methods or populations may explain different results.</p>
        </article>
        <article>
          <span className="principle-number">03</span>
          <h2>Honest uncertainty</h2>
          <p>A limited search is not proof that a topic is unexplored.</p>
        </article>
      </section>

      <footer className="footer">
        <span>ResearchPilot AI</span>
        <span>Early-stage literature exploration · Evidence over assumptions</span>
      </footer>
    </main>
  );
}
