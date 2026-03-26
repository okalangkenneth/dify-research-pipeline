# NicheIQ — AI Market Intelligence for Etsy Sellers

> *Know before you build.* Enter a product idea. NicheIQ scrapes live Etsy data, runs it through three specialised AI agents, and returns a complete market brief in under 60 seconds.

**Portfolio Project 3** — Multi-agent AI pipeline built on [Dify](https://github.com/langgenius/dify) + Docker.

🔗 [Live Demo](http://localhost/nicheiq.html) · [Project 1: Etsy Toolkit](https://github.com/okalangkenneth/dify-etsy-toolkit) · [Project 2: Support Agent](https://github.com/okalangkenneth/dify-customer-support-agent)

---

## What it does

A seller types "ADHD daily planner" and gets back:

- ✅ **GO / NO-GO verdict** with rationale
- 📊 **Opportunity score** (0–10) based on real market signals
- 💰 **Recommended price** and saturation risk level
- 🏷️ **3 Etsy title options** (SEO-optimised, 3–14 words)
- 📝 **Product description** ready to paste
- 🔖 **13 Etsy tags** (each ≤20 chars, copy-all button)
- 🎨 **Mockup style** and format recommendation
- ⚡ **48-hour quick win** — one concrete action to take immediately

On page load, 5 AI-selected opportunity chips appear — pre-screened for demand and low saturation this month. Click any chip to fire the analysis instantly.

---

## Architecture

```
User Input (product idea)
        │
        ▼
  Flask API Route (/console/api/nicheiq/analyze)
        │
        ├─► Etsy Scraper ──► live listings, prices, review counts
        │   (falls back to LLM knowledge if Etsy blocks)
        │
        ▼
  Dify Workflow (nicheiq-pipeline.yml)
        │
        ├─► [Research Agent]     claude-haiku — extracts market signals from scraped data
        │         │ JSON: price_range, top_keywords, demand_signals, supply_signals
        │
        ├─► [Analysis Agent]     claude-haiku — scores opportunity, finds the gap
        │         │ JSON: opportunity_score, market_gap, pricing_sweet_spot, saturation_risk
        │
        ├─► [Brief Writer]       claude-haiku — produces the ready-to-use product brief
        │         │ JSON: title_options, description, tags, mockup_style, quick_win_tip
        │
        └─► [Output Validator]   Python code node — validates all 3 agents completed,
                  │              assembles final structured output, rejects incomplete pipelines
                  ▼
           Final Brief → rendered in nicheiq-demo.html
```

**Key technical patterns:**
- Each agent outputs structured JSON — strict schema, no free-form text between agents
- Output Validator code node enforces pipeline integrity before returning to user
- Etsy scraper uses public HTML parsing (no API key) with graceful fallback
- Trending chips endpoint calls Haiku directly with a "pre-screen for GO" prompt

---

## Stack

| Layer | Technology |
|---|---|
| Workflow engine | Dify 1.13.2 (self-hosted, Docker) |
| LLM | Claude Haiku (via Anthropic plugin) |
| Backend | Python 3.12 + Flask (mounted into Dify API container) |
| Frontend | Vanilla HTML/CSS/JS served via nginx |
| Infrastructure | Docker Compose (11 containers) |
| Market data | Live Etsy HTML scraping + LLM fallback |

---

## How it differs from Projects 1 & 2

| | Project 1 | Project 2 | Project 3 (NicheIQ) |
|---|---|---|---|
| Pattern | Workflow + validator | Agent + RAG + hallucination guard | **Multi-agent + live web data** |
| Agents | 1 LLM | 1 Agent + 1 validator | **3 specialised agents in sequence** |
| Data source | User input | Knowledge base | **Live Etsy scrape** |
| Real users? | Internal tool | Demo | **8M+ Etsy sellers** |

---

## Project structure

```
dify-research-pipeline/
├── api/controllers/console/
│   └── nicheiq.py              # Flask routes: /analyze + /trending
├── dify-workflows/
│   └── nicheiq-pipeline.yml    # Dify DSL: 5-node workflow
├── docs/
│   └── multi-agent-patterns.md # Technical explainer
├── nicheiq-demo.html           # Full product UI
└── CLAUDE.md                   # Build log + session notes
```

---

## Setup

This project runs inside the same Docker stack as Projects 1 & 2.

**Prerequisites:** Docker Desktop, Dify running at `localhost` (see [Project 1 setup](https://github.com/okalangkenneth/dify-etsy-toolkit))

**1. Add env vars** to `dify-etsy-toolkit/dify/docker/.env`:
```
NICHEIQ_WORKFLOW_KEY=app-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**2. Import the workflow** in Dify:
Studio → Import DSL → `dify-workflows/nicheiq-pipeline.yml` → Publish

**3. Mount the API route** via `docker-compose.override.yml` (already configured in Project 1):
```bash
cd C:\Projects\dify-etsy-toolkit\dify\docker
docker compose up -d --no-deps --force-recreate api
```

**4. Serve the demo UI:**
```bash
docker cp nicheiq-demo.html docker-nginx-1:/usr/share/nginx/html/nicheiq.html
```

Open `http://localhost/nicheiq.html` (must be logged into Dify).

---

## What I learned

- **Multi-agent structured handoffs**: each agent must output valid JSON — if any agent returns free text, the downstream agent's context collapses. Enforcing schema at the prompt level is not enough; the code validator node is what makes it reliable.
- **Graceful degradation**: the Etsy scraper fails silently and the workflow still runs on LLM knowledge. Users see an amber badge ("LLM knowledge only") instead of an error. This is the right UX pattern for unreliable data sources.
- **The pre-screening problem**: surfacing "trending" ideas that then return NO-GO destroys user trust. The solution was to reframe the chips as "AI-selected opportunities" and write the Haiku prompt to only return ideas that would score 7+. One chip still failed — which is actually the honest outcome.
- **`memory.window` is required** in Dify 1.13 LLM nodes: `{enabled: false, window: {enabled: false, size: 10}}` — the short form causes a pydantic validation error on workflow run.
