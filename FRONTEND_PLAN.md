# Frontend Development Plan - Next.js Integration

## Overview

This document outlines the complete plan for integrating all backend APIs into the existing Next.js frontend. The backend provides comprehensive AI audit, comparison, and evaluation services that need to be exposed through a modern, user-friendly interface.

---

## Table of Contents

1. [API Endpoints Summary](#api-endpoints-summary)
2. [Frontend Architecture](#frontend-architecture)
3. [Pages & Routes](#pages--routes)
4. [Components Structure](#components-structure)
5. [State Management](#state-management)
6. [API Integration Layer](#api-integration-layer)
7. [Authentication Flow](#authentication-flow)
8. [UI/UX Design Considerations](#uiux-design-considerations)
9. [Implementation Priority](#implementation-priority)
10. [Technical Stack Recommendations](#technical-stack-recommendations)

---

## API Endpoints Summary

### 1. Authentication APIs (`/api/v1/auth`)
- **POST** `/api/v1/auth/login` - User login
- **POST** `/api/v1/auth/register` - User registration
- **POST** `/api/v1/auth/refresh` - Refresh access token
- **GET** `/api/v1/auth/me` - Get current user info

### 2. Comparison APIs (`/api/v1/comparison`)
- **GET** `/api/v1/comparison/` - List user's comparisons (with filtering, pagination, sorting)
- **POST** `/api/v1/comparison/submit` - Submit prompt for comparison (triggers all 20 audit features)
- **GET** `/api/v1/comparison/{comparisonId}/results` - Get comparison results with all audit scores
- **GET** `/api/v1/comparison/{comparisonId}/status` - Get comparison processing status

### 3. Multi-LLM APIs (`/api/v1/multi-llm`)
- **POST** `/api/v1/multi-llm/collect` - Collect responses from multiple LLMs simultaneously

### 4. Responses APIs (`/api/v1/responses`)
- **GET** `/api/v1/responses/` - Get saved LLM responses (with filters)
- **GET** `/api/v1/responses/request/{request_id}` - Get responses by request ID
- **GET** `/api/v1/responses/providers` - Get list of providers
- **GET** `/api/v1/responses/stats` - Get statistics

### 5. Similarity APIs (`/api/v1/similarity`)
- **POST** `/api/v1/similarity/process` - Process similarity analysis for responses

### 6. Contradiction APIs (`/api/v1/contradiction`)
- **POST** `/api/v1/contradiction/detect` - Detect contradictions between responses

### 7. User Preference APIs (`/api/v1/user-preference`)
- **POST** `/api/v1/user-preference/record` - Record user preference for LLM output
- **GET** `/api/v1/user-preference/analytics` - Get preference analytics

### 8. LLM Promotion APIs (`/api/v1/llm-promotion`)
- **POST** `/api/v1/llm-promotion/register` - Register new LLM provider
- **GET** `/api/v1/llm-promotion/providers` - Get approved providers

### 9. Promotion Payment APIs (`/api/v1/promotion-payment`)
- **POST** `/api/v1/promotion-payment/create` - Create payment for promotion

### 10. Chatbot Evaluation APIs (`/api/v1/chatbot-evaluation`)
- **POST** `/api/v1/chatbot-evaluation/create` - Create evaluation job
- **POST** `/api/v1/chatbot-evaluation/{evaluation_id}/process` - Process evaluation
- **GET** `/api/v1/chatbot-evaluation/{evaluation_id}` - Get evaluation results

### 11. Core Endpoints
- **POST** `/audit` - Primary audit endpoint
- **GET** `/health` - Health check
- **GET** `/metrics` - Prometheus metrics

---

## Frontend Architecture

### Recommended Folder Structure

```
frontend/
├── app/                          # Next.js App Router (if using App Router)
│   ├── (auth)/
│   │   ├── login/
│   │   └── register/
│   ├── (dashboard)/
│   │   ├── dashboard/
│   │   ├── comparisons/
│   │   │   ├── [id]/
│   │   │   └── new/
│   │   ├── responses/
│   │   ├── chatbot-evaluation/
│   │   └── settings/
│   └── api/                      # API routes (if needed for proxy)
│
├── components/
│   ├── auth/
│   │   ├── LoginForm.tsx
│   │   ├── RegisterForm.tsx
│   │   └── AuthGuard.tsx
│   ├── comparison/
│   │   ├── ComparisonForm.tsx
│   │   ├── ComparisonResults.tsx
│   │   ├── ComparisonStatus.tsx
│   │   ├── AuditScores.tsx
│   │   ├── ScoreCard.tsx
│   │   ├── PlatformComparison.tsx
│   │   └── DeviationMap.tsx
│   ├── responses/
│   │   ├── ResponseList.tsx
│   │   ├── ResponseCard.tsx
│   │   ├── ResponseFilters.tsx
│   │   └── ResponseStats.tsx
│   ├── similarity/
│   │   ├── SimilarityAnalysis.tsx
│   │   └── SimilarityMatrix.tsx
│   ├── chatbot/
│   │   ├── EvaluationForm.tsx
│   │   ├── EvaluationResults.tsx
│   │   └── QuestionVariations.tsx
│   ├── common/
│   │   ├── Layout.tsx
│   │   ├── Header.tsx
│   │   ├── Sidebar.tsx
│   │   ├── LoadingSpinner.tsx
│   │   ├── ErrorBoundary.tsx
│   │   ├── Toast.tsx
│   │   └── Modal.tsx
│   └── ui/                       # Reusable UI components
│       ├── Button.tsx
│       ├── Input.tsx
│       ├── Select.tsx
│       ├── Card.tsx
│       ├── Badge.tsx
│       └── ProgressBar.tsx
│
├── lib/
│   ├── api/
│   │   ├── client.ts            # Axios/Fetch client with interceptors
│   │   ├── auth.ts              # Auth API calls
│   │   ├── comparison.ts        # Comparison API calls
│   │   ├── responses.ts        # Responses API calls
│   │   ├── similarity.ts       # Similarity API calls
│   │   ├── chatbot.ts          # Chatbot evaluation API calls
│   │   └── types.ts            # TypeScript types for API responses
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useComparison.ts
│   │   ├── usePolling.ts
│   │   └── useLocalStorage.ts
│   ├── utils/
│   │   ├── formatters.ts
│   │   ├── validators.ts
│   │   └── constants.ts
│   └── store/                   # State management (Zustand/Redux)
│       ├── authStore.ts
│       ├── comparisonStore.ts
│       └── uiStore.ts
│
├── types/
│   ├── api.ts                   # API request/response types
│   ├── comparison.ts
│   └── user.ts
│
└── styles/
    ├── globals.css
    └── components/
```

---

## Pages & Routes

### Public Routes
1. **`/login`** - Login page
2. **`/register`** - Registration page

### Protected Routes (Require Authentication)
1. **`/dashboard`** - Main dashboard with overview
2. **`/comparisons`** - List of all comparisons
3. **`/comparisons/new`** - Create new comparison
4. **`/comparisons/[id]`** - View comparison results
5. **`/responses`** - Browse saved LLM responses
6. **`/responses/[requestId]`** - View responses for specific request
7. **`/similarity`** - Similarity analysis page
8. **`/contradiction`** - Contradiction detection page
9. **`/chatbot-evaluation`** - Chatbot evaluation dashboard
10. **`/chatbot-evaluation/[id]`** - View evaluation results
11. **`/llm-promotion`** - LLM provider promotion page
12. **`/preferences`** - User preferences and analytics
13. **`/settings`** - User settings

---

## Components Structure

### 1. Authentication Components

#### `LoginForm.tsx`
- Email and password inputs
- Form validation
- Error handling
- Redirect after successful login

#### `RegisterForm.tsx`
- Name, email, password inputs
- Password confirmation
- Form validation
- Auto-login after registration

#### `AuthGuard.tsx`
- HOC/Component to protect routes
- Redirects to login if not authenticated
- Checks token validity

### 2. Comparison Components

#### `ComparisonList.tsx`
- Display list of user's comparisons
- Filter by status (queued, processing, completed, failed)
- Pagination controls
- Sort by date, status, completion time
- Search/filter by prompt text
- Click to view details
- Status badges
- Progress indicators for processing comparisons
- Empty state when no comparisons

#### `ComparisonForm.tsx`
- Prompt textarea
- Platform selection (multi-select checkboxes)
  - OpenAI/ChatGPT
  - Gemini
  - Groq
  - Hugging Face
- Judge selection (radio buttons)
- Submit button with loading state

#### `ComparisonStatus.tsx`
- Real-time status display
- Progress bar
- Estimated time remaining
- Completed/pending platforms list
- Auto-polling for status updates

#### `ComparisonResults.tsx`
- Overall winner display
- Platform comparison cards
- Score visualization (charts/graphs)
- Expandable sections for detailed scores

#### `AuditScores.tsx`
- Display all 20 audit scores
- Color-coded scores (green/yellow/red)
- Category grouping
- Expandable explanations
- Score breakdown:
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

#### `ScoreCard.tsx`
- Individual score display
- Visual indicator (progress bar/circle)
- Category badge
- Explanation tooltip

#### `PlatformComparison.tsx`
- Side-by-side comparison
- Response text display
- Score comparison
- Top reasons list

#### `DeviationMap.tsx`
- Sentence-level comparison
- Highlight conflicts
- Visual diff view

### 3. Responses Components

#### `ResponseList.tsx`
- Table/list of responses
- Pagination
- Filters (provider, request_id)
- Search functionality

#### `ResponseCard.tsx`
- Response preview
- Provider badge
- Timestamp
- Metrics (latency, tokens)
- Expand to view full response

#### `ResponseFilters.tsx`
- Provider dropdown
- Request ID input
- Date range picker
- Clear filters button

#### `ResponseStats.tsx`
- Total responses
- By provider breakdown
- Average metrics
- Charts/graphs

### 4. Similarity Components

#### `SimilarityAnalysis.tsx`
- Request ID input
- Process button
- Results display
- Similarity matrix visualization

#### `SimilarityMatrix.tsx`
- Heatmap visualization
- Pairwise similarity scores
- Interactive tooltips

### 5. Chatbot Evaluation Components

#### `EvaluationForm.tsx`
- Questions input (multi-line, add/remove)
- Chatbot URL input
- API key input (optional)
- Submit button

#### `EvaluationResults.tsx`
- Questions list
- Variations display
- Correct answers
- Chatbot responses
- Comparison results
- Improvement recommendations

#### `QuestionVariations.tsx`
- Display original question
- Show all variations
- Expandable sections

### 6. Common Components

#### `Layout.tsx`
- Main layout wrapper
- Header
- Sidebar navigation
- Footer (optional)

#### `Header.tsx`
- Logo
- Navigation links
- User menu (dropdown)
- Logout button

#### `Sidebar.tsx`
- Navigation menu
- Active route highlighting
- Collapsible sections

#### `LoadingSpinner.tsx`
- Reusable loading indicator
- Full-page and inline variants

#### `ErrorBoundary.tsx`
- Error catching
- Error display
- Retry functionality

#### `Toast.tsx`
- Success/error/info notifications
- Auto-dismiss
- Stack multiple toasts

---

## State Management

### Recommended: Zustand (Lightweight) or Redux Toolkit

### Store Structure

#### `authStore.ts`
```typescript
- user: User | null
- token: string | null
- refreshToken: string | null
- isAuthenticated: boolean
- login: (email, password) => Promise<void>
- logout: () => void
- refreshAccessToken: () => Promise<void>
- getCurrentUser: () => Promise<void>
```

#### `comparisonStore.ts`
```typescript
- comparisons: Comparison[]
- currentComparison: Comparison | null
- isLoading: boolean
- error: string | null
- submitComparison: (data) => Promise<string>
- getComparisonStatus: (id) => Promise<void>
- getComparisonResults: (id) => Promise<void>
- pollComparisonStatus: (id) => void
```

#### `uiStore.ts`
```typescript
- theme: 'light' | 'dark'
- sidebarOpen: boolean
- toasts: Toast[]
- setTheme: (theme) => void
- toggleSidebar: () => void
- addToast: (toast) => void
- removeToast: (id) => void
```

---

## API Integration Layer

### API Client Setup (`lib/api/client.ts`)

```typescript
// Using Axios or Fetch
import axios from 'axios';

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - Add auth token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor - Handle token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Try to refresh token
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        try {
          const { data } = await axios.post('/api/v1/auth/refresh', {
            refreshToken,
          });
          localStorage.setItem('access_token', data.data.token);
          // Retry original request
          return apiClient.request(error.config);
        } catch (refreshError) {
          // Refresh failed, redirect to login
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;
```

### API Functions (`lib/api/comparison.ts`)

```typescript
import apiClient from './client';
import type { SubmitComparisonRequest, ComparisonResponse } from '../types';

export const comparisonApi = {
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

### Custom Hooks (`lib/hooks/useComparison.ts`)

```typescript
import { useState, useEffect } from 'react';
import { comparisonApi } from '../api/comparison';
import { usePolling } from './usePolling';

export const useComparison = (comparisonId: string | null) => {
  const [comparison, setComparison] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchResults = async () => {
    if (!comparisonId) return;
    setLoading(true);
    try {
      const data = await comparisonApi.getResults(comparisonId);
      setComparison(data.data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Poll for results if status is processing
  usePolling(
    () => {
      if (comparison?.status === 'processing') {
        fetchResults();
      }
    },
    comparison?.status === 'processing' ? 2000 : null
  );

  return { comparison, loading, error, refetch: fetchResults };
};
```

---

## Authentication Flow

### 1. Login Flow
```
User enters credentials
  ↓
POST /api/v1/auth/login
  ↓
Store tokens in localStorage/cookies
  ↓
Store user info in state
  ↓
Redirect to dashboard
```

### 2. Token Refresh Flow
```
API request with expired token
  ↓
401 Unauthorized response
  ↓
POST /api/v1/auth/refresh with refreshToken
  ↓
Update access token
  ↓
Retry original request
```

### 3. Protected Route Flow
```
User navigates to protected route
  ↓
Check if token exists
  ↓
Validate token (optional: call /api/v1/auth/me)
  ↓
If valid: Render page
If invalid: Redirect to /login
```

---

## UI/UX Design Considerations

### 1. Color Coding for Scores
- **Green (8-10)**: Excellent
- **Yellow (5-7)**: Good
- **Red (0-4)**: Needs Improvement

### 2. Loading States
- Show skeleton loaders for better UX
- Progress indicators for long-running operations
- Optimistic UI updates where possible

### 3. Error Handling
- User-friendly error messages
- Retry mechanisms
- Fallback UI states

### 4. Responsive Design
- Mobile-first approach
- Tablet and desktop optimizations
- Touch-friendly interactions

### 5. Accessibility
- ARIA labels
- Keyboard navigation
- Screen reader support
- Color contrast compliance

### 6. Performance
- Lazy loading for heavy components
- Virtual scrolling for long lists
- Image optimization
- Code splitting

### 7. Data Visualization
- Use chart libraries (Recharts, Chart.js, D3.js)
- Interactive graphs for scores
- Heatmaps for similarity matrices
- Progress bars for status

---

## Implementation Priority

### Phase 1: Core Features (Week 1-2)
1. ✅ Authentication (Login/Register)
2. ✅ API client setup
3. ✅ Comparison form and submission
4. ✅ Comparison results display
5. ✅ Basic dashboard

### Phase 2: Enhanced Features (Week 3-4)
1. ✅ Real-time status polling
2. ✅ All 20 audit scores display
3. ✅ Responses browsing
4. ✅ Similarity analysis
5. ✅ Contradiction detection

### Phase 3: Advanced Features (Week 5-6)
1. ✅ Chatbot evaluation
2. ✅ User preferences
3. ✅ LLM promotion
4. ✅ Payment integration
5. ✅ Analytics dashboard

### Phase 4: Polish & Optimization (Week 7-8)
1. ✅ Performance optimization
2. ✅ Error handling improvements
3. ✅ UI/UX refinements
4. ✅ Testing
5. ✅ Documentation

---

## Technical Stack Recommendations

### Core
- **Framework**: Next.js 14+ (App Router recommended)
- **Language**: TypeScript
- **Styling**: Tailwind CSS + shadcn/ui (or Material-UI, Chakra UI)
- **State Management**: Zustand or Redux Toolkit
- **API Client**: Axios or native Fetch with React Query

### Additional Libraries
- **Forms**: React Hook Form + Zod validation
- **Charts**: Recharts or Chart.js
- **Date Handling**: date-fns or Day.js
- **HTTP State**: React Query (TanStack Query) for caching/polling
- **Notifications**: react-hot-toast or sonner
- **Icons**: Lucide React or Heroicons
- **Code Highlighting**: react-syntax-highlighter (for code responses)

### Development Tools
- **Linting**: ESLint
- **Formatting**: Prettier
- **Type Checking**: TypeScript strict mode
- **Testing**: Jest + React Testing Library (optional)

---

## Environment Variables

Create `.env.local` in frontend directory:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=AI Audit Platform
```

---

## API Response Format

All APIs follow this standard format:

```typescript
// Success Response
{
  "success": true,
  "data": {
    // Response data
  }
}

// Error Response
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Error message"
  }
}
```

---

## Key Implementation Notes

### 1. Polling Strategy
- Use `setInterval` or React Query's `refetchInterval` for status polling
- Stop polling when status is "completed" or "failed"
- Exponential backoff for failed requests

### 2. Token Management
- Store tokens securely (httpOnly cookies preferred over localStorage)
- Implement automatic token refresh
- Clear tokens on logout

### 3. Error Handling
- Global error boundary for React errors
- API error handling in interceptors
- User-friendly error messages

### 4. Type Safety
- Generate TypeScript types from API responses
- Use strict TypeScript configuration
- Validate API responses with Zod schemas

### 5. Performance
- Implement request caching with React Query
- Use React.memo for expensive components
- Lazy load routes and heavy components
- Optimize bundle size

---

## Next Steps

1. **Setup Next.js Project** (if not already done)
   ```bash
   npx create-next-app@latest frontend --typescript --tailwind --app
   ```

2. **Install Dependencies**
   ```bash
   npm install axios zustand react-hook-form zod @tanstack/react-query
   npm install recharts date-fns react-hot-toast lucide-react
   ```

3. **Create API Client** - Set up base API client with interceptors

4. **Implement Authentication** - Login/Register pages and auth flow

5. **Build Comparison Feature** - Start with the core comparison functionality

6. **Add Other Features** - Gradually add remaining features based on priority

7. **Testing & Refinement** - Test all features and refine UI/UX

---

## Questions to Consider

1. **Existing Frontend**: Does the Next.js frontend already exist? What's the current structure?
2. **Design System**: Is there an existing design system or should we create one?
3. **Authentication**: What authentication method is currently in place (if any)?
4. **State Management**: Is there existing state management setup?
5. **Styling**: What CSS framework/library is being used?

---

## Support & Documentation

- Backend API Documentation: `http://localhost:8000/docs` (FastAPI Swagger)
- API Routes Guide: `docs/API_ROUTES_GUIDE.md`
- Feature Routes: `FEATURE_ROUTES.md`
- API Status: `API_STATUS.md`

---

**Last Updated**: [Current Date]
**Version**: 1.0

