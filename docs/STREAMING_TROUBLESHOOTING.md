# Streaming Troubleshooting Guide

## Issue: Responses Not Streaming Word-by-Word

If responses are appearing all at once instead of streaming word-by-word, follow this guide.

## Backend Changes Made

### 1. Optimized Event Queue Timeout
- Reduced timeout from 100ms to 10ms for faster event delivery
- Events are now sent almost immediately when chunks arrive

### 2. Immediate Event Emission
- Added `await asyncio.sleep(0)` after emitting chunk events
- This yields control to allow events to be sent immediately

### 3. Early Event Manager Creation
- Event manager is now created when the comparison is submitted
- This ensures streaming works even if the frontend connects after processing starts

## Frontend Requirements

For streaming to work, your frontend **must**:

### 1. Connect to the Stream Endpoint

The frontend needs to connect to the SSE stream endpoint:

```javascript
const eventSource = new EventSource(
  `http://localhost:8001/api/v1/comparison/${comparisonId}/stream`,
  {
    withCredentials: true  // If using cookies for auth
  }
);
```

### 2. Handle `response_chunk` Events

Listen for `response_chunk` events and update the UI incrementally:

```javascript
eventSource.addEventListener('response_chunk', (event) => {
  const data = JSON.parse(event.data);
  const { platform_id, data: chunkData } = data;
  
  // chunkData contains:
  // - chunk: the new text chunk (word/token)
  // - accumulated_text: the full text so far
  
  // Update the UI for this platform
  updatePlatformResponse(platform_id, chunkData.accumulated_text);
});
```

### 3. Connect Before or Immediately After Submission

**Important**: The frontend should connect to the stream endpoint:
- **Before** submitting the comparison, OR
- **Immediately after** receiving the comparison ID

If you wait too long, you might miss early chunks.

### 4. Handle All Event Types

The stream sends various event types:

- `stream_connected` - Connection established
- `response_started` - A platform started generating a response
- `response_chunk` - New text chunk (this is what you need for word-by-word)
- `response_complete` - Platform finished generating response
- `comparison_complete` - All processing finished

## Testing Streaming

### 1. Check Backend Logs

Look for these log entries:
```
comparison.stream.request
comparison.stream.retry
event_manager.emit_event
```

### 2. Test with curl

Test the stream endpoint directly:

```bash
curl -N -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8001/api/v1/comparison/COMPARISON_ID/stream
```

You should see events like:
```
data: {"type":"stream_connected",...}
data: {"type":"response_started",...}
data: {"type":"response_chunk","data":{"chunk":"Hello","accumulated_text":"Hello"}}
data: {"type":"response_chunk","data":{"chunk":" world","accumulated_text":"Hello world"}}
...
```

### 3. Check Network Tab

In browser DevTools:
1. Open Network tab
2. Filter by "EventStream" or "stream"
3. Click on the stream request
4. Check the "EventStream" tab
5. You should see events arriving in real-time

## Common Issues

### Issue: Events arrive but UI doesn't update

**Solution**: Make sure you're updating the UI in the event handler:
```javascript
eventSource.addEventListener('response_chunk', (event) => {
  const data = JSON.parse(event.data);
  // Update UI immediately
  document.getElementById(`response-${data.platform_id}`).textContent = 
    data.data.accumulated_text;
});
```

### Issue: Full response appears at once

**Possible causes**:
1. Frontend is polling `/results` endpoint instead of using `/stream`
2. Frontend is buffering chunks before displaying
3. Frontend connected to stream too late (missed early chunks)

**Solution**: 
- Use the `/stream` endpoint, not `/results`
- Display chunks immediately as they arrive
- Connect to stream before or immediately after submission

### Issue: No events received

**Check**:
1. Is the comparison being processed? Check status
2. Is the event manager created? (Backend creates it automatically now)
3. Are there any errors in backend logs?
4. Is CORS configured correctly for SSE?

## Backend Configuration

The streaming is configured with:
- **Event queue timeout**: 10ms (very fast)
- **SSE headers**: Properly set for streaming
- **No buffering**: Events sent immediately

## Verification

To verify streaming is working:

1. **Backend**: Check logs show `response_chunk` events being emitted
2. **Network**: Check browser shows EventStream connection
3. **Frontend**: Check UI updates incrementally, not all at once

If you're still seeing issues after these changes, check:
- Frontend code is using EventSource API correctly
- Frontend is handling `response_chunk` events
- Frontend is updating UI immediately (not buffering)
