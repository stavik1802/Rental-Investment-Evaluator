// src/api.ts

import type {
  SearchParams,
  EvaluationResponse,
  RentOnlyResponse,
} from "./types";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function estimateRent(
  params: SearchParams
): Promise<RentOnlyResponse> {
  const res = await fetch(`${API_BASE}/api/estimate-rent`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(
      `Rent API error (${res.status}): ${text || res.statusText}`
    );
  }

  return res.json();
}

export async function evaluateInvestment(
  params: SearchParams
): Promise<EvaluationResponse> {
  const res = await fetch(`${API_BASE}/api/evaluate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(
      `Evaluate API error (${res.status}): ${text || res.statusText}`
    );
  }

  return res.json();
}
