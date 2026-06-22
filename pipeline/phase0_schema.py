"""Phase 0 — create the `curveiq` write schema and its tables.

CurveIQ reads authentic data from `bond` + `core` and writes its canonical,
cleaned store here. Every fact table carries a `source` provenance column so the
authenticity of each row can be audited.
"""
from __future__ import annotations

from . import db

DDL = """
create schema if not exists curveiq;

-- Canonical cleaned time series (long format). One row per (series_id, obs_date).
create table if not exists curveiq.rates_timeseries (
    id         bigserial primary key,
    country    text not null check (country in ('US','IN')),
    series_id  text not null,
    role       text not null check (role in ('market','administered')),
    category   text not null,                 -- curve|spread|real|breakeven|policy|equity
    obs_date   date not null,
    value      numeric,
    source     text not null,                 -- authentic-source provenance
    unique (series_id, obs_date)
);
create index if not exists rates_ts_country_cat_idx
    on curveiq.rates_timeseries (country, category, obs_date);

-- US full curve, tenor-keyed (India has no free curve -> 10Y level only).
create table if not exists curveiq.curve_points (
    id           bigserial primary key,
    country      text not null check (country in ('US','IN')),
    obs_date     date not null,
    tenor_months int  not null,
    tenor_label  text not null,
    yield        numeric,
    source       text not null,
    unique (country, obs_date, tenor_months)
);
create index if not exists curve_points_country_date_idx
    on curveiq.curve_points (country, obs_date);

-- L1 computed metrics (Phase 1).
create table if not exists curveiq.computed_metrics (
    id          bigserial primary key,
    country     text not null check (country in ('US','IN')),
    metric_name text not null,
    obs_date    date not null,
    value       numeric,
    label       text,
    regime      text,
    unique (country, metric_name, obs_date)
);

-- Regime / crisis windows (US from NBER/USREC; India from manual constants).
create table if not exists curveiq.regimes (
    id          bigserial primary key,
    country     text not null check (country in ('US','IN')),
    regime_name text not null,
    start_date  date not null,
    end_date    date,
    source      text not null,
    unique (country, regime_name, start_date)
);

-- Read access for the API roles (frontend reads pre-computed data).
grant usage on schema curveiq to anon, authenticated, service_role;
grant select on all tables in schema curveiq to anon, authenticated;
grant all on all tables in schema curveiq to service_role;
alter default privileges in schema curveiq
    grant select on tables to anon, authenticated;
alter default privileges in schema curveiq
    grant all on tables to service_role;
"""


def run() -> None:
    with db.cursor() as cur:
        cur.execute(DDL)
        cur.execute("""select table_name from information_schema.tables
                       where table_schema='curveiq' order by table_name""")
        tables = [r[0] for r in cur.fetchall()]
    print("curveiq schema ready. tables:", tables)


if __name__ == "__main__":
    run()
