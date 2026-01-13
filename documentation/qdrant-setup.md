# Qdrant Setup & Configuration for Pixie AI Service

## Overview

Qdrant is an open-source vector database optimized for storing and searching high-dimensional vectors. For Pixie, Qdrant powers the RAG (Retrieval Augmented Generation) system by enabling fast semantic search across user tasks, events, and conversation history.

---

## 1. What is Qdrant?

### Core Concept

**Vector Database** - Specialized database for storing numerical representations (embeddings) of data and performing similarity searches.

**How It Works:**
1. Text/data is converted to vectors using embedding models (e.g., text-embedding-3-small)
2. Vectors are stored in Qdrant with associated metadata (payloads)
3. Queries are converted to vectors and compared against stored vectors
4. Most similar vectors are retrieved based on distance metrics

### Key Features

**Fast Similarity Search**
- Uses HNSW algorithm for Approximate Nearest Neighbor (ANN) search
- Handles millions of vectors with sub-second query times
- Written in Rust for high performance

**Payload Support**
- Attach metadata to each vector (task details, timestamps, user ID)
- Filter search results by metadata before vector search
- Enables hybrid search: semantic + metadata filtering

**Scalability**
- Horizontal scaling via sharding and replication
- Vertical scaling by adding more resources
- Supports distributed deployments for production

### Why Qdrant for Pixie?

**RAG Architecture**
- Retrieve relevant user data based on semantic similarity
- Provide LLM with context from past tasks, events, conversations
- Prevents hallucinations by grounding responses in actual user data

**Performance**
- Fast enough for real-time queries (sub-100ms for most searches)
- Efficient memory usage with quantization support
- On-disk storage for large datasets with intelligent caching

**Simplicity**
- Easy to setup (Docker, self-hosted, or cloud)
- RESTful API and Python SDK
- Good documentation and community support

---

## 2. HNSW Indexing Algorithm

### What is HNSW?

**Hierarchical Navigable Small World graphs** - Algorithm for approximate nearest neighbor search in high-dimensional spaces.

**Key Characteristics:**
- Graph-based structure with multiple layers
- Greedy search starting from top layer, moving down
- Approximate (not exact) but very fast
- Trade-off between accuracy and speed

### How HNSW Works

**Graph Structure:**
- Nodes represent vectors
- Edges connect similar vectors
- Multiple layers create hierarchy
- Top layers: sparse, long-range connections
- Bottom layer: dense, local connections

**Search Process:**
1. Start at top layer with entry point
2. Navigate to closest neighbor in current layer
3. Move down to next layer
4. Repeat until bottom layer reached
5. Return K nearest neighbors

### HNSW Parameters

Two critical parameters control index quality and performance.

#### `m` - Maximum Connections Per Node

**What it controls:** Number of bidirectional links each node maintains in the graph.

**Higher `m` values (e.g., 32, 64):**
- **PRO:** Better search accuracy (more paths to explore)
- **PRO:** More resilient to deletions
- **CON:** Higher memory usage (more connections stored)
- **CON:** Slower index build time

**Lower `m` values (e.g., 8, 16):**
- **PRO:** Lower memory footprint
- **PRO:** Faster insertions
- **CON:** Lower search accuracy
- **CON:** Fewer alternative paths in graph

**Typical Range:** 8-64 (diminishing returns beyond 64)

**Recommended for Pixie:** 16-32
- Balanced accuracy vs memory
- Good for datasets up to 1M vectors
- Adequate for personal assistant use case

#### `ef_construct` - Construction Search Depth

**What it controls:** Number of candidates evaluated when inserting a vector during index construction.

**Higher `ef_construct` values (e.g., 200, 400):**
- **PRO:** Better graph quality (more thorough neighbor selection)
- **PRO:** Higher search accuracy after build
- **CON:** Slower index construction
- **CON:** More CPU during insertions

**Lower `ef_construct` values (e.g., 100, 150):**
- **PRO:** Faster index building
- **PRO:** Lower CPU usage during inserts
- **CON:** Suboptimal graph structure
- **CON:** Lower eventual search accuracy

**Typical Range:** 100-500 (diminishing returns beyond 512)

**Important Rule:** `ef_construct` should be >= `m` (usually 2-10x higher)

**Recommended for Pixie:** 128-256
- Good graph quality for production
- Reasonable build time
- Works well with m=16-32

### Search-Time Parameter: `ef`

**What it controls:** Number of candidates evaluated during search (not index construction).

**Higher `ef` values:**
- More accurate results
- Slower searches
- Use for complex queries needing high precision

**Lower `ef` values:**
- Faster searches
- Slightly less accurate
- Use for real-time queries

**Recommended for Pixie:** 64-128
- Balance speed vs accuracy
- Adjust per query type if needed

---

## 3. Collection Setup

### Collection Structure

Collections in Qdrant are logical groups of vectors with shared configuration.

**For Pixie, consider:**
- Single collection with filtered searches (simpler)
- OR separate collections per user (better isolation)
- OR separate collections per data type (tasks vs events)

