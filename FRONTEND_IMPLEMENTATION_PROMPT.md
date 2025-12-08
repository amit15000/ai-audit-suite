# Frontend Implementation Prompt

## Context
You are building a Next.js frontend for an AI Audit Platform. The backend APIs are fully functional and documented. Your task is to integrate all APIs into a modern, user-friendly frontend interface.

## Backend API Base URL
```
http://localhost:8000
```

## Authentication
- **Login**: `POST /api/v1/auth/login` (email, password)
- **Register**: `POST /api/v1/auth/register` (name, email, password)
- **Refresh Token**: `POST /api/v1/auth/refresh` (refreshToken)
- **Current User**: `GET /api/v1/auth/me` (requires Bearer token)

**Response Format:**
```json
{
  "success": true,
  "data": {
    "user": { "id", "email", "name" },
    "token": "jwt_access_token",
    "refreshToken": "jwt_refresh_token"
  }
}
```

**All authenticated endpoints require:**
```
Authorization: Bearer {access_token}
```

---

## Core Feature: Comparison System

### List User's Comparisons
**Endpoint**: `GET /api/v1/comparison/`

**Query Parameters:**
- `status` (optional): Filter by status (`queued`, `processing`, `completed`, `failed`)
- `limit` (optional, default: 50): Maximum number of results (1-100)
- `offset` (optional, default: 0): Number of results to skip
- `sort_by` (optional, default: `created_at`): Sort field (`created_at`, `completed_at`, `status`)
- `sort_order` (optional, default: `desc`): Sort order (`asc`, `desc`)

**Response:**
```json
{
  "success": true,
  "data": {
    "comparisons": [
      {
        "id": "comp_abc123",
        "messageId": "msg_xyz789",
        "prompt": "Full prompt text...",
        "promptPreview": "First 100 chars...",
        "judgePlatform": "openai",
        "selectedPlatforms": ["openai", "gemini", "groq"],
        "platformsCount": 3,
        "status": "completed",
        "progress": 100,
        "winner": {
          "id": "gemini",
          "name": "Gemini",
          "score": 85
        },
        "createdAt": "2024-01-15T10:30:00.000Z",
        "completedAt": "2024-01-15T10:30:30.000Z",
        "errorMessage": null
      }
    ],
    "total": 25,
    "limit": 50,
    "offset": 0,
    "hasMore": false
  }
}
```

### Submit Comparison
**Endpoint**: `POST /api/v1/comparison/submit`

**Request:**
```json
{
  "prompt": "Explain quantum computing in simple terms",
  "platforms": ["openai", "gemini", "groq"],
  "judge": "openai"
}
```

**Available Platforms**: `openai`, `gemini`, `groq`, `huggingface`
**Available Judges**: `openai`, `chatgpt`, `gemini`, `groq`

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

### Get Status
**Endpoint**: `GET /api/v1/comparison/{comparisonId}/status`

**Note**: Users can only access their own comparisons. Returns 403 Forbidden if comparison belongs to another user.

**Response:**
```json
{
  "success": true,
  "data": {
    "comparisonId": "comp_abc123",
    "status": "processing" | "completed" | "failed",
    "progress": 45,
    "estimatedTimeRemaining": 16,
    "completedPlatforms": ["gemini"],
    "pendingPlatforms": ["groq"]
  }
}
```

### Get Results
**Endpoint**: `GET /api/v1/comparison/{comparisonId}/results`

**Note**: Users can only access their own comparisons. Returns 403 Forbidden if comparison belongs to another user.

**Response Structure:**
```json
{
  "success": true,
  "data": {
    "comparisonId": "comp_abc123",
    "prompt": "...",
    "status": "completed",
    "judge": { "id": "openai", "name": "ChatGPT" },
    "platforms": [
      {
        "id": "gemini",
        "name": "Gemini",
        "score": 85,
        "response": "Full response text...",
        "detailedScores": {
          "overallScore": 7,
          "scores": [
            {
              "name": "Hallucination Score",
              "value": 8,
              "maxValue": 10,
              "category": "Accuracy",
              "isCritical": false,
              "explanation": "Detailed explanation..."
            }
            // ... 19 more scores
          ]
        },
        "topReasons": [
          "Strong performance in Hallucination Score (8/10)",
          "Excellent reasoning quality"
        ]
      }
    ],
    "winner": { "id": "gemini", "name": "Gemini", "score": 85 }
  }
}
```

