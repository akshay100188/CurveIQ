"""
Shared Supabase client for CurveIQ.

Usage:
    from db.supabase_client import get_client

    client = get_client()
    result = client.table("ciq_yield_curve_daily").select("*").limit(1).execute()

The client is pre-configured to use the curveiq schema via .schema("curveiq"),
so all .table() calls target curveiq.<table> without needing a prefix.

IMPORTANT: Always use the service role key (SUPABASE_KEY), never the anon key.
The service role key bypasses Row Level Security, which is required for
server-side reads and writes. Never expose this key to the frontend.
"""

import os
from functools import lru_cache

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()


@lru_cache(maxsize=1)
def get_client() -> Client:
    """
    Return a schema-switched Supabase client targeting curveiq.
    Cached after first call — one client per process lifetime.
    """
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")

    if not url:
        raise EnvironmentError("SUPABASE_URL is not set in environment")
    if not key:
        raise EnvironmentError("SUPABASE_KEY is not set in environment")

    client = create_client(url, key)
    return client.schema("curveiq")
