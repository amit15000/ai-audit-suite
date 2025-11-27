# Backend Implementation Summary

This document summarizes the backend implementation for the AI Audit Platform according to the provided API documentation.

## What Was Implemented

### 1. Authentication System
- **JWT-based authentication** with access and refresh tokens
- **Password hashing** using bcrypt
- **User model** in database
- **Login endpoint** at `POST /api/v1/auth/login`

### 2. Database Models
- **User model**: Stores user credentials and profile information
- **Comparison model**: Stores comparison requests, status, progress, and results
- Both models integrated with SQLAlchemy ORM

### 3. Comparison API Endpoints
- **POST /api/v1/comparison/submit**: Submit a prompt for comparison across multiple AI platforms
- **GET /api/v1/comparison/{comparisonId}/results**: Get comparison results
- **GET /api/v1/comparison/{comparisonId}/status**: Get comparison status

### 4. Services
- **AIPlatformService**: Handles communication with AI platform adapters
- **AuditScorer**: Calculates 20 audit metrics for each platform response
- **ComparisonService**: Orchestrates the comparison process
- **AuthService**: Handles user authentication and token generation

### 5. Platform Integration
- **Platform mapping**: Maps frontend platform IDs (chatgpt, gemini, etc.) to backend adapters
- **Adapter integration**: Uses existing adapter system (openai, gemini, groq, etc.)
- **Response collection**: Collects responses from multiple platforms in parallel

### 6. Audit Scoring System
- **20 audit metrics** as specified in the API documentation:
  1. Hallucination Score
  2. Factual Accuracy Score
  3. Multi-LLM Consensus Score
  4. Deviation Map
  5. Source Authenticity Checker
  6. Reasoning Quality Score
  7. Compliance Score
  8. Bias & Fairness Score
  9. Safety Score
  10. Context-Adherence Score
  11. Stability & Robustness Test
  12. Prompt Sensitivity Test
  13. AI Safety Guardrail Test
  14. Agent Action Safety Audit
  15. Code Vulnerability Auditor
  16. Data Extraction Accuracy Audit
  17. Brand Consistency Audit
  18. AI Output Plagiarism Checker
  19. Multi-judge AI Review
  20. Explainability Score

- **Scoring method**: Uses judge platform (LLM) to evaluate responses, with rule-based fallback
- **Top reasons generation**: Uses LLM to generate 5 winning reasons for each platform

### 7. Async Processing
- **Celery integration**: Comparison processing runs asynchronously via Celery tasks
- **Redis backend**: Uses Redis for Celery broker and result backend
- **Progress tracking**: Real-time progress updates during processing

### 8. Configuration
- **JWT settings**: Configurable secret key, algorithm, and token expiration
- **Celery settings**: Configurable broker and backend URLs
- **CORS settings**: Configurable allowed origins

## File Structure

```
app/
├── api/v1/routers/
│   ├── auth.py              # Authentication endpoints
│   └── comparison.py        # Comparison endpoints
├── core/
│   ├── config.py            # Configuration (updated with JWT/Celery)
│   └── database.py          # Database setup
├── domain/
│   ├── models.py            # Database models (User, Comparison)
│   ├── schemas.py           # Pydantic schemas (updated)
│   └── auth_schemas.py      # Auth schemas
├── services/
│   ├── ai_platform_service.py  # AI platform integration
│   ├── audit_scorer.py         # Audit scoring logic
│   ├── auth_service.py         # Authentication logic
│   └── comparison_service.py   # Comparison processing
├── tasks/
│   └── comparison_tasks.py     # Celery tasks
└── utils/
    ├── dependencies.py          # FastAPI dependencies (auth)
    ├── platform_mapping.py      # Platform ID mapping
    └── security.py              # JWT and password utilities
```

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create a `.env` file with:
```env
# Database
DB_URL=sqlite:///var/audit.db

# JWT
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# AI Platform API Keys
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
GROQ_API_KEY=...
```

### 3. Initialize Database
```bash
python scripts/init_db.py
```

This will:
- Create database tables
- Create a test user (test@example.com / test123)

### 4. Start Redis (for Celery)
```bash
redis-server
```

### 5. Start Celery Worker
```bash
celery -A app.tasks.comparison_tasks.celery_app worker --loglevel=info
```

### 6. Start FastAPI Server
```bash
uvicorn app.main:app --reload --port 3001
```

## API Usage Examples

### 1. Login
```bash
curl -X POST http://localhost:3001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'
```

### 2. Submit Comparison
```bash
curl -X POST http://localhost:3001/api/v1/comparison/submit \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain quantum computing in simple terms",
    "platforms": ["chatgpt", "gemini", "groq"],
    "judge": "chatgpt"
  }'
```

### 3. Get Results
```bash
curl -X GET http://localhost:3001/api/v1/comparison/{comparisonId}/results \
  -H "Authorization: Bearer {token}"
```

### 4. Get Status
```bash
curl -X GET http://localhost:3001/api/v1/comparison/{comparisonId}/status \
  -H "Authorization: Bearer {token}"
```

## Notes

1. **Platform Support**: Currently supports platforms that have adapters (openai, gemini, groq, huggingface). Additional platforms can be added by:
   - Creating new adapters in `app/adapters/`
   - Adding platform mappings in `app/utils/platform_mapping.py`

2. **Scoring**: The audit scoring uses the judge platform (LLM) to evaluate responses. If the judge platform fails, it falls back to rule-based scoring.

3. **Async Processing**: Comparisons are processed asynchronously. The frontend should poll the status endpoint or results endpoint to check progress.

4. **Error Handling**: All endpoints return errors in the format specified in the API documentation:
   ```json
   {
     "success": false,
     "error": {
       "code": "ERROR_CODE",
       "message": "Error message"
     }
   }
   ```

5. **Database**: Uses SQLite by default for local development. Can be configured to use PostgreSQL via `DB_URL` environment variable.

## Next Steps

1. **Add more platform adapters** (Claude, Perplexity, etc.)
2. **Implement rate limiting** as specified in API docs
3. **Add caching** for comparison results
4. **Add WebSocket support** for real-time updates (optional)
5. **Add pagination** for comparison history
6. **Add user registration endpoint** (currently only test user creation script)
7. **Add refresh token endpoint**
8. **Improve audit scoring** with more sophisticated evaluation methods

