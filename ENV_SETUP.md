# Environment Variables & Package Setup Guide

## New API Keys Required (Optional - Services Have Fallbacks)

All new features work without these API keys, but they provide enhanced functionality. Services will fall back to rule-based or LLM-based methods if API keys are not provided.

### 1. Google Custom Search API (For Feature 2: Factual Accuracy Score)

**Purpose:** Verify factual claims against Google search results

**How to Get:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable "Custom Search API"
4. Create credentials (API Key)
5. Create a Custom Search Engine at [Google Custom Search](https://programmablesearchengine.google.com/)
6. Get your Search Engine ID (CX)

**Add to `.env`:**
```env
# Google Custom Search API (for factual accuracy checking)
GOOGLE_CUSTOM_SEARCH_API_KEY=your_api_key_here
GOOGLE_CUSTOM_SEARCH_CX=your_search_engine_id_here

# Or with prefix:
EXTERNAL_API_GOOGLE_CUSTOM_SEARCH_API_KEY=your_api_key_here
EXTERNAL_API_GOOGLE_CUSTOM_SEARCH_CX=your_search_engine_id_here
```

**Cost:** Free tier: 100 queries/day, then $5 per 1,000 queries

---

### 2. Perspective API (For Feature 9: Safety Score - Toxicity Detection)

**Purpose:** Detect toxicity, hate speech, and harmful content

**How to Get:**
1. Go to [Perspective API](https://perspectiveapi.com/)
2. Sign up for API access
3. Get your API key

**Add to `.env`:**
```env
# Perspective API (for toxicity detection)
PERSPECTIVE_API_KEY=your_api_key_here

# Or with prefix:
EXTERNAL_API_PERSPECTIVE_API_KEY=your_api_key_here
```

**Cost:** Free tier available, then pay-as-you-go

---

### 3. Copyscape API (For Feature 18: Plagiarism Checker)

**Purpose:** Detect copied content, plagiarism

**How to Get:**
1. Go to [Copyscape](https://www.copyscape.com/)
2. Sign up for an account
3. Get API credentials (username and API key)

**Add to `.env`:**
```env
# Copyscape API (for plagiarism checking)
COPYSCAPE_USERNAME=your_username_here
COPYSCAPE_API_KEY=your_api_key_here

# Or with prefix:
EXTERNAL_API_COPYSCAPE_USERNAME=your_username_here
EXTERNAL_API_COPYSCAPE_API_KEY=your_api_key_here
```

**Cost:** Pay-per-use pricing

---

## Existing API Keys (Already Required)

These are already needed for the platform to work:

```env
# OpenAI API Key (for judge, evaluations, and OpenAI adapter)
OPENAI_API_KEY=your_openai_key_here

# Or with prefix:
ADAPTER_OPENAI_API_KEY=your_openai_key_here

# Other LLM API Keys (optional, for using those adapters)
GOOGLE_API_KEY=your_google_key_here
GEMINI_API_KEY=your_gemini_key_here
GROQ_API_KEY=your_groq_key_here
HUGGINGFACE_API_KEY=your_hf_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
PERPLEXITY_API_KEY=your_perplexity_key_here
```

---

## New Packages to Install

### Already Added to requirements.txt

The following package was already added:

```txt
wikipedia>=1.4.0
```

**Purpose:** Wikipedia API integration for factual accuracy checking (Feature 2)
**Cost:** Free, no API key needed

### Install Command

Run this to install the new package:

```bash
pip install wikipedia>=1.4.0
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

---

## Complete .env Example

Here's a complete `.env` file example with all optional new API keys:

```env
# ============================================
# EXISTING API KEYS (Required for core functionality)
# ============================================

# OpenAI API Key (Required for judge and OpenAI adapter)
OPENAI_API_KEY=sk-your-openai-key-here

# Other LLM Adapters (Optional)
GOOGLE_API_KEY=your-google-key
GEMINI_API_KEY=your-gemini-key
GROQ_API_KEY=your-groq-key
HUGGINGFACE_API_KEY=your-hf-key
ANTHROPIC_API_KEY=your-anthropic-key
PERPLEXITY_API_KEY=your-perplexity-key

# ============================================
# NEW API KEYS (Optional - Enhance Features 2, 9, 18)
# ============================================

# Google Custom Search API (Feature 2: Factual Accuracy)
GOOGLE_CUSTOM_SEARCH_API_KEY=your-google-custom-search-api-key
GOOGLE_CUSTOM_SEARCH_CX=your-search-engine-id

# Perspective API (Feature 9: Safety Score - Toxicity)
PERSPECTIVE_API_KEY=your-perspective-api-key

# Copyscape API (Feature 18: Plagiarism Checker)
COPYSCAPE_USERNAME=your-copyscape-username
COPYSCAPE_API_KEY=your-copyscape-api-key

# ============================================
# DATABASE (Already configured)
# ============================================
DB_URL=sqlite:///var/audit.db

# ============================================
# JWT (Already configured)
# ============================================
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
```

---

## Feature Behavior Without API Keys

### ✅ Works Without API Keys (Fallback Methods)

All features work without the new API keys, using fallback methods:

1. **Feature 2 (Factual Accuracy):**
   - ✅ Works: Uses LLM-based fact verification
   - ⚡ Enhanced: With Google Custom Search API - real-time web verification

2. **Feature 9 (Safety Score):**
   - ✅ Works: Uses rule-based keyword detection
   - ⚡ Enhanced: With Perspective API - advanced toxicity detection

3. **Feature 18 (Plagiarism):**
   - ✅ Works: Uses local similarity checking
   - ⚡ Enhanced: With Copyscape API - comprehensive web plagiarism detection

### 📝 Wikipedia API

- ✅ **No API key needed** - Wikipedia API is free and public
- ✅ Already works out of the box
- Package: `wikipedia>=1.4.0` (already in requirements.txt)

---

## Installation Steps

### 1. Install New Package

```bash
pip install wikipedia>=1.4.0
```

Or update all packages:

```bash
pip install -r requirements.txt --upgrade
```

### 2. Add API Keys to .env (Optional)

Create or update `.env` file in the project root:

```bash
# Copy example if you don't have one
cp .env.example .env  # If you have an example file

# Or create new .env file
# Add the API keys you want to use (see above)
```

### 3. Verify Installation

```bash
python -c "import wikipedia; print('Wikipedia package installed successfully')"
```

---

## Priority Recommendations

### High Priority (Recommended)
1. **OPENAI_API_KEY** - Required for judge and evaluations
2. **GOOGLE_CUSTOM_SEARCH_API_KEY + CX** - Significantly improves factual accuracy checking

### Medium Priority (Nice to Have)
3. **PERSPECTIVE_API_KEY** - Improves toxicity detection accuracy

### Low Priority (Optional)
4. **COPYSCAPE_API_KEY** - Only needed if you want web-based plagiarism detection

---

## Cost Summary

| API Service | Free Tier | Paid Tier |
|------------|-----------|-----------|
| Google Custom Search | 100 queries/day | $5/1,000 queries |
| Perspective API | Limited free tier | Pay-as-you-go |
| Copyscape | Pay-per-use | Pay-per-use |
| Wikipedia | Free (no key needed) | N/A |
| OpenAI | Pay-per-use | Pay-per-use |

---

## Testing Without API Keys

You can test all features without API keys. The system will:
- Use LLM-based fallbacks for fact checking
- Use rule-based keyword detection for safety
- Use local similarity checks for plagiarism

All features are fully functional, just with different methods!

