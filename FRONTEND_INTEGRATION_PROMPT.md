# Frontend Integration Prompt for External Fact Check Details

## Context
The backend API now returns detailed external fact check results in the Hallucination Score category. When a user navigates to **Hallucination → External Fact Verification**, they should see a comprehensive breakdown of all claims, their verification status, sources, and explanations.

## API Response Structure

The API response includes a new field `externalFactCheckDetails` in the `HallucinationSubScore` object. This field contains:

```typescript
interface ExternalFactCheckDetails {
  sub_score_name: string;  // "External Fact Check"
  score: number;           // 0-100 overall score
  coverage: number;        // 0-1 (percentage of claims with evidence)
  claims: ExternalFactCheckClaim[];
  sources_used: string[];  // Array of source URLs
  notes: string[];         // Additional notes or warnings
}

interface ExternalFactCheckClaim {
  id: string;              // Unique claim identifier (e.g., "c1", "c2")
  claim: string;           // The factual claim text (enriched with context)
  claim_type: string;       // Type of claim (default: "general")
  original_span: string;    // Original text span from the response
  risk: string;            // Risk level (default: "medium")
  verdict: "SUPPORTED" | "REFUTED" | "NOT_ENOUGH_INFO";  // Verification result
  confidence: number;      // 0-1 confidence score (1.0 for SUPPORTED, 0.0 for REFUTED)
  top_evidence: ExternalFactCheckEvidence[];
}

interface ExternalFactCheckEvidence {
  url: string;             // Full URL to the source page (clickable)
  title: string;           // Title or description of the source
  snippet: string;         // Relevant snippet/explanation from the source
  source_rank: number;     // Rank in search results (1, 2, 3, etc.)
  domain: string;          // Domain name (e.g., "en.wikipedia.org")
}
```

## Location in API Response

The data is nested in the comparison response and is **specifically linked to the "Checking facts against external sources" scorecard**:

```
comparisonResponse.platforms[].detailedScores.scores[].subScores.externalFactCheckDetails
```

**Important:** 
1. Find the score where `name === "Hallucination Score"`
2. Access `subScores.factCheckingScore` - this is the "Checking facts against external sources" score (0-10)
3. Access `subScores.externalFactCheckDetails` - this contains all the detailed results for that scorecard

**Full Path:**
```typescript
const hallucinationScore = platforms[i].detailedScores.scores.find(
  s => s.name === "Hallucination Score"
);

// The score displayed in the "Checking facts against external sources" card
const factCheckingScore = hallucinationScore.subScores.factCheckingScore; // 0-10

// The detailed results (claims, sources, explanations) for that scorecard
const factCheckDetails = hallucinationScore.subScores.externalFactCheckDetails;
```

**Note:** The `factCheckingScore` (0-10) is derived from the external fact check score (0-100) and represents the same verification. The `externalFactCheckDetails` contains all the detailed breakdown.

## Frontend Requirements

### 1. Navigation Path
- Add a new section/tab: **Hallucination → External Fact Verification**
- This should be accessible from the detailed scores view

### 2. Display Components Needed

#### Summary Card
- **Overall Score**: Display `externalFactCheckDetails.score` (0-100) with visual indicator (color-coded: green 80+, yellow 60-79, red <60)
- **Coverage**: Display `externalFactCheckDetails.coverage` as percentage (e.g., "100% coverage")
- **Claims Count**: Total number of claims verified
- **Sources Count**: Total number of unique sources used

#### Claims List
For each claim in `externalFactCheckDetails.claims`:
- **Claim Text**: Display `claim.claim` (the enriched, context-aware claim)
- **Verification Status**: 
  - Show badge/icon: ✅ "SUPPORTED" (green), ❌ "REFUTED" (red), ⚠️ "NOT_ENOUGH_INFO" (yellow)
  - Display `claim.verdict` clearly
- **Confidence**: Show `claim.confidence` as percentage or progress bar
- **Original Span**: Optionally show `claim.original_span` in a collapsible section to show where it came from in the original response

#### Sources Section (per claim)
For each evidence in `claim.top_evidence`:
- **Source Link**: Clickable link using `evidence.url` (full URL)
- **Source Title**: Display `evidence.title` or `evidence.domain` as fallback
- **Snippet/Explanation**: Display `evidence.snippet` (this contains the verification explanation)
- **Rank Indicator**: Optionally show `evidence.source_rank` to indicate relevance

#### All Sources Summary
- Display a deduplicated list of all `sources_used` URLs
- Make each URL clickable
- Group by domain if helpful

### 3. UI/UX Recommendations

- **Layout**: Use a card-based layout with expandable sections
- **Color Coding**: 
  - SUPPORTED claims: Green background/border
  - REFUTED claims: Red background/border
  - NOT_ENOUGH_INFO: Yellow/amber background/border
- **Interactivity**:
  - Expandable claim cards to show/hide evidence details
  - Clickable source URLs that open in new tab
  - Filter/search by verdict type
  - Sort by confidence or claim ID
- **Empty States**: 
  - If `externalFactCheckDetails` is `null`, show message: "External fact check not available for this response"
  - If `claims` array is empty, show: "No claims extracted from this response"

### 4. Example Data Structure

```json
{
  "platforms": [
    {
      "detailedScores": {
        "scores": {
          "hallucinationSubScore": {
            "externalFactCheckScore": 80,
            "externalFactCheckDetails": {
              "sub_score_name": "External Fact Check",
              "score": 80,
              "coverage": 1.0,
              "claims": [
                {
                  "id": "c1",
                  "claim": "New York City has a population of 8.8 million people according to the 2020 census",
                  "verdict": "SUPPORTED",
                  "confidence": 1.0,
                  "top_evidence": [
                    {
                      "url": "https://www.census.gov/quickfacts/newyorkcitynewyork",
                      "title": "census.gov - New York City Demographics",
                      "snippet": "The 2020 census confirmed that New York City's population is approximately 8.5 million...",
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
              "notes": ["3 claim(s) verified as TRUE, 2 claim(s) verified as FALSE"]
            }
          }
        }
      }
    }
  ]
}
```

### 5. Implementation Checklist

- [ ] Add route/navigation to External Fact Verification view
- [ ] Create summary card component showing overall score and metrics
- [ ] Create claim card component with verdict, confidence, and evidence
- [ ] Create source link component with clickable URLs
- [ ] Add expandable sections for detailed evidence
- [ ] Implement filtering/sorting for claims
- [ ] Add empty state handling
- [ ] Add loading states while data is being fetched
- [ ] Style with color coding for verdicts
- [ ] Test with real API responses

### 6. Key Points

- All source URLs are **full, clickable URLs** (not just domains)
- The `snippet` field in evidence contains the **explanation** of why the claim was verified
- Claims are **enriched with context** (e.g., "the city" becomes "New York City")
- The `verdict` field is the primary indicator: SUPPORTED = True, REFUTED = False
- `confidence` is 1.0 for SUPPORTED, 0.0 for REFUTED, and varies for NOT_ENOUGH_INFO

## Testing

Test with a comparison that includes the Hallucination Score category. Verify:
1. Data is correctly extracted from the nested path
2. All claims are displayed
3. All source URLs are clickable and open correctly
4. Verdict badges are color-coded correctly
5. Empty states work when data is missing
