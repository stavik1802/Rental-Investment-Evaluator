// src/pages/ResultsPage.tsx
import { useLocation, useNavigate } from "react-router-dom";
import type { EvaluationResponse, SearchParams } from "../types";

interface LocationState {
  searchParams: SearchParams;
  results: EvaluationResponse;
}

function ResultsPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as LocationState | null;

  if (!state) {
    return (
      <div className="card">
        <p>No results to display. Please run a search first.</p>
        <button
          onClick={() => navigate("/")}
          className="btn btn-primary"
          style={{ marginTop: 12 }}
        >
          Back to search
        </button>
      </div>
    );
  }

  const { searchParams, results } = state;

  const bestProperty =
    results.properties.length > 0
      ? [...results.properties].sort((a, b) => b.grossYield - a.grossYield)[0]
      : null;

  return (
    <div className="card">
      <header className="card-header" style={{ marginBottom: 8 }}>
        <button onClick={() => navigate(-1)} className="btn btn-ghost">
          ← Back
        </button>
        <h1 className="card-title" style={{ marginTop: 8 }}>
          Rent Estimate Preview
        </h1>
        <p className="card-subtitle">
          This is a mocked preview. Later it will use your LLM-backed backend.
        </p>
      </header>

      <div className="summary-card">
        <div>
          <div className="summary-label">Estimated average monthly rent</div>
          <div className="summary-value">
            ${results.averageRent.toLocaleString()}
          </div>
        </div>
        <div>
          <div className="summary-pill">
            {results.properties.length} sample properties
          </div>
        </div>
      </div>

      <div className="results-grid">
        {/* Left: search summary */}
        <section className="results-section">
          <h3>Search criteria</h3>
          <div className="results-tags">
            <div>
              <strong>Area:</strong> {searchParams.area || "—"}
            </div>
            <div>
              <strong>Price range:</strong>{" "}
              {searchParams.minPrice.toLocaleString()} –{" "}
              {searchParams.maxPrice.toLocaleString()} USD
            </div>
            <div>
              <strong>Bedrooms:</strong> {searchParams.bedrooms}
            </div>
            <div>
              <strong>Size:</strong> {searchParams.minSqft} –{" "}
              {searchParams.maxSqft} sqft
            </div>
          </div>

          {bestProperty && (
            <>
              <h3 style={{ marginTop: 12 }}>Best mock candidate</h3>
              <div className="results-tags">
                <div>
                  <strong>{bestProperty.address}</strong>
                </div>
                <div>
                  Price: ${bestProperty.price.toLocaleString()} · Beds:{" "}
                  {bestProperty.bedrooms} · {bestProperty.sqft} sqft
                </div>
                <div>
                  Est. rent: $
                  {bestProperty.estimatedRent.toLocaleString()} · Gross yield:{" "}
                  {(bestProperty.grossYield * 100).toFixed(2)}%
                </div>
              </div>
            </>
          )}
        </section>

        {/* Right: “raw data” preview */}
        <section className="results-section">
          <h3>Raw data preview</h3>
          <p className="results-tags">
            This is what the backend will send to the frontend later.
          </p>
          <pre className="code-block">
{JSON.stringify(results, null, 2)}
          </pre>
        </section>
      </div>
    </div>
  );
}

export default ResultsPage;
