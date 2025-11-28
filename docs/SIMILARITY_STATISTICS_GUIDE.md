# Understanding Similarity Analysis Statistics

This guide explains the statistical terms and concepts used in the similarity analysis feature.

## Overview

When you compare responses from multiple AI models, the similarity analysis generates several statistical metrics to help you understand:

- How similar the responses are to each other
- Which responses agree with the majority (consensus)
- Which responses are outliers (different from the group)

## Key Concepts

### 1. Embeddings

**What it is:** An embedding is a numerical representation of text as a vector (list of numbers). Similar texts have similar embeddings.

**Why it matters:** By converting text to numbers, we can mathematically measure how similar two pieces of text are.

**Example:**

- "The cat sat on the mat" → `[0.1, 0.3, -0.2, 0.5, ...]` (vector of numbers)
- "A cat was sitting on a mat" → `[0.12, 0.28, -0.18, 0.48, ...]` (similar vector)

### 2. Cosine Similarity

**What it is:** A measure of similarity between two vectors, ranging from -1 to 1.

**Interpretation:**  

- **1.0** = Identical (same meaning)
- **0.8-0.99** = Very similar (high agreement)
- **0.6-0.79** = Moderately similar (some agreement)
- **0.4-0.59** = Somewhat different (low agreement)
- **0.0-0.39** = Very different (little to no agreement)
- **-1.0** = Completely opposite

**Formula:**

```
similarity = (A · B) / (||A|| × ||B||)
```

Where:

- `A · B` = dot product of vectors A and B
- `||A||` = magnitude (length) of vector A
- `||B||` = magnitude (length) of vector B

**Example:**

- Response A vs Response B: 0.92 → Very similar (92% similar)
- Response A vs Response C: 0.65 → Moderately similar (65% similar)

### 3. Similarity Matrix

**What it is:** A table showing pairwise similarities between all responses.

**Structure:**

```
        OpenAI  Gemini  Groq
Openai   1.00   0.92   0.88
Gemini   0.92   1.00   0.93
Groq     0.88   0.93   1.00
```

**Reading the matrix:**

- **Diagonal (1.00)**: Each response compared to itself = perfect similarity
- **Off-diagonal values**: Similarity between different responses
- **Symmetric**: OpenAI vs Gemini = Gemini vs OpenAI (same value)

**What it tells you:**

- High values (0.8+) = Responses agree with each other
- Low values (<0.6) = Responses disagree significantly

**Example Interpretation:**

```
OpenAI vs Gemini: 0.92 → These two responses are very similar
OpenAI vs Groq:   0.88 → These are also similar, but slightly less
Gemini vs Groq:   0.93 → These two are the most similar pair
```

### 4. Consensus Score

**What it is:** The average similarity of one response to all other responses.

**Calculation:**

```
Consensus Score = (Sum of similarities to all others) / (Number of other responses)
```

**Interpretation:**

- **High consensus (0.8-1.0)**: Response agrees with the group
- **Medium consensus (0.6-0.79)**: Response partially agrees
- **Low consensus (<0.6)**: Response disagrees with the group (potential outlier)

**Example:**

```
OpenAI Consensus = (0.92 + 0.88) / 2 = 0.90
Gemini Consensus = (0.92 + 0.93) / 2 = 0.925
Groq Consensus   = (0.88 + 0.93) / 2 = 0.905
```

**What it means:**

- **Gemini (0.925)**: Highest consensus - most similar to the group
- **OpenAI (0.90)**: High consensus - agrees with others
- **Groq (0.905)**: High consensus - also agrees well

### 5. Outliers

**What it is:** Responses with significantly lower consensus scores than the group average.

**Detection Method:** Statistical threshold using mean and standard deviation

```
Threshold = Mean - (1.5 × Standard Deviation)
Outlier = Consensus Score < Threshold
```

**Why 1.5?** This is similar to the Interquartile Range (IQR) method, which identifies values that are unusually far from the center.

**Interpretation:**

- **Outlier detected**: Response is significantly different from the group
- **No outliers**: All responses are reasonably similar

**Example:**

```
Mean Consensus: 0.90
Std Dev: 0.02
Threshold: 0.90 - (1.5 × 0.02) = 0.87

If a response has consensus < 0.87, it's an outlier.
```

**What it means:**

- Outliers may indicate:
  - Different interpretation of the question
  - Unique perspective or approach
  - Potential error or misunderstanding
  - Creative or alternative answer

### 6. Statistical Measures

#### Mean (Average)

**What it is:** The average of all consensus scores.

**Formula:**

```
Mean = (Sum of all consensus scores) / (Number of responses)
```

**Interpretation:**

- **High mean (0.8+)**: Overall high agreement among responses
- **Low mean (<0.6)**: Overall low agreement (responses are diverse)

**Example:**

```
Consensus Scores: [0.90, 0.925, 0.905]
Mean = (0.90 + 0.925 + 0.905) / 3 = 0.91
```

This means, on average, responses are 91% similar to each other.

#### Standard Deviation (Std Dev)

**What it is:** A measure of how spread out the consensus scores are.

**Formula:**

```
Std Dev = √(Σ(xi - mean)² / n)
```

**Interpretation:**

