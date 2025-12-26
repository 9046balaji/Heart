"""Add missing tables

Revision ID: 002_add_missing_tables
Revises: 001_initial_schema
Create Date: 2025-12-24 12:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers
revision = '002_add_missing_tables'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create notification_failures table
    op.create_table(
        'notification_failures',
        sa.Column('id', sa.Integer, autoincrement=True, primary_key=True),
        sa.Column('notification_type', sa.String(50), nullable=False),
        sa.Column('recipient', sa.String(255), nullable=False),
        sa.Column('subject', sa.String(500)),
        sa.Column('content', sa.Text),
        sa.Column('original_attempt_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('retry_count', sa.Integer, default=0),
        sa.Column('max_retries', sa.Integer, default=5),
        sa.Column('next_retry_at', sa.TIMESTAMP),
        sa.Column('last_error', sa.Text),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('user_id', sa.String(255)),
        sa.Column('metadata_json', sa.JSON),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP')),
        mysql_charset='utf8mb4'
    )
    
    op.create_index('idx_status_next_retry', 'notification_failures', ['status', 'next_retry_at'])
    op.create_index('idx_nf_user_id', 'notification_failures', ['user_id'])
    op.create_index('idx_nf_created_at', 'notification_failures', ['created_at'])

    # Create rag_feedback table
    op.create_table(
        'rag_feedback',
        sa.Column('feedback_id', sa.String(255), primary_key=True),
        sa.Column('query', sa.Text),
        sa.Column('response_preview', sa.Text),
        sa.Column('rating', sa.Integer),
        sa.Column('user_id', sa.String(255)),
        sa.Column('timestamp', sa.String(255)),
        sa.Column('citations_count', sa.Integer),
        sa.Column('context_sources', sa.JSON),
        sa.Column('user_comment', sa.Text),
        mysql_charset='utf8mb4'
    )

    op.create_index('idx_feedback_rating_ts', 'rag_feedback', ['rating', 'timestamp'])
    op.create_index('idx_feedback_user', 'rag_feedback', ['user_id'])


def downgrade() -> None:
    op.drop_table('rag_feedback')
    op.drop_table('notification_failures')
