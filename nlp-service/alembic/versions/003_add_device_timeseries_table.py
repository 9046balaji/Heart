"""Add device_timeseries table

Revision ID: 003_add_device_timeseries_table
Revises: 002_add_missing_tables
Create Date: 2025-12-25 16:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers
revision = '003_add_device_timeseries_table'
down_revision = '002_add_missing_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create device_timeseries table
    op.create_table(
        'device_timeseries',
        sa.Column('id', sa.Integer, autoincrement=True, primary_key=True),
        sa.Column('device_id', sa.String(255), nullable=False),
        sa.Column('metric_type', sa.String(50), nullable=False),  # 'hr', 'ppg', 'steps', 'spo2'
        sa.Column('value', sa.Float, nullable=False),
        sa.Column('ts', sa.DateTime, nullable=False),  # timestamp
        sa.Column('idempotency_key', sa.String(255), nullable=True),  # for duplicate prevention
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP')),
        mysql_charset='utf8mb4'
    )
    
    # Create indexes for performance
    op.create_index('idx_device_timeseries_device', 'device_timeseries', ['device_id'])
    op.create_index('idx_device_timeseries_metric', 'device_timeseries', ['metric_type'])
    op.create_index('idx_device_timeseries_ts', 'device_timeseries', ['ts'])
    op.create_index('idx_device_timeseries_device_metric', 'device_timeseries', ['device_id', 'metric_type'])
    op.create_index('idx_device_timeseries_device_ts', 'device_timeseries', ['device_id', 'ts'])
    op.create_index('idx_device_timeseries_device_metric_ts', 'device_timeseries', ['device_id', 'metric_type', 'ts'])


def downgrade() -> None:
    op.drop_index('idx_device_timeseries_device_metric_ts', table_name='device_timeseries')
    op.drop_index('idx_device_timeseries_device_ts', table_name='device_timeseries')
    op.drop_index('idx_device_timeseries_device_metric', table_name='device_timeseries')
    op.drop_index('idx_device_timeseries_ts', table_name='device_timeseries')
    op.drop_index('idx_device_timeseries_metric', table_name='device_timeseries')
    op.drop_index('idx_device_timeseries_device', table_name='device_timeseries')
    op.drop_table('device_timeseries')