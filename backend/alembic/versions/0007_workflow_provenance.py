"""Enforce cross-entity workflow/review/publication provenance.

Revision ID: 0007_workflow_provenance
Revises: 0006_graph_checkpoints
"""

import re

from alembic import op

revision = "0007_workflow_provenance"
down_revision = "0006_graph_checkpoints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    statements = """
    CREATE FUNCTION guard_workflow_provenance() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'UPDATE' AND
        (NEW.id, NEW.document_version_id, NEW.requested_by, NEW.request_key,
         NEW.request_fingerprint, NEW.graph_version, NEW.created_at) IS DISTINCT FROM
        (OLD.id, OLD.document_version_id, OLD.requested_by, OLD.request_key,
         OLD.request_fingerprint, OLD.graph_version, OLD.created_at) THEN
        RAISE EXCEPTION 'Workflow identity and provenance are immutable';
      END IF;
      IF NEW.extraction_job_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM document_processing_jobs j WHERE j.id=NEW.extraction_job_id
          AND j.document_version_id=NEW.document_version_id) THEN
        RAISE EXCEPTION 'Extraction must belong to workflow document';
      END IF;
      IF TG_OP='UPDATE' AND OLD.published_rule_set_id IS NOT NULL AND
         NEW.published_rule_set_id IS DISTINCT FROM OLD.published_rule_set_id THEN
        RAISE EXCEPTION 'Published workflow rule binding is immutable';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER workflow_provenance BEFORE INSERT OR UPDATE ON agent_workflows
      FOR EACH ROW EXECUTE FUNCTION guard_workflow_provenance();
    CREATE FUNCTION guard_review_decision() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM review_revisions r JOIN policy_reviews p ON p.id=r.review_id
        JOIN users u ON u.id=NEW.reviewer_id
        WHERE r.id=NEW.revision_id AND r.review_id=NEW.review_id
          AND r.revision_number=p.revision_number AND u.role='admin' AND u.is_active) THEN
        RAISE EXCEPTION 'Decision requires current matching revision and active administrator';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER review_decision_provenance BEFORE INSERT ON review_decisions
      FOR EACH ROW EXECUTE FUNCTION guard_review_decision();
    CREATE FUNCTION guard_rule_publication() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM review_decisions d JOIN policy_reviews p ON p.id=d.review_id
        JOIN agent_workflows w ON w.id=p.workflow_id
        JOIN rule_sets r ON r.id=NEW.rule_set_id
        JOIN document_versions v ON v.id=w.document_version_id
        JOIN scheme_sources s ON s.id=v.source_id
        WHERE d.id=NEW.decision_id AND d.action='APPROVE' AND p.status='APPROVED'
          AND w.id=NEW.workflow_id AND r.approval_status='APPROVED'
          AND r.source_document_version_id=w.document_version_id AND r.scheme_id=s.scheme_id
          AND r.approved_by=d.reviewer_id::text AND r.approval_basis='human_review') THEN
        RAISE EXCEPTION 'Publication requires matching approved policy, document and human decision';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER rule_publication_provenance BEFORE INSERT ON rule_publications
      FOR EACH ROW EXECUTE FUNCTION guard_rule_publication();
    """
    for statement in re.split(r";\s+(?=CREATE)", statements):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    for table, trigger, function in (
        ("rule_publications", "rule_publication_provenance", "guard_rule_publication"),
        ("review_decisions", "review_decision_provenance", "guard_review_decision"),
        ("agent_workflows", "workflow_provenance", "guard_workflow_provenance"),
    ):
        op.execute(f"DROP TRIGGER {trigger} ON {table}")
        op.execute(f"DROP FUNCTION {function}()")
