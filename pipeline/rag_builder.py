"""
RAG knowledge base builder.

Usage:
  python pipeline/rag_builder.py           — seed initial 16 documents (idempotent)
  python pipeline/rag_builder.py --refresh — generate lesson docs from wrong predictions

Seeds curveiq.ciq_rag_documents and curveiq.ciq_rag_embeddings with:
  - 5 curve_event documents (yield curve inversion history)
  - 4 curve_event documents (credit crisis history)
  - 7 concept documents (fixed income education)

Chunking: each document is split into ~300-token chunks before embedding.
Embedding model: OpenAI text-embedding-3-small (1536 dimensions).
Deduplication: documents are matched by title; existing titles are skipped
  unless --force is passed.

For --refresh:
  Reads ciq_self_learning_log rows where was_correct=FALSE AND lesson_generated=FALSE.
  Generates a lesson document per wrong prediction.
  Sets lesson_generated=TRUE to prevent re-processing.
"""

import os
import sys
import argparse
import textwrap

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, ".env"))

from db.supabase_client import get_client

# ---------------------------------------------------------------------------
# Seed documents
# ---------------------------------------------------------------------------

SEED_DOCUMENTS = [
    # --- CURVE_EVENT: inversion history ---
    {
        "doc_type": "curve_event",
        "title": "2006-07 Yield Curve Inversion — Pre-Crisis Warning",
        "content": """
The 2Y/10Y spread inverted in July 2006, reaching -19bps. The Federal Reserve held
rates at 5.25% throughout. Despite the inversion, equity markets continued rising for
12 months. The recession began December 2007, 18 months after initial inversion. This
episode established the inversion as a leading indicator with a variable and long lag.
Key context: the Fed had completed a 425bp hiking cycle from June 2004 to June 2006.
The inversion occurred while nominal growth remained strong, highlighting how the curve
can signal future weakness even when current conditions appear healthy.
        """.strip(),
        "source": "FRED/NBER historical data",
        "doc_date": "2006-07-01",
    },
    {
        "doc_type": "curve_event",
        "title": "2019 Brief Inversion — False Alarm",
        "content": """
The 2Y/10Y spread briefly inverted in August 2019, reaching -5bps. The Fed began
cutting rates in July 2019. No recession followed from this inversion — COVID-19
caused the 2020 recession, not a credit cycle. This episode shows inversions are
necessary but not sufficient recession predictors. The brief duration (a few weeks)
and shallow depth (-5bps vs -108bps in 2023) are distinguishing features. Fed rate
cuts quickly restored curve steepness by late 2019.
        """.strip(),
        "source": "FRED historical data",
        "doc_date": "2019-08-01",
    },
    {
        "doc_type": "curve_event",
        "title": "2022-23 Deep Inversion — Most Extreme Since 1981",
        "content": """
The most aggressive Fed hiking cycle since the 1980s pushed the 2Y/10Y spread to
-108bps in March 2023, the deepest inversion in 42 years. The Fed raised rates from
0.25% in March 2022 to 5.50% by July 2023 — 525bps in 16 months. Despite this,
a recession had not materialised by mid-2024, extending the debate about inversion
lead times in the post-QE era. Factors complicating the signal: strong labour markets,
fiscal stimulus, and consumer balance sheet resilience from pandemic-era savings.
        """.strip(),
        "source": "FRED historical data",
        "doc_date": "2023-03-01",
    },
    {
        "doc_type": "curve_event",
        "title": "1989 Inversion — Clean Recession Predictor",
        "content": """
The 2Y/10Y inverted clearly in 1989. A recession followed in July 1990, approximately
10 months later. This is considered a textbook example of the yield curve as a recession
predictor, with a clean signal and relatively short lead time. The inversion occurred as
the Fed tightened to combat inflation, peaking at rates above 8%. The recession was mild
by historical standards, lasting 8 months. This episode is frequently cited as the ideal
inversion-to-recession pathway when curve analysis is discussed.
        """.strip(),
        "source": "FRED/NBER historical data",
        "doc_date": "1989-06-01",
    },
    {
        "doc_type": "curve_event",
        "title": "1998 Brief Inversion — No Recession",
        "content": """
Russian debt crisis and LTCM collapse caused brief curve distortion in 1998. The 2Y/10Y
spread went slightly negative. No recession followed. The Fed cut rates three times in
quick succession, restoring curve steepness. Flight-to-quality demand for Treasuries
distorted the signal — the inversion reflected a global risk-off trade into safe assets
rather than domestic credit cycle deterioration. This is the canonical example of an
inversion driven by external shock and flight-to-quality rather than domestic cycle.
        """.strip(),
        "source": "FRED historical data",
        "doc_date": "1998-10-01",
    },
    # --- CURVE_EVENT: credit crisis ---
    {
        "doc_type": "curve_event",
        "title": "2007 Credit Stress Onset — Early Warning Signals",
        "content": """
High Yield OAS began widening in June 2007 from 260bps to over 600bps by year-end as
subprime losses emerged. The TED spread spiked in August 2007 when BNP Paribas froze
redemptions on three funds. VIX rose from 12 to 32. These three signals — OAS, TED,
VIX — all crossed stress thresholds simultaneously, 13 months before Lehman bankruptcy.
The composite stress score would have been in the "watch" to "stress" regime throughout
H2 2007, providing an early warning signal that the credit cycle was deteriorating.
        """.strip(),
        "source": "FRED/Bloomberg historical data",
        "doc_date": "2007-08-01",
    },
    {
        "doc_type": "curve_event",
        "title": "2008 Full Crisis — Systemic Collapse Signals",
        "content": """
By September 2008, HY OAS exceeded 1,800bps (from 260bps pre-crisis). TED spread
reached 464bps on October 10, 2008 — extreme interbank stress. VIX hit 89.5 on
October 24, 2008. Investment grade OAS widened to 600bps. All four major stress
indicators simultaneously in crisis territory — a once-in-generation co-movement.
Lehman Brothers filed for bankruptcy September 15, 2008. Fed cut rates to 0-0.25%
in December 2008. The composite stress score would have been well above 75 (crisis
regime) from October 2008 through early 2009.
        """.strip(),
        "source": "FRED/Bloomberg historical data",
        "doc_date": "2008-10-10",
    },
    {
        "doc_type": "curve_event",
        "title": "2020 COVID Shock — Fast Spike, Fast Recovery",
        "content": """
COVID caused the fastest stress spike in market history. HY OAS went from 310bps to
1,100bps in 33 days (February-March 2020). VIX reached 85.5. TED spread rose sharply.
However, Fed intervention — $700B QE, 0% rates, corporate bond purchase programs —
reversed stress indicators within 3 months. The composite stress score hit crisis
territory briefly before rapid recovery. The speed of both the spike and recovery
distinguishes COVID from the 2008 GFC where stress persisted for 18+ months.
Fed balance sheet expanded from $4.2T to $7.2T in 6 months.
        """.strip(),
        "source": "FRED historical data",
        "doc_date": "2020-03-18",
    },
    {
        "doc_type": "curve_event",
        "title": "2011 European Sovereign Debt Contagion",
        "content": """
US credit markets showed stress as European sovereign issues spread. HY OAS widened
to 800bps. VIX reached 48. TED spread elevated. No US recession followed. Stress
was imported from Europe, contained by ECB intervention. Shows that stress scores
can reach watch/stress territory without full crisis materialising. The S&P 500 fell
20% from April to October 2011. US Treasury yields fell sharply as flight-to-quality
intensified. The 2Y/10Y spread was positive throughout, limiting the recession signal.
        """.strip(),
        "source": "FRED historical data",
        "doc_date": "2011-09-01",
    },
    # --- CONCEPT: fixed income education ---
    {
        "doc_type": "concept",
        "title": "Duration — Measuring Interest Rate Sensitivity",
        "content": """
Duration measures a bond's price sensitivity to interest rate changes. A bond with
duration of 7 years will lose approximately 7% in price if yields rise 1%. Modified
duration adjusts for the bond's yield, giving a more precise estimate. Higher duration
means greater rate risk. Long-maturity, low-coupon bonds have the highest duration.
Macaulay duration is the weighted average time to receive cash flows. Modified duration
= Macaulay duration / (1 + YTM/2) for semi-annual bonds. DV01 is the dollar change
for 1 basis point move, equal to modified duration × price × 0.0001.
        """.strip(),
        "source": "Fixed income fundamentals",
        "doc_date": None,
    },
    {
        "doc_type": "concept",
        "title": "Convexity — The Second Order Effect",
        "content": """
Convexity captures the curvature in the price-yield relationship that duration misses.
Positive convexity means a bond gains more when rates fall than it loses when rates
rise by the same amount. This asymmetry is a desirable property. High convexity bonds
outperform in volatile rate environments. The convexity-adjusted price change formula:
price_change = -duration × shock + 0.5 × convexity × shock². Zero-coupon bonds have
the highest convexity relative to duration. Callable bonds can have negative convexity
at low yield levels (price is capped by the call price).
        """.strip(),
        "source": "Fixed income fundamentals",
        "doc_date": None,
    },
    {
        "doc_type": "concept",
        "title": "DV01 — Dollar Value of a Basis Point",
        "content": """
DV01 is the dollar change in bond price for a 1 basis point (0.01%) move in yield.
A bond with DV01 of $850 loses $850 per million face value for each basis point rise
in yield. Portfolio managers use DV01 to size hedges precisely. DV01 = Modified Duration
× Price × 0.0001. For a 10-year Treasury at par with duration 8, DV01 ≈ $800 per
$1M face. DV01 increases with duration and with price. It is the standard risk measure
for fixed income position sizing and hedge ratio calculation.
        """.strip(),
        "source": "Fixed income fundamentals",
        "doc_date": None,
    },
    {
        "doc_type": "concept",
        "title": "Yield Curve Shapes and Their Meaning",
        "content": """
Normal (upward sloping): long rates > short rates. Signals economic expansion
expectation. Investors demand premium for longer maturities. spread_2y10y > 0.15%.
Inverted (downward sloping): short rates > long rates. Historically the most reliable
recession predictor. Markets expect rate cuts ahead. spread_2y10y < 0.
Flat: similar rates across maturities. Transitional state, often before inversion or
during Fed tightening. abs(spread_2y10y) <= 0.15%.
Humped: medium-term yields highest. Rare. Can signal temporary supply pressure or
uncertainty about the medium-term rate path. Peak at 3Y or 5Y tenor.
        """.strip(),
        "source": "Fixed income fundamentals",
        "doc_date": None,
    },
    {
        "doc_type": "concept",
        "title": "OAS — Option-Adjusted Spread Explained",
        "content": """
Option-Adjusted Spread is the yield spread of a bond over the risk-free Treasury rate,
adjusted for any embedded options. For corporate bonds, it represents the pure credit
risk premium. HY OAS (High Yield OAS) is the most widely watched credit stress
indicator — rising HY OAS signals markets pricing increased default risk across the
high yield universe. Historical HY OAS averages approximately 400-500bps in normal
environments, rising above 800bps in stress and 1000bps+ in crisis. The ICE BofA
US High Yield Index OAS (BAMLH0A0HYM2 on FRED) is the standard reference.
        """.strip(),
        "source": "Fixed income fundamentals",
        "doc_date": None,
    },
    {
        "doc_type": "concept",
        "title": "TED Spread — Interbank Stress Indicator",
        "content": """
The TED spread (Treasury-Eurodollar) is the difference between 3-month LIBOR and
3-month Treasury bill yield. It measures interbank lending stress — how much banks
charge each other above the risk-free rate. Normal TED spread: 10-50bps. Elevated:
50-100bps. Stress: >100bps. The TED spread reached 464bps in October 2008, signalling
complete breakdown of interbank trust. Post-LIBOR (after 2023), the proxy is
OBFR minus DGS3MO, which measures a similar overnight-to-3month bank funding premium.
TEDRATE series on FRED ended April 2023 with LIBOR discontinuation.
        """.strip(),
        "source": "Fixed income fundamentals",
        "doc_date": None,
    },
    {
        "doc_type": "concept",
        "title": "The 2Y/10Y Spread as Recession Predictor",
        "content": """
The 2-year vs 10-year Treasury spread is the most widely followed recession indicator.
Since 1978, every US recession has been preceded by an inversion (spread < 0). Lead
time varies from 6 to 24 months. False positives are rare but exist (1998, briefly 2019).
The signal is more reliable when combined with credit stress indicators — inversion plus
rising HY OAS has near-perfect historical accuracy. The 2022-23 inversion (-108bps peak)
was the deepest since 1981 but had not produced a recession by mid-2024, extending
the average lead time debate. The spread is computed as t10y minus t2y.
        """.strip(),
        "source": "Fixed income fundamentals",
        "doc_date": None,
    },
]


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

