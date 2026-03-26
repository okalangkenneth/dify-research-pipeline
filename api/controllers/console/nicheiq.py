import json
import logging
import os
import re
import time
import requests
from flask import request
from flask_restx import Resource
from pydantic import BaseModel, Field
from controllers.console import console_ns
from controllers.console.wraps import account_initialization_required, setup_required
from libs.login import login_required

logger = logging.getLogger(__name__)

NICHEIQ_WORKFLOW_KEY = os.environ.get("NICHEIQ_WORKFLOW_KEY", "")

ETSY_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class NicheIQPayload(BaseModel):
    product_idea: str = Field(..., min_length=3, max_length=300)


def scrape_etsy_market(query: str) -> dict:
    """
    Scrapes Etsy search results for a given product query.
    Returns structured market data: titles, prices, review counts, seller info.
    No API key required — parses public search HTML.
    Falls back to empty market data on any error (workflow still runs with LLM knowledge).
    """
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
    url = f"https://www.etsy.com/search?q={requests.utils.quote(query)}&ref=search_bar"

    try:
        resp = requests.get(url, headers=ETSY_HEADERS, timeout=12)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        logger.warning(f"NicheIQ: Etsy scrape failed for '{query}': {e}")
        return _fallback_market_data(query)


    # Extract listing data using regex on the JSON-LD / data attributes Etsy embeds
    listings = []

    # Prices — Etsy embeds these as data-appears-component-tracking JSON
    price_pattern = re.compile(r'"price":\s*"?([\d.]+)"?')
    prices = [float(p) for p in price_pattern.findall(html) if float(p) > 0.5][:40]

    # Titles — from listing-title spans and aria-label attributes
    title_pattern = re.compile(r'data-listing-id[^>]+aria-label="([^"]{10,120})"')
    titles = title_pattern.findall(html)[:20]
    if not titles:
        # fallback pattern
        title_pattern2 = re.compile(r'"name":\s*"([^"]{10,120})"')
        titles = list(dict.fromkeys(title_pattern2.findall(html)))[:20]

    # Review counts
    review_pattern = re.compile(r'"reviewCount":\s*(\d+)')
    reviews = [int(r) for r in review_pattern.findall(html)][:20]

    # Total results count
    total_match = re.search(r'"totalCount":\s*(\d+)', html)
    total_count = int(total_match.group(1)) if total_match else len(titles)

    # Build listings list
    for i, title in enumerate(titles[:15]):
        listing = {"title": title}
        if i < len(prices):
            listing["price_usd"] = prices[i]
        if i < len(reviews):
            listing["review_count"] = reviews[i]
        listings.append(listing)

    if not listings:
        logger.warning(f"NicheIQ: No listings parsed for '{query}', using fallback.")
        return _fallback_market_data(query)

    avg_reviews = round(sum(r.get("review_count", 0) for r in listings) / max(len(listings), 1), 1)
    price_vals = [l["price_usd"] for l in listings if "price_usd" in l]

    return {
        "query": query,
        "source": "etsy_live",
        "total_listings_estimate": total_count,
        "listings_sampled": len(listings),
        "listings": listings,
        "price_summary": {
            "min": min(price_vals) if price_vals else None,
            "max": max(price_vals) if price_vals else None,
            "avg": round(sum(price_vals) / len(price_vals), 2) if price_vals else None,
        },
        "avg_review_count": avg_reviews,
        "scrape_timestamp": int(time.time()),
    }


def _fallback_market_data(query: str) -> dict:
    """Used when Etsy scrape fails — workflow still runs on LLM knowledge alone."""
    return {
        "query": query,
        "source": "fallback_no_live_data",
        "total_listings_estimate": None,
        "listings_sampled": 0,
        "listings": [],
        "price_summary": {"min": None, "max": None, "avg": None},
        "avg_review_count": None,
        "scrape_timestamp": int(time.time()),
        "note": "Live Etsy data unavailable. Analysis based on LLM training knowledge.",
    }


@console_ns.route("/nicheiq/analyze")
class NicheIQApi(Resource):
    @setup_required
    @login_required
    @account_initialization_required
    def post(self):
        try:
            payload = NicheIQPayload.model_validate(request.json or {})
        except Exception as e:
            return {"message": f"Invalid input: {e}"}, 400

        if not NICHEIQ_WORKFLOW_KEY:
            return {"message": "NicheIQ workflow key not configured."}, 503

        # Step 1: Scrape live Etsy market data
        logger.info(f"NicheIQ: scraping Etsy for '{payload.product_idea}'")
        market_data = scrape_etsy_market(payload.product_idea)
        market_data_str = json.dumps(market_data, indent=2)

        # Step 2: Run the 3-agent Dify workflow
        try:
            resp = requests.post(
                "http://api:5001/v1/workflows/run",
                headers={"Authorization": f"Bearer {NICHEIQ_WORKFLOW_KEY}"},
                json={
                    "inputs": {
                        "topic": payload.product_idea,
                        "market_data": market_data_str,
                    },
                    "response_mode": "blocking",
                    "user": "nicheiq",
                },
                timeout=90,
            )
            resp.raise_for_status()
        except requests.Timeout:
            return {"message": "NicheIQ pipeline timed out (>90s)."}, 504
        except requests.RequestException as e:
            logger.error(f"NicheIQ: workflow call failed: {e}")
            return {"message": "NicheIQ workflow unreachable."}, 502

        outputs = resp.json().get("data", {}).get("outputs", {})

        # Step 3: Parse tag list from JSON string
        try:
            outputs["etsy_tags"] = json.loads(outputs.get("etsy_tags", "[]"))
        except Exception:
            outputs["etsy_tags"] = []

        # Step 4: Attach the raw market data source info for transparency
        outputs["market_data_source"] = market_data.get("source", "unknown")
        outputs["listings_sampled"] = market_data.get("listings_sampled", 0)

        return outputs, 200

