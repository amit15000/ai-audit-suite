# External Fact Check Testing Guide

This guide explains how to test the External Fact Check sub-score feature.

## Prerequisites

### 1. Install Dependencies

Make sure you have all required packages installed:

```bash
pip install -r requirements.txt
```

This includes:
- `duckduckgo-search>=6.0.0` (for web search - DuckDuckGo, free, no API key, no C compilation needed)
- `trafilatura>=1.6.0` (for text extraction from web pages)

### 2. Set Up Environment Variables

Create or update your `.env` file with:

```env
# External Fact Check Configuration
EXTERNAL_FACT_CHECK_ENABLED=true
EXTERNAL_FACT_CHECK_SEARCH_PROVIDER=duckduckgo  # Options: "duckduckgo" (free, default) or "serpapi" (requires API key)
EXTERNAL_FACT_CHECK_TOP_K_RESULTS=5
EXTERNAL_FACT_CHECK_CLAIM_EXTRACTION_USE_LLM=true
EXTERNAL_FACT_CHECK_VERIFICATION_TIMEOUT=30
EXTERNAL_FACT_CHECK_SEARCH_TIMEOUT=10
EXTERNAL_FACT_CHECK_MAX_CLAIMS_PER_RESPONSE=20

# Only needed if EXTERNAL_FACT_CHECK_SEARCH_PROVIDER=serpapi
# EXTERNAL_FACT_CHECK_SERPAPI_API_KEY=your-serpapi-api-key-here
# Or: SERPAPI_API_KEY=your-serpapi-api-key-here

# Required for LLM-based claim extraction and verification
OPENAI_API_KEY=your-openai-api-key-here
# Or use other LLM providers:
# GROQ_API_KEY=your-groq-api-key-here
# GEMINI_API_KEY=your-gemini-api-key-here
```

**Search Provider Options:**
- **DuckDuckGo (Default, Recommended)**: Free, no API key required. Just set `EXTERNAL_FACT_CHECK_SEARCH_PROVIDER=duckduckgo` (or leave default)
- **SerpAPI (Optional)**: Requires API key. Sign up at https://serpapi.com/ (100 searches/month free tier). Set `EXTERNAL_FACT_CHECK_SEARCH_PROVIDER=serpapi` and add your API key.

## Testing Methods

### Method 1: Run Unit Tests

Run the comprehensive test suite:

```bash
# Run all external fact check tests
pytest tests/test_external_fact_check.py -v

# Run specific test class
pytest tests/test_external_fact_check.py::TestClaimExtractor -v

# Run specific test
pytest tests/test_external_fact_check.py::TestClaimExtractor::test_extract_claims_rule_based_basic -v

# Run with coverage
pytest tests/test_external_fact_check.py --cov=app.services.comparison.hallucination.external_fact_check --cov-report=html
```

### Method 2: Run Integration Tests

Test the full flow with mocked external calls:

```bash
# Run integration tests
pytest tests/test_external_fact_check.py::TestExternalFactCheckIntegration -v
```

### Method 3: Manual Python Testing

Create a test script to test the components directly:

