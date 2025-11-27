# Prompt Review - What Each Platform Receives

This document shows exactly what prompt/payload is sent to each AI platform.

## Overview

All platforms receive the **user's prompt directly** via `invocation.instructions` - there is **NO modification, system prompts, or additional context** added to the user's prompt for regular responses.

---

## 1. OpenAI (ChatGPT)

**File:** `app/adapters/openai.py` (lines 51-57)

**Model:** `gpt-4o-mini`

**Prompt Sent:**
```python
client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "user", "content": invocation.instructions}  # ← User's prompt directly
    ],
    timeout=self._timeout,
)
```

**Example:**
If user sends: `"What is AI"`
OpenAI receives:
```json
{
  "model": "gpt-4o-mini",
  "messages": [
    {
      "role": "user",
      "content": "What is AI"
    }
  ]
}
```

**No system prompt, no modifications** - just the user's prompt as-is.

---

## 2. Google Gemini

**File:** `app/adapters/gemini.py` (lines 84-92)

**Model:** `gemini-2.5-flash`

**Prompt Sent:**
```python
request_body = {
    "contents": [
        {
            "parts": [
                {"text": invocation.instructions}  # ← User's prompt directly
            ]
        }
    ]
}
```

**Example:**
If user sends: `"What is AI"`
Gemini receives:
```json
{
  "contents": [
    {
      "parts": [
        {
          "text": "What is AI"
        }
      ]
    }
  ]
}
```

**No system prompt, no modifications** - just the user's prompt as-is.

---

## 3. Groq

**File:** `app/adapters/groq.py` (lines 76-83)

**Model:** `llama-3.1-8b-instant`

**Prompt Sent:**
```python
request_body = {
    "model": self._model,
    "messages": [
        {"role": "user", "content": invocation.instructions}  # ← User's prompt directly
    ],
    "temperature": 0.7,
    "max_tokens": 1024,
}
```

**Example:**
If user sends: `"What is AI"`
Groq receives:
```json
{
  "model": "llama-3.1-8b-instant",
  "messages": [
    {
      "role": "user",
      "content": "What is AI"
    }
  ],
  "temperature": 0.7,
  "max_tokens": 1024
}
```

**No system prompt, no modifications** - just the user's prompt as-is.

---

## 4. Hugging Face

**File:** `app/adapters/huggingface.py` (lines 77-84)

**Model:** `mistralai/Mistral-7B-Instruct-v0.2`

**Prompt Sent:**
```python
request_body = {
    "inputs": invocation.instructions,  # ← User's prompt directly
    "parameters": {
        "max_new_tokens": 512,
        "temperature": 0.7,
        "return_full_text": False,
    },
}
```

**Example:**
If user sends: `"What is AI"`
Hugging Face receives:
```json
{
  "inputs": "What is AI",
  "parameters": {
    "max_new_tokens": 512,
    "temperature": 0.7,
    "return_full_text": false
  }
}
```

**No system prompt, no modifications** - just the user's prompt as-is.

---

## Summary

### Key Points:

1. **All platforms receive the user's prompt DIRECTLY** - no modifications
2. **No system prompts** are added for regular responses
3. **No additional context** or instructions are prepended/appended
4. **The prompt is sent exactly as the user provides it**

### Code Flow:

```
User Request → SubmitComparisonRequest.prompt
    ↓
comparison_service.py: process_comparison()
    ↓
ai_service.get_response(platform_id, prompt_text)
    ↓
AdapterInvocation(instructions=prompt)  # ← Prompt passed directly
    ↓
adapter.invoke_async(invocation)
    ↓
Each adapter uses: invocation.instructions  # ← No modification
```

---

## Exception: Judge/Scorer

**Note:** The judge/scorer (used for evaluation) DOES have a custom prompt template. See `app/services/judge.py` (lines 48-71) for the scoring rubric prompt. This is separate from the main response generation.

---

## Recommendation

If you want to add system prompts or modify prompts before sending to platforms, you would need to modify:

1. **Individual adapters** - Add system prompts in each adapter's `invoke_async()` method
2. **Service layer** - Modify prompts in `app/services/ai_platform_service.py` before creating `AdapterInvocation`
3. **Comparison service** - Modify prompts in `app/services/comparison_service.py` before calling `get_response()`

