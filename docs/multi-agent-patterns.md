# Multi-Agent Patterns in Production AI Systems

## The problem with single-agent LLM pipelines

A single LLM asked to "research a market, analyse the opportunity, and write a product brief" will produce output that looks good but is structurally weak. The model context mixes research, reasoning, and writing — each task degrades the others. You get a plausible-sounding answer, not a reliable one.

The solution is agent specialisation: break the task into distinct roles with strict JSON contracts between them.

## The NicheIQ pattern: three agents, one pipeline

NicheIQ uses three Claude Haiku agents in sequence, each with a single responsibility:

**Research Agent** — given raw Etsy market data, extracts structured signals.
Output: `price_range`, `top_keywords`, `demand_signals`, `supply_signals`, `data_confidence`

**Analysis Agent** — given research signals, scores the opportunity.
Output: `opportunity_score` (0–10), `market_gap`, `saturation_risk`, `pricing_sweet_spot`, `differentiation_angle`

**Brief Writer** — given analysis + research, produces the ready-to-use brief.
Output: `title_options`, `description`, `etsy_tags`, `mockup_style`, `quick_win_tip`, `go_no_go`

Each agent sees only the output of the previous one — not the raw Etsy data, not the user's original input. This forces clean separation.

## Why JSON contracts between agents matter

If the Research Agent returns free text instead of JSON, the Analysis Agent's prompt context becomes noisy. It might still produce output, but the downstream reliability collapses.

Enforcing the schema at the prompt level alone is not sufficient — LLMs occasionally deviate. The Output Validator code node strips markdown fences, parses JSON with error catching, and rejects incomplete pipelines before they reach the user. This is the production pattern for multi-agent reliability.

## Graceful degradation with real data sources

NicheIQ scrapes live Etsy listings before calling the workflow. When Etsy blocks the scrape, the system falls back to LLM knowledge and signals this with an amber badge in the UI. The workflow still runs — the Research Agent simply works with less data and lowers its `data_confidence` field accordingly.

This pattern — fail gracefully, be transparent with the user, maintain functionality — is how production AI systems handle unreliable data sources.

## The pre-screening problem

The trending chips feature exposed a real product design challenge: if you surface "hot" ideas that then return NO-GO verdicts, you destroy user trust in the product.

The solution was to reframe the feature entirely. The Haiku prompt for chip generation asks specifically for ideas that would score 7+ on the opportunity scale — low saturation, clear demand, specific niches. The label changed from "trending right now" to "AI-selected opportunities." One chip still returned NO-GO in testing, which is the honest outcome and builds credibility rather than eroding it.
