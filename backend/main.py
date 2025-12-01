import os
import json
import re
from typing import List, Tuple

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

# ----------------------------
# Load environment + clients
# ----------------------------

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is missing from .env")
if not PERPLEXITY_API_KEY:
    raise RuntimeError("PERPLEXITY_API_KEY is missing from .env")

openai_client = OpenAI(api_key=OPENAI_API_KEY)


# ----------------------------
# Models (must match frontend)
# ----------------------------

class SearchParams(BaseModel):
    minPrice: float
    maxPrice: float
    area: str
    bedrooms: int
    minSqft: float
    maxSqft: float


class PropertyResult(BaseModel):
    id: str
    address: str
    price: float
    bedrooms: int
    sqft: float
    estimatedRent: float
    grossYield: float  # e.g. 0.08 = 8%
    url: str           # direct link to listing (may be empty)


class EvaluationResponse(BaseModel):
    averageRent: float
    currency: str = "USD"
    properties: List[PropertyResult] = []


class RentOnlyResponse(BaseModel):
    averageRent: float
    currency: str = "USD"


# ----------------------------
# FastAPI + CORS
# ----------------------------

app = FastAPI(title="Real Estate Investment Tool (Perplexity + OpenAI)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------
# Helpers
# ----------------------------

def strip_markdown_fences(text: str) -> str:
    """
    Remove ```json ... ``` or ``` ... ``` fences around the content if present.
    """
    text = text.strip()

    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        else:
            text = text.lstrip("`")

        if text.rstrip().endswith("```"):
            text = text.rstrip()
            end_idx = text.rfind("```")
            text = text[:end_idx].strip()

    return text


def _safe_float(x):
    """
    Convert x to float, being tolerant of things like:
    "$450,000", "900 sq ft", "3,200", "450k", etc.
    """
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        cleaned = re.sub(r"[^0-9.]", "", x)
        if not cleaned:
            raise ValueError(f"Cannot parse float from: {x!r}")
        return float(cleaned)
    raise TypeError(f"Unexpected type for float: {type(x)}")


def _safe_int(x):
    """
    Convert x to int, being tolerant of things like:
    "2 bd", "3 beds", "4.0", etc.
    """
    if isinstance(x, int):
        return x
    if isinstance(x, float):
        return int(x)
    if isinstance(x, str):
        m = re.search(r"\d+", x)
        if not m:
            raise ValueError(f"Cannot parse int from: {x!r}")
        return int(m.group(0))
    raise TypeError(f"Unexpected type for int: {type(x)}")


# ===============================
# 1) Perplexity: average rent step
# ===============================

async def fetch_average_rent_from_perplexity(params: SearchParams) -> float:
    """
    Step 1:
    Use Perplexity (with live web search) to estimate the typical monthly rent
    for the given profile, based on real rental websites.

    Perplexity returns JSON, we parse it directly (after stripping fences).
    """

    system_prompt = (
        "You are a rental market analyst with live web access. "
        "You MUST use current data from real rental listing sites "
        "such as Zillow, Apartments.com, Rent.com, etc. "
        "You only respond with JSON (no markdown)."
    )

    user_prompt = f"""
Using live web search across real rental listing sites (Zillow, Apartments.com, Rent.com, etc.),
estimate the typical MONTHLY rent in USD for a property with these characteristics:

- Area: {params.area}
- Bedrooms: around {params.bedrooms}
- Purchase price range (for context): {params.minPrice}–{params.maxPrice} USD
- Size: {params.minSqft}–{params.maxSqft} square feet

You may look at multiple current rental listings in this area to inform your estimate.

Respond in STRICT JSON with this exact shape:

{{
  "average_rent_usd": 2800,
  "min_rent_usd": 2300,
  "max_rent_usd": 3400,
  "sample_size": 12
}}

Rules:
- Do NOT wrap in ``` or ```json fences.
- Do NOT add any extra top-level keys.
- All values are numbers (no commas, no currency symbols).
""".strip()

    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "sonar-pro",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload,
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail=f"Perplexity rent API error: {resp.status_code} {resp.text}",
        )

    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected Perplexity rent response structure: {e} | {data}",
        )

    cleaned = strip_markdown_fences(content)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse rent JSON from Perplexity: {e} | content={content!r}",
        )

    try:
        avg = float(parsed["average_rent_usd"])
        if avg <= 0:
            raise ValueError("average_rent_usd must be positive")
        return avg
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Rent JSON missing or invalid fields: {e} | parsed={parsed!r}",
        )


# ===============================
# 3) Perplexity: sale listings step
# ===============================

