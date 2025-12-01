// src/pages/ResultsPage.tsx
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type {
  EvaluationResponse,
  SearchParams,
  PropertyResult,
} from "../types";
import { evaluateInvestment } from "../api";

interface LocationState {
  searchParams: SearchParams;
  initialAverageRent: number;
}

function ResultsPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as LocationState | null;

  const [averageRent, setAverageRent] = useState<number | null>(
    state?.initialAverageRent ?? null
  );
  const [properties, setProperties] = useState<PropertyResult[]>([]);
  const [isPropertiesLoading, setIsPropertiesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  const { searchParams } = state;

  useEffect(() => {
    let isCancelled = false;

    async function loadFullEvaluation() {
      try {
        setIsPropertiesLoading(true);
        setError(null);

        const fullResult: EvaluationResponse = await evaluateInvestment(
          searchParams
        );

        if (isCancelled) return;

        setProperties(fullResult.properties || []);
        setAverageRent(fullResult.averageRent);
      } catch (err: any) {
        console.error(err);
        if (!isCancelled) {
          setError(
            err?.message ||
              "Something went wrong while loading sample properties."
          );
        }
      } finally {
        if (!isCancelled) {
          setIsPropertiesLoading(false);
        }
      }
    }

    loadFullEvaluation();

    return () => {
      isCancelled = true;
    };
  }, [searchParams]);

  const bestProperty =
    properties.length > 0
      ? [...properties].sort((a, b) => b.grossYield - a.grossYield)[0]
      : null;

  return (
    <div className="card">
      <header className="card-header" style={{ marginBottom: 8 }}>
        <button onClick={() => navigate(-1)} className="btn btn-ghost">
          ← Back
        </button>
        <h1 className="card-title" style={{ marginTop: 8 }}>
          Rent & Yield Estimate
        </h1>
        <p className="card-subtitle">
          Average rent appears first. Sample properties and yields load
          afterwards.
        </p>
      </header>

      <div className="summary-card">
        <div>
          <div className="summary-label">Estimated average monthly rent</div>
          <div className="summary-value">
            {averageRent !== null ? (
              <>${averageRent.toLocaleString()}</>
            ) : (
              <span>Loading rent estimate…</span>
            )}
          </div>
        </div>
        <div>
          <div className="summary-pill">
            {isPropertiesLoading
              ? "Loading sample properties…"
              : `${properties.length} sample properties`}
          </div>
        </div>
      </div>

      <div className="results-grid">
        {/* Left: search summary + best property */}
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
              <h3 style={{ marginTop: 12 }}>Top yield candidate</h3>
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
                {bestProperty.url && (
                  <div>
                    Listing:{" "}
                    <a
                      href={bestProperty.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      View on site
                    </a>
                  </div>
                )}
              </div>
            </>
          )}
        </section>

        {/* Right: properties table */}
        <section className="results-section">
          <h3>Sample properties</h3>

          {error && <div className="error-box">{error}</div>}

          {isPropertiesLoading && !properties.length && (
            <p>Loading properties from Perplexity + OpenAI…</p>
          )}

          {!isPropertiesLoading && properties.length === 0 && !error && (
            <p>No sample properties found for this search.</p>
          )}

          {properties.length > 0 && (
            <div className="table-wrapper">
              <table className="results-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Location</th>
                    <th>Listing</th>
                    <th>Price</th>
                    <th>Est. Rent</th>
                    <th>Gross Yield</th>
                  </tr>
                </thead>
                <tbody>
                  {properties.map((p, idx) => (
                    <tr key={p.id || idx}>
                      <td>{idx + 1}</td>
                      <td>{p.address}</td>
                      <td>
                        {p.url ? (
                          <a href={p.url} target="_blank" rel="noreferrer">
                            Open listing
                          </a>
                        ) : (
                          <span>—</span>
                        )}
                      </td>
                      <td>${p.price.toLocaleString()}</td>
                      <td>${p.estimatedRent.toLocaleString()}</td>
                      <td>{(p.grossYield * 100).toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default ResultsPage;
