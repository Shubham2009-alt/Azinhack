from sqlalchemy import delete, func, select

from app.database import SessionLocal
from app.models import Claim, ClaimRelation, Report, ResearchRun, Source
from app.services.comparison_gap_analysis import (
    compare_claims_and_identify_gaps,
)
from app.services.llm_analysis import (
    AnalysisConfigurationError,
    AnalysisProviderError,
    extract_source_claims,
    verify_source_claims,
)


def run_research_analysis(run_id: str) -> None:
    """Extract source-grounded claims, then compare claims across sources."""
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
        unretrieved_source_count = db.scalar(
            select(func.count(Source.id)).where(
                Source.run_id == run_id,
                Source.retrieval_status != "retrieved",
            )
        ) or 0
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

        claim_ids = select(Claim.id).where(Claim.run_id == run_id)
        db.execute(
            delete(ClaimRelation).where(
                (ClaimRelation.from_claim_id.in_(claim_ids))
                | (ClaimRelation.to_claim_id.in_(claim_ids))
            )
        )
        db.execute(delete(Claim).where(Claim.run_id == run_id))
        db.commit()

        extracted_count = 0
        rejected_claim_count = 0
        warnings: list[str] = []
        if unretrieved_source_count:
            warnings.append(
                f"{unretrieved_source_count} source(s) could not be retrieved; results may be partial."
            )
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

            try:
                decisions = verify_source_claims(
                    claims=claims,
                    content=source.content_text or "",
                )
            except AnalysisConfigurationError:
                warnings.append("Claim verification is not configured; unverified claims were not saved.")
                continue
            except AnalysisProviderError:
                warnings.append(f"Claim verification failed for one source: {source.title[:160]}.")
                continue

            for index, item in enumerate(claims):
                # Exact excerpt matching and a separate verification verdict are both
                # required. Missing/ambiguous verdicts fail closed.
                if item.evidence_excerpt not in (source.content_text or ""):
                    rejected_claim_count += 1
                    continue
                verdict = decisions.get(index)
                if verdict not in {"supported", "inferred"}:
                    rejected_claim_count += 1
                    continue
                db.add(
                    Claim(
                        run_id=run.id,
                        source_id=source.id,
                        claim_text=item.claim_text,
                        claim_type=item.claim_type,
                        evidence_excerpt=item.evidence_excerpt,
                        confidence_label=item.confidence_label,
                        is_inference=verdict == "inferred",
                    )
                )
                extracted_count += 1
            db.commit()

        persisted_claims = list(
            db.scalars(
                select(Claim).where(Claim.run_id == run_id).order_by(Claim.created_at, Claim.id)
            )
        )
        source_by_id = {source.id: source for source in sources}
        comparison_payload: list[dict[str, str | None]] = []
        for claim in persisted_claims:
            source = source_by_id.get(claim.source_id or "")
            comparison_payload.append(
                {
                    "id": claim.id,
                    "source_id": claim.source_id,
                    "claim_text": claim.claim_text[:2000],
                    "evidence_excerpt": (claim.evidence_excerpt or "")[:1200],
                    "claim_type": claim.claim_type,
                    "confidence_label": claim.confidence_label,
                    "source_title": source.title[:500] if source else None,
                    "source_url": source.canonical_url if source else None,
                }
            )

        comparison_result = None
        if persisted_claims:
            run.stage = "cross_source_comparison"
            run.progress = 88
            db.commit()
            try:
                comparison_result = compare_claims_and_identify_gaps(
                    question=run.question,
                    claims=comparison_payload,
                )
            except AnalysisConfigurationError:
                warnings.append("Cross-source comparison was skipped because LLM configuration is incomplete.")
            except AnalysisProviderError:
                warnings.append("Cross-source comparison could not be validated; extracted claims were retained.")

        relation_count = 0
        candidate_gaps: list[dict[str, object]] = []
        comparison_sections: list[dict[str, object]] = []
        if comparison_result is not None:
            valid_claims = {claim.id: claim for claim in persisted_claims}
            seen_relations: set[tuple[str, str, str]] = set()
            for proposed in comparison_result.relations:
                claim_a = valid_claims.get(proposed.claim_a_id)
                claim_b = valid_claims.get(proposed.claim_b_id)
                if (
                    claim_a is None
                    or claim_b is None
                    or claim_a.id == claim_b.id
                    or claim_a.source_id is None
                    or claim_b.source_id is None
                    or claim_a.source_id == claim_b.source_id
                ):
                    continue
                pair = tuple(sorted((claim_a.id, claim_b.id))) + (proposed.relationship,)
                if pair in seen_relations:
                    continue
                seen_relations.add(pair)
                db.add(
                    ClaimRelation(
                        from_claim_id=claim_a.id,
                        to_claim_id=claim_b.id,
                        relationship=proposed.relationship,
                        rationale=proposed.rationale,
                        confidence_label=proposed.confidence_label,
                    )
                )
                relation_count += 1
                comparison_sections.append(
                    {
                        "claim_a_id": claim_a.id,
                        "claim_b_id": claim_b.id,
                        "relationship": proposed.relationship,
                        "rationale": proposed.rationale,
                        "confidence_label": proposed.confidence_label,
                    }
                )

            for gap in comparison_result.candidate_gaps:
                basis_ids = list(
                    dict.fromkeys(
                        claim_id for claim_id in gap.basis_claim_ids if claim_id in valid_claims
                    )
                )
                if not basis_ids:
                    continue
                candidate_gaps.append(
                    {
                        "title": gap.title,
                        "description": gap.description,
                        "evidence_level": gap.evidence_level,
                        "basis_claim_ids": basis_ids,
                        "rationale": gap.rationale,
                        "is_confirmed_novelty": False,
                    }
                )
            db.commit()

        report = db.scalar(select(Report).where(Report.run_id == run_id))
        if report is None:
            report = Report(run_id=run_id)
            db.add(report)
        report.structured_sections = {
            "analysis_stage": "cross_source_analysis_draft",
            "research_question": run.question,
            "cross_source_comparisons": comparison_sections,
            "candidate_research_gaps": candidate_gaps,
            "limitations": [
                "Candidate gaps are hypotheses for further literature review, not proof of novelty.",
                "Only claims with an exact source excerpt and a separate verifier verdict were retained.",
                "Claims marked as inference require interpretation and are not direct source statements.",
                "Unverified, unsupported, or ambiguous claims are excluded; verifier errors can reduce recall.",
                "Comparison quality depends on source coverage and model output.",
            ],
        }
        report.validation_warnings = list(warnings)
        db.commit()

        run.progress = 92
        run.stage = "cross_source_analysis_complete"
        run.status = "partial" if warnings else "succeeded"
        parts = [
            f"Claims retained after source verification: {extracted_count}.",
            f"Claims rejected or left unverified: {rejected_claim_count}.",
            f"Cross-source relations saved: {relation_count}.",
            f"Candidate research gaps saved: {len(candidate_gaps)}.",
            "These gaps are tentative and do not establish global novelty.",
            "The report and graph APIs expose the available evidence; candidate gaps do not establish global novelty.",
        ]
        if warnings:
            parts.append(" ".join(warnings))
        run.warning_summary = " ".join(parts)
        db.commit()
