# OpenAI Judge Setup Guide

This guide explains how to use OpenAI for judging AI responses in the AI Audit platform.

## Overview

The platform uses OpenAI to evaluate and score AI-generated responses based on multiple criteria. There are two ways OpenAI is used for judging:

1. **Detailed JudgeEngine** - Uses OpenAI GPT-4o-mini with a comprehensive rubric for detailed scoring
2. **Platform Judge** - Uses OpenAI (via adapter) as the judge platform in comparisons

## Setup Instructions

### 1. Get OpenAI API Key

1. Go to [OpenAI API Keys](https://platform.openai.com/api-keys)
2. Create a new API key
3. Copy the key (it starts with `sk-`)

### 2. Configure API Key

Add the OpenAI API key to your `.env` file:

```env
# Option 1: Standard environment variable (recommended)
OPENAI_API_KEY=sk-your-api-key-here

# Option 2: Using adapter prefix (also works)
ADAPTER_OPENAI_API_KEY=sk-your-api-key-here
```

### 3. Verify Configuration

The system will automatically:
- Load the API key from environment variables
- Initialize the OpenAI client
- Enable judging functionality

If the API key is missing, you'll see a warning in the logs and the system will use placeholder scoring.

## How Judging Works

### JudgeEngine (Detailed Scoring)

The `JudgeEngine` class provides comprehensive evaluation using OpenAI GPT-4o-mini:

**Evaluation Criteria:**
- **Accuracy** (0-10): Factual correctness and precision
- **Completeness** (0-10): How fully the question is addressed
- **Clarity** (0-10): How clear and understandable the response is
- **Reasoning** (0-10): Quality of logical reasoning and explanation
- **Safety** (0-10): Absence of harmful, biased, or inappropriate content
- **Hallucination Risk** (0-10): Likelihood of made-up or unsupported information (lower is better)

**Model Used:** `gpt-4o-mini`
**Temperature:** `0.3` (low for consistency)

### Platform Judge (Comparison Scoring)

When you select "chatgpt" or "openai" as the judge platform in a comparison:

1. The system uses the OpenAI adapter to call the model
2. Sends evaluation prompts for each scoring category
3. Extracts scores from the responses
4. Calculates overall scores

**Usage in API:**
```json
{
  "prompt": "Explain quantum computing",
  "platforms": ["gemini", "groq"],
  "judge": "chatgpt"  // or "openai"
}
```

## Code Examples

### Using JudgeEngine Directly

```python
from app.services.judge import JudgeEngine

# Initialize judge (automatically uses OPENAI_API_KEY)
judge = JudgeEngine()

# Score a response
result = judge.score("Your AI response text here")

# Access scores
scores = result.payload
print(f"Accuracy: {scores.accuracy}/10")
print(f"Completeness: {scores.completeness}/10")
print(f"Clarity: {scores.clarity}/10")
print(f"Reasoning: {scores.reasoning}/10")
print(f"Safety: {scores.safety}/10")
print(f"Hallucination Risk: {scores.hallucination_risk}/10")
```

### Judge Prompt Structure

The judge uses a detailed system prompt that emphasizes:
- **Impartiality**: No bias toward any model
- **Evidence-Based**: Grounded in the actual response
- **Determinism**: Consistent scoring
- **Transparency**: Clear reasoning
- **Ethical Standards**: Safety and accuracy

## Troubleshooting

### Issue: "OPENAI_API_KEY not found"

**Solution:** 
1. Check your `.env` file has the key set
2. Restart your application
3. Verify the key is valid at https://platform.openai.com/api-keys

### Issue: Judge returns placeholder scores

**Solution:**
- The API key might not be loaded
- Check application logs for warnings
- Ensure `.env` file is in the correct location (project root)

### Issue: Judge responses are inconsistent

**Solution:**
- The judge uses `temperature=0.3` for consistency
- If you need even more consistency, you can modify `app/services/judge.py` to use `temperature=0`

## Configuration Files

- **Judge Engine**: `app/services/judge.py`
- **Settings**: `app/core/config.py`
- **OpenAI Adapter**: `app/adapters/openai.py`

## Advanced Configuration

### Change Judge Model

To use a different OpenAI model, edit `app/services/judge.py`:

```python
response = self._client.chat.completions.create(
    model="gpt-4o",  # Change from "gpt-4o-mini" to "gpt-4o"
    # ... rest of config
)
```

### Adjust Temperature

For more deterministic results, set temperature to 0:

```python
temperature=0,  # Change from 0.3 to 0
```

## Testing

You can test the judge setup with a simple script:

```python
# test_judge.py
from app.services.judge import JudgeEngine

judge = JudgeEngine()
result = judge.score("This is a test response to evaluate.")

print(f"Fallback applied: {result.fallback_applied}")
print(f"Scores: {result.payload}")
```

Run it:
```bash
python test_judge.py
```

If `fallback_applied` is `False`, OpenAI judging is working correctly!

