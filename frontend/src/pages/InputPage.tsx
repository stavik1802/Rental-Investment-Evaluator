// src/pages/InputPage.tsx
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { SearchParams, EvaluationResponse } from "../types";
import { evaluateInvestment } from "../api";

const defaultValues: SearchParams = {
  minPrice: 200000,
  maxPrice: 500000,
  area: "",
  bedrooms: 2,
  minSqft: 600,
  maxSqft: 1500,
};

function InputPage() {
  const [form, setForm] = useState<SearchParams>(defaultValues);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const navigate = useNavigate();

  function handleChange(
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) {
    const { name, value } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: name === "area" ? value : Number(value),
    }));
  }

  function validateForm(): string | null {
    if (!form.area.trim()) return "Area is required.";
    if (form.minPrice <= 0 || form.maxPrice <= 0)
      return "Price must be positive.";
    if (form.minPrice > form.maxPrice)
      return "Min price cannot be greater than max price.";
    if (form.minSqft <= 0 || form.maxSqft <= 0)
      return "Sqft must be positive.";
    if (form.minSqft > form.maxSqft)
      return "Min sqft cannot be greater than max sqft.";
    if (form.bedrooms <= 0) return "Bedrooms must be at least 1.";
    return null;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    try {
      setIsLoading(true);

      // 🔗 REAL BACKEND CALL HERE
      const result: EvaluationResponse = await evaluateInvestment(form);

      // Navigate to results page with response from backend
      navigate("/results", {
        state: { searchParams: form, results: result },
      });
    } catch (err: any) {
      console.error(err);
      setError(err?.message || "Something went wrong while contacting backend.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="card">
      <header className="card-header">
        <h1 className="card-title">Real Estate Investment Tool</h1>
        <p className="card-subtitle">
          Enter your criteria to estimate rental potential using the LLM agent.
        </p>
      </header>

      <div className="chip-row">
        <span className="chip">Step 1 · Input Criteria</span>
        <span className="chip">Step 2 · View Rent Estimate</span>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Area */}
        <div>
          <label className="label" htmlFor="area">
            Area (city / neighborhood / ZIP)
          </label>
          <input
            id="area"
            name="area"
            type="text"
            value={form.area}
            onChange={handleChange}
            className="input"
            placeholder="e.g. Brooklyn, NY"
          />
        </div>

        {/* Price range */}
        <div className="form-grid-2">
          <div>
            <label className="label" htmlFor="minPrice">
              Min Price
            </label>
            <input
              id="minPrice"
              name="minPrice"
              type="number"
              value={form.minPrice}
              onChange={handleChange}
              className="input"
            />
          </div>
          <div>
            <label className="label" htmlFor="maxPrice">
              Max Price
            </label>
            <input
              id="maxPrice"
              name="maxPrice"
              type="number"
              value={form.maxPrice}
              onChange={handleChange}
              className="input"
            />
          </div>
        </div>

        {/* Bedrooms */}
        <div>
          <label className="label" htmlFor="bedrooms">
            Bedrooms
          </label>
          <input
            id="bedrooms"
            name="bedrooms"
            type="number"
            min={1}
            value={form.bedrooms}
            onChange={handleChange}
            className="input"
          />
        </div>

        {/* Sqft range */}
        <div className="form-grid-2">
          <div>
            <label className="label" htmlFor="minSqft">
              Min Sqft
            </label>
            <input
              id="minSqft"
              name="minSqft"
              type="number"
              value={form.minSqft}
              onChange={handleChange}
              className="input"
            />
          </div>
          <div>
            <label className="label" htmlFor="maxSqft">
              Max Sqft
            </label>
            <input
              id="maxSqft"
              name="maxSqft"
              type="number"
              value={form.maxSqft}
              onChange={handleChange}
              className="input"
            />
          </div>
        </div>

        {error && <div className="error-box">{error}</div>}

        <button
          type="submit"
          disabled={isLoading}
          className="btn btn-primary"
        >
          {isLoading ? "Contacting rent agent..." : "Get Rent Estimate"}
        </button>
      </form>
    </div>
  );
}

export default InputPage;
