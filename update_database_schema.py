"""
Database Schema Update Script
============================
Creates all missing tables required by the HeartGuard/Memori chatbot system.

Run this script to ensure your database has all required tables.

Usage:
    conda run -n rag_memory python update_database_schema.py
"""

import os
import sys
from datetime import datetime

# ============================================================================
# SQL Statements for Missing Tables
# ============================================================================

# Session Archives Table (from workers/session_archiver.py)
SESSION_ARCHIVES_SQL = """
CREATE TABLE IF NOT EXISTS session_archives (
    id SERIAL PRIMARY KEY,
    thread_id VARCHAR(255) NOT NULL UNIQUE,
    user_id VARCHAR(255) NOT NULL,
    workflow_type VARCHAR(100) DEFAULT 'chat',
    
    -- Session metadata
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    
    -- State data (compressed JSON)
    initial_state JSONB,
    final_state JSONB,
    checkpoints JSONB,  -- Array of checkpoint summaries
    
    -- Statistics
    total_steps INTEGER DEFAULT 0,
    total_messages INTEGER DEFAULT 0,
    
    -- Audit fields
    archived_at TIMESTAMPTZ DEFAULT NOW(),
    archived_by VARCHAR(100) DEFAULT 'session_archiver',
    
    -- Indexes for queries
    CONSTRAINT idx_user_completed UNIQUE (user_id, completed_at, thread_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_session_archives_user_id ON session_archives(user_id);
CREATE INDEX IF NOT EXISTS idx_session_archives_completed_at ON session_archives(completed_at);
CREATE INDEX IF NOT EXISTS idx_session_archives_archived_at ON session_archives(archived_at);
CREATE INDEX IF NOT EXISTS idx_session_archives_thread_id ON session_archives(thread_id);
"""

