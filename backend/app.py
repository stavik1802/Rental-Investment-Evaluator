import os
import json
import re
from datetime import datetime
from typing import List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ----------------------------
# Configuration
# ----------------------------

# In production, load this from os.getenv("GEMINI_API_KEY")
GEMINI_API_KEY = "AIzaSyAc1sa46rs3TC4M3vQvg_cAEAyms-fXb60" 

# Use Gemini 1.5 Flash for speed and cost-efficiency
GEMINI_MODEL_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

app = FastAPI(title="Real Estate Investment Tool (Gemini Powered)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# Models (Matching your Types.ts)
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
    grossYield: float
    url: str = ""

class EvaluationResponse(BaseModel):
    averageRent: float
    currency: str = "USD"
    properties: List[PropertyResult] = []

class RentOnlyResponse(BaseModel):
    averageRent: float
    currency: str = "USD"
    analysis: str = "" # Added to show Gemini's reasoning if needed

# ----------------------------
# Gemini Helper Functions
# ----------------------------

async def call_gemini_json(prompt: str) -> dict:
    """
    Sends a prompt to Gemini and parses the response as JSON.
    Includes error handling and clean-up of markdown code fences.
    """
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "response_mime_type": "application/json"
        }
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(GEMINI_MODEL_URL, json=payload)
            response.raise_for_status()
            result = response.json()
            
            # Extract text from Gemini response structure
            text_content = result.get('candidates', [])[0].get('content', {}).get('parts', [])[0].get('text', '')
            
            # Parse JSON
            return json.loads(text_content)
        except Exception as e:
            print(f"Gemini API Error: {str(e)}")
            # Fallback/Default if API fails
            return {"average_rent": 0, "error": str(e)}

# ----------------------------
# Core Logic
# ----------------------------

async def get_rental_data_from_gemini(params: SearchParams) -> dict:
    """
    Asks Gemini for rental market data based on search parameters.
    """
    prompt = f"""
    Act as a real estate data analyst. 
    I need the estimated monthly rental price for a property with these specs:
    
    - Location: {params.area}
    - Bedrooms: {params.bedrooms}
    - Square Footage: {params.minSqft} - {params.maxSqft} sqft
    - Purchase Price Context: ${params.minPrice} - ${params.maxPrice}

    Please analyze the current market trends for this area.
    
    Return a JSON object with this EXACT structure:
    {{
        "average_rent": number,
        "min_rent": number,
        "max_rent": number,
        "currency": "USD",
        "market_analysis": "A short 1-sentence summary of the rental market here."
    }}
    """
    
    return await call_gemini_json(prompt)

async def parse_and_find_properties(params: SearchParams, avg_rent: float) -> List[PropertyResult]:
    """
    Simulates finding properties and using Gemini to 'parse' or generate valid mock listings 
    if you don't have a live Zillow API. 
    
    (Note: To get REAL live listings, you usually need a specialized API like Zillow/Redfin 
    via RapidAPI, or a SERP tool. Gemini can't browse live Zillow listings in real-time 
    without a search tool attached. Below we simulate the 'Parsing' step you asked for 
    using Gemini to generate realistic examples based on the area).
    """
    prompt = f"""
    Generate 5 realistic real estate sale listings for: {params.area}
    that match: {params.bedrooms} beds, price ${params.minPrice}-${params.maxPrice}.
    
    For each listing, estimate the potential Gross Yield based on an average rent of ${avg_rent}.
    Gross Yield = (Annual Rent / Purchase Price).
    
    Return JSON:
    {{
        "listings": [
            {{
                "address": "Street address, City, Zip",
                "price": number,
                "bedrooms": number,
                "sqft": number,
                "url": "https://zillow.com/..."
            }}
        ]
    }}
    """
    
    data = await call_gemini_json(prompt)
    listings = data.get("listings", [])
    
    results = []
    for idx, item in enumerate(listings):
        price = item.get("price", 0)
        # Recalculate yield to be safe
        gross_yield = (avg_rent * 12) / price if price > 0 else 0
        
        results.append(PropertyResult(
            id=f"prop_{idx}",
            address=item.get("address", "Unknown"),
            price=price,
            bedrooms=item.get("bedrooms", params.bedrooms),
            sqft=item.get("sqft", 0),
            estimatedRent=avg_rent,
            grossYield=float(f"{gross_yield:.4f}"), # round to 4 decimals
            url=item.get("url", "")
        ))
        
    return results

# ----------------------------
# Endpoints
# ----------------------------

@app.post("/api/estimate-rent", response_model=RentOnlyResponse)
async def estimate_rent(params: SearchParams):
    """
    Step 1: Get Average Rent from Gemini
    """
    data = await get_rental_data_from_gemini(params)
    return RentOnlyResponse(
        averageRent=data.get("average_rent", 0),
        currency=data.get("currency", "USD"),
        analysis=data.get("market_analysis", "")
    )

@app.post("/api/evaluate", response_model=EvaluationResponse)
async def evaluate_investment(params: SearchParams):
    """
    Step 2: Full Evaluation (Rent + Listings Parsing)
    """
    # 1. Get Rent
    rent_data = await get_rental_data_from_gemini(params)
    avg_rent = rent_data.get("average_rent", 0)
    
    # 2. Get/Parse Listings (Simulated here with Gemini generation for "parsing")
    properties = await parse_and_find_properties(params, avg_rent)
    
    # 3. Sort by Yield
    properties.sort(key=lambda x: x.grossYield, reverse=True)
    
    return EvaluationResponse(
        averageRent=avg_rent,
        currency="USD",
        properties=properties
    )

# ----------------------------
# Optional: Text-to-Params Parser
# ----------------------------
class RawInput(BaseModel):
    query: str

@app.post("/api/parse-query", response_model=SearchParams)
async def parse_natural_language(input: RawInput):
    """
    Extra: specific helper if frontend sends "2 bed in Miami under 400k"
    """
    prompt = f"""
    Extract real estate search parameters from this text: "{input.query}"
    
    Return JSON with these keys (guess reasonable defaults if missing):
    - minPrice (number)
    - maxPrice (number)
    - area (string)
    - bedrooms (number)
    - minSqft (number)
    - maxSqft (number)
    """
    data = await call_gemini_json(prompt)
    return SearchParams(**data)

if __name__ == "__main__":
    import uvicorn
    print("Starting server on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
