"""
RAG similarity retriever using pgvector via Supabase RPC.

Input:
  query_text      — natural language query string
  top_k           — number of results to return (default: 5)
  doc_type_filter — list of doc_types to restrict results, or None for all
                    e.g. ["curve_event", "concept"]

Output:
  list of dicts, ordered by similarity descending:
  [
    {
      document_id: int,
      title:       str,
      content:     str,
      doc_type:    str,
      doc_date:    str | None,
      similarity:  float,
    },
    ...
  ]

Implementation:
  1. Embed query_text with OpenAI text-embedding-3-small
  2. Call curveiq.match_documents() via supabase.rpc()
     (raw SQL is not supported by supabase-py — RPC is required for pgvector)
  3. Return top_k results

The match_documents Postgres function is defined in db/schema.sql.
Call signature: match_documents(query_embedding, match_count, filter_types)
"""

import os
from functools import lru_cache

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))


@lru_cache(maxsize=128)
def _embed_cached(text: str) -> list:
    """Embed a single string. Cached to avoid re-embedding the same query."""
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=[text],
    )
    return response.data[0].embedding


def retrieve(query_text: str, top_k: int = 5,
             doc_type_filter: list = None) -> list:
    """
    Retrieve semantically similar RAG documents for a query string.

    Args:
        query_text:      The search query.
        top_k:           Maximum number of results to return.
        doc_type_filter: Optional list of doc_types to restrict to.
                         e.g. ["curve_event", "concept"]

    Returns:
        List of result dicts ordered by similarity descending.
        Empty list if no results or on error.
    """
    from db.supabase_client import get_client

    if not query_text or not query_text.strip():
        return []

    # Embed the query
    embedding = _embed_cached(query_text.strip())

    # Call the Postgres function via RPC
    # supabase-py does not support raw parameterised SQL — RPC is the correct approach
    db = get_client()
    params = {
        "query_embedding": embedding,
        "match_count": top_k,
    }
    if doc_type_filter:
        params["filter_types"] = doc_type_filter

    result = db.rpc("match_documents", params).execute()

    if not result.data:
        return []

    return [
        {
            "document_id": row.get("document_id"),
            "title":       row.get("title", ""),
            "content":     row.get("content", ""),
            "doc_type":    row.get("doc_type", ""),
            "doc_date":    row.get("doc_date"),
            "similarity":  round(float(row.get("similarity", 0)), 4),
        }
        for row in result.data
    ]
