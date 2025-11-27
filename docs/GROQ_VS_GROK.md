# Groq vs Grok - Which One to Use?

## Quick Answer

**Use `"groq"`** - this is the actual implemented platform in your codebase.

## Differences

### Groq ✅ (Recommended)
- **What it is**: Groq is an AI inference company that provides fast LLM API access
- **API**: `https://api.groq.com`
- **Models**: Uses models like Llama-3.1-8b-instant
- **Status**: ✅ **Fully implemented** in your codebase
- **Adapter**: `app/adapters/groq.py`
- **API Key**: Set `GROQ_API_KEY` in your `.env` file

**Usage:**
```json
{
  "prompt": "Your prompt here",
  "platforms": ["groq"],  // ✅ Use this
  "judge": "chatgpt"
}
```

### Grok ❌ (Not Implemented)
- **What it is**: X/Twitter's AI chatbot (different product)
- **Status**: ❌ **Not implemented** - no adapter exists
- **Current behavior**: When you use `"grok"`, it redirects to the Groq adapter as a proxy
- **Recommendation**: Don't use `"grok"` - use `"groq"` instead

**What happens if you use "grok":**
```json
{
  "platforms": ["grok"]  // ⚠️ This will actually use Groq adapter
}
```

The codebase maps `"grok"` → `"groq"` adapter, so you'll get Groq responses anyway.

## Implementation Details

Looking at `app/utils/platform_mapping.py`:

```python
PLATFORM_TO_ADAPTER: dict[str, str] = {
    "groq": "groq",      # ✅ Direct mapping to GroqAdapter
    "grok": "groq",      # ⚠️ Proxy - redirects to GroqAdapter
    # ...
}
```

## Recommendation

1. **Always use `"groq"`** in your API calls
2. **Set up Groq API key**: Get it from https://console.groq.com
3. **Add to `.env`**: `GROQ_API_KEY=your_key_here`

## Example API Call

```bash
curl -X POST http://localhost:3001/api/v1/comparison/submit \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain quantum computing",
    "platforms": ["gemini", "groq"],  // ✅ Use "groq"
    "judge": "chatgpt"
  }'
```

## Getting Groq API Key

1. Go to https://console.groq.com
2. Sign up or log in
3. Navigate to API Keys
4. Create a new API key
5. Add to your `.env` file: `GROQ_API_KEY=gsk_...`

## Summary

| Feature | Groq | Grok |
|---------|------|------|
| Implemented | ✅ Yes | ❌ No |
| Adapter exists | ✅ Yes (`GroqAdapter`) | ❌ No |
| API endpoint | ✅ api.groq.com | ❌ N/A |
| Recommended | ✅ **YES** | ❌ No |
| Use in API | ✅ `"groq"` | ⚠️ Redirects to Groq |

**Bottom line: Use `"groq"` for all your API calls.**