### Basic Collection Creation

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, HnswConfigDiff

client = QdrantClient(host="localhost", port=6333)

client.create_collection(
    collection_name="pixie_data",
    vectors_config=VectorParams(
        size=1536,  # text-embedding-3-small dimensions
        distance=Distance.COSINE  # Cosine similarity
    ),
    hnsw_config=HnswConfigDiff(
        m=16,  # Connections per node
        ef_construct=128,  # Construction search depth
        full_scan_threshold=10000  # Use brute force for small collections
    )
)
```

### Distance Metrics

**Cosine** - Measures angle between vectors
- Range: -1 to 1 (1 = identical, -1 = opposite)
- Best for: Text embeddings (direction matters more than magnitude)
- **Recommended for Pixie**

**Euclidean (L2)** - Measures straight-line distance
- Range: 0 to infinity (0 = identical)
- Best for: Image embeddings, spatial data

**Dot Product** - Combination of magnitude and direction
- Range: -infinity to infinity
- Best for: When vector magnitude has meaning

### Payload Indexing

Create indexes on frequently filtered fields for faster queries.

```python
from qdrant_client.models import PayloadSchemaType, TextIndexParams

# Index for filtering by user_id
client.create_payload_index(
    collection_name="pixie_data",
    field_name="user_id",
    field_schema=PayloadSchemaType.KEYWORD
)

# Index for filtering by data type
client.create_payload_index(
    collection_name="pixie_data",
    field_name="type",  # "task", "event", "note"
    field_schema=PayloadSchemaType.KEYWORD
)

# Index for timestamp-based filtering
client.create_payload_index(
    collection_name="pixie_data",
    field_name="timestamp",
    field_schema=PayloadSchemaType.INTEGER
)
```

**When to index:**
- Fields used in filters frequently (user_id, type, status)
- Fields with high cardinality (many unique values)
- NOT needed for full-text search on payloads

---

## 4. Performance Tuning

### Memory Optimization

**Vector Quantization** - Compress vectors to reduce memory usage.

**Scalar Quantization:**
```python
from qdrant_client.models import ScalarQuantization, ScalarType, QuantizationSearchParams

client.update_collection(
    collection_name="pixie_data",
    quantization_config=ScalarQuantization(
        scalar=ScalarType.INT8,  # 8-bit integers instead of 32-bit floats
        always_ram=True  # Keep quantized vectors in RAM
    )
)
```

**Benefits:**
- 4x memory reduction (32-bit float → 8-bit int)
- Faster search (smaller data to compare)
- Slight accuracy loss (usually <2%)

**Use when:** Memory is constrained or dataset >100K vectors

**Storage Configuration:**

```python
from qdrant_client.models import VectorParams

# In-memory (fastest, limited by RAM)
vectors_config=VectorParams(
    size=1536,
    distance=Distance.COSINE,
    on_disk=False  # Keep in RAM
)

# On-disk with caching (scalable, slower)
vectors_config=VectorParams(
    size=1536,
    distance=Distance.COSINE,
    on_disk=True  # Store on disk, cache frequently accessed
)
```

**Recommendation for Pixie:**
- Start with in-memory for <100K vectors
- Switch to on-disk when RAM becomes constrained
- Qdrant automatically caches hot vectors in RAM

### Index Optimization

**Bulk Upload Strategy:**

```python
# Disable HNSW during bulk upload
client.update_collection(
    collection_name="pixie_data",
    hnsw_config=HnswConfigDiff(m=0)  # Disable indexing
)

# Upload vectors in batches
# ... batch upload code ...

# Re-enable HNSW
client.update_collection(
    collection_name="pixie_data",
    hnsw_config=HnswConfigDiff(m=16, ef_construct=128)
)
```

**Benefits:**
- Faster bulk uploads (no real-time indexing overhead)
- Lower CPU/memory during ingestion
- Index built once after all data loaded

**Optimizers:**

Qdrant includes automatic optimizers:

**Vacuum Optimizer** - Reclaims space from deleted vectors
- Qdrant marks deletions, doesn't immediately reclaim space
- Vacuum runs periodically to clean up
- Prevents storage bloat

**Merge Optimizer** - Consolidates segments
- Qdrant stores vectors in segments
- Merge combines small segments into larger ones
- Improves search efficiency

Both run automatically, but can be triggered manually if needed.

### Search Optimization

**Adjust `ef` per query type:**

```python
# High-precision search (slower)
results = client.search(
    collection_name="pixie_data",
    query_vector=embedding,
    limit=5,
    search_params={"ef": 128}  # Higher ef = better accuracy
)

# Fast search (lower precision acceptable)
results = client.search(
    collection_name="pixie_data",
    query_vector=embedding,
    limit=5,
    search_params={"ef": 64}  # Lower ef = faster
)
```

**Filter before vector search:**

```python
# Efficient: filter first, then search
from qdrant_client.models import Filter, FieldCondition, MatchValue

