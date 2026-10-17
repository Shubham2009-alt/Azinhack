from sqlalchemy import delete, select

from app.database import SessionLocal
from app.models import Claim, ResearchRun, Source
from app.services.llm_analysis import (
    AnalysisConfigurationError,
    AnalysisProviderError,
    extract_source_claims,
)


def run_research_analysis(run_id: str) -> None:
    """Extract claims from retrieved pages and persist only source-validated evidence."""
    with SessionLocal() as db:
        run = db.get(ResearchRun, run_id)
        if run is None:
            return
        sources = list(
            db.scalars(
                select(Source).where(
                    Source.run_id == run_id,
                    Source.retrieval_status == "retrieved",
                    Source.content_text.is_not(None),
                )
            )
        )
        if not sources:
            run.status = "partial"
            run.stage = "analysis_skipped"
            run.progress = max(run.progress, 60)
            run.warning_summary = "No full-text sources were available for evidence extraction."
            db.commit()
            return

        run.status = "analyzing"
        run.stage = "claim_extraction"
        run.progress = 65
        db.commit()

        # A retry replaces this run's previous extraction rather than duplicating claims.
        db.execute(delete(Claim).where(Claim.run_id == run_id))
        db.commit()

        extracted_count = 0
        warnings: list[str] = []
        for source in sources:
            try:
                claims = extract_source_claims(
                    question=run.question,
                    source_id=source.id,
                    title=source.title,
                    url=source.canonical_url,
                    content=source.content_text or "",
                )
            except AnalysisConfigurationError:
                warnings.append("LLM analysis is not configured; source retrieval completed without claim extraction.")
                break
            except AnalysisProviderError:
                warnings.append(f"Claim extraction failed for one source: {source.title[:160]}.")
                continue

            for item in claims:
                # Defence in depth: excerpts must remain verbatim in the stored source text.
                if item.evidence_excerpt not in (source.content_text or ""):
                    continue
                db.add(
                    Claim(
                        run_id=run.id,
                        source_id=source.id,
                        claim_text=item.claim_text,
                        claim_type=item.claim_type,
                        evidence_excerpt=item.evidence_excerpt,
                        confidence_label=item.confidence_label,
                        is_inference=False,
                    )
                )
                extracted_count += 1
            db.commit()

        run.progress = 85
        run.stage = "claim_extraction_complete"
        if extracted_count and not warnings:
            run.status = "partial"
            run.warning_summary = (
                "Source-grounded claims were extracted. Cross-source comparison, candidate-gap analysis, "
                "final report generation and graph API are not implemented yet."
            )
        elif extracted_count:
            run.status = "partial"
            run.warning_summary = " ".join(warnings) + (
                f" Validated claims saved: {extracted_count}. "
                "Comparison, gap analysis and report generation remain pending."
            )
        else:
            run.status = "partial"
            run.warning_summary = " ".join(warnings) if warnings else (
                "No claims passed evidence validation. This is not evidence that no relevant findings exist."
            )
        db.commit()