- **Low std dev (<0.05)**: Consensus scores are close together (consistent agreement)
- **High std dev (>0.1)**: Consensus scores vary widely (inconsistent agreement)

**Example:**

```
Consensus Scores: [0.90, 0.925, 0.905]
Mean: 0.91
Std Dev: 0.012

Low std dev → All responses agree similarly with the group
```

**What it means:**

- Low std dev = Responses are consistently similar
- High std dev = Some responses agree more than others

#### Minimum (Min)

**What it is:** The lowest consensus score in the group.

**Interpretation:**

- Shows the response that agrees least with the group
- If min is low, at least one response is quite different

**Example:**

```
Min: 0.88
→ The least similar response is still 88% similar (high agreement)
```

#### Maximum (Max)

**What it is:** The highest consensus score in the group.

**Interpretation:**

- Shows the response that agrees most with the group
- The "most representative" response

**Example:**

```
Max: 0.925
→ The most similar response is 92.5% similar to others
```

#### Count

**What it is:** The number of responses analyzed.

**Interpretation:**

- More responses = More reliable statistics
- Need at least 2 responses for similarity analysis
- Recommended: 3+ responses for meaningful analysis

## Complete Example

### Input: 3 Responses

```
OpenAI: "Artificial intelligence is the simulation of human intelligence by machines."
Gemini: "AI refers to computer systems that can perform tasks requiring human intelligence."
Groq:   "Artificial intelligence enables machines to mimic human cognitive functions."
```

### Similarity Matrix

```
        OpenAI  Gemini  Groq
Openai   1.00   0.92   0.88
Gemini   0.92   1.00   0.93
Groq     0.88   0.93   1.00
```

### Consensus Scores

```
OpenAI: 0.90  (Average of 0.92 and 0.88)
Gemini: 0.925 (Average of 0.92 and 0.93)
Groq:   0.905 (Average of 0.88 and 0.93)
```

### Statistics

```
Mean:     0.91   (Average consensus)
Std Dev:  0.012  (Low variation - consistent agreement)
Min:      0.90   (Lowest consensus)
Max:      0.925  (Highest consensus)
Count:    3      (Number of responses)
```

### Outlier Analysis

```
Threshold: 0.91 - (1.5 × 0.012) = 0.892
Outliers:  []  (No outliers - all scores > 0.892)
```

### Interpretation

- **All responses are very similar** (consensus scores 0.90-0.925)
- **High agreement** (mean 0.91, low std dev 0.012)
- **No outliers** (all responses agree with the group)
- **Gemini has highest consensus** (most representative of the group)

## Practical Use Cases

### 1. Quality Assurance

- **High consensus (0.8+)**: Responses are consistent → Good quality
- **Low consensus (<0.6)**: Responses vary → May need review

### 2. Finding Best Response

- **Highest consensus score**: Most representative of the group
- **Not an outlier**: Agrees with others

### 3. Detecting Issues

- **Outliers detected**: One response is very different
  - Could indicate: error, misunderstanding, or unique perspective
  - Action: Review the outlier response

### 4. Model Comparison

- **Compare consensus scores**: Which model's responses agree most with others?
- **High consensus**: Model produces typical/expected responses
- **Low consensus**: Model produces unique/different responses

## Common Questions

### Q: What's a "good" consensus score?

**A:**

- **0.8-1.0**: Excellent agreement
- **0.6-0.79**: Good agreement
- **<0.6**: Low agreement (may be an outlier)

### Q: Why are some similarity scores different in the matrix?

**A:** Each pair comparison is independent. Small differences are normal due to:

- Different wording
- Different emphasis
- Numerical precision

### Q: What if all responses are outliers?

**A:** This means responses are very different from each other. Consider:

- Are the prompts clear?
- Are the models appropriate for the task?
- Is the question ambiguous?

### Q: Can I trust a response with low consensus?

**A:** It depends:

- **Low consensus + outlier**: Review carefully - may be wrong or unique
- **Low consensus + not outlier**: Still within normal range, just less typical

### Q: How many responses do I need?

**A:**

- **Minimum**: 2 (for basic similarity)
- **Recommended**: 3-5 (for reliable statistics)
- **More responses**: Better statistics, but diminishing returns

## Technical Notes

### Embedding Model

- Uses OpenAI's `text-embedding-3-large` model
- Generates 3072-dimensional vectors
- Optimized for semantic similarity

### Calculation Method

- **Similarity**: Cosine similarity (normalized dot product)
- **Consensus**: Arithmetic mean of similarities
- **Outliers**: Statistical method (mean - 1.5 × std dev)

### Performance

- Batch processing for efficiency
- Async operations for speed
- Results cached in database

## Summary

| Term | What It Measures | Good Value |
|------|-----------------|------------|
| **Similarity** | How similar two responses are | 0.8+ |
| **Consensus Score** | How well a response agrees with the group | 0.8+ |
| **Mean** | Average agreement across all responses | 0.8+ |
| **Std Dev** | Consistency of agreement | <0.05 |
| **Outliers** | Responses that disagree significantly | None |

**Key Takeaway:** High consensus scores (0.8+) and low standard deviation (<0.05) indicate that all AI models are producing similar, consistent responses - which is generally a good sign of quality and reliability.
