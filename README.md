# TextAI API

> Pay-per-use text AI: summarize, extract keywords & translate — powered by USDC micropayments on Solana

**API:** https://textai-api.overtek.deno.net  
**Product Hunt:** https://www.producthunt.com/products/textai-api

---

## Why pay-per-use?

Most text AI APIs force monthly subscriptions. TextAI charges per call — you only pay for what you use. Perfect for side projects, batch jobs, or bursty workloads.

**1 USDC = 1,000 credits** (no subscription, no minimum)

| Endpoint | Cost |
|----------|------|
| Summarize | 10 credits/call |
| Keywords | 5 credits/call |
| Translate | 15 credits/call |

---

## Quick Start (2 minutes)

### 1. Create an API key (100 free demo credits)
```bash
curl -X POST https://textai-api.overtek.deno.net/keys/create
# {"apiKey":"sk_...","credits":100,"demo":true}
```

### 2. Summarize text
```bash
curl -X POST https://textai-api.overtek.deno.net/summarize \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "Your long article or document here...", "max_sentences": 3}'
```

### 3. Extract keywords
```bash
curl -X POST https://textai-api.overtek.deno.net/keywords \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "Your text here..."}'
```

### 4. Translate text
```bash
curl -X POST https://textai-api.overtek.deno.net/translate \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "targetLang": "fr"}'
```

### 5. Check your balance
```bash
curl https://textai-api.overtek.deno.net/credits/balance \
  -H "Authorization: Bearer YOUR_API_KEY"
```

---

## Buying Credits with USDC

```bash
# Step 1: Request a deposit address
curl -X POST https://textai-api.overtek.deno.net/credits/buy \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"usdc_amount": 1}'
# Returns: {"wallet":"<Solana address>","amount":1,"credits":1000}

# Step 2: Send USDC to the returned wallet address on Solana devnet

# Step 3: Confirm the transaction
curl -X POST https://textai-api.overtek.deno.net/credits/confirm \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tx_signature": "YOUR_TX_SIG"}'
```

---

## Complete Demo Script

Full bash walkthrough: https://gist.github.com/mokchou/6643f93ff59501f93e2e26c0db4374d1

---

## Cost Calculator

| Use case | Calls | Cost |
|----------|-------|------|
| 100 document summaries | 100 | $1 USDC |
| 200 keyword extractions | 200 | $1 USDC |
| 1,000 summaries | 1,000 | $10 USDC |
| Mixed batch (50% summarize, 50% keywords) | 200 | $0.75 USDC |

---

## Tech Stack

- **Runtime:** Deno Deploy (Hono framework)
- **Payments:** USDC on Solana devnet
- **Auth:** API key (Bearer token)
- **Format:** REST / JSON

---

## Links

- [Live API](https://textai-api.overtek.deno.net)
- [Product Hunt Launch](https://www.producthunt.com/products/textai-api)
- [DEV.to Article](https://dev.to/sbastien_lopez_399f3f6b8/pay-per-use-text-ai-api-with-usdc-micropayments-on-solana-57k2)
- [Demo Script (Gist)](https://gist.github.com/mokchou/6643f93ff59501f93e2e26c0db4374d1)
