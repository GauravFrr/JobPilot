"""initial migration

Revision ID: 0001
Revises: 
Create Date: 2026-08-12

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 0. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 1. jobs_raw
    op.create_table(
        'jobs_raw',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source', sa.Text(), nullable=False),
        sa.Column('source_tier', sa.CHAR(1), nullable=False),
        sa.Column('source_job_id', sa.Text(), nullable=True),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('company', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description_text', sa.Text(), nullable=False),
        sa.Column('location', sa.Text(), nullable=True),
        sa.Column('is_remote', sa.Boolean(), nullable=True),
        sa.Column('posted_date', sa.Date(), nullable=True),
        sa.Column('discovered_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('raw_payload', postgresql.JSONB(), nullable=True),
        sa.Column('status', sa.Text(), server_default='discovered', nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'source_job_id', name='uq_source_source_job_id')
    )

    # 2. resume_profile
    op.create_table(
        'resume_profile',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('content_json', postgresql.JSONB(), nullable=False),
        sa.Column('embedding', Vector(768), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # 3. job_scores
    op.create_table(
        'job_scores',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('resume_profile_version', sa.Integer(), nullable=False),
        sa.Column('embedding_score', sa.Float(), nullable=True),
        sa.Column('llm_rerank_score', sa.Float(), nullable=True),
        sa.Column('final_score', sa.Float(), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('scored_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['jobs_raw.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 4. resume_versions
    op.create_table(
        'resume_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content_json', postgresql.JSONB(), nullable=False),
        sa.Column('pdf_path', sa.Text(), nullable=False),
        sa.Column('model_used', sa.Text(), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['jobs_raw.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 5. applications
    op.create_table(
        'applications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('resume_version_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('tier', sa.CHAR(1), nullable=False),
        sa.Column('method', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('request_payload_snapshot', postgresql.JSONB(), nullable=True),
        sa.Column('result', postgresql.JSONB(), nullable=True),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['jobs_raw.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resume_version_id'], ['resume_versions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # 6. contacts
    op.create_table(
        'contacts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('company', sa.Text(), nullable=True),
        sa.Column('linkedin_url', sa.Text(), nullable=True),
        sa.Column('email', sa.Text(), nullable=True),
        sa.Column('email_confidence', sa.Text(), nullable=True),
        sa.Column('website', sa.Text(), nullable=True),
        sa.Column('social_profiles', postgresql.JSONB(), nullable=True),
        sa.Column('evidence', postgresql.JSONB(), nullable=True),
        sa.Column('found_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['jobs_raw.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 7. outreach_drafts
    op.create_table(
        'outreach_drafts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('contact_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('channel', sa.Text(), nullable=False),
        sa.Column('draft_text', sa.Text(), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('sent', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs_raw.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 8. target_companies
    op.create_table(
        'target_companies',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('domain', sa.Text(), nullable=True),
        sa.Column('careers_url', sa.Text(), nullable=True),
        sa.Column('detected_ats', sa.Text(), nullable=True),
        sa.Column('last_crawled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # 9. dork_queries
    op.create_table(
        'dork_queries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('query_template', sa.Text(), nullable=False),
        sa.Column('target_group', sa.Text(), nullable=True),
        sa.Column('role_keyword_source', sa.Text(), server_default='resume_profile.target_roles', nullable=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # 10. settings
    op.create_table(
        'settings',
        sa.Column('key', sa.Text(), nullable=False),
        sa.Column('value', postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint('key')
    )

    # 11. source_health
    op.create_table(
        'source_health',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source', sa.Text(), nullable=False),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), server_default='0', nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Indices for performance (as described in doc 11/17)
    op.create_index('ix_jobs_raw_status', 'jobs_raw', ['status'])
    op.create_index('ix_jobs_raw_source_tier', 'jobs_raw', ['source_tier'])
    op.create_index('ix_jobs_raw_discovered_at', 'jobs_raw', ['discovered_at'])
    op.create_index('ix_applications_status', 'applications', ['status'])


def downgrade() -> None:
    op.drop_table('source_health')
    op.drop_table('settings')
    op.drop_table('dork_queries')
    op.drop_table('target_companies')
    op.drop_table('outreach_drafts')
    op.drop_table('contacts')
    op.drop_table('applications')
    op.drop_table('resume_versions')
    op.drop_table('job_scores')
    op.drop_table('resume_profile')
    op.drop_table('jobs_raw')
    op.execute("DROP EXTENSION IF EXISTS vector;")
