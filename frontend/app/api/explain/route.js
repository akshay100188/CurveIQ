import { lintForbidden } from "@/lib/forbidden";

export const runtime = "nodejs";

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY;
const OPENAI_KEY = process.env.OPENAI_API_KEY;
const ANTHROPIC_KEY = process.env.ANTHROPIC_API_KEY;

const SYSTEM = `You are the explainer for CurveIQ, a strictly descriptive and
retrospective yield-curve analytics tool. Rules you must obey:
- Narrate ONLY the numbers provided in the FACTS block and the supplied context.
- Never compute or assert a figure that was not given to you.
- Never give advice, recommendations, or predictions.
- Never say what will happen next. Describe only what the data has shown, in the
  past/present tense.
- Do NOT use these words: will, should, expect, likely, forecast, predict, buy, sell,
  recommend. Reword any such idea as a description of what the data shows.
- 3-5 sentences, calm and precise. No bullet points.`;

async function embed(text) {
  const r = await fetch("https://api.openai.com/v1/embeddings", {
    method: "POST",
    headers: { Authorization: `Bearer ${OPENAI_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({ model: "text-embedding-3-small", input: text }),
  });
  if (!r.ok) throw new Error(`embeddings ${r.status}`);
  const j = await r.json();
  return j.data[0].embedding;
}

async function retrieve(embedding, country) {
  const r = await fetch(`${SUPABASE_URL}/rest/v1/rpc/match_corpus`, {
    method: "POST",
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`,
      "Content-Type": "application/json",
      "Content-Profile": "curveiq",
    },
    body: JSON.stringify({
      query_embedding: `[${embedding.join(",")}]`,
      filter_country: country || null,
      match_count: 4,
    }),
  });
  if (!r.ok) throw new Error(`retrieve ${r.status} ${await r.text()}`);
  return r.json();
}

async function narrate(topic, country, facts, chunks, avoid = []) {
  const context = chunks
    .map((c) => `### ${c.title}\n${c.content}`)
    .join("\n\n");
  // Stable prefix — identical across the up-to-3 retries within one request. Kept
  // in its own block with a cache breakpoint so retries read it at ~0.1x. (No-op
  // when system+prefix is under Haiku's 4096-token minimum; correct and free.)
  const stable = `TOPIC: ${topic} (${country})

FACTS (the only numbers you may state):
${JSON.stringify(facts, null, 2)}

CONTEXT (curated notes — use for explanation, not for new numbers):
${context}`;

  const content = [
    { type: "text", text: stable, cache_control: { type: "ephemeral" } },
  ];

  // On a retry, tell the model exactly which phrases were rejected — appended
  // AFTER the cache breakpoint so it never invalidates the cached prefix above.
  if (avoid.length) {
    content.push({
      type: "text",
      text: `REWRITE NOTICE: a previous draft was rejected because it contained prescriptive or
forward-looking language: ${avoid.map((p) => `"${p}"`).join(", ")}. Rewrite the
explanation so NONE of those phrases (or equivalents) appear. Stay strictly
descriptive and retrospective: describe only what the data has shown, in the
past/present tense. Do not predict, recommend, or advise, and avoid words like
"will", "should", "expect", "likely", "forecast", "buy", or "sell".`,
    });
  }

  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": ANTHROPIC_KEY,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: "claude-haiku-4-5-20251001",
      max_tokens: 400,
      // Prompt-cache the (static) system prompt — the rules are identical on every
      // request, so caching them cuts input tokens and latency (spec §7).
      system: [{ type: "text", text: SYSTEM, cache_control: { type: "ephemeral" } }],
      messages: [{ role: "user", content }],
    }),
  });
  if (!r.ok) throw new Error(`anthropic ${r.status} ${await r.text()}`);
  const j = await r.json();
  return j.content?.[0]?.text?.trim() || "";
}

export async function POST(req) {
  try {
    if (!SUPABASE_URL || !OPENAI_KEY || !ANTHROPIC_KEY) {
      return Response.json(
        { error: "server missing SUPABASE_URL / OPENAI_API_KEY / ANTHROPIC_API_KEY" },
        { status: 500 }
      );
    }
    const { country, topic, facts } = await req.json();
    const query = `${topic} ${Object.keys(facts || {}).join(" ")}`;
    const embedding = await embed(query);
    const chunks = await retrieve(embedding, country);

    // Guardrail with self-correction: if the draft trips the forbidden-language
    // lint, regenerate (up to 3 tries) telling the model exactly which phrases to
    // reword — only fall back to the blocked message if it still won't comply.
    let explanation = "";
    let violations = [];
    let avoid = [];
    for (let attempt = 0; attempt < 3; attempt++) {
      explanation = await narrate(topic, country, facts || {}, chunks, avoid);
      violations = lintForbidden(explanation);
      if (!violations.length) {
        return Response.json({
          explanation,
          sources: chunks.map((c) => c.title),
          retries: attempt,
        });
      }
      avoid = [...new Set([...avoid, ...violations])]; // accumulate flagged phrases
    }

    return Response.json({
      explanation:
        "This panel is descriptive only. (The narration kept using prescriptive or " +
        "forward-looking language even after rewrites, so it was withheld.)",
      blocked: violations,
    });
  } catch (e) {
    return Response.json({ error: String(e.message || e) }, { status: 500 });
  }
}
