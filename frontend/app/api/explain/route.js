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
- Never give advice, recommendations, or predictions. No "buy/sell/should".
- Never say what will happen next. Describe what the data shows, in plain language.
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

async function narrate(topic, country, facts, chunks) {
  const context = chunks
    .map((c) => `### ${c.title}\n${c.content}`)
    .join("\n\n");
  const user = `TOPIC: ${topic} (${country})

FACTS (the only numbers you may state):
${JSON.stringify(facts, null, 2)}

CONTEXT (curated notes — use for explanation, not for new numbers):
${context}`;

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
      system: SYSTEM,
      messages: [{ role: "user", content: user }],
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
    const explanation = await narrate(topic, country, facts || {}, chunks);

    // Guardrail: block prescriptive / forward-looking phrasing.
    const violations = lintForbidden(explanation);
    if (violations.length) {
      return Response.json({
        explanation:
          "This panel is descriptive only. (The generated narration was blocked " +
          "for using prescriptive or forward-looking language.)",
        blocked: violations,
      });
    }
    return Response.json({ explanation, sources: chunks.map((c) => c.title) });
  } catch (e) {
    return Response.json({ error: String(e.message || e) }, { status: 500 });
  }
}
