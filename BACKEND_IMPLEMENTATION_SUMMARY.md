# Backend Implementation Summary - External Fact Check API Response

## ✅ Implementation Status

All requirements have been implemented. The backend now sends external fact check details in the correct format.

## Key Changes Made

### 1. Event Emission (`audit_scorer.py`)
- ✅ Changed `sub_scores` to `subScores` (camelCase) in event data
- ✅ Ensured `subScores` is always an object (dict), never an array
- ✅ Added validation to ensure proper serialization

### 2. Error Handling (`hallucination_scorer.py`)
- ✅ On error, sends `ExternalFactCheckResult` with error notes (not null)
- ✅ Always includes all required fields (empty arrays if no data)

### 3. Explanation Storage (`external_fact_check.py`)
- ✅ Explanation is stored in `evidence[0].snippet` (first evidence gets full explanation)
- ✅ All required fields are always present

## API Response Structure

### Streaming Event (`audit_score`)
```json
{
  "type": "audit_score",
  "platform_id": "openai",
  "data": {
    "score_name": "Hallucination Score",
    "score_value": 8,
    "category": "Hallucination",
    "explanation": "...",
    "subScores": {
      "factCheckingScore": 8,
      "fabricatedCitationsScore": 7,
      "contradictoryInfoScore": 9,
      "multiLLMComparisonScore": 8,
      "externalFactCheckScore": 80,
      "externalFactCheckDetails": {
        "sub_score_name": "External Fact Check",
        "score": 80,
        "coverage": 1.0,
        "claims": [...],
        "sources_used": [...],
        "notes": [...]
      }
    }
  }
}
```

### Final Results (`/api/v1/comparison/{id}/results`)
```json
{
  "platforms": [{
    "detailedScores": {
      "scores": [{
        "name": "Hallucination Score",
        "value": 8,
        "subScores": {
          "factCheckingScore": 8,
          "externalFactCheckDetails": {...}
        }
      }]
    }
  }]
}
```

## Field Requirements - All Met ✅

### `subScores` Structure
- ✅ **Object (dict)**, not array
- ✅ `externalFactCheckDetails` is a direct property
- ✅ Path: `score.subScores.externalFactCheckDetails`

### `externalFactCheckDetails` Fields
- ✅ `sub_score_name`: Always present
- ✅ `score`: 0-100, always present
- ✅ `coverage`: 0-1, always present
- ✅ `claims`: Array (can be empty), always present
- ✅ `sources_used`: Array (can be empty), always present
- ✅ `notes`: Array (can be empty), always present

### Claim Fields
- ✅ `id`: Unique identifier
- ✅ `claim`: Claim text
- ✅ `claim_type`: Always "general"
- ✅ `original_span`: Original text
- ✅ `risk`: Always "medium"
- ✅ `verdict`: "SUPPORTED" | "REFUTED" | "NOT_ENOUGH_INFO"
- ✅ `confidence`: 0-1
- ✅ `top_evidence`: Array (can be empty)

### Evidence Fields
- ✅ `url`: Full URL (clickable)
- ✅ `title`: Source title
- ✅ `snippet`: Explanation (stored here)
- ✅ `source_rank`: Number (1, 2, 3...)
- ✅ `domain`: Domain name

## Error Handling

### On Failure
If external fact check fails, the backend sends:
```json
{
  "externalFactCheckDetails": {
    "sub_score_name": "External Fact Check",
    "score": 0,
    "coverage": 0.0,
    "claims": [],
    "sources_used": [],
    "notes": ["External fact checking failed: <error message>"]
  }
}
```

**Never sends `null`** - always includes the structure with error notes.

## Testing

To verify the implementation:

1. **Check serialization:**
   ```python
   from app.domain.schemas import HallucinationSubScore, ExternalFactCheckResult
   subscore = HallucinationSubScore(...)
   assert isinstance(subscore.model_dump(), dict)  # Must be dict, not list
   assert "externalFactCheckDetails" in subscore.model_dump()
   ```

2. **Check event emission:**
   - Verify `subScores` key in event data (camelCase)
   - Verify `subScores` is an object, not array
   - Verify `externalFactCheckDetails` exists

3. **Check final results:**
   - Verify same structure in `/api/v1/comparison/{id}/results`
   - Verify all required fields are present
   - Verify arrays are never null (empty arrays if no data)

## Files Modified

1. `app/services/comparison/audit_scorer.py`
   - Changed event emission to use `subScores` (camelCase)
   - Added validation for object structure

2. `app/services/comparison/hallucination_scorer.py`
   - Improved error handling (sends result object with error notes)
   - Linked external fact check to `factCheckingScore`

3. `app/services/comparison/hallucination/external_fact_check.py`
   - Improved explanation storage in evidence snippet
   - Ensured all required fields are always present

## Summary

✅ **All requirements met:**
- `subScores` is an object (not array)
- `externalFactCheckDetails` is a direct property
- All required fields are always present
- Error handling sends structure (not null)
- Data sent in both streaming events and final results
- Field names use camelCase (`subScores`, `externalFactCheckDetails`)

The backend is now fully compliant with frontend requirements.