async def fetch_listings_from_perplexity(params: SearchParams) -> str:
    """
    Step 3:
    Use Perplexity with live web search to gather REAL for-sale listings text
    (addresses, prices, bedrooms, sqft, URLs) from Zillow/Redfin/Realtor/Trulia/etc.

    We deliberately request PLAIN TEXT (not JSON) because OpenAI will parse it.
    We ask for approximate matches and REQUIRE each listing to include an https URL.
    """

    system_prompt = (
        "You are a property search assistant with live web access. "
        "You MUST open real estate listing pages (Zillow, Redfin, Realtor.com, "
        "Trulia, Compass, Elliman, etc.) and extract ACTUAL, CURRENT for-sale listings. "
        "It is OK if the listings do not perfectly match the user's exact filters; "
        "approximate matches are fine. "
        "You must return listing bullets with real, clickable URLs starting with https://."
    )

    user_prompt = f"""
Search the live web for REAL, CURRENT residential properties for sale in or very close to:

    {params.area}

Your goals:

1. Open listing pages on sites like Zillow, Redfin, Realtor.com, Trulia, Compass, Elliman, etc.
2. Extract at least 5 and up to 15 individual for-sale listings that are:
   - Located in {params.area} or nearby neighborhoods in Brooklyn, NY.
   - Roughly in the price band {params.minPrice}–{params.maxPrice} USD, if possible.
   - Around {params.bedrooms} bedrooms (1–3 bedrooms is acceptable).
   - Around {params.minSqft}–{params.maxSqft} sq ft, if this information is available.

IMPORTANT URL RULES (CRITICAL):
- For EACH listing, you MUST include a single https URL at the END of the bullet, in parentheses.
- The URL MUST start with "https://".
- If you cannot find the exact property detail URL, construct a reasonable search URL on a major site,
  for example:
    - https://www.redfin.com/search?q=3025+Ocean+Ave+Brooklyn+NY+11235
    - or https://www.zillow.com/homes/for_sale/Brooklyn-NY_rb/
- But you MUST still output SOME https:// URL per listing.
- Do NOT say that you cannot provide URLs. Always provide a best-effort URL.

For each listing, output a single bullet that contains AT LEAST:
- Address or neighborhood + city
- Asking price
- Number of bedrooms
- Approximate square footage (if not listed, give a reasonable estimate and label it as an estimate)
- A direct URL to the listing or a search URL on a major platform

Formatting rules:
- Return PLAIN TEXT only.
- One listing per bullet.
- Each listing MUST start with "- " (dash + space).
- The URL MUST be at the END of the line in parentheses, like:
  - 3025 Ocean Ave Unit 1O, Brooklyn, NY 11235 | $300,000 | 1 bed, 1 bath | 750 sq ft (https://www.redfin.com/search?q=3025+Ocean+Ave+Brooklyn+NY+11235)
- Do NOT format as JSON.
- Do NOT use ``` code fences.
- Do NOT include long general analysis, disclaimers, or explanations about limitations.
- Do NOT talk about aggregator pages or suggest going to Zillow/Redfin manually. Just output the bullets.
""".strip()

    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "sonar-pro",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload,
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail=f"Perplexity listings API error: {resp.status_code} {resp.text}",
        )

    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected Perplexity listings response structure: {e} | {data}",
        )

    # Optional debug
    print("\n=== RAW LISTINGS TEXT ===")
    print(content)
    print("================================\n")

    return content



# ===============================
# 2 & 4) OpenAI: parse listings + compute yields
# ===============================