results = client.search(
    collection_name="pixie_data",
    query_vector=embedding,
    query_filter=Filter(
        must=[
            FieldCondition(
                key="user_id",
                match=MatchValue(value="user_123")
            )
        ]
    ),
    limit=5
)
```

**Benefits:**
- Reduces search space dramatically
- Faster queries (fewer vectors to compare)
- Essential for  multi-tenant setups

---

## 5. Production Deployment

### Deployment Options

**Docker (Recommended for MVP):**
```bash
docker run -p 6333:6333 -v $(pwd)/qdrant_storage:/qdrant/storage qdrant/qdrant
```

**Qdrant Cloud:**
- Managed service, no infrastructure management
- Automatic scaling and backups
- Higher cost but less operational overhead

**Kubernetes:**
- Self-managed cluster
- Full control over scaling and configuration
- Requires DevOps expertise

### Monitoring Metrics

**Key Metrics to Track:**
- Search latency (p50, p95, p99)
- Index build time
- Memory usage (RAM, disk)
- Request throughput (queries per second)
- Collection size (number of vectors)

**Integration:**
- Qdrant supports Prometheus metrics export
- Use Grafana for visualization
- Set alerts on high latency or memory usage

### Backup and Recovery

**Snapshots:**
```python
# Create snapshot
snapshot_info = client.create_snapshot(collection_name="pixie_data")

# Download snapshot
client.download_snapshot(
    collection_name="pixie_data",
    snapshot_name=snapshot_info.name,
    output_path="./backups/"
)
```

**Recovery:**
```python
# Restore from snapshot
client.recover_snapshot(
    collection_name="pixie_data",
    location="./backups/snapshot_name.snapshot"
)
```

**Recommendation:**
- Daily snapshots for production
- Store snapshots off-server (S3, cloud storage)
- Test recovery process regularly

### Scaling Strategies

**Single Node (0-1M vectors):**
- Simplest setup
- Adequate for most MVP scenarios
- Vertical scaling (add RAM/CPU) when needed

**Horizontal Scaling (1M+ vectors):**
- Sharding: Split collection across multiple nodes
- Replication: Duplicate data for fault tolerance
- Load balancing: Distribute queries across nodes

**For Pixie MVP:**
- Start with single Docker instance
- 4-8 GB RAM should handle 100K-500K vectors
- Scale when reaching 70-80% capacity

---

## 6. Configuration Recommendations

### Small Dataset (<10K vectors)

```python
hnsw_config=HnswConfigDiff(
    m=16,
    ef_construct=100,
    full_scan_threshold=10000  # Use brute force below this
)
```

**Rationale:** Small datasets don't need complex indexing

### Medium Dataset (10K-100K vectors)

```python
hnsw_config=HnswConfigDiff(
    m=16,
    ef_construct=128,
    full_scan_threshold=10000
)
```

**Rationale:** Balanced performance for typical personal assistant usage

### Large Dataset (100K-1M vectors)

```python
hnsw_config=HnswConfigDiff(
    m=32,
    ef_construct=256,
    full_scan_threshold=10000
)

# Enable quantization
quantization_config=ScalarQuantization(
    scalar=ScalarType.INT8,
    always_ram=True
)
```

**Rationale:** Higher quality index + memory optimization needed

### Very Large Dataset (1M+ vectors)

```python
hnsw_config=HnswConfigDiff(
    m=64,
    ef_construct=400,
    full_scan_threshold=10000
)

# On-disk storage with quantization
vectors_config=VectorParams(
    size=1536,
    distance=Distance.COSINE,
    on_disk=True
)

quantization_config=ScalarQuantization(
    scalar=ScalarType.INT8,
    always_ram=True
)
```

**Rationale:** Maximum accuracy, scalable storage, memory efficiency

---

## 7. Best Practices Summary

**Index Configuration:**
- Start with m=16, ef_construct=128 for MVP
- Increase m and ef_construct as dataset grows
- Use quantization when memory becomes constrained

**Query Performance:**
- Create payload indexes on filtered fields
- Filter before vector search when possible
- Adjust `ef` based on accuracy requirements

**Data Management:**
- Use meaningful payload structures
- Index only frequently-filtered fields
- Regular snapshots for backup

**Monitoring:**
- Track search latency and memory usage
- Set alerts for degraded performance
- Monitor collection growth rate

**Scaling:**
- Start single-node, scale vertically first
- Consider horizontal scaling at 1M+ vectors
- Test performance under expected load before production

---

## Summary

**Qdrant provides:**
- Fast vector similarity search for RAG
- Flexible configuration via HNSW parameters
- Scalable architecture from MVP to production
- Good balance of performance and ease of use

**For Pixie MVP:**
- Single Docker instance sufficient
- m=16, ef_construct=128, ef=64 for searches
- Payload indexes on user_id and type
- Daily snapshots to S3/cloud storage
- Monitor latency and plan scaling at 70% capacity

With proper configuration, Qdrant can handle Pixie's RAG requirements efficiently while maintaining sub-100ms search times for excellent user experience.
