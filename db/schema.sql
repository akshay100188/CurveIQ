-- CurveIQ — Full Application Schema
-- Run this in Supabase SQL Editor after phase0/schema_data_tables.sql.
-- All tables use the curveiq schema prefix.
-- This file is idempotent: safe to re-run (uses CREATE IF NOT EXISTS).

create extension if not exists vector;
create schema if not exists curveiq;

-- =========================================================================
-- DATA TABLES (also in phase0/schema_data_tables.sql)
-- =========================================================================

create table if not exists curveiq.ciq_yield_curve_daily (
  date             DATE PRIMARY KEY,
  t1m              NUMERIC(8,4),
  t3m              NUMERIC(8,4),
  t6m              NUMERIC(8,4),
  t1y              NUMERIC(8,4),
  t2y              NUMERIC(8,4),
  t3y              NUMERIC(8,4),
  t5y              NUMERIC(8,4),
  t7y              NUMERIC(8,4),
  t10y             NUMERIC(8,4),
  t20y             NUMERIC(8,4),
  t30y             NUMERIC(8,4),
  spread_2y10y     NUMERIC(8,4),
  spread_3m10y     NUMERIC(8,4),
  curve_shape      TEXT,
  created_at       TIMESTAMPTZ DEFAULT now()
);

create index if not exists idx_yield_curve_date_desc
  on curveiq.ciq_yield_curve_daily (date DESC);

-- -------------------------------------------------------------------------

create table if not exists curveiq.ciq_credit_stress_daily (
  date             DATE PRIMARY KEY,
  hy_oas           NUMERIC(8,4),
  ig_oas           NUMERIC(8,4),
  ted_spread       NUMERIC(8,4),
  vix              NUMERIC(8,4),
  sofr             NUMERIC(8,4),
  obfr             NUMERIC(8,4),
  stress_score     NUMERIC(6,2),
  stress_regime    TEXT,
  created_at       TIMESTAMPTZ DEFAULT now()
);

create index if not exists idx_credit_stress_date_desc
  on curveiq.ciq_credit_stress_daily (date DESC);

-- -------------------------------------------------------------------------

create table if not exists curveiq.ciq_fed_decisions (
  id               BIGSERIAL PRIMARY KEY,
  decision_date    DATE UNIQUE,
  rate_before      NUMERIC(5,2),
  rate_after       NUMERIC(5,2),
  rate_change      NUMERIC(5,2),
  decision_type    TEXT,
  statement_summary TEXT,
  created_at       TIMESTAMPTZ DEFAULT now()
);

create index if not exists idx_fed_decisions_date_desc
  on curveiq.ciq_fed_decisions (decision_date DESC);

-- =========================================================================
-- APPLICATION TABLES
-- =========================================================================

create table if not exists curveiq.ciq_bond_calculations (
  id                BIGSERIAL PRIMARY KEY,
  session_id        TEXT,
  face_value        NUMERIC(15,2),
  coupon_rate       NUMERIC(8,4),
  maturity_years    NUMERIC(8,2),
  ytm               NUMERIC(8,4),
  credit_rating     TEXT,
  price             NUMERIC(15,4),
  duration          NUMERIC(10,6),
  modified_duration NUMERIC(10,6),
  convexity         NUMERIC(12,6),
  dv01              NUMERIC(12,6),
  created_at        TIMESTAMPTZ DEFAULT now()
);

create index if not exists idx_bond_calc_session
  on curveiq.ciq_bond_calculations (session_id);

create index if not exists idx_bond_calc_created
  on curveiq.ciq_bond_calculations (created_at DESC);

-- -------------------------------------------------------------------------

create table if not exists curveiq.ciq_agent_narratives (
  id                    BIGSERIAL PRIMARY KEY,
  narrative_type        TEXT,
  input_snapshot        JSONB,
  narrative             JSONB,
  model_used            TEXT,
  curve_shape_at_time   TEXT,
  spread_2y10y_at_time  NUMERIC(8,4),
  stress_score_at_time  NUMERIC(6,2),
  stress_regime_at_time TEXT,
  user_feedback         BOOLEAN,
  created_at            TIMESTAMPTZ DEFAULT now()
);

-- Filtered index: primary access pattern (type + date)
create index if not exists idx_agent_narratives_type_date
  on curveiq.ciq_agent_narratives (narrative_type, created_at DESC);

-- Unfiltered recency index: for GET /api/agent/narratives?limit=N without type filter
create index if not exists idx_agent_narratives_created
  on curveiq.ciq_agent_narratives (created_at DESC);

-- -------------------------------------------------------------------------

create table if not exists curveiq.ciq_self_learning_log (
  id               BIGSERIAL PRIMARY KEY,
  narrative_id     BIGINT REFERENCES curveiq.ciq_agent_narratives(id) ON DELETE CASCADE,
  prediction_type  TEXT,
  predicted_value  TEXT,
  actual_value     TEXT,
  was_correct      BOOLEAN,
  lesson_generated BOOLEAN DEFAULT FALSE,
  outcome_date     DATE,
  created_at       TIMESTAMPTZ DEFAULT now()
);

create index if not exists idx_self_learning_outcome
  on curveiq.ciq_self_learning_log (outcome_date)
  where actual_value is null;

-- -------------------------------------------------------------------------

create table if not exists curveiq.ciq_rag_documents (
  id               BIGSERIAL PRIMARY KEY,
  doc_type         TEXT,
  title            TEXT,
  content          TEXT,
  source           TEXT,
  doc_date         DATE,
  created_at       TIMESTAMPTZ DEFAULT now()
);

-- -------------------------------------------------------------------------

create table if not exists curveiq.ciq_rag_embeddings (
  id               BIGSERIAL PRIMARY KEY,
  document_id      BIGINT REFERENCES curveiq.ciq_rag_documents(id) ON DELETE CASCADE,
  content_chunk    TEXT,
  embedding        vector(1536),
  created_at       TIMESTAMPTZ DEFAULT now()
);

-- HNSW index for fast cosine similarity search (pgvector >= 0.5.0)
create index if not exists idx_rag_embeddings_hnsw
  on curveiq.ciq_rag_embeddings
  using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64);

-- =========================================================================
-- PGVECTOR SEARCH FUNCTION
-- Used by skills/rag_retriever.py via supabase.rpc("match_documents", {...})
-- Direct SQL is not supported by supabase-py; this RPC approach is required.
-- =========================================================================

create or replace function curveiq.match_documents(
  query_embedding  vector(1536),
  match_count      int,
  filter_types     text[] default null
)
returns table (
  document_id   bigint,
  title         text,
  content       text,
  doc_type      text,
  doc_date      date,
  similarity    float
)
language sql stable
as $$
  select
    d.id          as document_id,
    d.title,
    d.content,
    d.doc_type,
    d.doc_date,
    1 - (e.embedding <=> query_embedding) as similarity
  from curveiq.ciq_rag_embeddings e
  join curveiq.ciq_rag_documents d on d.id = e.document_id
  where
    filter_types is null
    or d.doc_type = any(filter_types)
  order by e.embedding <=> query_embedding
  limit match_count;
$$;

-- Permissions: grant all Supabase roles access to curveiq schema
grant usage on schema curveiq to anon, authenticated, service_role;
grant all on all tables in schema curveiq to anon, authenticated, service_role;
grant all on all sequences in schema curveiq to anon, authenticated, service_role;
alter default privileges in schema curveiq grant all on tables to anon, authenticated, service_role;
alter default privileges in schema curveiq grant all on sequences to anon, authenticated, service_role;

