-- Phase 0 Schema: Data tables only.
-- Run this in Supabase SQL Editor BEFORE running 06_push_to_supabase.py.
-- Phase 1 will extend this with the full application schema.
--
-- Instructions:
--   1. Open Supabase dashboard → SQL Editor
--   2. Paste this entire file
--   3. Click Run
--   4. Verify: "Success. No rows returned."

-- Extensions and schema
create extension if not exists vector;
create schema if not exists curveiq;

-- -------------------------------------------------------------------------
-- ciq_yield_curve_daily
-- -------------------------------------------------------------------------
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
-- ciq_credit_stress_daily
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
-- ciq_fed_decisions
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

-- Permissions: grant all Supabase roles access to curveiq schema
grant usage on schema curveiq to anon, authenticated, service_role;
grant all on all tables in schema curveiq to anon, authenticated, service_role;
grant all on all sequences in schema curveiq to anon, authenticated, service_role;
alter default privileges in schema curveiq grant all on tables to anon, authenticated, service_role;
alter default privileges in schema curveiq grant all on sequences to anon, authenticated, service_role;

