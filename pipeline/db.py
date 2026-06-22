"""Postgres (Supabase) connection helpers.

Connects directly via DATABASE_URL (pooler). The pooler can be transiently
flaky on auth, so connect() retries a few times before giving up.
"""
from __future__ import annotations

import time
import urllib.parse
from contextlib import contextmanager

import psycopg2

from .config import DATABASE_URL


def connect(retries: int = 4, delay: float = 2.0):
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set in .env")
    p = urllib.parse.urlparse(DATABASE_URL)
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return psycopg2.connect(
                host=p.hostname, port=p.port or 5432,
                user=p.username, password=urllib.parse.unquote(p.password or ""),
                dbname=(p.path or "/postgres").lstrip("/") or "postgres",
                sslmode="require", connect_timeout=20,
            )
        except psycopg2.OperationalError as e:
            last_err = e
            if attempt < retries:
                print(f"  [db] connect attempt {attempt} failed, retrying in {delay}s …")
                time.sleep(delay)
    raise RuntimeError(f"DB connection failed after {retries} attempts: {last_err}")


@contextmanager
def cursor():
    conn = connect()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
