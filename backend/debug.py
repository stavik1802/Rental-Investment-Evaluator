# backend/test_perpex.py

import asyncio
from pprint import pprint

from dotenv import load_dotenv

from main import SearchParams, call_perplexity_investment_agent


TEST_CASES = [
    SearchParams(
        minPrice=300000,
        maxPrice=550000,
        area="Brooklyn, NY",
        bedrooms=2,
        minSqft=700,
        maxSqft=1100,
    ),
    SearchParams(
        minPrice=300000,
        maxPrice=1000000,
        area="Manhattan Beach, Brooklyn, NY",
        bedrooms=2,
        minSqft=700,
        maxSqft=1100,
    ),
]


async def run_single_test(params: SearchParams):
    print("\n===================================================")
    print(f"🔍 Testing Perplexity + OpenAI pipeline for area: {params.area}")
    print("Params:")
    pprint(params.model_dump())
    print("===================================================\n")

    avg_rent, properties = await call_perplexity_investment_agent(params)

    print(f"✅ Average Rent (USD): {avg_rent}")
    print(f"✅ Properties Returned: {len(properties)}\n")

    if not properties:
        print("⚠️ No properties were parsed for this query.")
        return

    for i, p in enumerate(properties, start=1):
        print(f"—— Property #{i} ——")
        print("ID:           ", p.id)
        print("Address:      ", p.address)
        print("Price (USD):  ", p.price)
        print("Bedrooms:     ", p.bedrooms)
        print("Sqft:         ", p.sqft)
        print("Est. Rent:    ", p.estimatedRent)  # should equal avg_rent for all
        print("Gross Yield:  ", f"{p.grossYield * 100:.2f}%")
        print()

    # Quick sanity check: are all estimated rents equal to avg_rent?
    all_same = all(abs(p.estimatedRent - avg_rent) < 1e-6 for p in properties)
    print(f"🔎 All properties use the same estimatedRent as avg_rent? {all_same}")
    print("🎉 Done for area:", params.area)
    print("===================================================\n")


async def run_all_tests():
    load_dotenv()

    for params in TEST_CASES:
        await run_single_test(params)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
