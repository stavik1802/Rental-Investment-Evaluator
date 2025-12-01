import os
import json
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
# Pydantic models (match frontend)
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
    grossYield: float  # 0.08 = 8%

class EvaluationResponse(BaseModel):
    averageRent: float
    currency: str = "USD"
    properties: List[PropertyResult] = []


# ----------------------------
# FastAPI app + CORS
# ----------------------------

app = FastAPI(title="Real Estate Investment Tool (Perplexity + OpenAI Parser)")

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
# 1) Perplexity: fetch raw listings text
# ----------------------------

async def fetch_listings_from_perplexity(params: SearchParams) -> str:
    """
    Use Perplexity to gather real listings text from the live web.
    We explicitly ask for plain text, not JSON, because OpenAI will parse it.
    """

    system_prompt = (
        "You are a property search assistant with live web access. "
        "You search sites like Zillow, Redfin, Realtor, and Trulia and return "
        "real, current listings. You MUST NOT output JSON; just plain text."
    )

    user_prompt = f"""
Search the live web for REAL, CURRENT properties for sale that match:

- Area: {params.area}
- Price range: {params.minPrice}–{params.maxPrice} USD
- Bedrooms: around {params.bedrooms}
- Size: {params.minSqft}–{params.maxSqft} square feet

For each listing you find, include:
- Address or neighborhood + city
- Asking price
- Number of bedrooms
- Approximate square footage (if available; otherwise estimate)
- A direct URL to the listing (Zillow/Redfin/Realtor/Trulia/etc.)

Return the results as plain text with one listing per bullet or paragraph.
Do NOT format as JSON.
Do NOT use ``` code fences.
Do NOT include any analysis, only the listing details.
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
            detail=f"Perplexity API error: {resp.status_code} {resp.text}",
        )

    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected Perplexity response structure: {e} | {data}",
        )

    return content


# ----------------------------
# 2) OpenAI: parse Perplexity text into strict JSON + rent per property
# ----------------------------

def parse_listings_with_openai(
    raw_text: str,
    params: SearchParams,
) -> Tuple[float, List[PropertyResult]]:
    """
    Send Perplexity's unstructured text to OpenAI,
    and convert it into strict JSON:

    {
      "average_rent_usd": 2600,
      "properties": [
        {
          "id": "prop-1",
          "address": "string",
          "price_usd": 123456,
          "bedrooms": 2,
          "sqft": 850,
          "url": "http://...",
          "estimated_rent_usd": 2600
        },
        ...
      ]
    }

    Returns (average_rent_usd, [PropertyResult, ...]).
    """

    system_prompt = """
You are a strict JSON parsing and rent estimation engine.

You receive messy text that describes REAL property listings found online.
Your job is to:

1. Extract clean structured data for each listing.
2. Estimate the monthly rent (USD) for each listing based on its location, size, and price.
3. Compute the typical average rent (USD) across these listings.

You MUST:

- Output ONLY valid JSON (no markdown, no ``` fences).
- Use this exact top-level shape:

{
  "average_rent_usd": 2600,
  "properties": [
    {
      "id": "prop-1",
      "address": "string",
      "price_usd": 123456,
      "bedrooms": 2,
      "sqft": 850,
      "url": "https://...",
      "estimated_rent_usd": 2600
    }
  ]
}

- Do NOT add extra top-level keys.
- Numbers must be plain numbers (no commas, no currency symbols).
""".strip()

    user_prompt = f"""
Here is the raw text containing real property listings:

---
{raw_text}
---

The user is interested in:

- Area: {params.area}
- Target price range: {params.minPrice}–{params.maxPrice} USD
- Target bedrooms: about {params.bedrooms}
- Target size: {params.minSqft}–{params.maxSqft} sq ft

From this text:

1. Extract up to 10 listings that roughly match the user's criteria.
2. For each listing:
   - "id": a unique id like "prop-1", "prop-2", etc.
   - "address": concise address or neighborhood + city
   - "price_usd": asking price (numeric, no commas)
   - "bedrooms": integer number of bedrooms
   - "sqft": square footage (numeric; if missing, estimate reasonably)
   - "url": URL string to the listing (if present; else empty string)
   - "estimated_rent_usd": your estimate of MONTHLY rent for this listing.

3. Compute "average_rent_usd" as a typical monthly rent for this user profile
   in this area, based on the listings you extracted.

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
        data = json.loads(content)

        # Extract average rent
        avg_rent = float(data.get("average_rent_usd", 0.0))

        raw_props = data.get("properties", [])
        if not isinstance(raw_props, list) or len(raw_props) == 0:
            raise ValueError(f"No properties found in parsed JSON: {data!r}")

        properties: List[PropertyResult] = []
        rents_for_avg = []

        for i, p in enumerate(raw_props, start=1):
            try:
                price = float(p["price_usd"])
                est_rent = float(p["estimated_rent_usd"])
                bedrooms = int(p["bedrooms"])
                sqft = float(p["sqft"])
                address = str(p["address"])
                pid = str(p.get("id", f"prop-{i}"))

                if price <= 0 or est_rent <= 0:
                    continue

                gross_yield = (est_rent * 12.0) / price
                rents_for_avg.append(est_rent)

                prop = PropertyResult(
                    id=pid,
                    address=address,
                    price=price,
                    bedrooms=bedrooms,
                    sqft=sqft,
                    estimatedRent=est_rent,
                    grossYield=gross_yield,
                )
                properties.append(prop)
            except (KeyError, ValueError, TypeError):
                # Skip malformed entry
                continue

        if not properties:
            raise ValueError("All properties parsed were invalid or filtered out.")

        # If avg_rent from JSON is missing or <=0, compute from properties
        if avg_rent <= 0 and rents_for_avg:
            avg_rent = sum(rents_for_avg) / len(rents_for_avg)

        if avg_rent <= 0:
            # As a fallback, use median-ish of property rents
            rents_for_avg_sorted = sorted(rents_for_avg)
            if rents_for_avg_sorted:
                mid = len(rents_for_avg_sorted) // 2
                avg_rent = rents_for_avg_sorted[mid]

        if avg_rent <= 0:
            raise ValueError(
                f"average_rent_usd is invalid after parsing: {avg_rent} | data={data!r}"
            )

        return avg_rent, properties

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse JSON from OpenAI parser: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"OpenAI parsing/estimation error: {e}",
        )


# ----------------------------
# Combined agent used by API and tests
# ----------------------------

async def call_perplexity_investment_agent(
    params: SearchParams,
) -> Tuple[float, List[PropertyResult]]:
    """
    High-level pipeline:
    1. Perplexity: real listings text from the web.
    2. OpenAI: parse that text into structured properties + average rent.
    3. Return (average_rent_usd, properties[])
    """
    raw_text = await fetch_listings_from_perplexity(params)
    avg_rent, properties = parse_listings_with_openai(raw_text, params)
    return avg_rent, properties


# ----------------------------
# API route
# ----------------------------

@app.post("/api/evaluate", response_model=EvaluationResponse)
async def evaluate_investment(params: SearchParams):
    """
    API entrypoint for the frontend.

    1. Calls Perplexity to search real listings.
    2. Uses OpenAI to structure + estimate rent.
    3. Computes gross yield (already done in parser step).
    4. Returns EvaluationResponse that the frontend expects.
    """
    avg_rent, properties = await call_perplexity_investment_agent(params)

    # Optional: sort by best yield (descending)
    properties_sorted = sorted(properties, key=lambda p: p.grossYield, reverse=True)

    return EvaluationResponse(
        averageRent=avg_rent,
        currency="USD",
        properties=properties_sorted,
    )