TARGET_CHUNK_TOKENS = 300
APPROX_CHARS_PER_TOKEN = 4


def chunk_text(text: str, max_chars: int = TARGET_CHUNK_TOKENS * APPROX_CHARS_PER_TOKEN) -> list:
    """Split text into chunks of approximately max_chars characters at sentence boundaries."""
    sentences = text.replace("\n", " ").split(". ")
    chunks = []
    current = []
    current_len = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if not sentence.endswith("."):
            sentence += "."

        if current_len + len(sentence) > max_chars and current:
            chunks.append(" ".join(current))
            current = [sentence]
            current_len = len(sentence)
        else:
            current.append(sentence)
            current_len += len(sentence)

    if current:
        chunks.append(" ".join(current))

    return [c for c in chunks if len(c.strip()) > 20]


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def embed_texts(texts: list) -> list:
    """Embed a list of strings using OpenAI text-embedding-3-small. Returns list of vectors."""
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    return [item.embedding for item in response.data]


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

def get_existing_titles(db) -> set:
    result = db.table("ciq_rag_documents").select("title").execute()
    return {row["title"] for row in result.data}


def seed_documents(db, force: bool = False):
    existing_titles = get_existing_titles(db)
    inserted = 0
    skipped = 0

    for doc in SEED_DOCUMENTS:
        if not force and doc["title"] in existing_titles:
            skipped += 1
            continue

        print(f"  Inserting: {doc['title'][:60]}...")

        # Insert document
        doc_result = db.table("ciq_rag_documents").insert({
            "doc_type": doc["doc_type"],
            "title": doc["title"],
            "content": doc["content"],
            "source": doc["source"],
            "doc_date": doc.get("doc_date"),
        }).execute()

        doc_id = doc_result.data[0]["id"]

        # Chunk and embed
        chunks = chunk_text(doc["content"])
        if not chunks:
            chunks = [doc["content"]]

        embeddings = embed_texts(chunks)

        embedding_rows = [
            {
                "document_id": doc_id,
                "content_chunk": chunk,
                "embedding": embedding,
            }
            for chunk, embedding in zip(chunks, embeddings)
        ]

        db.table("ciq_rag_embeddings").insert(embedding_rows).execute()
        print(f"    → {len(chunks)} chunk(s) embedded")
        inserted += 1

    print(f"\n  Seed complete: {inserted} inserted, {skipped} skipped (already exist)")


