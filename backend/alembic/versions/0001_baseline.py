"""Establish the versioned baseline schema and adopt legacy MVP databases."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    tables = _tables()

    if "research_runs" not in tables:
        op.create_table(
            "research_runs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("owner_id", sa.String(36), nullable=True),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("year_min", sa.Integer(), nullable=True),
            sa.Column("year_max", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("stage", sa.String(80), nullable=False),
            sa.Column("progress", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("error_code", sa.String(80), nullable=True),
            sa.Column("warning_summary", sa.Text(), nullable=True),
            sa.CheckConstraint("progress >= 0 AND progress <= 100", name="ck_run_progress"),
        )
        tables.add("research_runs")
    elif "owner_id" not in _columns("research_runs"):
        op.add_column("research_runs", sa.Column("owner_id", sa.String(36), nullable=True))

    if "sources" not in tables:
        op.create_table(
            "sources",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("run_id", sa.String(36), sa.ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("canonical_url", sa.Text(), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("publisher", sa.String(300), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("retrieval_status", sa.String(30), nullable=False),
            sa.Column("content_hash", sa.String(128), nullable=True),
            sa.Column("publication_year", sa.Integer(), nullable=True),
            sa.Column("authors", sa.JSON(), nullable=False),
            sa.Column("venue", sa.String(500), nullable=True),
            sa.Column("citation_count", sa.Integer(), nullable=True),
            sa.Column("excerpt", sa.Text(), nullable=True),
            sa.Column("content_text", sa.Text(), nullable=True),
            sa.Column("failure_code", sa.String(80), nullable=True),
            sa.Column("query_provenance", sa.JSON(), nullable=False),
            sa.UniqueConstraint("run_id", "canonical_url", name="uq_source_run_url"),
        )
        tables.add("sources")
    elif "content_text" not in _columns("sources"):
        op.add_column("sources", sa.Column("content_text", sa.Text(), nullable=True))

    if "claims" not in tables:
        op.create_table(
            "claims",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("run_id", sa.String(36), sa.ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_id", sa.String(36), sa.ForeignKey("sources.id", ondelete="SET NULL"), nullable=True),
            sa.Column("claim_text", sa.Text(), nullable=False),
            sa.Column("claim_type", sa.String(40), nullable=False),
            sa.Column("evidence_excerpt", sa.Text(), nullable=True),
            sa.Column("confidence_label", sa.String(20), nullable=False),
            sa.Column("is_inference", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        tables.add("claims")

    if "reports" not in tables:
        op.create_table(
            "reports",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("run_id", sa.String(36), sa.ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("structured_sections", sa.JSON(), nullable=False),
            sa.Column("validation_warnings", sa.JSON(), nullable=False),
            sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("run_id", name="uq_report_run_id"),
        )
        tables.add("reports")

    if "evidence_links" not in tables:
        op.create_table(
            "evidence_links",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("claim_id", sa.String(36), sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_id", sa.String(36), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
            sa.Column("relationship", sa.String(20), nullable=False),
            sa.Column("excerpt", sa.Text(), nullable=False),
            sa.Column("rationale", sa.Text(), nullable=False),
            sa.Column("confidence_label", sa.String(20), nullable=False),
            sa.CheckConstraint("relationship IN ('supports', 'contradicts', 'qualifies')", name="ck_evidence_relationship"),
        )
        tables.add("evidence_links")

    if "claim_relations" not in tables:
        op.create_table(
            "claim_relations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("from_claim_id", sa.String(36), sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
            sa.Column("to_claim_id", sa.String(36), sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
            sa.Column("relationship", sa.String(20), nullable=False),
            sa.Column("rationale", sa.Text(), nullable=False),
            sa.Column("confidence_label", sa.String(20), nullable=False),
            sa.CheckConstraint("relationship IN ('supports', 'contradicts', 'qualifies', 'derived_from')", name="ck_claim_relation_type"),
        )
        tables.add("claim_relations")

    # Old test/demo databases may have deliberately incomplete tables. Only add
    # an index when its indexed columns are present; a real legacy MVP schema
    # contains all model columns except the two compatibility columns above.
    index_specs = {
        "research_runs": [("ix_run_status_created", ["status", "created_at"])],
        "sources": [("ix_source_run_status", ["run_id", "retrieval_status"])],
        "claims": [("ix_claim_run_type", ["run_id", "claim_type"])],
        "evidence_links": [("ix_evidence_claim", ["claim_id"])],
        "claim_relations": [("ix_relation_from", ["from_claim_id"]), ("ix_relation_to", ["to_claim_id"])],
    }
    for table, specs in index_specs.items():
        existing = _indexes(table)
        columns = _columns(table)
        for index_name, indexed_columns in specs:
            if index_name not in existing and all(col in columns for col in indexed_columns):
                op.create_index(index_name, table, indexed_columns)


def downgrade() -> None:
    raise RuntimeError(
        "The baseline may adopt an existing database. Do not automatically drop research data; "
        "restore a backup to roll back this initial migration."
    )
