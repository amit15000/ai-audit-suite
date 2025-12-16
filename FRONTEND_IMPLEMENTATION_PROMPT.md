# Frontend Implementation Prompt for Cursor

Copy and paste this prompt into Cursor for your frontend codebase:

---

## Implement Real-Time Streaming for Comparison Results

I need to implement Server-Sent Events (SSE) streaming to show real-time progress during comparison processing. The backend has been updated with a streaming endpoint that emits events as responses are generated and judge evaluations are calculated.

### Backend Endpoint

**SSE Endpoint**: `GET /api/v1/comparison/{comparison_id}/stream`

**Headers Required**:
- `Authorization: Bearer {jwt_token}`

**Response**: Server-Sent Events (SSE) stream with `text/event-stream` content type

### Event Structure

Each event is a JSON object with this structure:
```json
{
  "type": "event_type",
  "platform_id": "openai" | null,
  "timestamp": "2025-01-01T12:00:00",
  "data": {
    // Event-specific data
  }
}
```

### Event Types

1. **`stream_connected`** - Initial connection event
   ```json
   {
     "type": "stream_connected",
     "platform_id": null,
     "data": {
       "comparison_id": "comp_abc123",
       "status": "processing",
       "progress": 0
     }
   }
   ```

2. **`processing_started`** - Processing has begun
   ```json
   {
     "type": "processing_started",
     "data": {
       "comparison_id": "comp_abc123",
       "platforms": ["openai", "gemini", "groq"]
     }
   }
   ```

3. **`response_started`** - A platform started generating response
   ```json
   {
     "type": "response_started",
     "platform_id": "openai",
     "data": {
       "platform_name": "OpenAI"
     }
   }
   ```

4. **`response_chunk`** - A chunk of response text arrived
   ```json
   {
     "type": "response_chunk",
     "platform_id": "openai",
     "data": {
       "chunk": "This is a chunk of text...",
       "accumulated_text": "This is a chunk of text..."
     }
   }
   ```

5. **`response_complete`** - A platform finished generating response
   ```json
   {
     "type": "response_complete",
     "platform_id": "openai",
     "data": {
       "response": "Full response text here...",
       "platform_name": "OpenAI"
     }
   }
   ```

6. **`similarity_analysis_started`** - Similarity analysis began
   ```json
   {
     "type": "similarity_analysis_started",
     "data": {
       "valid_responses_count": 3
     }
   }
   ```

7. **`similarity_analysis_complete`** - Similarity analysis finished
   ```json
   {
     "type": "similarity_analysis_complete",
     "data": {
       "consensus_scores": {...},
       "outliers": []
     }
   }
   ```

8. **`judge_started`** - Judge evaluation started for a platform
   ```json
   {
     "type": "judge_started",
     "platform_id": "openai",
     "data": {
       "judge_platform": "openai"
     }
   }
   ```

9. **`judge_chunk`** - Chunk of judge response arrived
   ```json
   {
     "type": "judge_chunk",
     "platform_id": "openai",
     "data": {
       "chunk": "{\"accuracy\":",
       "accumulated_text": "{\"accuracy\":"
     }
   }
   ```

10. **`judge_parameter`** - A judge parameter was calculated
    ```json
    {
      "type": "judge_parameter",
      "platform_id": "openai",
      "data": {
        "parameter_name": "accuracy",
        "value": 9,
        "accumulated_scores": {
          "accuracy": 9
        }
      }
    }
    ```

11. **`judge_complete`** - Judge evaluation finished for a platform
    ```json
    {
      "type": "judge_complete",
      "platform_id": "openai",
      "data": {
        "scores": {
          "accuracy": 9,
          "completeness": 8,
          "clarity": 9,
          "reasoning": 8,
          "safety": 10,
          "hallucination_risk": 2
        },
        "trust_score": 8.7,
        "fallback_applied": false
      }
    }
    ```

12. **`progress`** - Progress update
    ```json
    {
      "type": "progress",
      "data": {
        "progress": 45,
        "stage": "response_generation" | "scoring"
      }
    }
    ```

13. **`comparison_complete`** - Entire comparison finished
    ```json
    {
      "type": "comparison_complete",
      "data": {
        "results": {
          // Full comparison results object
        }
      }
    }
    ```

14. **`error`** - An error occurred
    ```json
    {
      "type": "error",
      "platform_id": "openai" | null,
      "data": {
        "error": "Error message",
        "stage": "response_generation" | "judge_evaluation" | "similarity_analysis" | "processing"
      }
    }
    ```

### Implementation Requirements

1. **Create SSE Connection Hook/Service**
   - Connect to `/api/v1/comparison/{comparison_id}/stream`
   - Handle authentication (Bearer token)
   - Parse SSE events (format: `data: {json}\n\n`)
   - Handle reconnection on disconnect
   - Clean up on component unmount

2. **Update UI Components**
   - Show response text as it streams in real-time (character by character or word by word)
   - Display each platform's response in a separate card/section
   - Show judge parameters as they're calculated (update UI incrementally)
   - Display progress bar that updates in real-time
   - Show loading states for each platform
   - Handle errors gracefully

3. **State Management**
   - Store accumulated response text per platform
   - Store judge parameters as they arrive
   - Track progress percentage
   - Maintain platform status (pending, generating, completed, error)

4. **User Experience**
   - Don't wait for 100% completion - show results as they arrive
   - Update UI smoothly without flickering
   - Show which platform is currently generating
   - Display judge scores as they're calculated (not all at once at the end)
   - Provide visual feedback for each stage

### Example Implementation Pattern

**Option 1: Using Fetch with ReadableStream (Recommended - supports headers)**