```python
# test_external_fact_check_manual.py
import asyncio
from app.services.comparison.hallucination.external_fact_check import (
    ClaimExtractor,
    ExternalFactCheckScorer,
)
from app.services.llm.ai_platform_service import AIPlatformService

async def test_claim_extraction():
    """Test claim extraction."""
    ai_service = AIPlatformService()
    extractor = ClaimExtractor(use_llm=True, ai_service=ai_service)
    
    response = """
    New York City has a population of 8.5 million people. 
    In 2020, the city experienced significant growth. 
    According to recent research, 50% of residents prefer public transportation.
    """
    
    claims = await extractor.extract_claims(response, max_claims=10)
    print(f"Extracted {len(claims)} claims:")
    for claim in claims:
        print(f"  - {claim.id}: {claim.claim[:60]}... ({claim.claim_type}, risk: {claim.risk})")

async def test_full_scoring():
    """Test full external fact check scoring."""
    ai_service = AIPlatformService()
    scorer = ExternalFactCheckScorer(ai_service, "openai")
    
    response = """
    The population of New York City is 8.5 million people according to the 2020 census.
    The city covers an area of 468 square miles.
    Research shows that 50% of residents use public transportation daily.
    """
    
    result = await scorer.calculate_sub_score(response)
    
    print(f"\nExternal Fact Check Results:")
    print(f"  Score: {result.score}/100")
    print(f"  Coverage: {result.coverage:.2%}")
    print(f"  Claims Verified: {len(result.claims)}")
    print(f"  Sources Used: {len(result.sources_used)}")
    
    print(f"\nClaim Details:")
    for claim in result.claims:
        print(f"  - {claim.claim[:60]}...")
        print(f"    Verdict: {claim.verdict}, Confidence: {claim.confidence:.2f}")
        print(f"    Evidence: {len(claim.top_evidence)} sources")

if __name__ == "__main__":
    asyncio.run(test_claim_extraction())
    print("\n" + "="*50 + "\n")
    asyncio.run(test_full_scoring())
```

Run it:
```bash
python test_external_fact_check_manual.py
```

### Method 4: Test via API Endpoint

Test through the comparison/audit API endpoint:

#### 1. Start the Server

```bash
uvicorn app.main:app --reload
```

#### 2. Test via cURL

```bash
curl -X POST http://localhost:8000/api/v1/comparison \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Tell me about New York City",
    "platforms": ["openai"],
    "judge_platform": "openai"
  }'
```

#### 3. Test via Python Requests

```python
import requests
import json

url = "http://localhost:8000/api/v1/comparison"
payload = {
    "prompt": "New York City has a population of 8.5 million people. The city was founded in 1624.",
    "platforms": ["openai"],
    "judge_platform": "openai"
}

response = requests.post(url, json=payload)
data = response.json()

# Check external fact check score
for platform_result in data.get("results", []):
    scores = platform_result.get("detailedScores", {}).get("scores", [])
    for score in scores:
        if score.get("name") == "Hallucination Score":
            sub_scores = score.get("subScores", {})
            external_fact_check = sub_scores.get("externalFactCheckScore")
            print(f"External Fact Check Score: {external_fact_check}/100")
```

#### 4. Test via API Docs (Swagger UI)

1. Start the server: `uvicorn app.main:app --reload`
2. Open http://localhost:8000/docs
3. Find the `/api/v1/comparison` endpoint
4. Click "Try it out"
5. Enter test data and execute
6. Check the response for `externalFactCheckScore` in the Hallucination Score sub-scores

## Test Scenarios

### Scenario 1: Test with Factual Claims

**Input:**
```
The population of New York City is 8.5 million people according to the 2020 census.
The city covers an area of 468 square miles.
```

**Expected:**
- Claims extracted: 2-3 claims
- Evidence retrieved for each claim
- Verdicts: SUPPORTED (if evidence confirms)
- Score: 60-90/100 (depending on verification)

### Scenario 2: Test with False Claims

**Input:**
```
The population of New York City is 50 million people.
The city was founded in 1500.
```

**Expected:**
- Claims extracted: 2 claims
- Evidence retrieved
- Verdicts: REFUTED (if evidence contradicts)
- Score: 20-40/100 (lower due to refuted claims)

### Scenario 3: Test with Unverifiable Claims

**Input:**
```
The city has a unique cultural atmosphere.
Many people enjoy living there.
```

**Expected:**
- Fewer claims extracted (opinion statements filtered)
- Verdicts: NOT_ENOUGH_INFO (if no specific facts)
- Score: 40-60/100 (neutral)

### Scenario 4: Test with Research Claims

**Input:**
```
According to a 2023 study, 75% of residents prefer public transportation.
Research shows that the city's economy grew by 5% last year.
```

