"""Phase 3 — build and embed the RAG corpus into curveiq.corpus_chunks (pgvector).

Corpus lives as markdown in corpus/*.md. Each file begins with a `country: <US|IN|
null>` line; each `## heading` starts a chunk (title = heading, content = body). The
chunks are embedded with OpenAI text-embedding-3-small (1536d) and upserted.

Run:    python -m pipeline.phase3_rag
Search: python -m pipeline.phase3_rag "why does the curve invert"
"""
from __future__ import annotations

import sys
from pathlib import Path

from psycopg2.extras import execute_values

from . import db
from .sources import openai_embed

CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus"

SCHEMA_DDL = f"""
create extension if not exists vector with schema extensions;
create table if not exists curveiq.corpus_chunks (
    id         bigserial primary key,
    source     text,
    country    text,
    title      text,
    content    text not null,
    embedding  extensions.vector({openai_embed.DIM}),
    metadata   jsonb,
    created_at timestamptz default now(),
    unique (source, title)
);
grant usage on schema curveiq to anon, authenticated, service_role;
grant select on curveiq.corpus_chunks to anon, authenticated;
grant all on curveiq.corpus_chunks to service_role;
"""


def parse_corpus() -> list[dict]:
    chunks: list[dict] = []
    for path in sorted(CORPUS_DIR.glob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        country = None
        body_start = 0
        if lines and lines[0].lower().startswith("country:"):
            val = lines[0].split(":", 1)[1].strip()
            country = None if val.lower() in ("null", "none", "") else val
            body_start = 1
        title, buf = None, []
        for line in lines[body_start:]:
            if line.startswith("## "):
                if title and buf:
                    chunks.append({"source": path.stem, "country": country,
                                   "title": title, "content": "\n".join(buf).strip()})
                title, buf = line[3:].strip(), []
            else:
                buf.append(line)
        if title and buf:
            chunks.append({"source": path.stem, "country": country,
                           "title": title, "content": "\n".join(buf).strip()})
    return chunks


def build() -> int:
    with db.cursor() as cur:
        cur.execute(SCHEMA_DDL)
    chunks = parse_corpus()
    texts = [f"{c['title']}\n\n{c['content']}" for c in chunks]
    print(f"embedding {len(chunks)} chunks …")
    vecs = openai_embed.embed(texts)
    rows = [(c["source"], c["country"], c["title"], c["content"],
             "[" + ",".join(map(str, v)) + "]") for c, v in zip(chunks, vecs)]
    with db.cursor() as cur:
        cur.execute("truncate curveiq.corpus_chunks restart identity")
        execute_values(cur,
            "insert into curveiq.corpus_chunks "
            "(source,country,title,content,embedding) values %s",
            rows, template="(%s,%s,%s,%s,%s::extensions.vector)", page_size=100)
        # NOTE: no ivfflat index. ivfflat is an *approximate* index — with a corpus
        # this small (tens of rows) each probe list holds ~1 chunk, so relevant
        # results get skipped. An exact sequential scan over a few dozen rows is
        # instant and correct. Add ivfflat back only if the corpus grows to 1000s.
        cur.execute("drop index if exists curveiq.corpus_chunks_embedding_idx")
    print(f"corpus_chunks: {len(rows)} chunks embedded (exact search, no ivfflat)")
    return len(rows)


def retrieve(query: str, country: str | None = None, k: int = 4) -> list[tuple]:
    qv = "[" + ",".join(map(str, openai_embed.embed_one(query))) + "]"
    where = ""
    params: list = [qv]
    if country:
        where = "where country is null or country = %s"
        params.append(country)
    params.append(qv)
    with db.cursor() as cur:
        cur.execute(f"""select title, source, country,
                          1 - (embedding <=> %s::extensions.vector) as score
                        from curveiq.corpus_chunks {where}
                        order by embedding <=> %s::extensions.vector
                        limit {k}""", params)
        return cur.fetchall()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        for title, src, cty, score in retrieve(" ".join(sys.argv[1:])):
            print(f"  {score:.3f}  [{src}] {title}")
    else:
        build()
