# backend/test_perpex.py

import asyncio
from pprint import pprint

from dotenv import load_dotenv

from main import SearchParams, call_perplexity_investment_agent

TEST_PARAMS = SearchParams(
    minPrice=300000,
    maxPrice=1000000,
    area="Manhattan Beach, Brooklyn, NY",
    bedrooms=2,
    minSqft=700,
    maxSqft=1100,
)

async def run_test():
    load_dotenv()

    print("🔍 Testing Perplexity + OpenAI pipeline with params:")
    pprint(TEST_PARAMS.model_dump())
    print("\nCalling pipeline...\n")

    avg_rent, properties = await call_perplexity_investment_agent(TEST_PARAMS)

    print("✅ Average Rent (USD):", avg_rent)
    print(f"✅ Properties Returned: {len(properties)}\n")

    for i, p in enumerate(properties, start=1):
        print(f"—— Property #{i} ——")
        print("ID:          ", p.id)
        print("Address:     ", p.address)
        print("Price (USD): ", p.price)
        print("Bedrooms:    ", p.bedrooms)
        print("Sqft:        ", p.sqft)
        print("Est. Rent:   ", p.estimatedRent)
        print("Gross Yield: ", f"{p.grossYield * 100:.2f}%")
        print()

    print("🎉 Done!")

if __name__ == "__main__":
    asyncio.run(run_test())