**All 20 Audit Scores Included:**
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

---

## Other APIs

### Multi-LLM Collection
**Endpoint**: `POST /api/v1/multi-llm/collect`
**Request**: `{ "prompt": "...", "adapter_ids": ["openai", "gemini"] }`
**Response**: All responses with metrics (latency, tokens)

### Responses
**Endpoints**:
- `GET /api/v1/responses/` - List responses (query: request_id, provider, limit, offset)
- `GET /api/v1/responses/request/{request_id}` - Get by request ID
- `GET /api/v1/responses/providers` - List providers
- `GET /api/v1/responses/stats` - Statistics

### Similarity Analysis
**Endpoint**: `POST /api/v1/similarity/process`
**Request**: `{ "request_id": "..." }`
**Response**: Similarity matrix and analysis

### Contradiction Detection
**Endpoint**: `POST /api/v1/contradiction/detect`
**Request**: `{ "request_id": "..." }` or `{ "responses": {...} }`
**Response**: Contradictions found between responses

### User Preference
**Endpoints**:
- `POST /api/v1/user-preference/record` - Record preference
- `GET /api/v1/user-preference/analytics` - Get analytics

### LLM Promotion
**Endpoints**:
- `POST /api/v1/llm-promotion/register` - Register provider
- `GET /api/v1/llm-promotion/providers` - List providers

### Promotion Payment
**Endpoint**: `POST /api/v1/promotion-payment/create`
**Request**: `{ "provider_id": "...", "tier": "basic|premium", "amount": "99.99" }`

### Chatbot Evaluation
**Endpoints**:
- `POST /api/v1/chatbot-evaluation/create` - Create evaluation
- `POST /api/v1/chatbot-evaluation/{id}/process` - Process evaluation
- `GET /api/v1/chatbot-evaluation/{id}` - Get results

---

## Implementation Requirements

### 1. Setup
- Next.js 14+ with TypeScript
- Tailwind CSS for styling
- Axios or Fetch for API calls
- Zustand or Redux for state management
- React Hook Form + Zod for forms

### 2. Pages to Build

#### Authentication Pages
- `/login` - Login form
- `/register` - Registration form