```typescript
// Hook example using fetch (supports authentication headers)
const useComparisonStream = (comparisonId: string, token: string) => {
  const [responses, setResponses] = useState<Record<string, string>>({});
  const [judgeScores, setJudgeScores] = useState<Record<string, any>>({});
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<'connecting' | 'streaming' | 'completed' | 'error'>('connecting');

  useEffect(() => {
    let abortController = new AbortController();
    let isMounted = true;

    const connectStream = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/v1/comparison/${comparisonId}/stream`,
          {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Accept': 'text/event-stream',
            },
            signal: abortController.signal,
          }
        );

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        if (!reader) {
          throw new Error('No reader available');
        }

        while (true) {
          const { done, value } = await reader.read();
          
          if (done) {
            if (isMounted) setStatus('completed');
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // Keep incomplete line in buffer

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6)); // Remove 'data: ' prefix
                
                if (!isMounted) return;

                switch (data.type) {
                  case 'response_chunk':
                    setResponses(prev => ({
                      ...prev,
                      [data.platform_id]: data.data.accumulated_text
                    }));
                    break;
                  case 'response_complete':
                    setResponses(prev => ({
                      ...prev,
                      [data.platform_id]: data.data.response
                    }));
                    break;
                  case 'judge_parameter':
                    setJudgeScores(prev => ({
                      ...prev,
                      [data.platform_id]: {
                        ...prev[data.platform_id] || {},
                        [data.data.parameter_name]: data.data.value,
                        ...data.data.accumulated_scores
                      }
                    }));
                    break;
                  case 'judge_complete':
                    setJudgeScores(prev => ({
                      ...prev,
                      [data.platform_id]: data.data
                    }));
                    break;
                  case 'progress':
                    setProgress(data.data.progress);
                    break;
                  case 'comparison_complete':
                    setStatus('completed');
                    break;
                  case 'error':
                    console.error('Stream error:', data.data.error);
                    setStatus('error');
                    break;
                }
              } catch (e) {
                console.error('Error parsing event:', e, line);
              }
            }
          }
        }
      } catch (error: any) {
        if (error.name !== 'AbortError' && isMounted) {
          console.error('Stream error:', error);
          setStatus('error');
        }
      }
    };

    connectStream();

    return () => {
      isMounted = false;
      abortController.abort();
    };
  }, [comparisonId, token]);

  return { responses, judgeScores, progress, status };
};
```

**Option 2: Using EventSource (Simpler but token must be in URL)**

```typescript
// Note: EventSource doesn't support custom headers in browsers
// Token must be passed as query parameter or use a proxy
const useComparisonStream = (comparisonId: string, token: string) => {
  const [responses, setResponses] = useState<Record<string, string>>({});
  const [judgeScores, setJudgeScores] = useState<Record<string, any>>({});
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<'connecting' | 'streaming' | 'completed' | 'error'>('connecting');

  useEffect(() => {
    // Pass token as query param since EventSource doesn't support headers
    const eventSource = new EventSource(
      `${API_BASE_URL}/api/v1/comparison/${comparisonId}/stream?token=${encodeURIComponent(token)}`
    );

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'response_chunk':
          setResponses(prev => ({
            ...prev,
            [data.platform_id]: data.data.accumulated_text
          }));
          break;
        case 'judge_parameter':
          setJudgeScores(prev => ({
            ...prev,
            [data.platform_id]: {
              ...prev[data.platform_id] || {},
              [data.data.parameter_name]: data.data.value,
              ...data.data.accumulated_scores
            }
          }));
          break;
        case 'progress':
          setProgress(data.data.progress);
          break;
        case 'comparison_complete':
          setStatus('completed');
          eventSource.close();
          break;
        // ... handle other event types
      }
    };

    eventSource.onerror = () => {
      setStatus('error');
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [comparisonId, token]);

  return { responses, judgeScores, progress, status };
};
```

### Important Notes

- **Authentication**: 
  - **Recommended**: Use `fetch()` with `ReadableStream` (Option 1 above) - supports Authorization headers
  - **Alternative**: Use `EventSource` with token in query parameter (Option 2 above) - simpler but less secure
  - **Backend Note**: If using query parameter, backend needs to accept token from query string
- **Reconnection**: Implement automatic reconnection logic with exponential backoff
- **Error Handling**: Handle network errors, parsing errors, and API errors gracefully
- **Performance**: 
  - Debounce rapid updates if needed to prevent UI lag
  - Use `useMemo` and `useCallback` to optimize re-renders
  - Consider virtualizing if displaying many platforms
- **Accessibility**: Ensure screen readers announce progress updates
- **Browser Support**: Fetch with ReadableStream works in all modern browsers (IE11 not supported)

### UI Components to Update

1. **Comparison Results Page/Component**
   - Add real-time response display
   - Add judge score cards that update incrementally
   - Add progress indicator

2. **Platform Response Cards**
   - Show streaming text (typewriter effect or smooth append)
   - Display loading spinner while generating
   - Show completion status

3. **Judge Evaluation Section**
   - Display parameters as they arrive (not all at once)
   - Show trust score when available
   - Update scores in real-time

4. **Progress Bar**
   - Update based on `progress` events
   - Show current stage (response generation, scoring, etc.)

### Testing Checklist

- [ ] SSE connection establishes successfully
- [ ] Response text streams in real-time
- [ ] Judge parameters appear as they're calculated
- [ ] Progress bar updates smoothly
- [ ] Errors are handled gracefully
- [ ] Reconnection works on disconnect
- [ ] UI doesn't flicker during updates
- [ ] All platforms show their responses
- [ ] Judge scores display correctly
- [ ] Final results match expected format

---

**Implementation Priority**: 
1. First: Get SSE connection working and log all events
2. Second: Display response text streaming
3. Third: Display judge parameters incrementally
4. Fourth: Add progress bar and polish UI

