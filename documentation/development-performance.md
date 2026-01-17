# Development & Performance Guide

## Overview

Combined guide covering caching strategy, performance benchmarks, database schema, and development workflow for the Pixie AI service.

---

## Caching Strategy

### Why Caching Matters

**Cost Reduction**
- Embedding API calls: $0.00001 per 1K tokens
- Repeated identical queries waste resources
- Cache hits eliminate redundant processing

**Performance Improvement**
- Cached embeddings: <10ms retrieval
- Fresh embeddings: 100-200ms API latency
- 10-20x speed improvement for common queries

### Embedding Cache

**Strategy**
- Cache text-to-embedding transformations
- Key: hash of input text
- Value: embedding vector + metadata
- TTL: 30 days (embeddings are stable)

**Implementation Approach**
```python
import hashlib
import redis

class EmbeddingCache:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.ttl = 30 * 24 * 60 * 60  # 30 days
    
    def get_embedding(self, text: str):
        cache_key = f"emb:{hashlib.sha256(text.encode()).hexdigest()}"
        cached = self.redis.get(cache_key)
        
        if cached:
            return json.loads(cached)
        
        # Generate fresh embedding
        embedding = openai_client.embeddings.create(text)
        self.redis.setex(cache_key, self.ttl, json.dumps(embedding))
        return embedding
```

**Cache Effectiveness**
- Common queries: 60-80% hit rate
- User-specific queries: 20-40% hit rate
- Overall savings: 50% reduction in embedding costs

### LLM Response Cache

**Challenges**
- Responses should be contextual and fresh
- Exact duplicate queries are rare
- Semantic similarity needed for matching

**Semantic Caching Approach**
- Store query embedding + response
- For new query, compute embedding similarity
- If similarity > 0.95, return cached response
- TTL: 1 hour (balance freshness vs. efficiency)

**Advanced Optimization Techniques**
- **Remove Semantic Noise**: Filter common words and boilerplate to improve precision
- **Similarity Threshold Tuning**: Start at 0.95, adjust based on false positive rate
- **LLM-based Reranking**: Add lightweight validation layer for top candidates
- **Metadata Filters**: Enhance cache with user_id, query type metadata
- **Adaptive TTLs**: Shorter TTL for time-sensitive queries, longer for static FAQs
- **Cache Pre-warming**: Preload common queries to avoid cold start

**Implementation Pattern**
```python
import numpy as np

class SemanticCache:
    def __init__(self, redis_client, similarity_threshold=0.95):
        self.redis = redis_client
        self.threshold = similarity_threshold
    
    async def get_cached_response(self, query_embedding, user_id):
        cache_key_pattern = f"sem_cache:{user_id}:*"
        keys = self.redis.keys(cache_key_pattern)
        
        best_match = None
        best_similarity = 0
        
        for key in keys:
            cached_data = json.loads(self.redis.get(key))
            cached_embedding = cached_data["embedding"]
            
            # Cosine similarity
            similarity = np.dot(query_embedding, cached_embedding) / \
                (np.linalg.norm(query_embedding) * np.linalg.norm(cached_embedding))
            
            if similarity > best_similarity and similarity >= self.threshold:
                best_similarity = similarity
                best_match = cached_data["response"]
        
        return best_match
```

**When to Use**
- FAQ-style queries with stable answers
- Read-only operations (task listing, event viewing)
- Informational queries without user-specific context

