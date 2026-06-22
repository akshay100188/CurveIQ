// Forbidden-language lint for L2 output. CurveIQ is strictly descriptive and
// retrospective: block prescriptive (advice / positioning) and forward-looking
// (prediction) phrasing. Patterns are deliberately tight so legitimate descriptive
// terms — "short rates", "long-term yield", "buyers" — do NOT trip the guard.
const PATTERNS = [
  // prescriptive / advice
  /\byou should\b/i,
  /\b(should|must|ought to)\s+(buy|sell|hold|consider|avoid|own|reduce|add)\b/i,
  /\bgo (long|short)\b/i,
  /\b(buy|sell|short|overweight|underweight)\s+(bonds|treasuries|gilts|g-secs?|equities|stocks|duration|the\s+\w+)\b/i,
  /\b(recommend|recommendation|advise|advice|suggest you)\b/i,
  // forward-looking / prediction
  /\b(will|won't|is going to|are going to)\s+(rise|fall|increase|decrease|drop|climb|rally|crash|continue|invert|steepen|flatten)\b/i,
  /\b(forecast|predict|prediction|projected to|likely to)\b/i,
  /\bexpect(s|ed)?\s+to\s+(rise|fall|increase|decrease|drop|climb|widen|narrow)\b/i,
  /\bin the (coming|next)\s+(days|weeks|months|quarters?|years?)\b/i,
  /\b(guarantee|certain to|bound to|set to)\b/i,
];

export function lintForbidden(text) {
  const hits = [];
  for (const re of PATTERNS) {
    const m = text.match(re);
    if (m) hits.push(m[0]);
  }
  return hits;
}
