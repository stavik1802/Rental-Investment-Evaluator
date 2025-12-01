# backend/test_perplexity_agent.py

import asyncio
from pprint import pprint

from dotenv import load_dotenv

from main import SearchParams, call_perplexity_investment_agent

# Optional: tweak these to test different scenarios
TEST_PARAMS = SearchParams(
    minPrice=300000,
    maxPrice=550000,
    area="Brooklyn, NY",
    bedrooms=2,
    minSqft=700,
    maxSqft=1100,
)


async def run_test():
    # make sure .env is loaded so PERPLEXITY_API_KEY is available
    load_dotenv()

    print("🔍 Testing Perplexity investment agent with params:")
    pprint(TEST_PARAMS.model_dump())
    print("\nCalling Perplexity...\n")

    avg_rent, properties = await call_perplexity_investment_agent(TEST_PARAMS)

    print("✅ Average rent (USD):", avg_rent)
    print(f"✅ Number of properties returned: {len(properties)}\n")

    for i, p in enumerate(properties, start=1):
        print(f"—— Property #{i} ——")
        print("ID:          ", p.id)
        print("Address:     ", p.address)
        print("Price (USD): ", p.price)
        print("Bedrooms:    ", p.bedrooms)
        print("Sqft:        ", p.sqft)
        print("Est. rent:   ", p.estimatedRent)
        print("Gross yield: ", f"{p.grossYield * 100:.2f}%")
        print()

    print("Done.")


if __name__ == "__main__":
    asyncio.run(run_test())
