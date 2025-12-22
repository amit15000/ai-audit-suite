# External Fact Check API Response Path

## ✅ YES - The data IS being sent to the frontend!

The external fact check details are automatically included in the API response and are **linked to the "Checking facts against external sources" scorecard** (which corresponds to `factCheckingScore`).

## API Response Structure

### Full Path to External Fact Check Details:
```
GET /api/v1/comparison/{comparisonId}/results

Response:
{
  "platforms": [
    {
      "id": "platform_id",
      "name": "Platform Name",
      "detailedScores": {
        "scores": [
          {
            "name": "Hallucination Score",
            "value": 8,
            "subScores": {
              "factCheckingScore": 8,  // ← This is the "Checking facts against external sources" score (0-10)
              "fabricatedCitationsScore": 7,
              "contradictoryInfoScore": 9,
              "multiLLMComparisonScore": 8,
              "externalFactCheckScore": 80,  // Original 0-100 scale
              "externalFactCheckDetails": {  // ← THIS IS THE DATA FOR "Checking facts against external sources"
                "sub_score_name": "External Fact Check",
                "score": 80,
                "coverage": 1.0,
                "claims": [
                  {
                    "id": "c1",
                    "claim": "New York City has a population of 8.8 million people...",
                    "claim_type": "general",
                    "original_span": "The city has a population...",
                    "risk": "medium",
                    "verdict": "SUPPORTED",
                    "confidence": 1.0,
                    "top_evidence": [
                      {
                        "url": "https://www.census.gov/quickfacts/newyorkcitynewyork",
                        "title": "census.gov - New York City Demographics",
                        "snippet": "The 2020 census confirmed that New York City's population...",
                        "source_rank": 1,
                        "domain": "census.gov"
                      }
                    ]
                  }
                ],
                "sources_used": [
                  "https://www.census.gov/quickfacts/newyorkcitynewyork",
                  "https://en.wikipedia.org/wiki/New_York_City"
                ],
                "notes": [
                  "3 claim(s) verified as TRUE",
                  "2 claim(s) verified as FALSE"
                ]
              }
            }
          }
        ]
      }
    }
  ]
}
```

## How to Access in Frontend

### JavaScript/TypeScript Path:
```typescript
// Get the first platform's external fact check details
// These details are associated with the "Checking facts against external sources" scorecard
const platform = response.data.platforms[0];
const hallucinationScore = platform.detailedScores.scores.find(
  score => score.name === "Hallucination Score"
);

if (hallucinationScore?.subScores) {
  // The "Checking facts against external sources" score (0-10 scale)
  const factCheckingScore = hallucinationScore.subScores.factCheckingScore;
  
  // The detailed external fact check results (for the scorecard above)
  const factCheckDetails = hallucinationScore.subScores.externalFactCheckDetails;
  
  if (factCheckDetails) {
    // Access the data:
    console.log("Score (0-10):", factCheckingScore); // Displayed in the scorecard
    console.log("Overall Score (0-100):", factCheckDetails.score); // Detailed score
    console.log("Coverage:", factCheckDetails.coverage); // 0-1
    console.log("Claims:", factCheckDetails.claims); // Array of claims
    console.log("Sources:", factCheckDetails.sources_used); // Array of URLs
  }
}
```

### React Example:
```typescript
interface ExternalFactCheckDetails {
  sub_score_name: string;
  score: number;
  coverage: number;
  claims: Array<{
    id: string;
    claim: string;
    verdict: "SUPPORTED" | "REFUTED" | "NOT_ENOUGH_INFO";
    confidence: number;
    top_evidence: Array<{
      url: string;
      title: string;
      snippet: string;
      source_rank: number;
      domain: string;
    }>;
  }>;
  sources_used: string[];
  notes: string[];
}

// In your component:
const getExternalFactCheckDetails = (platform: PlatformResult): ExternalFactCheckDetails | null => {
  const hallucinationScore = platform.detailedScores.scores.find(
    s => s.name === "Hallucination Score"
  );
  
  if (hallucinationScore?.subScores && 'externalFactCheckDetails' in hallucinationScore.subScores) {
    return (hallucinationScore.subScores as any).externalFactCheckDetails;
  }
  
  return null;
};
```

## Data Flow in Backend

1. **HallucinationScorer** calculates external fact check → returns `HallucinationSubScore` with `externalFactCheckDetails`
2. **AuditScorer** receives `HallucinationSubScore` → assigns to `AuditScore.subScores`
3. **AuditScore** is added to `AuditorDetailedScores.scores` array
4. **PlatformResult** contains `AuditorDetailedScores` in `detailedScores` field
5. **ComparisonResponse** contains `PlatformResult[]` in `platforms` array
6. **FastAPI** automatically serializes Pydantic models to JSON → sent to frontend

## Important Notes

- ✅ The data is **automatically included** - no additional API calls needed
- ✅ Available in the same comparison results endpoint
- ✅ Serialized as JSON automatically by Pydantic
- ✅ Available for **all platforms** in the comparison
- ⚠️ If external fact check calculation fails, `externalFactCheckDetails` will be `null`
- ⚠️ If no claims are extracted, `claims` array will be empty

## Testing

To verify the data is present:
1. Make a comparison request with Hallucination Score enabled
2. Check the response at: `platforms[].detailedScores.scores[].subScores.externalFactCheckDetails`
3. Verify the structure matches the TypeScript interface above
