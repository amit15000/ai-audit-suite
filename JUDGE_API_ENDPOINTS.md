# Judge LLM Evaluation - API Endpoints

## Main API Endpoint

### `GET /api/v1/comparison/{comparison_id}/results`

This is the **primary endpoint** where you can see judge LLM evaluation results.

**Full URL:** `http://localhost:8001/api/v1/comparison/{comparison_id}/results`

**Method:** GET

**Headers:**
```
Authorization: Bearer {your_jwt_token}
```

**Response Structure:**
```json
{
  "success": true,
  "data": {
    "comparisonId": "comp_abc123",
    "messageId": "msg_xyz789",
    "prompt": "Explain quantum computing",
    "timestamp": "2025-11-29T03:00:00",
    "status": "completed",
    "judge": {
      "id": "openai",
      "name": "OpenAI"
    },
    "platforms": [
      {
        "id": "openai",
        "name": "OpenAI",
        "score": 85,
        "response": "Full response text...",
        "detailedScores": {
          "auditorId": "openai",
          "auditorName": "OpenAI",
          "overallScore": 7,
          "scores": [...]
        },
        "topReasons": [...],
        "judgeEvaluation": {
          "scores": {
            "accuracy": 9,
            "completeness": 8,
            "clarity": 9,
            "reasoning": 8,
            "safety": 10,
            "hallucination_risk": 2
          },
          "trustScore": 8.7,
          "fallbackApplied": false,
          "weights": {
            "accuracy": 0.25,
            "completeness": 0.20,
            "clarity": 0.15,
            "reasoning": 0.15,
            "safety": 0.15,
            "hallucination_risk": 0.10
          }
        }
      }
    ],
    "sortedBy": "score",
    "winner": {
      "id": "openai",
      "name": "OpenAI",
      "score": 85
    }
  }
}
```

**Judge Evaluation Fields:**
- `judgeEvaluation.scores` - Individual criterion scores (0-10)
  - `accuracy` - Factual correctness
  - `completeness` - How fully question is addressed
  - `clarity` - Readability and structure
  - `reasoning` - Quality of logical reasoning
  - `safety` - Absence of harmful content
  - `hallucination_risk` - Likelihood of unsupported claims
- `judgeEvaluation.trustScore` - Weighted trust score (0-10)
- `judgeEvaluation.fallbackApplied` - Whether fallback scores were used
- `judgeEvaluation.weights` - Weights used for trust score calculation

---

## Workflow

### Step 1: Submit Comparison
**POST** `/api/v1/comparison/submit`

Include `judge` field in request:
```json
{
  "prompt": "Explain quantum computing",
  "platforms": ["openai", "gemini"],
  "judge": "openai"
}
```

### Step 2: Check Status (Optional)
**GET** `/api/v1/comparison/{comparison_id}/status`

Wait until `status` is `"completed"`

### Step 3: Get Results (Contains Judge Evaluation)
**GET** `/api/v1/comparison/{comparison_id}/results`

This endpoint returns judge evaluation in `platforms[].judgeEvaluation`

---

## Example cURL Commands

### 1. Submit Comparison
```bash
curl -X POST http://localhost:8001/api/v1/comparison/submit \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is machine learning?",
    "platforms": ["openai", "gemini", "groq"],
    "judge": "openai"
  }'
```

### 2. Get Results (with Judge Evaluation)
```bash
curl -X GET http://localhost:8001/api/v1/comparison/comp_abc123/results \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Notes

- Judge evaluation is **automatically included** when you submit a comparison with a `judge` field
- Each platform's response gets evaluated by the judge LLM
- Judge evaluation may be `null` if evaluation failed (comparison still completes)
- The `overallScore` (60-100) uses judge `trustScore` when available and valid
- Judge evaluation is stored in the comparison results JSON in the database

