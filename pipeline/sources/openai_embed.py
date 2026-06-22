"""OpenAI embeddings client (REST, no SDK dependency).

Uses text-embedding-3-small (1536 dims) to match the corpus_chunks vector column.
"""
from __future__ import annotations

import time

import requests

from ..config import ENV

MODEL = "text-embedding-3-small"
DIM = 1536
_URL = "https://api.openai.com/v1/embeddings"


def embed(texts: list[str]) -> list[list[float]]:
    key = ENV.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set in .env")
    last_err = None
    for attempt in range(1, 4):
        try:
            r = requests.post(_URL, timeout=60,
                              headers={"Authorization": f"Bearer {key}",
                                       "Content-Type": "application/json"},
                              json={"model": MODEL, "input": texts})
            r.raise_for_status()
            data = r.json()["data"]
            return [d["embedding"] for d in sorted(data, key=lambda x: x["index"])]
        except requests.RequestException as e:
            last_err = e
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"OpenAI embeddings failed: {last_err}")


def embed_one(text: str) -> list[float]:
    return embed([text])[0]