**Expected:**
- Claims extracted: 2 claims (high risk)
- Evidence retrieved
- Verdicts: SUPPORTED/REFUTED/NOT_ENOUGH_INFO
- Score: Varies based on evidence

## Debugging

### Enable Debug Logging

Set log level in `.env`:
```env
LOG_LEVEL=DEBUG
```

### Check Logs

The system logs key operations:
- Claim extraction (LLM vs rule-based)
- Evidence retrieval (SerpAPI calls)
- Verification results
- Score calculation

Look for log entries like:
```
llm_extraction_success
using_rule_based_extraction
serpapi_key_missing
evidence_retrieval_error
verification_timeout
```

### Common Issues

#### 1. No Claims Extracted

**Symptoms:** Score is 50, no claims in result

**Solutions:**
- Check if response contains factual statements
- Verify LLM extraction is working (check logs)
- Try with `EXTERNAL_FACT_CHECK_CLAIM_EXTRACTION_USE_LLM=false` to test rule-based

#### 2. No Evidence Retrieved

**Symptoms:** All claims have NOT_ENOUGH_INFO verdict

**Solutions:**
- If using DuckDuckGo (default): Check network connectivity, install `duckduckgo-search` package (`pip install duckduckgo-search`)
- If using SerpAPI: Verify `SERPAPI_API_KEY` is set correctly, check quota (free tier: 100 searches/month)
- Review logs for search errors
- Try switching to DuckDuckGo: `EXTERNAL_FACT_CHECK_SEARCH_PROVIDER=duckduckgo`

#### 3. Verification Timeout

**Symptoms:** Some claims not verified, timeout warnings in logs

**Solutions:**
- Increase `EXTERNAL_FACT_CHECK_VERIFICATION_TIMEOUT`
- Check LLM API key and quota
- Reduce `EXTERNAL_FACT_CHECK_MAX_CLAIMS_PER_RESPONSE`

#### 4. LLM Extraction Fails

**Symptoms:** Falls back to rule-based extraction

**Solutions:**
- Verify LLM API key is set (OPENAI_API_KEY, etc.)
- Check LLM API quota
- Review logs for LLM errors
- Rule-based fallback should still work

## Performance Testing

### Test with Different Response Lengths

```python
# Short response
short_response = "New York City has 8.5 million people."

# Medium response
medium_response = """
New York City has a population of 8.5 million people.
The city covers 468 square miles.
In 2020, the city experienced growth.
"""

# Long response
long_response = """
[Long text with many factual claims...]
"""

# Test each
for response in [short_response, medium_response, long_response]:
    result = await scorer.calculate_sub_score(response)
    print(f"Response length: {len(response)}, Claims: {len(result.claims)}, Time: {result.score}")
```

### Test Concurrency

The system uses bounded concurrency (max 3 parallel searches). Test with multiple claims:

```python
response = """
Claim 1: New York has 8.5 million people.
Claim 2: Los Angeles has 4 million people.
Claim 3: Chicago has 2.7 million people.
Claim 4: Houston has 2.3 million people.
Claim 5: Phoenix has 1.6 million people.
"""
```

## Validation Checklist

- [ ] Unit tests pass: `pytest tests/test_external_fact_check.py -v`
- [ ] Integration tests pass
- [ ] SerpAPI key is configured
- [ ] LLM API key is configured (for LLM extraction)
- [ ] Claims are extracted from test responses
- [ ] Evidence is retrieved for claims
- [ ] Verdicts are assigned (SUPPORTED/REFUTED/NOT_ENOUGH_INFO)
- [ ] Scores are calculated (0-100 range)
- [ ] Coverage metric is calculated
- [ ] API endpoint returns externalFactCheckScore
- [ ] Logs show proper operation flow

## Next Steps

- Review the [Architecture Documentation](architecture.md)
- Check the [API Routes Guide](API_ROUTES_GUIDE.md)
- See [Local Setup Guide](LOCAL_SETUP.md) for environment setup