#### Main Pages
- `/dashboard` - Overview dashboard
- `/comparisons` - List all user's comparisons (with filtering, pagination, sorting)
- `/comparisons/new` - Create new comparison
- `/comparisons/[id]` - View comparison results (only user's own comparisons)
- `/responses` - Browse LLM responses
- `/similarity` - Similarity analysis
- `/contradiction` - Contradiction detection
- `/chatbot-evaluation` - Chatbot evaluation
- `/preferences` - User preferences
- `/llm-promotion` - LLM provider promotion

### 3. Key Components

#### Comparison Flow
1. **ComparisonList**: List all user's comparisons with filters, pagination, sorting
2. **ComparisonForm**: Prompt input, platform selection, judge selection
3. **ComparisonStatus**: Real-time status with progress bar (poll every 2s)
4. **ComparisonResults**: 
   - Winner display
   - Platform cards with scores
   - All 20 audit scores (expandable)
   - Response text comparison
   - Deviation map visualization

#### Score Display
- Color-coded scores: Green (8-10), Yellow (5-7), Red (0-4)
- Category grouping
- Expandable explanations
- Visual charts/graphs

### 4. Comparison List API

```typescript
// lib/api/comparison.ts
export const comparisonApi = {
  list: async (params?: {
    status?: string;
    limit?: number;
    offset?: number;
    sort_by?: string;
    sort_order?: string;
  }) => {
    const response = await apiClient.get('/api/v1/comparison/', { params });
    return response.data;
  },

  submit: async (data: SubmitComparisonRequest) => {
    const response = await apiClient.post('/api/v1/comparison/submit', data);
    return response.data;
  },

  getStatus: async (comparisonId: string) => {
    const response = await apiClient.get(
      `/api/v1/comparison/${comparisonId}/status`
    );
    return response.data;
  },

  getResults: async (comparisonId: string) => {
    const response = await apiClient.get(
      `/api/v1/comparison/${comparisonId}/results`
    );
    return response.data;
  },
};
```

### 5. API Client Setup

```typescript
// lib/api/client.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
});

// Add auth token to requests
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 - refresh token
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Refresh token logic
    }
    return Promise.reject(error);
  }
);
```

### 6. Polling Strategy

For comparison status, poll every 2 seconds until status is "completed" or "failed":

```typescript
useEffect(() => {
  if (status === 'processing') {
    const interval = setInterval(async () => {
      const data = await getStatus(comparisonId);
      if (data.status === 'completed' || data.status === 'failed') {
        clearInterval(interval);
      }
    }, 2000);
    return () => clearInterval(interval);
  }
}, [status, comparisonId]);
```

### 7. Error Handling

- Show user-friendly error messages
- Handle network errors gracefully
- Retry failed requests where appropriate
- Global error boundary

### 8. UI/UX Requirements

- **Responsive**: Mobile, tablet, desktop
- **Loading States**: Skeleton loaders, progress bars
- **Error States**: Clear error messages with retry options
- **Accessibility**: ARIA labels, keyboard navigation
- **Performance**: Lazy loading, code splitting, optimized images

### 9. State Management

Store:
- Auth state (user, token)
- Comparison state (current comparison, list)
- UI state (theme, sidebar, toasts)

### 10. Token Management

- Store tokens in localStorage (or httpOnly cookies)
- Auto-refresh expired tokens
- Redirect to login on auth failure
- Clear tokens on logout

---

## Design Guidelines

### Color Scheme for Scores
- **Excellent (8-10)**: Green (#10b981)
- **Good (5-7)**: Yellow (#f59e0b)
- **Poor (0-4)**: Red (#ef4444)

### Typography
- Headings: Bold, clear hierarchy
- Body: Readable, appropriate line height
- Code: Monospace for responses

### Spacing
- Consistent padding/margins
- Adequate whitespace
- Card-based layouts

### Components
- Use shadcn/ui or similar component library
- Consistent button styles
- Form inputs with validation
- Modal dialogs for confirmations
- Toast notifications for feedback

---

## Testing Checklist

- [ ] Login/Register flow
- [ ] Token refresh mechanism
- [ ] Protected routes
- [ ] List user's comparisons (with filters, pagination)
- [ ] Submit comparison
- [ ] Status polling
- [ ] Results display
- [ ] Security: Users can only see their own comparisons
- [ ] All 20 audit scores visible
- [ ] Response browsing
- [ ] Similarity analysis
- [ ] Contradiction detection
- [ ] Chatbot evaluation
- [ ] Mobile responsiveness
- [ ] Error handling
- [ ] Loading states

---

## Quick Start Commands

```bash
# Create Next.js app
npx create-next-app@latest frontend --typescript --tailwind --app

# Install dependencies
npm install axios zustand react-hook-form zod @tanstack/react-query
npm install recharts date-fns react-hot-toast lucide-react

# Run development server
npm run dev
```

---

## Priority Order

1. **Phase 1**: Authentication + Comparison (core feature)
2. **Phase 2**: Results display + Status polling
3. **Phase 3**: Responses browsing + Similarity
4. **Phase 4**: Other features (chatbot, preferences, etc.)
5. **Phase 5**: Polish, optimization, testing

---

## Notes

- All API responses follow `{ success: boolean, data: {...} }` format
- Error responses: `{ success: false, error: { code, message } }`
- Comparison processing is async - use polling for status
- All authenticated endpoints require Bearer token
- Base URL should be configurable via environment variable

---

**Start with authentication, then build the comparison feature as it's the core functionality. Everything else can be added incrementally.**

