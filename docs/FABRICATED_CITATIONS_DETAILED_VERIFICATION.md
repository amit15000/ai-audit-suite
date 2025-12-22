# Fabricated Citations - Detailed Verification

## Overview

The fabricated citations detection system has been enhanced to verify citations across multiple academic and legal sources, providing detailed JSON reports with verification status for each citation.

## Features

### 1. Citation Enrichment
- Extracts metadata from citations:
  - **Title**: Article/paper title
  - **Authors**: Author names
  - **Year**: Publication year
  - **DOI**: Digital Object Identifier
  - **Source Type**: Academic, legal, web, or unknown

### 2. Multi-Source Verification
Citations are verified across multiple sources:

- **DOI Resolver** (`doi.org`)
  - Verifies DOI citations
  - Provides canonical URL to the source
  - High confidence (0.9)

- **PubMed** (`pubmed.ncbi.nlm.nih.gov`)
  - Verifies medical/biological research citations
  - Searches by DOI, title, or author/year
  - Medium-high confidence (0.8)

- **Google Scholar** (`scholar.google.com`)
  - Verifies academic citations
  - Searches by title, authors, and year
  - Medium confidence (0.5-0.7)

- **CourtListener** (`www.courtlistener.com`)
  - Verifies legal citations
  - Searches for court cases and legal documents
  - Medium confidence (0.6)

- **Web URL Verification**
  - Verifies direct web URLs
  - Checks accessibility and follows redirects
  - Medium-high confidence (0.8)

### 3. Detailed JSON Response

The system returns a comprehensive JSON report:

```json
{
  "total_citations": 3,
  "verified_count": 2,
  "fabricated_count": 1,
  "score": 7,
  "citations": [
    {
      "index": 1,
      "original_citation": "https://www.example.com/article",
      "verified": true,
      "verified_source_url": "https://www.example.com/article",
      "verification_sources": [
        {
          "source_name": "web",
          "verified": true,
          "source_url": "https://www.example.com/article",
          "confidence": 0.8,
          "error": null
        }
      ],
      "metadata": {
        "title": "Example Article",
        "authors": null,
        "year": null,
        "doi": null,
        "source_type": "web"
      }
    },
    {
      "index": 2,
      "original_citation": "DOI: 10.1038/s41586-2023-12345",
      "verified": true,
      "verified_source_url": "https://www.nature.com/articles/s41586-2023-12345",
      "verification_sources": [
        {
          "source_name": "doi",
          "verified": true,
          "source_url": "https://www.nature.com/articles/s41586-2023-12345",
          "confidence": 0.9,
          "error": null
        },
        {
          "source_name": "pubmed",
          "verified": true,
          "source_url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
          "confidence": 0.8,
          "error": null
        },
        {
          "source_name": "google_scholar",
          "verified": true,
          "source_url": "https://scholar.google.com/scholar?q=...",
          "confidence": 0.7,
          "error": null
        }
      ],
      "metadata": {
        "title": "Research Paper Title",
        "authors": ["Author 1", "Author 2"],
        "year": 2023,
        "doi": "10.1038/s41586-2023-12345",
        "source_type": "academic"
      }
    },
    {
      "index": 3,
      "original_citation": "https://fake-url-xyz.com/article",
      "verified": false,
      "verified_source_url": null,
      "verification_sources": [
        {
          "source_name": "web",
          "verified": false,
          "source_url": null,
          "confidence": 0.0,
          "error": "URL not accessible (status: 404)"
        }
      ],
      "metadata": {
        "title": null,
        "authors": null,
        "year": null,
        "doi": null,
        "source_type": "web"
      }
    }
  ]
}
```

## Usage

### Basic Usage

```python
from app.services.comparison.citation_verifier import CitationVerifier
from app.services.comparison.citation_enricher import CitationEnricher
from app.services.comparison.citation_source_verifier import CitationSourceVerifier
from app.services.comparison.hallucination.fabricated_citations import FabricatedCitationsScorer
from app.services.llm.ai_platform_service import AIPlatformService

# Initialize services
citation_verifier = CitationVerifier()
ai_service = AIPlatformService()
citation_enricher = CitationEnricher()
source_verifier = CitationSourceVerifier()

# Create scorer
scorer = FabricatedCitationsScorer(
    citation_verifier,
    ai_service,
    citation_enricher,
    source_verifier
)

# Get detailed verification report
response = "According to DOI: 10.1038/s41586-2023-12345, the research shows..."
report = await scorer.get_detailed_verification_report(
    response,
    judge_platform_id="openai",
    use_llm=False
)

print(json.dumps(report, indent=2))
```

### Simple Score Calculation

```python
# Just get the score (0-10)
score = await scorer.calculate_score(
    response,
    judge_platform_id="openai",
    use_llm=False
)
print(f"Score: {score}/10")
```

## API Integration

The detailed verification report can be integrated into the API response. The report is available via:

```python
# In your API endpoint
report = await fabricated_citations_scorer.get_detailed_verification_report(
    response,
    judge_platform_id,
    use_llm=use_llm
)
```

## Testing

### Run the Test Script

```bash
python scripts/test_fabricated_citations_detailed.py
```

This will test:
- Academic citations with DOI
- Legal citations (CourtListener)
- Mixed citations (valid and fabricated)
- Web URLs

### Run Unit Tests

```bash
pytest tests/test_fabricated_citations.py -v
```

## Score Calculation

The score (0-10) is calculated based on:

- **9-10**: All citations verified (100% verified)
- **8**: Most citations verified (≥90% verified)
- **7**: Many citations verified (≥70% verified)
- **6**: Moderate verification (50-70% verified)
- **4**: Low verification (30-50% verified)
- **2**: Very low verification (10-30% verified)
- **1**: Critical (≤10% verified)
- **6**: No citations found (neutral)

## Source Priority

When multiple sources verify a citation, the system uses:
1. **DOI** (highest confidence: 0.9)
2. **PubMed** (high confidence: 0.8)
3. **Web URL** (high confidence: 0.8)
4. **Google Scholar** (medium confidence: 0.5-0.7)
5. **CourtListener** (medium confidence: 0.6)

The `verified_source_url` field contains the URL from the highest confidence source.

## Error Handling

- If a source verification fails, it's included in `verification_sources` with `verified: false` and an `error` message
- The overall citation is marked as `verified: false` only if ALL sources fail
- Network errors, timeouts, and invalid formats are handled gracefully

## Limitations

1. **Google Scholar**: Uses web scraping (simplified). For production, consider using Google Scholar API if available.
2. **PubMed**: Uses web search. For production, consider using PubMed API (E-utilities).
3. **CourtListener**: Uses web search. For production, consider using CourtListener API if available.
4. **Rate Limiting**: Be mindful of rate limits when verifying many citations.

## Future Enhancements

- Add support for more sources (arXiv, SSRN, etc.)
- Implement caching for verified citations
- Add batch verification for multiple citations
- Improve HTML parsing for better metadata extraction
- Add support for citation format detection (APA, MLA, etc.)