**When NOT to Use**
- Write operations (create, update, delete)
- Time-sensitive queries (today's schedule)
- User-specific data requiring current state

### Cache Infrastructure

**Redis Setup**
```python
import redis

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=6379,
    db=0,
    decode_responses=True,
    socket_timeout=5,
    socket_connect_timeout=5
)
```

**Memory Management**
- Max memory: 512MB for MVP
- Eviction policy: `allkeys-lru` (least recently used)
- Monitor memory usage with `INFO memory`

### Cache Invalidation

**TTL-Based Expiration**
- Embeddings: 30 days
- LLM responses: 1 hour
- User sessions: 24 hours

**Manual Invalidation**
- User data updates: invalidate user-specific caches
- Document uploads: invalidate related embedding caches
- System prompt changes: flush all LLM response caches

**Pattern**
```python
def invalidate_user_cache(user_id: str):
    pattern = f"cache:user:{user_id}:*"
    keys = redis_client.keys(pattern)
    if keys:
        redis_client.delete(*keys)
```

---

## Semantic Cache Complete Implementation

### Full Workflow

```python
import redis
import numpy as np
from typing import Optional, Dict

class SemanticCache:
    def __init__(self, redis_client, similarity_threshold=0.95):
        self.redis = redis_client
        self.threshold = similarity_threshold
    
    async def get(self, user_id: str, query_embedding: list) -> Optional[Dict]:
        """Check cache for semantically similar query"""
        # Get all cached queries for this user
        cache_keys = self.redis.keys(f"semantic_cache:{user_id}:*")
        
        if not cache_keys:
            return None
        
        # Find most similar cached query
        best_match = None
        best_similarity = 0
        
        for key in cache_keys:
            cached_data = self.redis.get(key)
            if not cached_data:
                continue
            
            cached = json.loads(cached_data)
            cached_embedding = cached["query_embedding"]
            
            # Calculate cosine similarity
            similarity = self._cosine_similarity(query_embedding, cached_embedding)
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = cached
        
        # Return if similarity above threshold
        if best_similarity >= self.threshold:
            logger.info(f"Cache hit", extra={
                "user_id": user_id,
                "similarity": best_similarity
            })
            return best_match["response"]
        
        return None
    
    async def set(self, user_id: str, query: str, query_embedding: list, 
                  response: Dict, ttl: int = 3600):
        """Store query-response pair in cache"""
        cache_key = f"semantic_cache:{user_id}:{hash(query)}"
        
        cache_data = {
            " query": query,
            "query_embedding": query_embedding,
            "response": response,
            "timestamp": datetime.now().isoformat()
        }
        
        self.redis.setex(
            cache_key,
            ttl,
            json.dumps(cache_data)
        )
        
        logger.info(f"Cache set", extra={"user_id": user_id, "ttl": ttl})
    
    @staticmethod
    def _cosine_similarity(a: list, b: list) -> float:
        """Calculate cosine similarity between two vectors"""
        a = np.array(a)
        b = np.array(b)
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
```

### Integration with LLM Processing

```python
redis_client = redis.Redis(host='localhost', port=6379, db=0)
semantic_cache = SemanticCache(redis_client, similarity_threshold=0.95)

async def process_query(user_id: str, query: str):
    """Process query with semantic caching"""
    # 1. Generate embedding
    query_embedding = await generate_embedding(query)
    
    # 2. Check semantic cache
    cached_response = await semantic_cache.get(user_id, query_embedding)
    
    if cached_response:
        # Cache hit - return immediately
        return {
            "response": cached_response["text"],
            "tool_calls": cached_response.get("tool_calls", []),
            "source": "cache"
        }
    
    # 3. Cache miss - generate LLM response
    response = await llm.generate(
        user_id=user_id,
        query=query,
        context=await fetch_context(user_id, query)
    )
    
    # 4. Cache for future
    await semantic_cache.set(
        user_id=user_id,
        query=query,
        query_embedding=query_embedding,
        response=response,
        ttl=3600  # 1 hour
    )
    
    return response
```

### Cache Monitoring

**Track Cache Performance:**
```python
from prometheus_client import Counter, Histogram

cache_hits = Counter('semantic_cache_hits_total', 'Total cache hits')
cache_misses = Counter('semantic_cache_misses_total', 'Total cache misses')
cache_latency = Histogram('semantic_cache_latency_seconds', 'Cache lookup latency')

class MonitoredSemanticCache(SemanticCache):
    async def get(self, user_id: str, query_embedding: list) -> Optional[Dict]:
        start = time.time()
        
        result = await super().get(user_id, query_embedding)
        
        # Record metrics
        cache_latency.observe(time.time() - start)
        
        if result:
            cache_hits.inc()
        else:
            cache_misses.inc()
        
        return result
```

**Calculate Cache Hit Rate:**
```python
async def get_cache_stats():
    """Get cache performance statistics"""
    hits = cache_hits._value.get()
    misses = cache_misses._value.get()
    total = hits + misses
    
    if total == 0:
        return {"hit_rate": 0, "total_requests": 0}
    
    hit_rate = hits / total
    
    return {
        "hit_rate": hit_rate,
        "total_requests": total,
        "hits": hits,
        "misses": misses,
        "avg_latency_ms": cache_latency._sum.get() / cache_latency._count.get() * 1000
    }

# Daily report
async def daily_cache_report():
    stats = await get_cache_stats()
    logger.info("Daily cache report", extra=stats)
    
    # Alert if hit rate too low
    if stats["hit_rate"] < 0.2:  # Below 20%
        await alert_ops("Cache hit rate below threshold", stats)
```

---

## Performance Benchmarks

### Latency Targets

**End-to-End Query Processing**
- p50 (median): < 1.5 seconds
- p95: < 3 seconds
- p99: < 5 seconds
- Timeout: 10 seconds

**Component Breakdown**
- Embedding generation: 100-200ms
- Vector search (Qdrant): 50-100ms
- LLM generation: 800-1500ms
- Total overhead: <100ms

### Throughput Targets

**Concurrent Users**
- MVP: 100 concurrent users
- Production: 500 concurrent users
- Peak capacity: 1000 concurrent users

**Requests Per Second**
- Sustained: 10 RPS per instance
- Burst: 50 RPS for 30 seconds
- Single instance limit: 20 RPS

### Load Testing Methodology

**Gradual Ramp-Up**
1. Start with 10 users
2. Add 10 users every 30 seconds
3. Continue until latency exceeds targets
4. Identify breaking point

**Test Scenarios**
- Simple query (no RAG): "What can you help me with?"
- RAG query: "What are my tasks for today?"
- Complex multi-turn: "Create task, then list all tasks"
- Heavy load: All users querying simultaneously

**Metrics to Monitor**
- Response time percentiles (p50, p95, p99)
- Error rate (should be <1%)
- Database connection pool utilization
- Qdrant query latency
- LLM API latency
- Memory usage per instance

### Performance Optimization Strategies

**Query Optimization**
- Limit Qdrant results to top 5 documents
- Use cached embeddings when possible
- Implement request debouncing (300ms)

**Model Selection**
- Simple queries: GPT-4o mini (faster, cheaper)
- Complex queries: GPT-4o (better accuracy)
- Route based on complexity estimation

**Connection Pooling**
- PostgreSQL: 10 connections per instance
- Qdrant: HTTP keep-alive enabled
- Redis: connection pool of 20

**Horizontal Scaling Thresholds**
- CPU > 70% for 5 minutes: add instance
- Memory > 80%: add instance
- Response time p95 > 3s: add instance

---

## Database Schema Details

### PostgreSQL Tables

**users** (managed by Node.js)
- Stores user authentication and profile data
- Python service performs READ-ONLY operations
- No direct user management from Python

**tasks**
```
id: UUID (primary key)
user_id: UUID (foreign key to users)
title: VARCHAR(500)
description: TEXT
due_date: TIMESTAMP
status: VARCHAR(50) ['pending', 'completed', 'cancelled']
priority: VARCHAR(20) ['low', 'medium', 'high']
created_at: TIMESTAMP
updated_at: TIMESTAMP
```

**events**
```
id: UUID (primary key)
user_id: UUID (foreign key to users)
title: VARCHAR(500)
description: TEXT
start_time: TIMESTAMP
end_time: TIMESTAMP
location: VARCHAR(500)
attendees: JSONB
created_at: TIMESTAMP
updated_at: TIMESTAMP
```

### Indexes

**Performance Indexes**
```sql
CREATE INDEX idx_tasks_user_id ON tasks(user_id);
CREATE INDEX idx_tasks_due_date ON tasks(due_date);
CREATE INDEX idx_events_user_id ON events(user_id);
CREATE INDEX idx_events_start_time ON events(start_time);
```

**Composite Indexes**
```sql
CREATE INDEX idx_tasks_user_status ON tasks(user_id, status);
CREATE INDEX idx_events_user_time ON events(user_id, start_time);
```

### Qdrant Collections

**user_documents**
```
Vector dimension: 1536 (text-embedding-3-small)
Distance metric: Cosine similarity
Index type: HNSW

Payload structure:
{
  "user_id": "uuid",
  "document_id": "uuid",
  "content": "original text",
  "metadata": {
    "source": "task|event|note",
    "created_at": "timestamp",
    "title": "document title"
  }
}
```

**HNSW Parameters**
```python
from qdrant_client.models import Distance, VectorParams, HnswConfigDiff

collection_config = {
    "vectors": VectorParams(
        size=1536,
        distance=Distance.COSINE
    ),
    "hnsw_config": HnswConfigDiff(
        m=16,  # connections per node (8-64 range)
        ef_construct=128,  # construction quality (STANDARD)
        max_indexing_threads=0  # auto-detect CPU cores
    )
}
```

**Parameter Tuning Guidelines**
- **m (connections)**: Higher = better accuracy, slower indexing
  - 16: Balanced for most use cases
  - 32-64: High-accuracy scenarios
  - 8: Fast indexing, acceptable accuracy

- **ef_construct**: Quality during index building
  - 100: Standard RAG applications
  - 200+: Critical accuracy requirements
  - 50: Fast prototyping

- **Search-time ef**: Adjust per query for speed/accuracy trade-off
  - Query parameter, not collection config
  - Higher = more accurate, slower

**Bulk Upload Optimization**
```python
# For initial data load, disable HNSW temporarily
collection_config_bulk = {
    "hnsw_config": HnswConfigDiff(m=0)  # Disable during bulk
}

# After upload complete, rebuild index
client.update_collection(
    collection_name="user_documents",
    hnsw_config=HnswConfigDiff(m=16, ef_construct=100)
)
```

### Database Access Patterns

**Python Service (Read-Only)**
```python
# Query tasks for user
SELECT * FROM tasks 
WHERE user_id = :user_id 
  AND status = 'pending'
ORDER BY due_date ASC
LIMIT 10;

# Query upcoming events
SELECT * FROM events
WHERE user_id = :user_id
  AND start_time >= NOW()
  AND start_time <= NOW() + INTERVAL '7 days'
ORDER BY start_time ASC;
```

**Connection Management**
```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import QueuePool

# Use asyncpg for high-performance async operations
engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/pixie",
    poolclass=QueuePool,
    pool_size=10,  # persistent connections
    max_overflow=20,  # additional connections when pool exhausted
    pool_pre_ping=True,  # verify connections before use
    pool_recycle=3600,  # recycle after 1 hour
    pool_timeout=30,  # wait 30s for connection
    echo=False  # disable SQL logging in production
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)
```

**FastAPI Dependency Pattern**
```python
from fastapi import Depends

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Usage in route handler
@app.get("/tasks")
async def get_tasks(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Task).where(Task.user_id == user_id)
    )
    return result.scalars().all()
```

**Lifespan Management**
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connection pool initialized automatically
    yield
    # Shutdown: properly close connections
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
```

### Migration Strategy

**Coordination with Node.js Team**
- All schema changes originate from Node.js backend
- Python team receives migration notifications
- Update Python models to match new schema
- No independent migrations from Python service

**Version Control**
- Node.js uses Prisma/TypeORM for migrations
- Python uses SQLAlchemy models (no migrations)
- Keep models in sync manually
- Document breaking changes in shared changelog

---

## Development Workflow

### Git Branching Strategy

**Main Branches**
- `main`: production-ready code
- `develop`: integration branch for features
- `staging`: pre-production testing

**Feature Branches**
- Format: `feature/description-of-feature`
- Example: `feature/add-rate-limiting`
- Create from: `develop`
- Merge to: `develop`

**Bugfix Branches**
- Format: `bugfix/issue-description`
- Example: `bugfix/fix-qdrant-timeout`
- Create from: `develop` or `main` (for hotfixes)

**Workflow**
1. Branch from `develop`
2. Implement feature with tests
3. Create pull request to `develop`
4. Code review required (1 approval minimum)
5. Merge to `develop` after approval
6. Periodic promotion: `develop` → `staging` → `main`

### Local Development Setup

**Prerequisites**
```bash
Python 3.11+
PostgreSQL 14+
Redis 7+
Qdrant (Docker)
```

**Initial Setup**
```bash
# Clone repository
git clone <repo-url>
cd pixie-ai-service

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # testing tools

# Copy environment template
cp .env.example .env
# Edit .env with your API keys

# Start Qdrant locally
docker run -p 6333:6333 qdrant/qdrant

# Start Redis locally
docker run -p 6379:6379 redis:7-alpine

# Run migrations (coordinated with Node.js team)
# Initialize Qdrant collection
python scripts/init_qdrant.py

# Run application
uvicorn main:app --reload --port 8000
```

### Code Organization

**Project Structure**
```
pixie-ai-service/
├── main.py                 # FastAPI app entry
├── config.py              # Configuration
├── models/                # Database models
│   ├── task.py
│   └── event.py
├── services/              # Business logic
│   ├── llm_service.py
│   ├── rag_service.py
│   └── search_service.py
├── api/                   # Route handlers
│   ├── query.py
│   └── health.py
├── utils/                 # Utilities
│   ├── validation.py
│   └── caching.py
├── tests/                 # Test suite
│   ├── unit/
│   └── integration/
└── scripts/               # Utility scripts
    └── init_qdrant.py
```

### Code Review Process

**Review Checklist**
- Tests pass locally and in CI
- Code coverage meets threshold (80%)
- No security vulnerabilities (run `pip-audit`)
- Follows PEP 8 style guide
- Docstrings for public functions
- Error handling implemented
- Logging added for important operations

**Review Focus Areas**
- Security: Input validation, authorization checks
- Performance: Database queries, caching usage
- Error handling: Graceful degradation
- Testing: Adequate coverage of new code
- Documentation: README updates if needed

### CI/CD Pipeline

**GitHub Actions Workflow**
```yaml
name: Test and Deploy

on:
  push:
    branches: [develop, staging, main]
  pull_request:
    branches: [develop]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.11', '3.12']
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Code quality checks
        run: |
          ruff check .
          ruff format --check .
      
      - name: Run tests
        run: pytest --cov --cov-report=xml
        timeout-minutes: 10
      
      - name: Security scan
        run: pip-audit --require-hashes
  
  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name == 'push'
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Build Docker image
        run: docker build -t pixie-ai:${{ github.sha }} .
      
      - name: Push to registry
        run: |
          echo "${{ secrets.GITHUB_TOKEN }}" | docker login ghcr.io -u ${{ github.actor }} --password-stdin
          docker tag pixie-ai:${{ github.sha }} ghcr.io/${{ github.repository }}:${{ github.sha }}
          docker push ghcr.io/${{ github.repository }}:${{ github.sha }}
```

**Best Practices**
- **Matrix Builds**: Test across Python 3.11 and 3.12
- **Dependency Caching**: Use `cache: 'pip'` to speed up workflow
- **Job Timeouts**: Prevent runaway jobs with `timeout-minutes`
- **Secrets Management**: Use GitHub Secrets for credentials
- **Least Privilege**: Grant minimum permissions to workflows
- **Reusable Workflows**: Create shared workflows for common tasks
- **Parallel Jobs**: Run independent jobs concurrently

**Deployment Stages**
- Develop → Automatic deploy to dev environment
- Staging → Manual approval, deploy to staging
- Main → Manual approval, deploy to production

### Documentation Standards

**Code Documentation**
```python
def process_query(user_id: str, query: str) -> dict:
    """
    Process user query through RAG pipeline and generate response.
    
    Args:
        user_id: Unique user identifier for data isolation
        query: Raw user query text (max 1000 chars)
    
    Returns:
        dict containing:
            - response: Generated text response
            - tool_calls: List of tool invocations
            - sources: Retrieved document references
    
    Raises:
        ValueError: If query exceeds length limit
        RateLimitError: If user exceeds request quota
    """
```

**README Updates**
- Update for new features
- Document environment variables
- Include setup instructions
- Maintain API documentation
- Link to relevant docs

### Environment Management

**Environment Variables**
```bash
# .env.example template
OPENAI_API_KEY=sk-...
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your-key
DATABASE_URL=postgresql://user:pass@localhost/pixie
REDIS_HOST=localhost
REDIS_PORT=6379
LOG_LEVEL=INFO
ENVIRONMENT=development
```

**Environment Separation**
- Development: Local services, verbose logging
- Staging: Cloud services, moderate logging
- Production: Managed services, minimal logging

---

## Performance Monitoring

### Real-Time Metrics

**Application Metrics**
- Request latency (p50, p95, p99)
- Requests per second
- Error rate by endpoint
- LLM token usage per user
- Cache hit rates

**Infrastructure Metrics**
- CPU utilization per instance
- Memory usage
- Database connection pool stats
- Qdrant query performance
- Redis memory usage

### Alerts

**Critical Alerts**
- Error rate > 5% for 2 minutes
- p95 latency > 5 seconds for 5 minutes
- Service unavailable for any endpoint
- Database connection pool exhausted

**Warning Alerts**
- Error rate > 2% for 5 minutes
- p95 latency > 3 seconds for 10 minutes
- Cache miss rate > 80%
- High memory usage (>85%)

---

## Optimization Checklist

### Caching
- [ ] Implement Redis for embedding cache
- [ ] Set up semantic LLM response cache
- [ ] Configure cache TTLs appropriately
- [ ] Monitor cache hit rates
- [ ] Implement cache invalidation strategy

### Performance
- [ ] Establish baseline performance benchmarks
- [ ] Set up load testing with Locust
- [ ] Configure connection pooling
- [ ] Implement horizontal scaling triggers
- [ ] Optimize Qdrant HNSW parameters

### Database
- [ ] Create necessary indexes
- [ ] Configure read-only access for Python
- [ ] Set up connection pooling
- [ ] Coordinate migration strategy with Node.js
- [ ] Document data access patterns

### Development
- [ ] Set up Git branching strategy
- [ ] Configure local development environment
- [ ] Implement CI/CD pipeline
- [ ] Establish code review process
- [ ] Document coding standards
