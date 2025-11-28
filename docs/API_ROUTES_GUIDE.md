# API Routes Guide - Using OpenAI as Judge

This guide shows you the exact API routes to call for comparing AI responses with OpenAI as the judge.

## Prerequisites

1. **Get your access token** - Login first to get JWT token
2. **Set OPENAI_API_KEY** - Add to `.env` file for judge functionality

## API Routes

### 1. Login (Get Authentication Token)

**Endpoint:** `POST /api/v1/auth/login`

**Request:**
```bash
curl -X POST http://localhost:3001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "test123"
  }'
```

**Response:**
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "user_123",
      "email": "test@example.com",
      "name": "Test User"
    },
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refreshToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

**Save the `token` from the response - you'll need it for authenticated requests.**

---

### 2. Submit Comparison (Use OpenAI as Judge)

**Endpoint:** `POST /api/v1/comparison/submit`

**Headers:**
- `Authorization: Bearer {your_token_here}`
- `Content-Type: application/json`

**Request Body:**
```json
{
  "prompt": "Explain quantum computing in simple terms",
  "platforms": ["gemini", "groq"],
  "judge": "chatgpt"
}
```

**Available Platforms:**
- `"chatgpt"` or `"openai"` - OpenAI GPT models
- `"gemini"` - Google Gemini
- `"groq"` - **Groq API** (fast inference, uses Llama models) ✅ **Recommended**
- `"grok"` - Maps to Groq (Grok/X-Twitter not implemented, uses Groq as proxy)
- `"huggingface"` - Hugging Face (if configured)

**Note:** Use `"groq"` - it's the actual implemented platform. Grok is not implemented and will just use Groq adapter.

**Available Judges:**
- `"chatgpt"` - Uses OpenAI as judge (recommended)
- `"openai"` - Same as chatgpt
- `"gemini"` - Uses Gemini as judge
- `"groq"` - Uses Groq as judge

**Example cURL:**
```bash
curl -X POST http://localhost:3001/api/v1/comparison/submit \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain quantum computing in simple terms",
    "platforms": ["gemini", "groq"],
    "judge": "chatgpt"
  }'
```

**Response:**
```json
{
  "success": true,
  "data": {
    "comparisonId": "comp_abc123",
    "messageId": "msg_xyz789",
    "status": "queued",
    "estimatedTime": 30
  }
}
```

**Save the `comparisonId` - you'll need it to check results.**

---

### 3. Get Comparison Status

**Endpoint:** `GET /api/v1/comparison/{comparisonId}/status`

**Example:**
```bash
curl -X GET http://localhost:3001/api/v1/comparison/comp_abc123/status \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

**Response (Processing):**
```json
{
  "success": true,
  "data": {
    "comparisonId": "comp_abc123",
    "status": "processing",
    "progress": 45,
    "estimatedTimeRemaining": 16,
    "completedPlatforms": ["gemini"],
    "pendingPlatforms": ["groq"]
  }
}
```

**Response (Completed):**
```json
{
  "success": true,
  "data": {
    "comparisonId": "comp_abc123",
    "status": "completed",
    "progress": 100,
    "estimatedTimeRemaining": null,
    "completedPlatforms": ["gemini", "groq"],
    "pendingPlatforms": []
  }
}
```

---

### 4. Get Comparison Results

**Endpoint:** `GET /api/v1/comparison/{comparisonId}/results`

**Example:**
```bash
curl -X GET http://localhost:3001/api/v1/comparison/comp_abc123/results \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

**Response (Still Processing - 202 Accepted):**
```json
{
  "success": true,
  "data": {
    "comparisonId": "comp_abc123",
    "status": "processing",
    "progress": 45,
    "estimatedTimeRemaining": 16
  }
}
```

