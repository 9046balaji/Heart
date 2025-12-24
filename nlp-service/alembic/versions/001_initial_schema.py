"""initial_schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2025-12-24 00:16:27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer, autoincrement=True, primary_key=True),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255)),
        sa.Column('email', sa.String(255)),
        sa.Column('date_of_birth', sa.DateTime),
        sa.Column('gender', sa.String(20)),
        sa.Column('blood_type', sa.String(5)),
        sa.Column('weight_kg', sa.Float),
        sa.Column('height_cm', sa.Float),
        sa.Column('known_conditions', sa.JSON),
        sa.Column('medications', sa.JSON),
        sa.Column('allergies', sa.JSON),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('user_id', name='uq_user_id'),
        mysql_charset='utf8mb4'
    )
    
    # Create devices table
    op.create_table(
        'devices',
        sa.Column('id', sa.Integer, autoincrement=True, primary_key=True),
        sa.Column('device_id', sa.String(255), nullable=False),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('device_type', sa.String(50)),
        sa.Column('model', sa.String(100)),
        sa.Column('last_sync', sa.TIMESTAMP),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.UniqueConstraint('device_id', name='uq_device_id'),
        mysql_charset='utf8mb4'
    )
    
    # Create patient_records table
    op.create_table(
        'patient_records',
        sa.Column('id', sa.Integer, autoincrement=True, primary_key=True),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('record_type', sa.String(100)),
        sa.Column('data', sa.JSON),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP')),
        mysql_charset='utf8mb4'
    )
    
    # Create vitals table
    op.create_table(
        'vitals',
        sa.Column('id', sa.Integer, autoincrement=True, primary_key=True),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('device_id', sa.String(255)),
        sa.Column('metric_type', sa.String(50)),
        sa.Column('value', sa.Float),
        sa.Column('unit', sa.String(20)),
        sa.Column('recorded_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP')),
        mysql_charset='utf8mb4'
    )
    
    # Create health_alerts table
    op.create_table(
        'health_alerts',
        sa.Column('id', sa.Integer, autoincrement=True, primary_key=True),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('alert_type', sa.String(50)),
        sa.Column('severity', sa.String(20)),
        sa.Column('message', sa.Text),
        sa.Column('is_resolved', sa.Boolean, default=False),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('resolved_at', sa.TIMESTAMP, nullable=True),
        mysql_charset='utf8mb4'
    )
    
    # Create medical_knowledge_base table
    op.create_table(
        'medical_knowledge_base',
        sa.Column('id', sa.Integer, autoincrement=True, primary_key=True),
        sa.Column('content', sa.Text),
        sa.Column('content_type', sa.String(100)),
        sa.Column('embedding', sa.Text),  # Using TEXT instead of BLOB for compatibility
        sa.Column('metadata_json', sa.JSON),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP')),
        mysql_charset='utf8mb4'
    )
    
    # Create chat_sessions table
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Integer, autoincrement=True, primary_key=True),
        sa.Column('session_id', sa.String(255), nullable=False),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('started_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('ended_at', sa.TIMESTAMP, nullable=True),
        sa.UniqueConstraint('session_id', name='uq_session_id'),
        mysql_charset='utf8mb4'
    )
    
    # Create chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer, autoincrement=True, primary_key=True),
        sa.Column('session_id', sa.String(255), nullable=False),
        sa.Column('message_type', sa.String(20)),  # 'user' or 'assistant'
        sa.Column('content', sa.Text),
        sa.Column('metadata_json', sa.JSON),
        sa.Column('timestamp', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP')),
        mysql_charset='utf8mb4'
    )
    
    # Create notification_failures table
    op.create_table(
        'notification_failures',
        sa.Column('id', sa.Integer, autoincrement=True, primary_key=True),
        # Notification details
        sa.Column('notification_type', sa.String(50), nullable=False),  # 'email', 'push', 'sms'
        sa.Column('recipient', sa.String(255), nullable=False),         # Email or phone number
        sa.Column('subject', sa.String(500)),
        sa.Column('content', sa.Text),
        
        # Failure tracking
        sa.Column('original_attempt_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('retry_count', sa.Integer, default=0),
        sa.Column('max_retries', sa.Integer, default=5),
        sa.Column('next_retry_at', sa.TIMESTAMP),
        
        # Error details
        sa.Column('last_error', sa.Text),
        sa.Column('status', sa.String(20), default='pending'),  # 'pending', 'retrying', 'failed', 'succeeded'
        
        # Metadata
        sa.Column('user_id', sa.String(255)),
        sa.Column('metadata_json', sa.JSON),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')),
        mysql_charset='utf8mb4'
    )
    
    # Create indexes
    op.create_index('idx_user_id', 'users', ['user_id'])
    op.create_index('idx_device_user', 'devices', ['user_id'])
    op.create_index('idx_patient_user', 'patient_records', ['user_id'])
    op.create_index('idx_patient_created', 'patient_records', ['user_id', 'created_at'])
    op.create_index('idx_vitals_user', 'vitals', ['user_id'])
    op.create_index('idx_vitals_recorded', 'vitals', ['user_id', 'recorded_at'])
    op.create_index('idx_vitals_metric', 'vitals', ['metric_type'])
    op.create_index('idx_alerts_user', 'health_alerts', ['user_id'])
    op.create_index('idx_knowledge_type', 'medical_knowledge_base', ['content_type'])
    op.create_index('idx_session_user', 'chat_sessions', ['user_id'])
    op.create_index('idx_message_session', 'chat_messages', ['session_id'])
    op.create_index('idx_status_next_retry', 'notification_failures', ['status', 'next_retry_at'])
    op.create_index('idx_nf_user_id', 'notification_failures', ['user_id'])
    op.create_index('idx_nf_created_at', 'notification_failures', ['created_at'])


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('idx_nf_created_at', table_name='notification_failures')
    op.drop_index('idx_nf_user_id', table_name='notification_failures')
    op.drop_index('idx_status_next_retry', table_name='notification_failures')
    op.drop_index('idx_message_session', table_name='chat_messages')
    op.drop_index('idx_session_user', table_name='chat_sessions')
    op.drop_index('idx_knowledge_type', table_name='medical_knowledge_base')
    op.drop_index('idx_alerts_user', table_name='health_alerts')
    op.drop_index('idx_vitals_metric', table_name='vitals')
    op.drop_index('idx_vitals_recorded', table_name='vitals')
    op.drop_index('idx_vitals_user', table_name='vitals')
    op.drop_index('idx_patient_created', table_name='patient_records')
    op.drop_index('idx_patient_user', table_name='patient_records')
    op.drop_index('idx_device_user', table_name='devices')
    op.drop_index('idx_user_id', table_name='users')
    
    # Drop tables in reverse order

    op.drop_table('chat_messages')
    op.drop_table('chat_sessions')
    op.drop_table('medical_knowledge_base')
    op.drop_table('health_alerts')
    op.drop_table('vitals')
    op.drop_table('patient_records')
    op.drop_table('devices')
    op.drop_table('users')