# Similarity Analysis - Quick Reference

## What It Does
Compares AI model responses to find:
- How similar they are to each other
- Which responses agree with the group (consensus)
- Which responses are different (outliers)

## Key Terms (Simple Explanation)

### 1. Embedding
- Text converted to numbers (vector)
- Similar text = similar numbers

### 2. Cosine Similarity
**Score Range: 0 to 1**
- **0.9-1.0** = Very similar ✅
- **0.7-0.89** = Similar ✓
- **0.5-0.69** = Somewhat different ⚠️
- **<0.5** = Very different ❌

### 3. Similarity Matrix
Table showing how similar each pair of responses is.

**Example:**
```
        OpenAI  Gemini  Groq
Openai   1.00   0.92   0.88
Gemini   0.92   1.00   0.93
Groq     0.88   0.93   1.00
```
- Diagonal (1.00) = Same response (always 1.0)
- Other numbers = Similarity between different responses

### 4. Consensus Score
**Average similarity of one response to all others**

**What it means:**
- **0.8-1.0** = High consensus (agrees with group) ✅
- **0.6-0.79** = Medium consensus ✓
- **<0.6** = Low consensus (potential outlier) ⚠️

**Example:**
- OpenAI: 0.90 = 90% similar to others
- Gemini: 0.925 = 92.5% similar to others (highest)
- Groq: 0.88 = 88% similar to others

### 5. Outliers
Responses that are significantly different from the group.

**Detection:** Automatically calculated using statistics
- **No outliers** = All responses are similar ✅
- **Outliers found** = Some responses are very different ⚠️

### 6. Statistics

| Term | What It Means | Good Value |
|------|---------------|------------|
| **Mean** | Average consensus score | 0.8+ |
| **Std Dev** | How consistent the scores are | <0.05 |
| **Min** | Lowest consensus score | 0.8+ |
| **Max** | Highest consensus score | 0.8+ |

