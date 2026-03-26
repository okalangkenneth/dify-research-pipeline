# Project Rules - dify-research-pipeline

## What we are building

A **Multi-Agent Research Pipeline** built on Dify's workflow engine.
Three specialized LLM agents collaborate in sequence:

1. **Research Agent** — given a topic, produces structured research notes
2. **Analysis Agent** — takes the research, extracts key insights and patterns
3. **Writer Agent** — takes the analysis, produces a polished report

Portfolio goal: demonstrate multi-agent orchestration, agent handoffs, and
structured inter-agent communication — targeting AI engineering roles and
Upwork jobs around LLM pipelines and AI automation.

**GitHub**: https://github.com/okalangkenneth/dify-research-pipeline

---

## Architecture

```
User Topic Input
      |
      v
[Research Agent LLM]
  Prompt: "You are a Research Specialist. Given a topic, produce
           structured research notes covering: background, key facts,
           recent developments, and open questions. Output JSON."
      |
      v
[Analysis Agent LLM]
  Prompt: "You are an Analysis Specialist. Given research notes,
           extract: core themes, surprising insights, gaps, and
           a confidence score. Output JSON."
      |
      v
[Writer Agent LLM]
  Prompt: "You are a Senior Writer. Given analysis and research,
           produce a polished 3-section report: Summary, Key Findings,
           and Recommendations."
      |
      v
[Output Validator Code Node]
  Checks all three stages completed, formats final output
      |
      v
Final Report (title + summary + key_findings + recommendations + metadata)
```

---

## Build Progress (update every session)

### COMPLETED
- Project scaffold created (CLAUDE.md, dirs, .gitignore)
- Workflow DSL written (nicheiq-pipeline.yml) — 5 nodes: Start → Research Agent → Analysis Agent → Brief Writer → Output Validator → End
- Flask API route written (nicheiq.py) — scrapes live Etsy data, calls workflow, returns structured brief
- docker-compose.override.yml updated (all 3 projects mounted)
- nicheiq-demo.html built and served at localhost/nicheiq.html
- Workflow imported into Dify and published ✅
- nginx location block added for /nicheiq.html ✅
- memory.window validation error fixed in workflow DSL ✅
- nicheiq import added to __init__.py direct import block ✅
- End-to-end test PASSED ✅ — "freelance invoice template" → GO, $12, 13 tags, full brief
- Trending chips feature added ✅ — live Haiku-generated opportunities on page load
- Chips pre-screened for demand + low saturation (4/5 GO rate confirmed in testing)
- ANTHROPIC_API_KEY wired into override + .env ✅

### REMAINING
- [ ] Git init + push to GitHub
- [ ] README.md with architecture diagram
- [ ] docs/multi-agent-patterns.md (portfolio + LinkedIn explainer)
- [ ] Record Loom demo (2 min)

### REMAINING
- [ ] Write Dify workflow DSL (research-pipeline.yml)
- [ ] Write API route (research_pipeline.py)
- [ ] Update docker-compose.override.yml
- [ ] Build demo HTML (research-pipeline-demo.html)
- [ ] Test end-to-end
- [ ] Write README with architecture diagram
- [ ] Write docs/multi-agent-patterns.md (portfolio explainer)
- [ ] Git init + push to GitHub
- [ ] Record Loom demo

---

## Tech Stack

- Backend: Python 3.12 + Flask (Dify API service, same Docker as etsy-toolkit)
- Frontend: Vanilla HTML served via nginx
- Container: Reuses C:\Projects\dify-etsy-toolkit\dify\docker (DO NOT start new Docker)
- Workflow: Dify DSL in dify-workflows/

## Business Rules (NON-NEGOTIABLE)

- Each agent outputs valid JSON — never plain text between agents
- Research Agent must include a `confidence` field (0.0-1.0) per fact
- Analysis Agent must flag any research gaps it detects
- Writer Agent must stay grounded in the analysis — no hallucinated facts
- Final output validator rejects incomplete pipelines (missing any stage)

## Session End Prompt

Update the Build Progress section in CLAUDE.md with completed work, then stop.