import calendar
from datetime import datetime


def _get_trending_ideas() -> list:
    """
    Calls Claude Haiku directly to get 5 trending digital product ideas
    tuned to the current month/season. Returns a list of dicts:
    [{"idea": str, "reason": str, "emoji": str}]
    Falls back to a hardcoded list if the API call fails.
    """
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not anthropic_key:
        return _fallback_trending()

    month_name = calendar.month_name[datetime.now().month]

    prompt = f"""You are a digital product market expert. It is {month_name}.

Return ONLY a JSON array of exactly 5 digital product ideas for Etsy sellers that RIGHT NOW have:
- Clear buyer demand (people actively searching for this)
- Low-to-medium competition (not completely saturated)
- High likelihood of a GO verdict (opportunity score 7 or above out of 10)

Each item must have: "idea" (3-6 words, the product name), "reason" (max 8 words, why it's a strong opportunity), "emoji" (1 relevant emoji).

Avoid ideas that are obviously oversaturated (generic planners, basic to-do lists).
Prioritise: specific niches, underserved audiences, seasonal timing, evergreen problems.

Respond with ONLY the JSON array. No preamble. No markdown. Example format:
[{{"idea": "ADHD Freelance Rate Calculator", "reason": "Niche tool, low competition", "emoji": "🧠"}}]"""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": anthropic_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 400,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json()["content"][0]["text"].strip()
        clean = re.sub(r"```(?:json)?|```", "", raw).strip()
        ideas = json.loads(clean)
        if isinstance(ideas, list) and len(ideas) == 5:
            return ideas
    except Exception as e:
        logger.warning(f"NicheIQ trending: Haiku call failed: {e}")

    return _fallback_trending()


def _fallback_trending() -> list:
    month = datetime.now().month
    # Rotate seasonally so it never feels completely stale
    season_sets = {
        "q1": [
            {"idea": "New Year Budget Planner", "reason": "January reset demand peaks", "emoji": "💰"},
            {"idea": "Habit Tracker Bundle", "reason": "Resolution season evergreen", "emoji": "✅"},
            {"idea": "Freelance Invoice Template", "reason": "Tax season approaching fast", "emoji": "🧾"},
            {"idea": "Study Schedule Planner", "reason": "Semester start surge", "emoji": "📚"},
            {"idea": "Meal Prep Tracker", "reason": "New year health goals", "emoji": "🥗"},
        ],
        "q2": [
            {"idea": "Wedding Budget Spreadsheet", "reason": "Peak wedding season starts", "emoji": "💍"},
            {"idea": "Garden Planner Printable", "reason": "Spring planting season", "emoji": "🌱"},
            {"idea": "Spring Cleaning Checklist", "reason": "Seasonal declutter demand", "emoji": "🧹"},
            {"idea": "Business Plan Template", "reason": "Q2 planning cycle begins", "emoji": "📊"},
            {"idea": "Travel Packing List", "reason": "Summer travel prep surge", "emoji": "✈️"},
        ],
        "q3": [
            {"idea": "Back to School Planner", "reason": "August demand always spikes", "emoji": "🎒"},
            {"idea": "Teacher Lesson Plan Bundle", "reason": "New school year prep", "emoji": "🍎"},
            {"idea": "Summer Reading Tracker", "reason": "Kids activity demand high", "emoji": "📖"},
            {"idea": "Freelance Rate Calculator", "reason": "Q3 contract renewals surge", "emoji": "💸"},
            {"idea": "Home Renovation Planner", "reason": "Summer project season", "emoji": "🔨"},
        ],
        "q4": [
            {"idea": "Holiday Gift Planner", "reason": "Christmas prep starts early", "emoji": "🎁"},
            {"idea": "Year in Review Journal", "reason": "December reflection demand", "emoji": "📝"},
            {"idea": "Black Friday Savings Tracker", "reason": "Shopping season peak", "emoji": "🛍️"},
            {"idea": "2025 Goal Setting Workbook", "reason": "New year prep in November", "emoji": "🎯"},
            {"idea": "Holiday Meal Planner", "reason": "Thanksgiving Christmas surge", "emoji": "🦃"},
        ],
    }
    q = "q1" if month <= 3 else "q2" if month <= 6 else "q3" if month <= 9 else "q4"
    return season_sets[q]



@console_ns.route("/nicheiq/trending")
class NicheIQTrendingApi(Resource):
    @setup_required
    @login_required
    @account_initialization_required
    def get(self):
        ideas = _get_trending_ideas()
        return {"trending": ideas}, 200