# ---------------------------------------------------------------------------
# Refresh (self-learning lessons)
# ---------------------------------------------------------------------------

def refresh_lessons(db):
    """Generate lesson documents from wrong predictions (was_correct=FALSE, lesson_generated=FALSE)."""
    result = db.table("ciq_self_learning_log").select(
        "id, narrative_id, prediction_type, predicted_value, actual_value, outcome_date, "
        "created_at"
    ).eq("was_correct", False).eq("lesson_generated", False).execute()

    rows = result.data
    if not rows:
        print("  No new wrong predictions to process.")
        return

    print(f"  Processing {len(rows)} wrong prediction(s)...")

    for row in rows:
        date_str = str(row.get("outcome_date", "unknown date"))
        pred_type = row.get("prediction_type", "")
        predicted = row.get("predicted_value", "")
        actual = row.get("actual_value", "")

        lesson_text = (
            f"On {date_str}, the model made a {pred_type} prediction of '{predicted}'. "
            f"The actual outcome after 30 days was '{actual}'. "
            f"This prediction was incorrect. Future analysis of similar conditions should "
            f"consider that {pred_type} signals can be misleading when predicted='{predicted}' "
            f"but actual='{actual}'."
        )

        title = f"Self-Learning Lesson: {pred_type} — {date_str}"

        doc_result = db.table("ciq_rag_documents").insert({
            "doc_type": "self_learning",
            "title": title,
            "content": lesson_text,
            "source": "ciq_self_learning_log",
            "doc_date": date_str if date_str != "unknown date" else None,
        }).execute()

        doc_id = doc_result.data[0]["id"]
        embedding = embed_texts([lesson_text])[0]

        db.table("ciq_rag_embeddings").insert({
            "document_id": doc_id,
            "content_chunk": lesson_text,
            "embedding": embedding,
        }).execute()

        # Mark as processed
        db.table("ciq_self_learning_log").update(
            {"lesson_generated": True}
        ).eq("id", row["id"]).execute()

        print(f"  Lesson created: {title[:70]}")

    print(f"\n  Refresh complete: {len(rows)} lessons added to RAG knowledge base")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="CurveIQ RAG Knowledge Base Builder")
    parser.add_argument("--refresh", action="store_true",
                        help="Generate lessons from wrong predictions (self-learning refresh)")
    parser.add_argument("--force", action="store_true",
                        help="Re-insert all seed documents even if they exist")
    args = parser.parse_args()

    print("\nCurveIQ — RAG Builder")

    db = get_client()

    if args.refresh:
        print("\n[REFRESH MODE] Generating self-learning lessons...")
        refresh_lessons(db)
    else:
        print(f"\n[SEED MODE] Inserting {len(SEED_DOCUMENTS)} knowledge base documents...")
        if args.force:
            print("  (--force: re-inserting all documents)")
        seed_documents(db, force=args.force)

        # Gate test
        print("\n  Testing RAG retrieval...")
        from skills.rag_retriever import retrieve
        results = retrieve("yield curve inversion recession", top_k=3)
        if results:
            print(f"  [OK] Test query returned {len(results)} result(s)")
            for r in results:
                print(f"       [{r['similarity']:.3f}] {r['title'][:60]}")
        else:
            print("  [WARN] Test query returned 0 results — check ciq_rag_embeddings table")


if __name__ == "__main__":
    main()