def parse_listings_with_openai(
    raw_text: str,
    avg_rent_hint: float,
    params: SearchParams,
) -> List[PropertyResult]:
    """
    Steps 2 + 4:
    - Take Perplexity's raw listings text (bullet lines, possibly with some explanation).
    - Use OpenAI to parse it into JSON properties.
    - For each property, use avg_rent_hint as estimatedRent.
    - Compute grossYield = avg_rent_hint * 12 / price_usd.
    """

    system_prompt = """
You are a strict JSON property listings parser.

You receive messy text that describes REAL property listings found online,
usually one listing per bullet starting with "- ".

Your job is to:

1. Extract clean structured data for each listing.
2. Output ONLY valid JSON (no markdown, no ``` fences).

Use this exact JSON shape:

{
  "properties": [
    {
      "id": "prop-1",
      "address": "string",
      "price_usd": 123456,
      "bedrooms": 2,
      "sqft": 850,
      "url": "https://..."
    }
  ]
}

Rules:
- Do NOT add extra top-level keys.
- "properties" should be an array of listing objects.
- Numbers must be plain numbers (no commas, no currency symbols).
- If a URL is not clearly present, set "url" to "".
- If square footage is not clearly present, estimate a reasonable number and use that.
""".strip()

    user_prompt = f"""
Here is the raw text containing REAL for-sale property listings
returned by a web-search assistant:

---
{raw_text}
---

The investor is interested in:

- Area: {params.area}
- Target price range: {params.minPrice}–{params.maxPrice} USD
- Target bedrooms: about {params.bedrooms}
- Target size: {params.minSqft}–{params.maxSqft} sq ft

From this text:

1. Extract up to 10 listings that roughly match the investor's criteria.
2. For each listing:
   - "id": a unique id like "prop-1", "prop-2", etc.
   - "address": concise address or neighborhood + city.
   - "price_usd": asking price (numeric, no commas).
   - "bedrooms": integer number of bedrooms.
   - "sqft": square footage (numeric; if missing, estimate reasonably).
   - "url": URL string to the listing (if present; else empty string).

The input may also contain explanatory text; ignore it and focus on lines
that clearly look like listings.

Remember:
- Output ONLY JSON in the exact shape described.
- Do NOT wrap the JSON in code fences.
""".strip()

    try:
        completion = openai_client.chat.completions.create(
            model="gpt-4.1-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )

        content = completion.choices[0].message.content

        # Optional debug
        print("\n=== RAW OPENAI JSON RESPONSE ===")
        print(content)
        print("================================\n")

        data = json.loads(content)

        raw_props = data.get("properties", [])
        if not isinstance(raw_props, list):
            raw_props = []

        properties: List[PropertyResult] = []

        for i, p in enumerate(raw_props, start=1):
            try:
                price_raw = (
                    p.get("price_usd")
                    or p.get("price")
                    or p.get("asking_price")
                )
                if price_raw is None:
                    raise KeyError("Missing price")

                price = _safe_float(price_raw)
                est_rent = float(avg_rent_hint)  # use global avg rent

                bedrooms = _safe_int(p.get("bedrooms", params.bedrooms))
                sqft = _safe_float(
                    p.get("sqft", (params.minSqft + params.maxSqft) / 2.0)
                )
                address = str(p.get("address", "Unknown address"))
                pid = str(p.get("id", f"prop-{i}"))
                url = str(p.get("url", ""))

                if price <= 0 or est_rent <= 0:
                    raise ValueError("Non-positive price or rent")

                gross_yield = (est_rent * 12.0) / price

                prop = PropertyResult(
                    id=pid,
                    address=address,
                    price=price,
                    bedrooms=bedrooms,
                    sqft=sqft,
                    estimatedRent=est_rent,
                    grossYield=gross_yield,
                    url=url,
                )
                properties.append(prop)

            except Exception as e:
                print(
                    f"[parse_listings_with_openai] Skipping listing due to error: {e} | p={p}"
                )
                continue

        return properties

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse JSON from OpenAI listings parser: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"OpenAI listings parsing/estimation error: {e}",
        )


# ===============================
# Combined pipeline for API + tests
# ===============================

async def call_perplexity_investment_agent(
    params: SearchParams,
) -> Tuple[float, List[PropertyResult]]:
    """
    High-level pipeline:

    1. Get average rent from Perplexity (live rental sites).
    2. Parse that JSON (no extra LLM).
    3. Get sale listings text from Perplexity (live sale sites).
    4. Use OpenAI to parse listings (price/address/bedrooms/sqft/url).
       For each listing, use the avg rent from step 1 as estimatedRent and compute yield.

    Returns:
        (average_rent_usd, [PropertyResult, ...])
    """
    avg_rent = await fetch_average_rent_from_perplexity(params)
    raw_listings_text = await fetch_listings_from_perplexity(params)
    properties = parse_listings_with_openai(raw_listings_text, avg_rent, params)
    return avg_rent, properties


# ===============================
# API endpoints
# ===============================

@app.post("/api/estimate-rent", response_model=RentOnlyResponse)
async def estimate_rent(params: SearchParams):
    """
    Returns only the average monthly rent estimate from Perplexity.
    Used by the frontend to show the rent quickly before full evaluation.
    """
    avg_rent = await fetch_average_rent_from_perplexity(params)
    return RentOnlyResponse(averageRent=avg_rent, currency="USD")


@app.post("/api/evaluate", response_model=EvaluationResponse)
async def evaluate_investment(params: SearchParams):
    """
    Frontend entrypoint: runs the full investment pipeline.
    """
    avg_rent, properties = await call_perplexity_investment_agent(params)

    properties_sorted = sorted(properties, key=lambda p: p.grossYield, reverse=True)

    return EvaluationResponse(
        averageRent=avg_rent,
        currency="USD",
        properties=properties_sorted,
    )
