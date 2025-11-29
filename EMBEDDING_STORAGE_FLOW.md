# Vector Embeddings Storage and Similarity Calculation Flow

## Where Embeddings Are Saved

### Database Table: `embeddings`

**Location:** SQLite database at `var/audit.db` (or PostgreSQL if configured)

**Schema:**
```sql
CREATE TABLE embeddings (
    id INTEGER PRIMARY KEY,
    request_id VARCHAR NOT NULL,           -- Groups embeddings from same comparison
    provider VARCHAR NOT NULL,             -- LLM provider (openai, gemini, groq, etc.)
    text TEXT NOT NULL,                    -- Original response text
    embedding_vector JSON NOT NULL,        -- Vector as JSON array of floats
    model_name VARCHAR NOT NULL,           -- Embedding model used (e.g., "text-embedding-3-small")
    embedding_dimension INTEGER NOT NULL,  -- Vector dimension (e.g., 1536)
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);
```

**Indexes:**
- `request_id` - For fast lookup by comparison/request
- `provider` - For filtering by provider
- `created_at` - For chronological ordering

---

## How Embeddings Are Saved

### Step-by-Step Process

1. **Generate Embeddings** (`app/services/embedding/embedding_service.py`)
   ```python
   # Uses OpenAI API to generate embeddings
   embedding_vectors = await embedding_service.generate_embeddings_batch(texts)
   # Returns: List[List[float]] - e.g., [[0.1, 0.2, ...], [0.3, 0.4, ...]]
   ```

2. **Save to Database** (`app/services/embedding/similarity_processor.py`)
   ```python
   # For each provider's embedding:
   embedding_repo.create(
       request_id=request_id,           # e.g., "comp_abc123"
       provider=provider,               # e.g., "openai"
       text=responses[provider],        # Original response text
       embedding_vector=embedding,      # List of floats
       model_name="text-embedding-3-small"
   )
   ```

3. **Repository Layer** (`app/repositories/embedding_repository.py`)
   ```python
   # Creates Embedding model instance and saves to database
   embedding = Embedding(
       request_id=request_id,
       provider=provider,
       text=text,
       embedding_vector=embedding_vector,  # Stored as JSON
       model_name=model_name,
       embedding_dimension=len(embedding_vector)
   )
   session.add(embedding)
   session.commit()
   ```

---

## When Similarity Is Calculated

### Trigger Points

1. **During Comparison Processing** (`app/services/comparison/comparison_service.py`)
   ```python
   # After getting responses from all platforms:
   similarity_processor = SimilarityProcessor()
   similarity_analysis = await similarity_processor.process_responses(
       request_id=comparison_id,
       responses=valid_responses,  # Dict of provider_id -> response_text
       persist=True  # Saves embeddings to database
   )
   ```

2. **Via API Endpoint** (`app/api/v1/routers/similarity.py`)
   ```python
   POST /api/v1/similarity/process
   {
     "request_id": "comp_abc123",
     "persist": true
   }
   ```

---

## How Similarity Is Calculated

### Complete Flow

```
1. Generate Embeddings
   └─> OpenAI API (text-embedding-3-small)
       └─> Returns: List[float] (1536 dimensions)

2. Save Embeddings (if persist=True)
   └─> EmbeddingRepository.create()
       └─> Database: embeddings table

3. Compute Similarity Matrix
   └─> SimilarityService.compute_similarity_matrix()
       └─> For each pair of embeddings:
           └─> Cosine Similarity = (A · B) / (||A|| × ||B||)
           └─> Result: similarity_matrix[provider1][provider2] = score

4. Calculate Consensus Scores
   └─> ConsensusScorer.calculate_consensus_scores()
       └─> Average similarity of each provider to all others
       └─> Result: consensus_scores[provider] = average_score

5. Detect Outliers
   └─> OutlierDetector.get_outlier_analysis()
       └─> Statistical analysis (mean, std_dev)
       └─> Identifies providers with low consensus scores

6. Save Similarity Analysis (if persist=True)
   └─> SimilarityAnalysisRepository.create()
       └─> Database: similarity_analyses table
```

### Code Flow

**File: `app/services/embedding/similarity_processor.py`**

```python
async def process_responses(request_id, responses, persist=True):
    # Step 1: Generate embeddings (batch)
    embedding_vectors = await self.embedding_service.generate_embeddings_batch(texts)
    
    # Step 2: Save embeddings to database
    if persist:
        for provider, embedding in zip(providers, embedding_vectors):
            self.embedding_repo.create(
                request_id=request_id,
                provider=provider,
                text=responses[provider],
                embedding_vector=embedding,
                model_name=self.embedding_service.model_name
            )
    
    # Step 3: Compute similarity matrix (uses embeddings in memory)
    similarity_matrix = self.similarity_service.compute_similarity_matrix(
        embeddings_dict  # Dict[provider_id, List[float]]
    )
    
    # Step 4: Calculate consensus scores
    consensus_scores = self.consensus_scorer.calculate_consensus_scores(
        similarity_matrix
    )
    
    # Step 5: Detect outliers
    outlier_analysis = self.outlier_detector.get_outlier_analysis(
        consensus_scores, similarity_matrix
    )
    
    # Step 6: Save similarity analysis to database
    if persist:
        self.similarity_repo.create(
            request_id=request_id,
            similarity_matrix=similarity_matrix,
            consensus_scores=consensus_scores,
            outliers=outliers,
            statistics=outlier_analysis["statistics"]
        )
```

---

## Retrieving Stored Embeddings

### From Database

**File: `app/repositories/embedding_repository.py`**

```python
# Get all embeddings for a request
embeddings = embedding_repo.get_by_request_id("comp_abc123")

# Get embeddings for a specific provider
embeddings = embedding_repo.get_by_provider("openai", request_id="comp_abc123")

# Access embedding vector
for emb in embeddings:
    vector = emb.embedding_vector  # List[float]
    text = emb.text                # Original text
    provider = emb.provider        # "openai"
    dimension = emb.embedding_dimension  # 1536
```

### Reusing for Similarity Calculation

**File: `app/services/embedding/similarity_processor.py`**

```python
async def get_analysis(request_id: str):
    # Retrieve stored embeddings
    embeddings = self.embedding_repo.get_by_request_id(request_id)
    embeddings_dict = {
        emb.provider: emb.embedding_vector for emb in embeddings
    }
    
    # Retrieve stored similarity analysis
    analysis = self.similarity_repo.get_by_request_id(request_id)
    
    # Return complete analysis
    return {
        "embeddings": embeddings_dict,
        "similarity_matrix": analysis.similarity_matrix,
        "consensus_scores": analysis.consensus_scores,
        "outliers": analysis.outliers
    }
```

---

## Key Points

1. **Storage Location:** SQLite database (`var/audit.db`) - `embeddings` table
2. **Storage Format:** JSON column containing array of floats
3. **When Saved:** During comparison processing (if `persist=True`)
4. **How Used:** 
   - Embeddings are generated in memory first
   - Saved to database for persistence
   - Similarity calculation uses in-memory embeddings (faster)
   - Stored embeddings can be retrieved later for re-analysis
5. **Similarity Method:** Cosine similarity between embedding vectors
6. **Batch Processing:** All embeddings generated in one API call for efficiency

---

## Database Tables Summary

### `embeddings` Table
- Stores individual embedding vectors
- One row per provider per request
- Contains original text and vector

### `similarity_analyses` Table
- Stores computed similarity results
- One row per request
- Contains similarity matrix, consensus scores, outliers, statistics

