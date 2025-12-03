# Quick Setup Guide - API Keys & Packages

## 📦 New Package to Install

**Only 1 new package needed:**

```bash
pip install wikipedia>=1.4.0
```

Or install all requirements:
```bash
pip install -r requirements.txt
```

**Note:** `wikipedia>=1.4.0` is already in `requirements.txt`, so running `pip install -r requirements.txt` will install it.

---

## 🔑 New API Keys for .env (All Optional)

Add these to your `.env` file to enhance specific features. **All features work without them** using fallback methods.

### 1. Google Custom Search API (Enhances Feature 2: Factual Accuracy)

```env
GOOGLE_CUSTOM_SEARCH_API_KEY=your_api_key_here
GOOGLE_CUSTOM_SEARCH_CX=your_search_engine_id_here
```

**Get it:** [Google Cloud Console](https://console.cloud.google.com/) → Enable Custom Search API → [Create Search Engine](https://programmablesearchengine.google.com/)

**Free tier:** 100 queries/day

---

### 2. Perspective API (Enhances Feature 9: Safety Score - Toxicity)

```env
PERSPECTIVE_API_KEY=your_api_key_here
```

**Get it:** [Perspective API](https://perspectiveapi.com/)

**Free tier:** Available

---

### 3. Copyscape API (Enhances Feature 18: Plagiarism Checker)

```env
COPYSCAPE_USERNAME=your_username_here
COPYSCAPE_API_KEY=your_api_key_here
```

**Get it:** [Copyscape](https://www.copyscape.com/)

**Cost:** Pay-per-use

---

## ✅ Complete .env Template

```env
# ============================================
# REQUIRED (For core functionality)
# ============================================
OPENAI_API_KEY=sk-your-openai-key-here

# ============================================
# OPTIONAL (Enhance features 2, 9, 18)
# ============================================
# Google Custom Search (Feature 2: Factual Accuracy)
GOOGLE_CUSTOM_SEARCH_API_KEY=your-key-here
GOOGLE_CUSTOM_SEARCH_CX=your-cx-here

# Perspective API (Feature 9: Safety Score)
PERSPECTIVE_API_KEY=your-key-here

# Copyscape (Feature 18: Plagiarism)
COPYSCAPE_USERNAME=your-username
COPYSCAPE_API_KEY=your-key-here
```

---

## 🚀 Quick Start

1. **Install package:**
   ```bash
   pip install wikipedia>=1.4.0
   ```

2. **Add API keys (optional):**
   - Copy the template above to your `.env` file
   - Add only the keys you want to use

3. **Done!** All features work with or without API keys.

---

## 📊 What Works Without API Keys?

✅ **All 24 features work without new API keys!**

- Feature 2 (Factual Accuracy): Uses LLM-based verification
- Feature 9 (Safety Score): Uses rule-based keyword detection  
- Feature 18 (Plagiarism): Uses local similarity checking

API keys just make these features more accurate/robust.

