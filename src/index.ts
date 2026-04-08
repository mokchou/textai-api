import { Hono } from "hono";
import { validateApiKey, createApiKey, getCredits, addCredits, deductCredits } from "./auth.ts";
import { summarize, extractKeywords, translate } from "./ai.ts";
import { createCreditBuyIntent, confirmUsdcPayment, getAgentWalletAddress } from "./solana.ts";
import { getConfig } from "./config.ts";

const app = new Hono();

const getApiKeyFromHeader = (req: Request): string | null => {
  const auth = req.headers.get("Authorization") ?? "";
  if (auth.startsWith("Bearer ")) return auth.slice(7).trim();
  return req.headers.get("X-API-Key");
};

// ---- Landing page ----
app.get("/landing", (c) => {
  const base = c.req.url.replace(/\/landing.*$/, "");
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TextAI API — AI Text Processing, Pay Per Use</title>
<meta name="description" content="AI-powered text summarization, keyword extraction, and translation via REST API. Pay per call with USDC — no subscription, no account. 100 free demo credits.">
<meta name="keywords" content="text summarization API, keyword extraction API, translation API, NLP API, pay per use AI, USDC payment, developer API">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://textai-api.overtek.deno.net/landing">
<meta property="og:type" content="website">
<meta property="og:url" content="https://textai-api.overtek.deno.net/landing">
<meta property="og:title" content="TextAI API — AI Text Processing, Pay Per Use">
<meta property="og:description" content="Summarize, extract keywords, and translate text via simple REST API. No subscription — pay only for what you use with USDC. Start free with 100 demo credits.">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="TextAI API — AI Text Processing, Pay Per Use">
<meta name="twitter:description" content="Summarize, extract keywords, and translate text via REST API. Pay per call with USDC. No subscription. 100 free credits to start.">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebAPI","name":"TextAI API","description":"AI-powered REST API for text summarization, keyword extraction and translation. Pay per call with USDC on Solana. No subscription.","url":"https://textai-api.overtek.deno.net","documentation":"https://textai-api.overtek.deno.net/landing#endpoints","provider":{"@type":"Organization","name":"TextAI API"},"offers":{"@type":"Offer","description":"Pay per API call with USDC on Solana. 100 free demo credits on sign-up. Summarize: 10 cr, Keywords: 5 cr, Translate: 15 cr."}}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #09090b;
  --surface: #111113;
  --border: #1f1f23;
  --border-hover: #2e2e35;
  --text: #fafafa;
  --muted: #71717a;
  --subtle: #3f3f46;
  --accent: #22d3ee;
  --accent-dim: rgba(34,211,238,.12);
  --green: #4ade80;
  --green-dim: rgba(74,222,128,.1);
  --amber: #fbbf24;
  --radius: 10px;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { font-family: 'Inter', -apple-system, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; font-size: 15px; }

/* NAV */
nav { position: sticky; top: 0; z-index: 50; background: rgba(9,9,11,.85); backdrop-filter: blur(12px); border-bottom: 1px solid var(--border); padding: 0 24px; height: 56px; display: flex; align-items: center; justify-content: space-between; }
.nav-logo { font-weight: 700; font-size: 1rem; letter-spacing: -.02em; color: var(--text); }
.nav-logo span { color: var(--accent); }
.nav-links { display: flex; gap: 24px; }
.nav-links a { color: var(--muted); text-decoration: none; font-size: .875rem; font-weight: 500; transition: color .15s; }
.nav-links a:hover { color: var(--text); }
.nav-cta { background: var(--text); color: var(--bg); padding: 6px 16px; border-radius: 6px; font-size: .875rem; font-weight: 600; text-decoration: none; transition: opacity .15s; }
.nav-cta:hover { opacity: .85; }

/* HERO */
.hero { padding: 96px 24px 80px; text-align: center; max-width: 720px; margin: 0 auto; position: relative; }
.hero::before { content: ''; position: absolute; inset: 0; background: radial-gradient(ellipse 60% 40% at 50% 0%, rgba(34,211,238,.08) 0%, transparent 70%); pointer-events: none; }
.eyebrow { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--border-hover); background: var(--surface); color: var(--muted); padding: 4px 12px; border-radius: 20px; font-size: .8rem; font-weight: 500; margin-bottom: 24px; letter-spacing: .01em; }
.eyebrow-dot { width: 6px; height: 6px; background: var(--accent); border-radius: 50%; }
h1 { font-size: clamp(2.2rem, 5vw, 3.4rem); font-weight: 700; letter-spacing: -.03em; line-height: 1.1; margin-bottom: 20px; }
h1 em { font-style: normal; color: var(--accent); }
.hero-sub { color: var(--muted); font-size: 1.1rem; max-width: 520px; margin: 0 auto 36px; line-height: 1.7; }
.hero-actions { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
.btn-primary { background: var(--accent); color: #000; padding: 11px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: .95rem; transition: opacity .15s; }
.btn-primary:hover { opacity: .85; }
.btn-secondary { background: var(--surface); color: var(--text); border: 1px solid var(--border-hover); padding: 11px 24px; border-radius: 8px; text-decoration: none; font-weight: 500; font-size: .95rem; transition: border-color .15s; }
.btn-secondary:hover { border-color: var(--subtle); }

/* STATS */
.stats { border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); padding: 32px 24px; display: flex; justify-content: center; gap: 0; flex-wrap: wrap; }
.stat { text-align: center; padding: 0 40px; border-right: 1px solid var(--border); }
.stat:last-child { border-right: none; }
.stat-val { font-size: 1.6rem; font-weight: 700; letter-spacing: -.03em; color: var(--text); }
.stat-label { font-size: .8rem; color: var(--muted); margin-top: 2px; }

/* SECTIONS */
.section { padding: 72px 24px; max-width: 1000px; margin: 0 auto; }
.section-label { font-size: .75rem; font-weight: 600; color: var(--accent); letter-spacing: .08em; text-transform: uppercase; margin-bottom: 12px; }
h2 { font-size: 1.75rem; font-weight: 700; letter-spacing: -.02em; margin-bottom: 8px; }
.section-sub { color: var(--muted); margin-bottom: 40px; }

/* PRICING CARDS */
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 28px; transition: border-color .2s; }
.card:hover { border-color: var(--border-hover); }
.card.featured { border-color: var(--accent); background: linear-gradient(145deg, rgba(34,211,238,.05) 0%, var(--surface) 60%); }
.card-icon { width: 40px; height: 40px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; margin-bottom: 16px; }
.card-icon.cyan { background: var(--accent-dim); }
.card-icon.green { background: var(--green-dim); }
.card-icon.amber { background: rgba(251,191,36,.1); }
.card-name { font-weight: 600; margin-bottom: 4px; }
.card-desc { color: var(--muted); font-size: .875rem; margin-bottom: 16px; line-height: 1.5; }
.card-price { font-size: 1.5rem; font-weight: 700; letter-spacing: -.02em; }
.card-price span { font-size: .875rem; font-weight: 400; color: var(--muted); }
.card-note { font-size: .8rem; color: var(--muted); margin-top: 6px; }

/* CODE BLOCKS */
pre { background: #0d0d10; border: 1px solid var(--border); border-radius: var(--radius); padding: 20px 24px; font-family: 'JetBrains Mono', monospace; font-size: .82rem; overflow-x: auto; line-height: 1.7; margin: 16px 0; }
.t-comment { color: #52525b; }
.t-key { color: #a5b4fc; }
.t-str { color: #86efac; }
.t-num { color: var(--amber); }
.t-cmd { color: var(--accent); }
.t-flag { color: #f9a8d4; }

/* STEPS */
.steps { counter-reset: steps; display: flex; flex-direction: column; gap: 32px; }
.step { display: flex; gap: 20px; align-items: flex-start; counter-increment: steps; }
.step-num { flex-shrink: 0; width: 32px; height: 32px; border-radius: 50%; background: var(--surface); border: 1px solid var(--border); display: flex; align-items: center; justify-content: center; font-size: .8rem; font-weight: 700; color: var(--accent); margin-top: 2px; }
.step-num::before { content: counter(steps); }
.step-body { flex: 1; }
.step-title { font-weight: 600; margin-bottom: 4px; }
.step-desc { color: var(--muted); font-size: .875rem; margin-bottom: 10px; }

/* ENDPOINTS */
.endpoint-table { border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
.ep-row { display: grid; grid-template-columns: 90px 1fr auto; gap: 16px; align-items: center; padding: 14px 20px; border-bottom: 1px solid var(--border); }
.ep-row:last-child { border-bottom: none; }
.ep-row:hover { background: var(--surface); }
.method-badge { font-family: 'JetBrains Mono', monospace; font-size: .72rem; font-weight: 700; padding: 3px 8px; border-radius: 5px; letter-spacing: .04em; text-align: center; }
.method-badge.post { background: var(--accent-dim); color: var(--accent); }
.method-badge.get { background: var(--green-dim); color: var(--green); }
.ep-path { font-family: 'JetBrains Mono', monospace; font-size: .84rem; color: var(--text); }
.ep-desc { font-size: .82rem; color: var(--muted); }
.ep-cost { font-size: .8rem; font-weight: 600; color: var(--amber); white-space: nowrap; }

/* FOOTER */
footer { border-top: 1px solid var(--border); padding: 40px 24px; text-align: center; }
.footer-chips { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; margin-bottom: 20px; }
.chip { background: var(--surface); border: 1px solid var(--border); color: var(--muted); font-size: .8rem; padding: 5px 12px; border-radius: 20px; }
.footer-copy { color: var(--muted); font-size: .85rem; }
.footer-copy a { color: var(--muted); text-decoration: underline; text-underline-offset: 3px; }
.footer-copy a:hover { color: var(--text); }
</style>
</head>
<body>

<nav>
  <div class="nav-logo">Text<span>AI</span></div>
  <div class="nav-links">
    <a href="#pricing">Pricing</a>
    <a href="#quickstart">Docs</a>
    <a href="#endpoints">API</a>
  </div>
  <a href="#quickstart" class="nav-cta">Get API Key</a>
</nav>

<div class="hero">
  <div class="eyebrow"><span class="eyebrow-dot"></span> Now with 100 free demo credits</div>
  <h1>AI text processing,<br><em>pay per call</em></h1>
  <p class="hero-sub">Summarize, extract keywords, and translate text via a simple REST API. No subscription — pay only for what you use with USDC.</p>
  <div class="hero-actions">
    <a href="#quickstart" class="btn-primary">Get started free</a>
    <a href="#endpoints" class="btn-secondary">View API reference</a>
  </div>
</div>

<div class="stats">
  <div class="stat"><div class="stat-val">3</div><div class="stat-label">AI endpoints</div></div>
  <div class="stat"><div class="stat-val">100</div><div class="stat-label">Free credits</div></div>
  <div class="stat"><div class="stat-val">10+</div><div class="stat-label">Languages</div></div>
  <div class="stat"><div class="stat-val">USDC</div><div class="stat-label">Top-up currency</div></div>
</div>

<div class="section" id="pricing">
  <div class="section-label">Pricing</div>
  <h2>Simple, per-call pricing</h2>
  <p class="section-sub">1 USDC = 1,000 credits &nbsp;·&nbsp; No expiry &nbsp;·&nbsp; Minimum top-up: 1 USDC</p>
  <div class="cards">
    <div class="card featured">
      <div class="card-icon cyan">📝</div>
      <div class="card-name">Summarize</div>
      <div class="card-desc">Compress any text to 1–5 clear sentences using AI.</div>
      <div class="card-price">10 <span>credits / call</span></div>
      <div class="card-note">≈ 100 calls per USDC</div>
    </div>
    <div class="card">
      <div class="card-icon green">🔑</div>
      <div class="card-name">Keywords</div>
      <div class="card-desc">Extract the most relevant keywords and phrases from any text.</div>
      <div class="card-price">5 <span>credits / call</span></div>
      <div class="card-note">≈ 200 calls per USDC</div>
    </div>
    <div class="card">
      <div class="card-icon amber">🌍</div>
      <div class="card-name">Translate</div>
      <div class="card-desc">Translate to EN, FR, ES, DE, IT, PT, RU, JA, ZH, AR.</div>
      <div class="card-price">15 <span>credits / call</span></div>
      <div class="card-note">≈ 66 calls per USDC</div>
    </div>
  </div>
</div>

<div class="section" id="quickstart">
  <div class="section-label">Quick start</div>
  <h2>Up and running in 60 seconds</h2>
  <p class="section-sub">No account needed — get a key and start calling the API immediately.</p>
  <div class="steps">
    <div class="step">
      <div class="step-num"></div>
      <div class="step-body">
        <div class="step-title">Create a free API key</div>
        <div class="step-desc">Includes 100 demo credits — no wallet, no sign-up.</div>
<pre><span class="t-cmd">curl</span> <span class="t-flag">-X POST</span> ${base}/keys/create</pre>
        <pre><span class="t-comment">// response</span>
{ <span class="t-key">"apiKey"</span>: <span class="t-str">"sk_abc123..."</span>, <span class="t-key">"credits"</span>: <span class="t-num">100</span>, <span class="t-key">"demo"</span>: <span class="t-num">true</span> }</pre>
      </div>
    </div>
    <div class="step">
      <div class="step-num"></div>
      <div class="step-body">
        <div class="step-title">Call an endpoint</div>
        <div class="step-desc">Pass your key as a Bearer token.</div>
<pre><span class="t-cmd">curl</span> <span class="t-flag">-X POST</span> ${base}/summarize \\
  <span class="t-flag">-H</span> <span class="t-str">"Authorization: Bearer sk_abc123..."</span> \\
  <span class="t-flag">-H</span> <span class="t-str">"Content-Type: application/json"</span> \\
  <span class="t-flag">-d</span> <span class="t-str">'{"text": "Your long text...", "maxSentences": 3}'</span></pre>
      </div>
    </div>
    <div class="step">
      <div class="step-num"></div>
      <div class="step-body">
        <div class="step-title">Top up with USDC when you need more</div>
        <div class="step-desc">Send USDC on Solana — credits appear instantly after confirmation.</div>
<pre><span class="t-cmd">curl</span> <span class="t-flag">-X POST</span> ${base}/credits/buy \\
  <span class="t-flag">-H</span> <span class="t-str">"Authorization: Bearer sk_abc123..."</span> \\
  <span class="t-flag">-d</span> <span class="t-str">'{"amount": 5}'</span></pre>
      </div>
    </div>
  </div>
</div>

<div class="section" id="endpoints">
  <div class="section-label">API Reference</div>
  <h2>All endpoints</h2>
  <p class="section-sub">Base URL: <code style="font-family:'JetBrains Mono',monospace;font-size:.85rem;color:var(--accent)">${base}</code></p>
  <div class="endpoint-table">
    <div class="ep-row"><span class="method-badge post">POST</span><div><div class="ep-path">/keys/create</div><div class="ep-desc">Create API key — returns 100 free credits</div></div><span class="ep-cost">free</span></div>
    <div class="ep-row"><span class="method-badge get">GET</span><div><div class="ep-path">/credits/balance</div><div class="ep-desc">Check remaining credits</div></div><span></span></div>
    <div class="ep-row"><span class="method-badge post">POST</span><div><div class="ep-path">/credits/buy</div><div class="ep-desc">Get Solana wallet for USDC top-up &nbsp;<code style="font-size:.78rem;color:var(--muted)">{"amount": 5}</code></div></div><span></span></div>
    <div class="ep-row"><span class="method-badge post">POST</span><div><div class="ep-path">/credits/confirm</div><div class="ep-desc">Confirm transaction &nbsp;<code style="font-size:.78rem;color:var(--muted)">{"txSignature": "..."}</code></div></div><span></span></div>
    <div class="ep-row"><span class="method-badge post">POST</span><div><div class="ep-path">/summarize</div><div class="ep-desc">Summarize text &nbsp;<code style="font-size:.78rem;color:var(--muted)">{"text":"...","maxSentences":3}</code></div></div><span class="ep-cost">10 cr</span></div>
    <div class="ep-row"><span class="method-badge post">POST</span><div><div class="ep-path">/keywords</div><div class="ep-desc">Extract keywords &nbsp;<code style="font-size:.78rem;color:var(--muted)">{"text":"...","maxKeywords":10}</code></div></div><span class="ep-cost">5 cr</span></div>
    <div class="ep-row"><span class="method-badge post">POST</span><div><div class="ep-path">/translate</div><div class="ep-desc">Translate text &nbsp;<code style="font-size:.78rem;color:var(--muted)">{"text":"...","targetLang":"fr"}</code></div></div><span class="ep-cost">15 cr</span></div>
  </div>
</div>

<footer>
  <div class="footer-chips">
    <span class="chip">◎ Solana devnet</span>
    <span class="chip">Llama 3 via Groq</span>
    <span class="chip">Deno Deploy</span>
  </div>
  <p class="footer-copy">TextAI API &nbsp;·&nbsp; <a href="${base}/">API status</a> &nbsp;·&nbsp; <a href="${base}/blog/add-ai-text-processing-in-30-seconds">Tutorial</a> &nbsp;·&nbsp; <a href="${base}/sitemap.xml">Sitemap</a></p>
</footer>

</body>
</html>`;
  return c.html(html);
});

// ---- Root: redirect browsers to landing page, serve JSON spec for curl/API clients ----
app.get("/", (c) => {
  const accept = c.req.header("accept") ?? "";
  if (accept.includes("text/html")) {
    return c.redirect("/landing", 302);
  }
  const config = getConfig();
  const network = config.solanaRpcUrl.includes("devnet") ? "devnet" : "mainnet-beta";
  return c.json({
    name: "micro-saas-api",
    version: "0.1.0",
    description: "AI text processing API — pay per use with USDC on Solana",
    network,
    ai_engine: config.groqApiKey ? "groq" : "rule-based",
    endpoints: {
      "POST /keys/create": "Create a new API key (free, 100 demo credits included)",
      "GET /credits/balance": "Check your credit balance",
      "POST /credits/buy": "Get wallet address to top up credits with USDC",
      "POST /credits/confirm": "Confirm USDC payment and receive credits",
      "POST /summarize": "Summarize text (10 credits)",
      "POST /keywords": "Extract keywords (5 credits)",
      "POST /translate": "Translate text (15 credits)",
      "GET /agent/wallet": "Agent wallet public address",
    },
    pricing: { "1 USDC": "1,000 credits", summarize: "10 credits", keywords: "5 credits", translate: "15 credits" },
  });
});

// ---- Create API key ----
app.post("/keys/create", async (c) => {
  try {
    // Extract client IP for demo key dedup (best effort)
    const clientIp =
      c.req.raw.headers.get("cf-connecting-ip") ??
      c.req.raw.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
      undefined;

    const result = await createApiKey(clientIp);

    if (result.alreadyHasDemo) {
      const credits = await getCredits(result.apiKey);
      return c.json({
        apiKey: result.apiKey,
        credits: credits ?? 0,
        demo: true,
        message: "Demo key already exists for your IP. Use this key to test. Top up with USDC at POST /credits/buy for more credits.",
      });
    }

    return c.json({
      apiKey: result.apiKey,
      credits: 100,
      demo: true,
      message: "API key created with 100 free demo credits (~10 summarize calls). Top up with USDC at POST /credits/buy for more.",
    });
  } catch (e: any) {
    return c.json({ error: e.message }, 500);
  }
});

// ---- Credit balance ----
app.get("/credits/balance", async (c) => {
  const apiKey = getApiKeyFromHeader(c.req.raw);
  if (!apiKey) return c.json({ error: "Missing API key. Use Authorization: Bearer sk_... header" }, 401);
  const credits = await getCredits(apiKey);
  if (credits === null) return c.json({ error: "API key not found" }, 404);
  return c.json({ credits });
});

// ---- Buy credits ----
app.post("/credits/buy", async (c) => {
  const apiKey = getApiKeyFromHeader(c.req.raw);
  if (!apiKey) return c.json({ error: "Missing API key" }, 401);

  let body: any;
  try { body = await c.req.json(); } catch { return c.json({ error: "Invalid JSON body" }, 400); }

  const usdcAmount = parseFloat(body?.amount ?? body?.usdcAmount ?? "1");
  if (isNaN(usdcAmount) || usdcAmount < 1) return c.json({ error: "Invalid amount. Minimum 1 USDC." }, 400);

  try {
    const intent = await createCreditBuyIntent(apiKey, usdcAmount);
    return c.json(intent);
  } catch (e: any) {
    return c.json({ error: e.message }, 400);
  }
});

// ---- Confirm USDC payment ----
app.post("/credits/confirm", async (c) => {
  const apiKey = getApiKeyFromHeader(c.req.raw);
  if (!apiKey) return c.json({ error: "Missing API key" }, 401);

  let body: any;
  try { body = await c.req.json(); } catch { return c.json({ error: "Invalid JSON body" }, 400); }

  const txSignature = body?.txSignature;
  if (!txSignature) return c.json({ error: "Missing txSignature" }, 400);

  try {
    const result = await confirmUsdcPayment(txSignature, apiKey);
    if (!result.success) return c.json({ error: result.error }, 400);
    const newBalance = await addCredits(apiKey, result.creditsAdded!);
    return c.json({ success: true, creditsAdded: result.creditsAdded, newBalance });
  } catch (e: any) {
    return c.json({ error: e.message }, 500);
  }
});

// ---- Summarize ----
app.post("/summarize", async (c) => {
  const apiKey = getApiKeyFromHeader(c.req.raw);
  if (!apiKey) return c.json({ error: "Missing API key" }, 401);

  const COST = 10;
  const validation = await validateApiKey(apiKey, COST);
  if (!validation.valid) return c.json({ error: validation.error, credits: validation.credits }, 402);

  let body: any;
  try { body = await c.req.json(); } catch { return c.json({ error: "Invalid JSON body" }, 400); }

  const { text, maxSentences } = body ?? {};
  if (!text || typeof text !== "string") return c.json({ error: "Missing or invalid 'text' field" }, 400);

  try {
    const result = await summarize(text, maxSentences ?? 3);
    await deductCredits(apiKey, COST);
    return c.json({ ...result, creditsUsed: COST, creditsRemaining: validation.credits! - COST });
  } catch (e: any) {
    return c.json({ error: e.message }, 400);
  }
});

// ---- Extract keywords ----
app.post("/keywords", async (c) => {
  const apiKey = getApiKeyFromHeader(c.req.raw);
  if (!apiKey) return c.json({ error: "Missing API key" }, 401);

  const COST = 5;
  const validation = await validateApiKey(apiKey, COST);
  if (!validation.valid) return c.json({ error: validation.error, credits: validation.credits }, 402);

  let body: any;
  try { body = await c.req.json(); } catch { return c.json({ error: "Invalid JSON body" }, 400); }

  const { text, maxKeywords } = body ?? {};
  if (!text || typeof text !== "string") return c.json({ error: "Missing or invalid 'text' field" }, 400);

  try {
    const result = await extractKeywords(text, maxKeywords ?? 10);
    await deductCredits(apiKey, COST);
    return c.json({ ...result, creditsUsed: COST, creditsRemaining: validation.credits! - COST });
  } catch (e: any) {
    return c.json({ error: e.message }, 400);
  }
});

// ---- Translate ----
app.post("/translate", async (c) => {
  const apiKey = getApiKeyFromHeader(c.req.raw);
  if (!apiKey) return c.json({ error: "Missing API key" }, 401);

  const COST = 15;
  const validation = await validateApiKey(apiKey, COST);
  if (!validation.valid) return c.json({ error: validation.error, credits: validation.credits }, 402);

  let body: any;
  try { body = await c.req.json(); } catch { return c.json({ error: "Invalid JSON body" }, 400); }

  const { text, targetLang } = body ?? {};
  if (!text || typeof text !== "string") return c.json({ error: "Missing or invalid 'text' field" }, 400);
  if (!targetLang || typeof targetLang !== "string") {
    return c.json({ error: "Missing 'targetLang'. Supported: en, fr, es, de, it, pt, ru, ja, zh, ar" }, 400);
  }

  try {
    const result = await translate(text, targetLang);
    await deductCredits(apiKey, COST);
    return c.json({ ...result, creditsUsed: COST, creditsRemaining: validation.credits! - COST });
  } catch (e: any) {
    return c.json({ error: e.message }, 400);
  }
});

// ---- Agent wallet ----
app.get("/agent/wallet", async (c) => {
  try {
    const config = getConfig();
    const wallet = await getAgentWalletAddress();
    const network = config.solanaRpcUrl.includes("devnet") ? "devnet" : "mainnet-beta";
    return c.json({ wallet, network, usdcMint: config.usdcMint });
  } catch (e: any) {
    return c.json({ error: e.message }, 500);
  }
});

// ---- robots.txt ----
app.get("/robots.txt", (c) => {
  const txt = `User-agent: *
Allow: /landing
Allow: /blog
Allow: /sitemap.xml
Disallow: /keys/
Disallow: /credits/
Disallow: /agent/

Sitemap: https://textai-api.overtek.deno.net/sitemap.xml
`;
  return c.text(txt);
});

// ---- sitemap.xml ----
app.get("/sitemap.xml", (c) => {
  const base = "https://textai-api.overtek.deno.net";
  const today = new Date().toISOString().slice(0, 10);
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>${base}/landing</loc><lastmod>${today}</lastmod><priority>1.0</priority><changefreq>monthly</changefreq></url>
  <url><loc>${base}/blog/add-ai-text-processing-in-30-seconds</loc><lastmod>${today}</lastmod><priority>0.8</priority><changefreq>monthly</changefreq></url>
  <url><loc>${base}/blog</loc><lastmod>${today}</lastmod><priority>0.6</priority><changefreq>weekly</changefreq></url>
</urlset>`;
  return c.body(xml, 200, { "Content-Type": "application/xml" });
});

// ---- Blog index ----
app.get("/blog", (c) => {
  const base = c.req.url.replace(/\/blog.*$/, "");
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TextAI API Blog — Developer Tutorials</title>
<meta name="description" content="Tutorials and guides for integrating AI text processing into your app using TextAI API.">
<link rel="canonical" href="https://textai-api.overtek.deno.net/blog">
<meta property="og:title" content="TextAI API Blog — Developer Tutorials">
<meta property="og:description" content="Tutorials and guides for integrating AI text processing into your app using TextAI API.">
<meta property="og:type" content="website">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{--bg:#09090b;--surface:#111113;--border:#1f1f23;--text:#fafafa;--muted:#71717a;--accent:#22d3ee;--radius:10px}
*{margin:0;padding:0;box-sizing:border-box}body{font-family:'Inter',-apple-system,sans-serif;background:var(--bg);color:var(--text);line-height:1.6;font-size:15px}
nav{position:sticky;top:0;z-index:50;background:rgba(9,9,11,.85);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);padding:0 24px;height:56px;display:flex;align-items:center;justify-content:space-between}
.nav-logo{font-weight:700;font-size:1rem;letter-spacing:-.02em}.nav-logo span{color:var(--accent)}
.nav-links a{color:var(--muted);text-decoration:none;font-size:.875rem;font-weight:500;margin-left:24px;transition:color .15s}.nav-links a:hover{color:var(--text)}
.container{max-width:760px;margin:0 auto;padding:64px 24px}
h1{font-size:2rem;font-weight:700;letter-spacing:-.03em;margin-bottom:8px}
.subtitle{color:var(--muted);margin-bottom:48px}
.post-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:28px;margin-bottom:20px;transition:border-color .2s;text-decoration:none;display:block}
.post-card:hover{border-color:#2e2e35}
.post-tag{font-size:.75rem;font-weight:600;color:var(--accent);letter-spacing:.08em;text-transform:uppercase;margin-bottom:10px}
.post-title{font-size:1.2rem;font-weight:600;color:var(--text);margin-bottom:6px}
.post-desc{color:var(--muted);font-size:.9rem}
.post-meta{font-size:.8rem;color:var(--muted);margin-top:12px}
footer{border-top:1px solid var(--border);padding:32px 24px;text-align:center;color:var(--muted);font-size:.85rem}
footer a{color:var(--muted);text-decoration:underline;text-underline-offset:3px}footer a:hover{color:var(--text)}
</style>
</head>
<body>
<nav>
  <div class="nav-logo">Text<span>AI</span></div>
  <div class="nav-links"><a href="${base}/landing">Home</a><a href="${base}/landing#endpoints">API Docs</a></div>
</nav>
<div class="container">
  <h1>Developer Blog</h1>
  <p class="subtitle">Tutorials, guides, and ideas for building with TextAI API.</p>
  <a href="${base}/blog/add-ai-text-processing-in-30-seconds" class="post-card">
    <div class="post-tag">Tutorial</div>
    <div class="post-title">How to add AI text processing to your app in 30 seconds</div>
    <div class="post-desc">A hands-on guide: get an API key, call summarize/keywords/translate, and integrate into your project — all in one sitting.</div>
    <div class="post-meta">April 2026 &nbsp;·&nbsp; 5 min read</div>
  </a>
</div>
<footer><a href="${base}/landing">TextAI API</a> &nbsp;·&nbsp; <a href="${base}/sitemap.xml">Sitemap</a></footer>
</body>
</html>`;
  return c.html(html);
});

// ---- Blog post: tutorial ----
app.get("/blog/add-ai-text-processing-in-30-seconds", (c) => {
  const base = c.req.url.replace(/\/blog.*$/, "");
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>How to add AI text processing to your app in 30 seconds — TextAI API</title>
<meta name="description" content="Step-by-step guide to integrating AI summarization, keyword extraction, and translation into any app using TextAI API. No subscription needed.">
<meta name="keywords" content="add AI to app, text summarization tutorial, keyword extraction API tutorial, NLP integration guide, pay per use AI API">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://textai-api.overtek.deno.net/blog/add-ai-text-processing-in-30-seconds">
<meta property="og:title" content="How to add AI text processing to your app in 30 seconds">
<meta property="og:description" content="Step-by-step guide: get an API key, call summarize/keywords/translate, integrate into your project. No subscription — pay per call with USDC.">
<meta property="og:type" content="article">
<meta property="og:url" content="https://textai-api.overtek.deno.net/blog/add-ai-text-processing-in-30-seconds">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="How to add AI text processing to your app in 30 seconds">
<meta name="twitter:description" content="Get a free API key, call AI endpoints, pay per use with USDC. No subscription needed.">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"TechArticle","headline":"How to add AI text processing to your app in 30 seconds","description":"Step-by-step tutorial for integrating TextAI API into any application. Covers summarization, keyword extraction, and translation endpoints.","url":"https://textai-api.overtek.deno.net/blog/add-ai-text-processing-in-30-seconds","datePublished":"2026-04-08","author":{"@type":"Organization","name":"TextAI API"},"publisher":{"@type":"Organization","name":"TextAI API"}}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{--bg:#09090b;--surface:#111113;--border:#1f1f23;--border-hover:#2e2e35;--text:#fafafa;--muted:#71717a;--accent:#22d3ee;--green:#4ade80;--amber:#fbbf24;--radius:10px}
*{margin:0;padding:0;box-sizing:border-box}body{font-family:'Inter',-apple-system,sans-serif;background:var(--bg);color:var(--text);line-height:1.7;font-size:15px}
nav{position:sticky;top:0;z-index:50;background:rgba(9,9,11,.85);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);padding:0 24px;height:56px;display:flex;align-items:center;justify-content:space-between}
.nav-logo{font-weight:700;font-size:1rem;letter-spacing:-.02em}.nav-logo span{color:var(--accent)}
.nav-links a{color:var(--muted);text-decoration:none;font-size:.875rem;font-weight:500;margin-left:24px;transition:color .15s}.nav-links a:hover{color:var(--text)}
article{max-width:720px;margin:0 auto;padding:64px 24px 96px}
.post-tag{font-size:.75rem;font-weight:600;color:var(--accent);letter-spacing:.08em;text-transform:uppercase;margin-bottom:16px}
h1{font-size:clamp(1.8rem,4vw,2.6rem);font-weight:700;letter-spacing:-.03em;line-height:1.15;margin-bottom:16px}
.post-meta{color:var(--muted);font-size:.875rem;margin-bottom:48px;padding-bottom:32px;border-bottom:1px solid var(--border)}
h2{font-size:1.3rem;font-weight:700;letter-spacing:-.02em;margin:48px 0 16px}
p{color:#d4d4d8;margin-bottom:20px}
pre{background:#0d0d10;border:1px solid var(--border);border-radius:var(--radius);padding:20px 24px;font-family:'JetBrains Mono',monospace;font-size:.82rem;overflow-x:auto;line-height:1.7;margin:16px 0 24px}
.t-comment{color:#52525b}.t-key{color:#a5b4fc}.t-str{color:#86efac}.t-num{color:var(--amber)}.t-cmd{color:var(--accent)}.t-flag{color:#f9a8d4}
code{font-family:'JetBrains Mono',monospace;font-size:.85em;background:var(--surface);border:1px solid var(--border);padding:2px 6px;border-radius:4px;color:var(--accent)}
.callout{background:var(--surface);border:1px solid var(--border);border-left:3px solid var(--accent);border-radius:var(--radius);padding:16px 20px;margin:24px 0}
.callout p{margin:0;color:var(--muted);font-size:.9rem}
.lang-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:8px;margin:16px 0 24px}
.lang-chip{background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:6px 10px;font-size:.8rem;text-align:center;color:var(--muted)}
.cta-box{background:linear-gradient(135deg,rgba(34,211,238,.08) 0%,var(--surface) 100%);border:1px solid var(--accent);border-radius:var(--radius);padding:32px;text-align:center;margin-top:64px}
.cta-box h3{font-size:1.2rem;font-weight:700;margin-bottom:8px}
.cta-box p{color:var(--muted);margin-bottom:20px}
.btn{background:var(--accent);color:#000;padding:10px 24px;border-radius:8px;text-decoration:none;font-weight:600;font-size:.9rem;display:inline-block;transition:opacity .15s}.btn:hover{opacity:.85}
footer{border-top:1px solid var(--border);padding:32px 24px;text-align:center;color:var(--muted);font-size:.85rem}
footer a{color:var(--muted);text-decoration:underline;text-underline-offset:3px}footer a:hover{color:var(--text)}
</style>
</head>
<body>
<nav>
  <div class="nav-logo">Text<span>AI</span></div>
  <div class="nav-links"><a href="${base}/blog">Blog</a><a href="${base}/landing">Home</a><a href="${base}/landing#endpoints">API Docs</a></div>
</nav>
<article>
  <div class="post-tag">Tutorial</div>
  <h1>How to add AI text processing to your app in 30 seconds</h1>
  <div class="post-meta">April 8, 2026 &nbsp;·&nbsp; 5 min read &nbsp;·&nbsp; <a href="${base}/landing">TextAI API</a></div>

  <p>Most AI text APIs require a credit card, an account, and a 10-step onboarding flow before you can make a single request. TextAI API skips all of that: you get an API key in one <code>curl</code> call, and you only pay for calls you actually make — using USDC on Solana, with a minimum of $0.005 per request.</p>

  <p>This guide walks you through the complete flow: get a key, call all three endpoints, and see how to wire it into a real application.</p>

  <h2>Step 1 — Get a free API key</h2>
  <p>No sign-up, no email. One POST request returns your key with 100 demo credits pre-loaded.</p>
<pre><span class="t-cmd">curl</span> <span class="t-flag">-X POST</span> ${base}/keys/create</pre>
<pre><span class="t-comment">// Response</span>
{
  <span class="t-key">"apiKey"</span>: <span class="t-str">"sk_abc123..."</span>,
  <span class="t-key">"credits"</span>: <span class="t-num">100</span>,
  <span class="t-key">"demo"</span>: <span class="t-num">true</span>,
  <span class="t-key">"message"</span>: <span class="t-str">"API key created with 100 free demo credits"</span>
}</pre>
  <div class="callout"><p>100 demo credits = 10 summarize calls, 20 keyword calls, or 6 translate calls. Enough to test the full API before spending a cent.</p></div>

  <h2>Step 2 — Summarize text</h2>
  <p>Pass any text and a max sentence count. The API returns a condensed summary using Llama 3 via Groq.</p>
<pre><span class="t-cmd">curl</span> <span class="t-flag">-X POST</span> ${base}/summarize \\
  <span class="t-flag">-H</span> <span class="t-str">"Authorization: Bearer sk_abc123..."</span> \\
  <span class="t-flag">-H</span> <span class="t-str">"Content-Type: application/json"</span> \\
  <span class="t-flag">-d</span> <span class="t-str">'{"text": "Artificial intelligence is transforming industries from healthcare to finance...", "maxSentences": 2}'</span></pre>
<pre><span class="t-comment">// Response (10 credits deducted)</span>
{
  <span class="t-key">"summary"</span>: <span class="t-str">"AI is rapidly transforming major industries. Adoption is accelerating across healthcare, finance, and logistics."</span>,
  <span class="t-key">"creditsUsed"</span>: <span class="t-num">10</span>,
  <span class="t-key">"creditsRemaining"</span>: <span class="t-num">90</span>
}</pre>

  <h2>Step 3 — Extract keywords</h2>
  <p>Identify the most relevant terms from any block of text. Useful for tagging, search indexing, or content analysis.</p>
<pre><span class="t-cmd">curl</span> <span class="t-flag">-X POST</span> ${base}/keywords \\
  <span class="t-flag">-H</span> <span class="t-str">"Authorization: Bearer sk_abc123..."</span> \\
  <span class="t-flag">-H</span> <span class="t-str">"Content-Type: application/json"</span> \\
  <span class="t-flag">-d</span> <span class="t-str">'{"text": "Machine learning models require large datasets for training...", "maxKeywords": 5}'</span></pre>
<pre><span class="t-comment">// Response (5 credits deducted)</span>
{
  <span class="t-key">"keywords"</span>: [<span class="t-str">"machine learning"</span>, <span class="t-str">"datasets"</span>, <span class="t-str">"training"</span>, <span class="t-str">"models"</span>, <span class="t-str">"neural networks"</span>],
  <span class="t-key">"creditsUsed"</span>: <span class="t-num">5</span>,
  <span class="t-key">"creditsRemaining"</span>: <span class="t-num">85</span>
}</pre>

  <h2>Step 4 — Translate text</h2>
  <p>Translate to any of 10 supported languages. Pass <code>targetLang</code> as a 2-letter ISO code.</p>
  <div class="lang-grid">
    <div class="lang-chip">en</div><div class="lang-chip">fr</div><div class="lang-chip">es</div>
    <div class="lang-chip">de</div><div class="lang-chip">it</div><div class="lang-chip">pt</div>
    <div class="lang-chip">ru</div><div class="lang-chip">ja</div><div class="lang-chip">zh</div>
    <div class="lang-chip">ar</div>
  </div>
<pre><span class="t-cmd">curl</span> <span class="t-flag">-X POST</span> ${base}/translate \\
  <span class="t-flag">-H</span> <span class="t-str">"Authorization: Bearer sk_abc123..."</span> \\
  <span class="t-flag">-H</span> <span class="t-str">"Content-Type: application/json"</span> \\
  <span class="t-flag">-d</span> <span class="t-str">'{"text": "Hello, world!", "targetLang": "fr"}'</span></pre>
<pre><span class="t-comment">// Response (15 credits deducted)</span>
{
  <span class="t-key">"translated"</span>: <span class="t-str">"Bonjour, le monde !"</span>,
  <span class="t-key">"targetLang"</span>: <span class="t-str">"fr"</span>,
  <span class="t-key">"creditsUsed"</span>: <span class="t-num">15</span>,
  <span class="t-key">"creditsRemaining"</span>: <span class="t-num">70</span>
}</pre>

  <h2>Check your credit balance</h2>
<pre><span class="t-cmd">curl</span> ${base}/credits/balance \\
  <span class="t-flag">-H</span> <span class="t-str">"Authorization: Bearer sk_abc123..."</span></pre>
<pre>{ <span class="t-key">"credits"</span>: <span class="t-num">70</span> }</pre>

  <h2>Top up with USDC when you need more</h2>
  <p>When your demo credits run out, top up with USDC on Solana devnet (free test tokens available from any Solana faucet).</p>
<pre><span class="t-comment"># Step 1: get a deposit wallet</span>
<span class="t-cmd">curl</span> <span class="t-flag">-X POST</span> ${base}/credits/buy \\
  <span class="t-flag">-H</span> <span class="t-str">"Authorization: Bearer sk_abc123..."</span> \\
  <span class="t-flag">-H</span> <span class="t-str">"Content-Type: application/json"</span> \\
  <span class="t-flag">-d</span> <span class="t-str">'{"amount": 1}'</span>
<span class="t-comment"># → {"wallet":"7xKz...","memo":"pay_...","creditsToReceive":1000}</span>

<span class="t-comment"># Step 2: send 1 devnet USDC to the wallet with the memo</span>
<span class="t-comment"># (get free devnet USDC at https://spl-token-faucet.com/?token-name=USDC-Dev)</span>

<span class="t-comment"># Step 3: confirm</span>
<span class="t-cmd">curl</span> <span class="t-flag">-X POST</span> ${base}/credits/confirm \\
  <span class="t-flag">-H</span> <span class="t-str">"Authorization: Bearer sk_abc123..."</span> \\
  <span class="t-flag">-H</span> <span class="t-str">"Content-Type: application/json"</span> \\
  <span class="t-flag">-d</span> <span class="t-str">'{"txSignature": "5HYxK..."}'</span></pre>

  <h2>Integrating into your app</h2>
  <p>Here's how to call the summarize endpoint from JavaScript (Node.js or browser):</p>
<pre><span class="t-comment">// JavaScript / Node.js</span>
<span class="t-key">const</span> res = <span class="t-key">await</span> fetch(<span class="t-str">"${base}/summarize"</span>, {
  method: <span class="t-str">"POST"</span>,
  headers: {
    <span class="t-str">"Authorization"</span>: <span class="t-str">"Bearer sk_abc123..."</span>,
    <span class="t-str">"Content-Type"</span>: <span class="t-str">"application/json"</span>,
  },
  body: JSON.stringify({ text: longArticle, maxSentences: <span class="t-num">3</span> }),
});
<span class="t-key">const</span> { summary, creditsRemaining } = <span class="t-key">await</span> res.json();</pre>

  <p>And from Python:</p>
<pre><span class="t-comment"># Python</span>
<span class="t-key">import</span> requests

response = requests.post(
    <span class="t-str">"${base}/keywords"</span>,
    headers={<span class="t-str">"Authorization"</span>: <span class="t-str">"Bearer sk_abc123..."</span>},
    json={<span class="t-str">"text"</span>: article_text, <span class="t-str">"maxKeywords"</span>: <span class="t-num">10</span>},
)
keywords = response.json()[<span class="t-str">"keywords"</span>]</pre>

  <div class="callout"><p><strong>Error handling:</strong> if you're out of credits, the API returns HTTP 402 with <code>{"error": "Insufficient credits"}</code>. Check <code>creditsRemaining</code> in each response to proactively top up.</p></div>

  <h2>Pricing at a glance</h2>
  <p>1 USDC = 1,000 credits. No subscription, no expiry, no minimum commitment beyond $1 per top-up.</p>
<pre><span class="t-comment">// Cost per call</span>
{ <span class="t-key">"summarize"</span>: <span class="t-str">"10 credits (~$0.01)"</span>, <span class="t-key">"keywords"</span>: <span class="t-str">"5 credits (~$0.005)"</span>, <span class="t-key">"translate"</span>: <span class="t-str">"15 credits (~$0.015)"</span> }</pre>

  <div class="cta-box">
    <h3>Ready to try it?</h3>
    <p>Get 100 free credits now — no account, no email, no credit card.</p>
    <a href="${base}/landing#quickstart" class="btn">Get started free →</a>
  </div>
</article>
<footer><a href="${base}/blog">Blog</a> &nbsp;·&nbsp; <a href="${base}/landing">TextAI API</a> &nbsp;·&nbsp; <a href="${base}/landing#endpoints">API Reference</a></footer>
</body>
</html>`;
  return c.html(html);
});

// ---- Serve ----
const port = parseInt(Deno.env.get("PORT") ?? "8000");
console.log(`micro-saas-api listening on http://localhost:${port}`);
Deno.serve({ port }, app.fetch);
