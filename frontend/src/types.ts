// src/types.ts

export interface SearchParams {
    minPrice: number;
    maxPrice: number;
    area: string;
    bedrooms: number;
    minSqft: number;
    maxSqft: number;
  }
  
  export interface PropertyResult {
    id: string;
    address: string;
    price: number;
    bedrooms: number;
    sqft: number;
    estimatedRent: number;
    grossYield: number;
  }
  
  export interface EvaluationResponse {
    averageRent: number;
    currency: string;
    properties: PropertyResult[];
  }
  