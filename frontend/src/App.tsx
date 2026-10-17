import { useState, type FormEvent } from "react";

const exampleQuestions = [
  "Can satellite imagery help detect river pollution?",
  "What limits the reliability of AI-generated medical summaries?",
  "How are low-cost sensors used to monitor urban air quality?",
];

export default function App() {
  const [question, setQuestion] = useState("");
  const [notice, setNotice] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim()) {
      setNotice("Enter a research question to continue.");
      return;
    }
    setNotice(
      "The interface is ready. Research processing will be connected in the next implementation step.",
    );
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
            }}
            maxLength={1000}
            placeholder="Enter a focused scientific or technical research question…"
            rows={4}
          />
          <div className="form-footer">
            <span className="character-count">{question.length}/1000</span>
            <button type="submit">Start research <span aria-hidden="true">→</span></button>
          </div>
          {notice && <p className="notice" role="status">{notice}</p>}
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
