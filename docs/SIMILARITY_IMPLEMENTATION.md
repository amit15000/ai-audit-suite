# Embedding & Similarity Processing Implementation

This document describes the implementation of the embedding and similarity processing features.

## Overview

The implementation provides a complete pipeline for:
1. Generating embeddings for each model's answer using one embedding model
2. Computing pairwise cosine similarity between all responses
3. Generating a similarity matrix
4. Calculating a "consensus score" for each answer based on similarity
5. Detecting outliers with low consensus scores

## Architecture

The implementation follows a modular, industry-level architecture with clear separation of concerns:

### Services Layer (`app/services/`)

1. **EmbeddingService** (`embedding_service.py`)
   - Generates embeddings using OpenAI's embedding model (configurable via `EMBED_MODEL_NAME`)
   - Supports single and batch embedding generation
   - Handles errors gracefully with structured logging

2. **SimilarityService** (`similarity_service.py`)
   - Computes cosine similarity between embedding vectors
   - Generates full similarity matrices
   - Provides pairwise similarity calculations

3. **ConsensusScorer** (`consensus_scorer.py`)
   - Calculates consensus scores based on average similarity to other responses
   - Supports weighted consensus scoring
   - Higher scores indicate higher agreement with the group

4. **OutlierDetector** (`outlier_detector.py`)
   - Detects outliers using statistical methods (mean - 1.5 * std_dev)
   - Provides comprehensive outlier analysis
   - Returns detailed outlier information including deviations

5. **SimilarityProcessor** (`similarity_processor.py`)
   - Orchestrates the complete pipeline
   - Coordinates all services
   - Handles persistence to database

### Data Layer (`app/domain/` & `app/repositories/`)

1. **Database Models** (`app/domain/models.py`)
   - `Embedding`: Stores embedding vectors for each response
   - `SimilarityAnalysis`: Stores similarity analysis results

2. **Repositories** (`app/repositories/embedding_repository.py`)
   - `EmbeddingRepository`: CRUD operations for embeddings
   - `SimilarityAnalysisRepository`: CRUD operations for similarity analyses

### API Layer (`app/api/v1/routers/`)

1. **Similarity Router** (`similarity.py`)
   - `POST /api/v1/similarity/process`: Process similarity analysis for a request
   - `GET /api/v1/similarity/{request_id}`: Retrieve stored similarity analysis

### Integration

The similarity processing is automatically integrated into the comparison service:
- Runs after collecting responses from all platforms
- Results are included in comparison results
- Can also be triggered independently via API endpoints

## Usage

### Automatic Integration

When a comparison is processed, similarity analysis is automatically performed:

```python
# In comparison_service.py
similarity_analysis = await similarity_processor.process_responses(
    request_id=comparison_id,
    responses=valid_responses,
    persist=True,
)
```

Results are included in the comparison response under `similarityAnalysis`:
- `consensusScores`: Consensus score for each platform
- `outliers`: List of outlier platform IDs
- `statistics`: Statistical summary

### Standalone API Usage

#### Process Similarity Analysis

```bash
POST /api/v1/similarity/process
{
  "request_id": "req_123",
  "persist": true
}
```

This endpoint:
1. Retrieves LLM responses for the request_id
2. Generates embeddings for all responses
3. Computes similarity matrix
4. Calculates consensus scores
5. Detects outliers
6. Persists results (if `persist=true`)

#### Get Similarity Analysis

```bash
GET /api/v1/similarity/{request_id}
```

Returns stored similarity analysis for a request ID.

## Configuration

### Embedding Model

Configure the embedding model via environment variable:

```bash
EMBED_MODEL_NAME=text-embedding-3-large
```

Default: `text-embedding-3-large`

### OpenAI API Key

Required for embedding generation:

```bash
OPENAI_API_KEY=your-api-key
# or
ADAPTER_OPENAI_API_KEY=your-api-key
```

## Database Schema

### Embeddings Table

```sql
CREATE TABLE embeddings (
    id INTEGER PRIMARY KEY,
    request_id VARCHAR NOT NULL,
    provider VARCHAR NOT NULL,
    text TEXT NOT NULL,
    embedding_vector JSON NOT NULL,
    model_name VARCHAR NOT NULL,
    embedding_dimension INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);
```

### Similarity Analyses Table

```sql
CREATE TABLE similarity_analyses (
    id INTEGER PRIMARY KEY,
    request_id VARCHAR NOT NULL,
    similarity_matrix JSON NOT NULL,
    consensus_scores JSON NOT NULL,
    outliers JSON,
    outlier_threshold VARCHAR,
    statistics JSON,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);
```

## Response Format

### Similarity Analysis Response

```json
{
  "success": true,
  "data": {
    "request_id": "req_123",
    "similarity_matrix": {
      "openai": {
        "openai": 1.0,
        "gemini": 0.85,
        "groq": 0.78
      },
      "gemini": {
        "openai": 0.85,
        "gemini": 1.0,
        "groq": 0.82
      },
      "groq": {
        "openai": 0.78,
        "gemini": 0.82,
        "groq": 1.0
      }
    },
    "consensus_scores": {
      "openai": 0.815,
      "gemini": 0.835,
      "groq": 0.80
    },
    "outliers": [],
    "outlier_threshold": 0.65,
    "statistics": {
      "mean": 0.816,
      "std_dev": 0.014,
      "min": 0.80,
      "max": 0.835,
      "count": 3
    },
    "outlier_details": []
  }
}
```

## Error Handling

All services include comprehensive error handling:
- Validation errors for empty inputs
- API errors for embedding generation
- Database errors for persistence
- Graceful degradation (similarity analysis failures don't break comparisons)

## Performance Considerations

1. **Batch Embedding Generation**: Embeddings are generated in batch for efficiency
2. **Lazy Client Initialization**: OpenAI client is initialized only when needed
3. **Database Persistence**: Optional persistence to avoid unnecessary writes
4. **Async Processing**: All I/O operations are async for better performance

## Testing

To test the implementation:

1. **Generate LLM Responses**: First, create responses using the multi-LLM endpoint
2. **Process Similarity**: Use the similarity processing endpoint
3. **Retrieve Results**: Get the analysis results

Example workflow:

```bash
# 1. Generate responses
POST /api/v1/multi-llm
{
  "prompt": "What is AI?",
  "adapter_ids": ["openai", "gemini", "groq"]
}
# Returns request_id: "req_abc123"

# 2. Process similarity
POST /api/v1/similarity/process
{
  "request_id": "req_abc123",
  "persist": true
}

# 3. Get results
GET /api/v1/similarity/req_abc123
```

## Dependencies

New dependencies added:
- `numpy>=1.24.0`: For efficient vector operations and cosine similarity calculations

Existing dependencies used:
- `openai>=1.0.0`: For embedding generation
- `sqlalchemy>=2.0.30`: For database operations
- `structlog>=24.1.0`: For structured logging

## Future Enhancements

Potential improvements:
1. Support for multiple embedding models
2. Caching of embeddings to avoid regeneration
3. Advanced outlier detection methods (IQR, Z-score, etc.)
4. Similarity-based clustering of responses
5. Visualization endpoints for similarity matrices