**Response (Completed - 200 OK):**
```json
{
  "success": true,
  "data": {
    "comparisonId": "comp_abc123",
    "messageId": "msg_xyz789",
    "prompt": "Explain quantum computing in simple terms",
    "timestamp": "2024-01-15T10:30:00.000Z",
    "status": "completed",
    "judge": {
      "id": "chatgpt",
      "name": "ChatGPT"
    },
    "platforms": [
      {
        "id": "gemini",
        "name": "Gemini",
        "score": 85,
        "response": "Quantum computing is a type of computing...",
        "detailedScores": {
          "auditorId": "gemini",
          "auditorName": "Gemini",
          "overallScore": 7,
          "scores": [
            {
              "name": "Hallucination Score",
              "value": 8,
              "maxValue": 10,
              "category": "Accuracy",
              "isCritical": false
            },
            {
              "name": "Factual Accuracy Score",
              "value": 7,
              "maxValue": 10,
              "category": "Accuracy",
              "isCritical": false
            }
            // ... 18 more scores
          ]
        },
        "topReasons": [
          "Strong performance in Hallucination Score (8/10)",
          "Excellent reasoning quality",
          "High safety score",
          "Good clarity and completeness",
          "Strong factual accuracy"
        ]
      },
      {
        "id": "groq",
        "name": "Groq",
        "score": 78,
        "response": "Quantum computing represents...",
        "detailedScores": { /* ... */ },
        "topReasons": [ /* ... */ ]
      }
    ],
    "sortedBy": "score",
    "winner": {
      "id": "gemini",
      "name": "Gemini",
      "score": 85
    }
  }
}
```

---

## Complete Workflow Example

```bash
# Step 1: Login
TOKEN=$(curl -s -X POST http://localhost:3001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}' \
  | jq -r '.data.token')

echo "Token: $TOKEN"

# Step 2: Submit comparison with OpenAI as judge
COMPARISON_ID=$(curl -s -X POST http://localhost:3001/api/v1/comparison/submit \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain quantum computing in simple terms",
    "platforms": ["gemini", "groq"],
    "judge": "chatgpt"
  }' | jq -r '.data.comparisonId')

echo "Comparison ID: $COMPARISON_ID"

# Step 3: Poll for results (check every 2 seconds)
while true; do
  STATUS=$(curl -s -X GET "http://localhost:3001/api/v1/comparison/$COMPARISON_ID/status" \
    -H "Authorization: Bearer $TOKEN" | jq -r '.data.status')
  
  echo "Status: $STATUS"
  
  if [ "$STATUS" == "completed" ]; then
    break
  fi
  
  sleep 2
done

# Step 4: Get final results
curl -X GET "http://localhost:3001/api/v1/comparison/$COMPARISON_ID/results" \
  -H "Authorization: Bearer $TOKEN" | jq
```

---

## How OpenAI Judge Works

When you set `"judge": "chatgpt"`:

1. **The system collects responses** from all selected platforms
2. **OpenAI evaluates each response** on 20 different criteria:
   - Hallucination Score
   - Factual Accuracy Score
   - Multi-LLM Consensus Score
   - Reasoning Quality Score
   - Safety Score
   - And 15 more...

3. **Scores are calculated** on a scale of 0-10 for each category
4. **Overall score** is calculated (60-100 range) 
5. **Top reasons** are generated for why each platform performed well
6. **Results are sorted** by score with a winner declared

---

## Notes

- **Authentication required**: All comparison endpoints require a valid JWT token
- **Async processing**: Comparisons process in the background - poll status or results endpoint
- **Judge selection**: Use `"chatgpt"` or `"openai"` to use OpenAI as the judge
- **OpenAI API Key**: Make sure `OPENAI_API_KEY` is set in `.env` for judge functionality
- **Processing time**: Typically 10-30 seconds depending on number of platforms

---

## Error Responses

**401 Unauthorized:**
```json
{
  "success": false,
  "error": {
    "code": "INVALID_TOKEN",
    "message": "Invalid or expired token"
  }
}
```

**404 Not Found:**
```json
{
  "success": false,
  "error": {
    "code": "COMPARISON_NOT_FOUND",
    "message": "Comparison with ID comp_abc123 not found"
  }
}
```

**400 Bad Request:**
```json
{
  "success": false,
  "error": {
    "code": "INVALID_PLATFORM",
    "message": "Platform 'invalid_platform' is not recognized"
  }
}
```