# Documents Table (general document storage)
DOCUMENTS_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(500),
    content TEXT NOT NULL,
    content_type VARCHAR(100) DEFAULT 'text',
    source VARCHAR(255),
    source_url TEXT,
    metadata_json JSONB,
    embedding TEXT,  -- Store as TEXT if pgvector not available
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_documents_doc_id ON documents(doc_id);
CREATE INDEX IF NOT EXISTS idx_documents_content_type ON documents(content_type);
CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source);
CREATE INDEX IF NOT EXISTS idx_documents_created ON documents(created_at);
"""

# Vector Tables for pgvector (requires pgvector extension)
VECTOR_MEDICAL_KNOWLEDGE_SQL = """
-- Vector Medical Knowledge Table
-- Stores medical guidelines, protocols, and reference documents
CREATE TABLE IF NOT EXISTS vector_medical_knowledge (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(255) UNIQUE NOT NULL,
    content TEXT NOT NULL,
    embedding vector(384),  -- all-MiniLM-L6-v2 dimension
    metadata JSONB,
    source VARCHAR(255),
    category VARCHAR(100),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vmk_doc_id ON vector_medical_knowledge(doc_id);
CREATE INDEX IF NOT EXISTS idx_vmk_category ON vector_medical_knowledge(category);
CREATE INDEX IF NOT EXISTS idx_vmk_source ON vector_medical_knowledge(source);

-- HNSW index for fast similarity search (if pgvector supports it)
-- Note: This requires pgvector 0.5.0+
DO $$
BEGIN
    CREATE INDEX IF NOT EXISTS idx_vmk_embedding_hnsw 
    ON vector_medical_knowledge 
    USING hnsw (embedding vector_cosine_ops);
EXCEPTION WHEN OTHERS THEN
    -- Fall back to IVFFlat if HNSW not available
    CREATE INDEX IF NOT EXISTS idx_vmk_embedding_ivfflat 
    ON vector_medical_knowledge 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
END $$;
"""

VECTOR_DRUG_INTERACTIONS_SQL = """
-- Vector Drug Interactions Table
-- Stores medication information for semantic search
CREATE TABLE IF NOT EXISTS vector_drug_interactions (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(255) UNIQUE NOT NULL,
    drug_name VARCHAR(255),
    content TEXT NOT NULL,
    embedding vector(384),
    metadata JSONB,
    source VARCHAR(255),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vdi_doc_id ON vector_drug_interactions(doc_id);
CREATE INDEX IF NOT EXISTS idx_vdi_drug_name ON vector_drug_interactions(drug_name);
CREATE INDEX IF NOT EXISTS idx_vdi_source ON vector_drug_interactions(source);

-- Vector similarity index
DO $$
BEGIN
    CREATE INDEX IF NOT EXISTS idx_vdi_embedding_hnsw 
    ON vector_drug_interactions 
    USING hnsw (embedding vector_cosine_ops);
EXCEPTION WHEN OTHERS THEN
    CREATE INDEX IF NOT EXISTS idx_vdi_embedding_ivfflat 
    ON vector_drug_interactions 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
END $$;
"""

VECTOR_SYMPTOMS_CONDITIONS_SQL = """
-- Vector Symptoms-Conditions Table
-- Stores symptom-to-condition mappings for diagnosis assistance
CREATE TABLE IF NOT EXISTS vector_symptoms_conditions (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(255) UNIQUE NOT NULL,
    symptom VARCHAR(255),
    condition VARCHAR(255),
    content TEXT NOT NULL,
    embedding vector(384),
    metadata JSONB,
    severity VARCHAR(50),
    source VARCHAR(255),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vsc_doc_id ON vector_symptoms_conditions(doc_id);
CREATE INDEX IF NOT EXISTS idx_vsc_symptom ON vector_symptoms_conditions(symptom);
CREATE INDEX IF NOT EXISTS idx_vsc_condition ON vector_symptoms_conditions(condition);
CREATE INDEX IF NOT EXISTS idx_vsc_severity ON vector_symptoms_conditions(severity);

-- Vector similarity index
DO $$
BEGIN
    CREATE INDEX IF NOT EXISTS idx_vsc_embedding_hnsw 
    ON vector_symptoms_conditions 
    USING hnsw (embedding vector_cosine_ops);
EXCEPTION WHEN OTHERS THEN
    CREATE INDEX IF NOT EXISTS idx_vsc_embedding_ivfflat 
    ON vector_symptoms_conditions 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
END $$;
"""

VECTOR_USER_MEMORIES_SQL = """
-- Vector User Memories Table
-- Stores per-user memory embeddings for personalized responses
CREATE TABLE IF NOT EXISTS vector_user_memories (
    id SERIAL PRIMARY KEY,
    memory_id VARCHAR(255) UNIQUE NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    embedding vector(384),
    metadata JSONB,
    memory_type VARCHAR(50) DEFAULT 'general',  -- general, preference, health, conversation
    importance_score FLOAT DEFAULT 0.5,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITHOUT TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_vum_memory_id ON vector_user_memories(memory_id);
CREATE INDEX IF NOT EXISTS idx_vum_user_id ON vector_user_memories(user_id);
CREATE INDEX IF NOT EXISTS idx_vum_user_type ON vector_user_memories(user_id, memory_type);
CREATE INDEX IF NOT EXISTS idx_vum_importance ON vector_user_memories(importance_score);
CREATE INDEX IF NOT EXISTS idx_vum_expires ON vector_user_memories(expires_at);

-- Vector similarity index
DO $$
BEGIN
    CREATE INDEX IF NOT EXISTS idx_vum_embedding_hnsw 
    ON vector_user_memories 
    USING hnsw (embedding vector_cosine_ops);
EXCEPTION WHEN OTHERS THEN
    CREATE INDEX IF NOT EXISTS idx_vum_embedding_ivfflat 
    ON vector_user_memories 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
END $$;
"""

# Memori tables for heartguard database (from memori/database/models.py)
MEMORI_CHAT_HISTORY_SQL = """
-- Chat History Table (Memori v2.0)
CREATE TABLE IF NOT EXISTS memori_chat_history (
    chat_id VARCHAR(255) PRIMARY KEY,
    user_input TEXT NOT NULL,
    ai_output TEXT NOT NULL,
    model VARCHAR(255) NOT NULL,
    session_id VARCHAR(255) NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    metadata_json JSONB,
    user_id VARCHAR(255) NOT NULL DEFAULT 'default',
    assistant_id VARCHAR(255),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_memori_chat_user_id ON memori_chat_history(user_id);
CREATE INDEX IF NOT EXISTS idx_memori_chat_user_assistant ON memori_chat_history(user_id, assistant_id);
CREATE INDEX IF NOT EXISTS idx_memori_chat_created ON memori_chat_history(created_at);
CREATE INDEX IF NOT EXISTS idx_memori_chat_model ON memori_chat_history(model);
CREATE INDEX IF NOT EXISTS idx_memori_chat_session ON memori_chat_history(session_id);
"""

MEMORI_SHORT_TERM_MEMORY_SQL = """
-- Short-Term Memory Table (Memori v2.0)
CREATE TABLE IF NOT EXISTS memori_short_term_memory (
    memory_id VARCHAR(255) PRIMARY KEY,
    chat_id VARCHAR(255) REFERENCES memori_chat_history(chat_id) ON DELETE SET NULL,
    processed_data JSONB NOT NULL,
    importance_score FLOAT NOT NULL DEFAULT 0.5,
    category_primary VARCHAR(255) NOT NULL,
    retention_type VARCHAR(50) NOT NULL DEFAULT 'short_term',
    user_id VARCHAR(255) NOT NULL DEFAULT 'default',
    assistant_id VARCHAR(255),
    session_id VARCHAR(255) NOT NULL DEFAULT 'default',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITHOUT TIME ZONE,
    searchable_content TEXT NOT NULL,
    summary TEXT NOT NULL,
    is_permanent_context BOOLEAN DEFAULT FALSE,
    search_vector tsvector
);

CREATE INDEX IF NOT EXISTS idx_memori_stm_user_id ON memori_short_term_memory(user_id);
CREATE INDEX IF NOT EXISTS idx_memori_stm_user_assistant ON memori_short_term_memory(user_id, assistant_id);
CREATE INDEX IF NOT EXISTS idx_memori_stm_category ON memori_short_term_memory(category_primary);
CREATE INDEX IF NOT EXISTS idx_memori_stm_importance ON memori_short_term_memory(importance_score);
CREATE INDEX IF NOT EXISTS idx_memori_stm_expires ON memori_short_term_memory(expires_at);
CREATE INDEX IF NOT EXISTS idx_memori_stm_created ON memori_short_term_memory(created_at);
CREATE INDEX IF NOT EXISTS idx_memori_stm_permanent ON memori_short_term_memory(is_permanent_context);
CREATE INDEX IF NOT EXISTS idx_memori_stm_search_vector ON memori_short_term_memory USING GIN(search_vector);
"""

MEMORI_LONG_TERM_MEMORY_SQL = """
-- Long-Term Memory Table (Memori v2.0)
CREATE TABLE IF NOT EXISTS memori_long_term_memory (
    memory_id VARCHAR(255) PRIMARY KEY,
    processed_data JSONB NOT NULL,
    importance_score FLOAT NOT NULL DEFAULT 0.5,
    category_primary VARCHAR(255) NOT NULL,
    retention_type VARCHAR(50) NOT NULL DEFAULT 'long_term',
    user_id VARCHAR(255) NOT NULL DEFAULT 'default',
    assistant_id VARCHAR(255),
    session_id VARCHAR(255) NOT NULL DEFAULT 'default',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    searchable_content TEXT NOT NULL,
    summary TEXT NOT NULL,
    novelty_score FLOAT DEFAULT 0.5,
    relevance_score FLOAT DEFAULT 0.5,
    actionability_score FLOAT DEFAULT 0.5,
    
    -- Enhanced Classification Fields
    classification VARCHAR(50) NOT NULL DEFAULT 'conversational',
    memory_importance VARCHAR(20) NOT NULL DEFAULT 'medium',
    topic VARCHAR(255),
    entities_json JSONB,
    keywords_json JSONB,
    
    -- Conscious Context Flags
    is_user_context BOOLEAN DEFAULT FALSE,
    is_preference BOOLEAN DEFAULT FALSE,
    is_skill_knowledge BOOLEAN DEFAULT FALSE,
    is_current_project BOOLEAN DEFAULT FALSE,
    promotion_eligible BOOLEAN DEFAULT FALSE,
    
    -- Memory Management
    duplicate_of VARCHAR(255),
    supersedes_json JSONB,
    related_memories_json JSONB,
    
    -- Technical Metadata
    confidence_score FLOAT DEFAULT 0.8,
    classification_reason TEXT,
    
    -- Processing Status
    processed_for_duplicates BOOLEAN DEFAULT FALSE,
    conscious_processed BOOLEAN DEFAULT FALSE,
    
    -- Concurrency Control
    version INTEGER NOT NULL DEFAULT 1,
    
    -- Full-text search
    search_vector tsvector
);

CREATE INDEX IF NOT EXISTS idx_memori_ltm_user_id ON memori_long_term_memory(user_id);
CREATE INDEX IF NOT EXISTS idx_memori_ltm_user_assistant ON memori_long_term_memory(user_id, assistant_id);
CREATE INDEX IF NOT EXISTS idx_memori_ltm_category ON memori_long_term_memory(category_primary);
CREATE INDEX IF NOT EXISTS idx_memori_ltm_importance ON memori_long_term_memory(importance_score);
CREATE INDEX IF NOT EXISTS idx_memori_ltm_created ON memori_long_term_memory(created_at);
CREATE INDEX IF NOT EXISTS idx_memori_ltm_classification ON memori_long_term_memory(classification);
CREATE INDEX IF NOT EXISTS idx_memori_ltm_memory_importance ON memori_long_term_memory(memory_importance);
CREATE INDEX IF NOT EXISTS idx_memori_ltm_topic ON memori_long_term_memory(topic);
CREATE INDEX IF NOT EXISTS idx_memori_ltm_conscious_flags ON memori_long_term_memory(is_user_context, is_preference, is_skill_knowledge, promotion_eligible);
CREATE INDEX IF NOT EXISTS idx_memori_ltm_conscious_processed ON memori_long_term_memory(conscious_processed);
CREATE INDEX IF NOT EXISTS idx_memori_ltm_duplicates ON memori_long_term_memory(processed_for_duplicates);
CREATE INDEX IF NOT EXISTS idx_memori_ltm_confidence ON memori_long_term_memory(confidence_score);
CREATE INDEX IF NOT EXISTS idx_memori_ltm_search_vector ON memori_long_term_memory USING GIN(search_vector);
"""

# Trigger functions for full-text search
MEMORI_TRIGGERS_SQL = """
-- Update function for short-term memory search vector
CREATE OR REPLACE FUNCTION update_memori_stm_search_vector() RETURNS trigger AS $$
BEGIN
    NEW.search_vector := to_tsvector('english', 
        COALESCE(NEW.searchable_content, '') || ' ' || 
        COALESCE(NEW.summary, '') || ' ' || 
        COALESCE(NEW.category_primary, '')
    );
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

-- Create trigger for short-term memory
DROP TRIGGER IF EXISTS trg_update_memori_stm_search_vector ON memori_short_term_memory;
CREATE TRIGGER trg_update_memori_stm_search_vector
BEFORE INSERT OR UPDATE ON memori_short_term_memory
FOR EACH ROW EXECUTE FUNCTION update_memori_stm_search_vector();

-- Update function for long-term memory search vector  
CREATE OR REPLACE FUNCTION update_memori_ltm_search_vector() RETURNS trigger AS $$
BEGIN
    NEW.search_vector := to_tsvector('english', 
        COALESCE(NEW.searchable_content, '') || ' ' || 
        COALESCE(NEW.summary, '') || ' ' || 
        COALESCE(NEW.topic, '') || ' ' ||
        COALESCE(NEW.category_primary, '')
    );
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

-- Create trigger for long-term memory
DROP TRIGGER IF EXISTS trg_update_memori_ltm_search_vector ON memori_long_term_memory;
CREATE TRIGGER trg_update_memori_ltm_search_vector
BEFORE INSERT OR UPDATE ON memori_long_term_memory
FOR EACH ROW EXECUTE FUNCTION update_memori_ltm_search_vector();
"""


def update_database():
    """Update database with all required tables."""
    from sqlalchemy import create_engine, text
    
    # Database connection
    PG_PASSWORD = os.getenv('PG_PASSWORD', '95889396')
    DATABASE_URL = os.getenv('DATABASE_URL', f"postgresql://postgres:{PG_PASSWORD}@localhost:5432/heartguard")
    
    print("=" * 80)
    print("DATABASE SCHEMA UPDATE")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 80)
    
    engine = create_engine(DATABASE_URL)
    
    # Get existing tables before update
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """))
        existing_tables = set(r[0] for r in result.fetchall())
    
    print(f"\n📋 Existing tables: {len(existing_tables)}")
    
    # Check for pgvector extension
    print("\n🔍 Checking pgvector extension...")
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
        ))
        row = result.fetchone()
        if row:
            print(f"   ✅ pgvector v{row[0]} installed - will create vector tables")
            pgvector_available = True
        else:
            print("   ⚠️ pgvector not installed - vector tables will use TEXT for embeddings")
            pgvector_available = False
    
    # Tables to create (non-vector)
    non_vector_tables = [
        ("session_archives", SESSION_ARCHIVES_SQL),
        ("documents", DOCUMENTS_SQL),
        ("memori_chat_history", MEMORI_CHAT_HISTORY_SQL),
        ("memori_short_term_memory", MEMORI_SHORT_TERM_MEMORY_SQL),
        ("memori_long_term_memory", MEMORI_LONG_TERM_MEMORY_SQL),
    ]
    
    # Vector tables (only if pgvector available)
    vector_tables = [
        ("vector_medical_knowledge", VECTOR_MEDICAL_KNOWLEDGE_SQL),
        ("vector_drug_interactions", VECTOR_DRUG_INTERACTIONS_SQL),
        ("vector_symptoms_conditions", VECTOR_SYMPTOMS_CONDITIONS_SQL),
        ("vector_user_memories", VECTOR_USER_MEMORIES_SQL),
    ]
    
    # Create non-vector tables
    print("\n📦 Creating non-vector tables...")
    for table_name, sql in non_vector_tables:
        try:
            with engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()
            
            status = "✅ Created" if table_name not in existing_tables else "✅ Verified"
            print(f"   {status}: {table_name}")
        except Exception as e:
            print(f"   ❌ Failed: {table_name} - {e}")
    
    # Create triggers for memori tables
    print("\n📦 Creating trigger functions...")
    try:
        with engine.connect() as conn:
            conn.execute(text(MEMORI_TRIGGERS_SQL))
            conn.commit()
        print("   ✅ Search vector triggers created")
    except Exception as e:
        print(f"   ⚠️ Trigger creation: {e}")
    
    # Create vector tables if pgvector available
    if pgvector_available:
        print("\n📦 Creating vector tables (pgvector)...")
        for table_name, sql in vector_tables:
            try:
                with engine.connect() as conn:
                    conn.execute(text(sql))
                    conn.commit()
                
                status = "✅ Created" if table_name not in existing_tables else "✅ Verified"
                print(f"   {status}: {table_name}")
            except Exception as e:
                print(f"   ❌ Failed: {table_name} - {e}")
    else:
        # Create fallback tables without vector type
        print("\n📦 Creating vector tables (TEXT fallback - no pgvector)...")
        for table_name, sql in vector_tables:
            # Replace vector(384) with TEXT
            fallback_sql = sql.replace("vector(384)", "TEXT")
            # Remove vector-specific index creation
            fallback_sql = fallback_sql.split("DO $$")[0] if "DO $$" in fallback_sql else fallback_sql
            
            try:
                with engine.connect() as conn:
                    conn.execute(text(fallback_sql))
                    conn.commit()
                
                status = "✅ Created (TEXT)" if table_name not in existing_tables else "✅ Verified"
                print(f"   {status}: {table_name}")
            except Exception as e:
                print(f"   ❌ Failed: {table_name} - {e}")
    
    # Verify final state
    print("\n" + "=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """))
        final_tables = set(r[0] for r in result.fetchall())
    
    new_tables = final_tables - existing_tables
    print(f"\n✅ Total tables: {len(final_tables)}")
    print(f"✅ New tables created: {len(new_tables)}")
    
    if new_tables:
        print("\n   New tables:")
        for t in sorted(new_tables):
            print(f"      - {t}")
    
    # Check required tables
    required = {
        "session_archives", "documents",
        "vector_medical_knowledge", "vector_drug_interactions",
        "vector_symptoms_conditions", "vector_user_memories",
        "memori_chat_history", "memori_short_term_memory", "memori_long_term_memory"
    }
    
    missing = required - final_tables
    if missing:
        print(f"\n⚠️ Still missing: {', '.join(sorted(missing))}")
    else:
        print("\n✅ All required tables are present!")
    
    print("\n" + "=" * 80)
    print("DATABASE UPDATE COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    update_database()
