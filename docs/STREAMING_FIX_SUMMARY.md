# Streaming and Response Persistence Fixes

## Issues Fixed

### 1. ✅ Response Not Streaming Chunk-by-Chunk
**Problem**: Responses appeared all at once instead of streaming word-by-word.

**Fixes Applied**:
- Reduced event queue timeout from 100ms to 10ms for faster delivery
- Added `await asyncio.sleep(0)` after emitting chunk events to yield control immediately
- Event manager now created early when comparison is submitted
- Chunks are sent immediately as they arrive from AI platforms

### 2. ✅ Response Disappearing After Scores Calculated
**Problem**: AI response text disappeared once audit scores were calculated.

**Fixes Applied**:
- Partial responses are now preserved in final results
- Response text is explicitly stored in `PlatformResult.response` field
- Partial responses are available via `/results` endpoint during processing
- Added `response_complete` event to notify frontend when response is fully received

## Backend Changes

### Files Modified

1. **`app/services/comparison/event_manager.py`**
   - Reduced timeout from 0.1s to 0.01s (10ms) for immediate event delivery

2. **`app/services/comparison/comparison_service.py`**
   - Added `await asyncio.sleep(0)` after emitting chunk events
   - Improved partial response preservation
   - Added `response_complete` event emission
   - Preserved partial responses in final results

3. **`app/api/v1/routers/comparison.py`**
   - Modified `/results` endpoint to return partial responses during processing
   - Early event manager creation when comparison is submitted

## Frontend Requirements

### For Streaming to Work

1. **Connect to Stream Endpoint**:
   ```javascript
   const eventSource = new EventSource(
     `http://localhost:8001/api/v1/comparison/${comparisonId}/stream`
   );
   ```

2. **Handle `response_chunk` Events**:
   ```javascript
   eventSource.addEventListener('response_chunk', (event) => {
     const data = JSON.parse(event.data);
     const { platform_id, data: chunkData } = data;
     
     // Update UI immediately with accumulated_text
     updateResponse(platform_id, chunkData.accumulated_text);
   });
   ```

3. **Handle `response_complete` Event**:
   ```javascript
   eventSource.addEventListener('response_complete', (event) => {
     const data = JSON.parse(event.data);
     // Response is complete, but keep displaying it
     // Don't clear the response when scores arrive
   });
   ```

4. **Preserve Response When Scores Arrive**:
   - Store the accumulated response text locally
   - Don't clear it when `audit_scores_complete` or `judge_complete` events arrive
   - The response should remain visible even after scoring

### Important Notes

- **Response is always in results**: The final `/results` endpoint includes `platforms[].response` field with the full text
- **Partial responses available**: During processing, `/results` returns `partialResponses` with response text
- **Stream events**: Use `/stream` endpoint for real-time updates, but also poll `/results` as backup

## Testing

### Verify Streaming Works

1. Open browser DevTools → Network tab
2. Filter by "EventStream" or look for `/stream` request
3. You should see `response_chunk` events arriving in real-time
4. Each event contains:
   - `chunk`: The new text chunk
   - `accumulated_text`: Full text so far

### Verify Response Persists

1. After comparison completes, call `/results` endpoint
2. Check `data.platforms[].response` - should contain full response text
3. Response should not be empty or null

## Quick Fix Checklist

- [x] Event queue timeout reduced to 10ms
- [x] Immediate event emission with yield
- [x] Early event manager creation
- [x] Partial responses preserved in database
- [x] Response text in final PlatformResult
- [x] Partial responses in /results during processing
- [x] response_complete event added

## If Issues Persist

1. **Check backend logs** for `response_chunk` events being emitted
2. **Check network tab** for EventStream connection
3. **Verify frontend** is handling `response_chunk` events correctly
4. **Check `/results` endpoint** - response should be in `platforms[].response`

The backend is now optimized for immediate streaming and response persistence. If responses still don't stream or disappear, the issue is likely in the frontend implementation.
