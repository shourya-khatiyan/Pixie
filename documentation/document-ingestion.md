# Document Ingestion & Vectorization

## Overview

This guide explains how user data (tasks, events, notes) gets transformed into searchable vectors and stored in Qdrant for RAG (Retrieval Augmented Generation).

---

## Architecture Flow

```
User creates task in frontend
    ↓
Node.js backend saves to PostgreSQL
    ↓
Node.js calls Python /api/ingest endpoint
    ↓
Python generates embedding (OpenAI API)
    ↓
Python stores vector in Qdrant with metadata
    ↓
Vector is now searchable for future queries
```

---

## Ingestion API Specification

### Endpoint: POST /api/ingest

**Purpose:** Convert user document to embedding and store in Qdrant

**Request:**
```json
{
  "user_id": "uuid",
  "document_id": "uuid",
  "document_type": "task|event|note",
  "content": "Combined text for embedding",
  "metadata": {
    "title": "Document title",
    "created_at": "2026-01-17T10:30:00Z",
    "source": "task"
  }
}
```

**Response:**
```json
{
  "success": true,
  "document_id": "uuid",
  "vector_id": "qdrant-point-id",
  "tokens_used": 25
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "embedding_generation_failed",
  "message": "OpenAI API timeout",
  "retry_after": 5
}
```

---

## Implementation

### Python FastAPI Endpoint

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict
import openai
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

router = APIRouter()

class IngestionRequest(BaseModel):
    user_id: str
    document_id: str
    document_type: str  # task, event, note
    content: str
    metadata: Dict

@router.post("/api/ingest")
async def ingest_document(request: IngestionRequest):
    """
    Generate embedding and store in Qdrant
    """
    try:
        # 1. Generate embedding
        embedding_response = await openai.Embedding.acreate(
            model="text-embedding-3-small",
            input=request.content
        )
        embedding = embedding_response['data'][0]['embedding']
        tokens_used = embedding_response['usage']['total_tokens']
        
        # 2. Prepare Qdrant point
        point = PointStruct(
            id=request.document_id,
            vector=embedding,
            payload={
                "user_id": request.user_id,
                "document_id": request.document_id,
                "document_type": request.document_type,
                "content": request.content,
                "metadata": request.metadata
            }
        )
        
        # 3. Upsert to Qdrant (upsert = insert or update)
        qdrant_client.upsert(
            collection_name="user_documents",
            points=[point]
        )
        
        return {
            "success": True,
            "document_id": request.document_id,
            "vector_id": request.document_id,
            "tokens_used": tokens_used
        }
        
    except openai.error.Timeout as e:
        raise HTTPException(
            status_code=504,
            detail={"error": "embedding_timeout", "retry_after": 5}
        )
    except openai.error.RateLimitError as e:
        # Check Retry-After header
        retry_after = e.headers.get('Retry-After', 60)
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limit", "retry_after": retry_after}
        )
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", extra={
            "user_id": request.user_id,
            "document_id": request.document_id
        })
        raise HTTPException(
            status_code=500,
            detail={"error": "ingestion_failed", "message": str(e)}
        )
```

---

## Node.js Integration

### When to Trigger Ingestion

**Task Created:**
```javascript
// After saving to PostgreSQL
const task = await prisma.task.create({
  data: { title, description, userId }
});

// Ingest to Qdrant for RAG
await ingestDocument({
  user_id: userId,
  document_id: task.id,
  document_type: 'task',
  content: `${task.title}. ${task.description}`,
  metadata: {
    title: task.title,
    status: task.status,
    priority: task.priority,
    created_at: task.createdAt
  }
});
```

**Task Updated:**
```javascript
// After update in PostgreSQL
const updated = await prisma.task.update({
  where: { id: taskId },
  data: { title: newTitle, description: newDescription }
});

// Re-ingest (upsert will update existing vector)
await ingestDocument({...});
```

**Task Deleted:**
```javascript
// After deletion from PostgreSQL
await prisma.task.delete({ where: { id: taskId } });

// Delete from Qdrant
await deleteDocument(taskId);
```

### Ingestion Helper Function

```javascript
// services/qdrant-ingestion.js
const PYTHON_AI_URL = process.env.PYTHON_AI_URL || 'http://localhost:8000';

async function ingestDocument(doc) {
  try {
    const response = await fetch(`${PYTHON_AI_URL}/api/ingest`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${process.env.INTERNAL_API_KEY}`
      },
      body: JSON.stringify(doc),
      timeout: 10000  // 10 second timeout
    });
    
    if (!response.ok) {
      const error = await response.json();
      
      // Retry on rate limit
      if (response.status === 429) {
        const retryAfter = error.retry_after || 60;
        await sleep(retryAfter * 1000);
        return ingestDocument(doc);  // Retry once
      }
      
      // Log and continue on other errors (don't block user)
      logger.error('Ingestion failed', { error, document_id: doc.document_id });
      return { success: false, error };
    }
    
    return await response.json();
    
  } catch (error) {
    // Network error - queue for retry
    logger.error('Ingestion network error', { error, doc });
    await queueForRetry(doc);
    return { success: false, error: 'network_error' };
  }
}

async function deleteDocument(documentId) {
  try {
    const response = await fetch(`${PYTHON_AI_URL}/api/ingest/${documentId}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${process.env.INTERNAL_API_KEY}` }
    });
    
    return response.ok;
  } catch (error) {
    logger.error('Document deletion failed', { error, documentId });
    return false;
  }
}
```

---

## Error Handling & Retry Logic

### Retry Queue

**Use background job queue for failed ingestions:**

```javascript
// Using Bull queue or similar
const ingestionQueue = new Queue('ingestion', {
  redis: { host: 'localhost', port: 6379 }
});

async function queueForRetry(doc) {
  await ingestionQueue.add(doc, {
    attempts: 3,
    backoff: {
      type: 'exponential',
      delay: 2000  // Start with 2 seconds
    }
  });
}

// Worker processes queue
ingestionQueue.process(async (job) => {
  return await ingestDocument(job.data);
});
```

### Failure Scenarios

**OpenAI API Down:**
- Queue document for retry (up to 24 hours)
- User operation succeeds (task still created)
- Document eventually indexed when API recovers

**Qdrant Connection Failed:**
- Retry 3 times with exponential backoff
- If all fail, alert monitoring
- Queue for manual reprocessing

**Invalid Content:**
- Log error with document details
- Don't retry (permanent failure)
- Alert team to investigate

---

## Content Preparation

### Task Ingestion

```python
def prepare_task_content(task):
    """Combine task fields for embedding"""
    parts = [task.title]
    
    if task.description:
        parts.append(task.description)
    
    if task.project:
        parts.append(f"Project: {task.project}")
    
    if task.priority:
        parts.append(f"Priority: {task.priority}")
    
    return ". ".join(parts)
```

**Example:**
- Input: `{title: "Fix login bug", description: "Auth issue", project: "Avenue", priority: "high"}`
- Output: `"Fix login bug. Auth issue. Project: Avenue. Priority: high"`

### Event Ingestion

```python
def prepare_event_content(event):
    """Combine event fields for embedding"""
    parts = [event.title]
    
    if event.description:
        parts.append(event.description)
    
    if event.location:
        parts.append(f"Location: {event.location}")
    
    if event.start_time:
        parts.append(f"Time: {event.start_time.strftime('%Y-%m-%d %H:%M')}")
    
    return ". ".join(parts)
```

---

## Bulk Ingestion

### Initial Data Load

**For existing users migrating to Pixie:**

```python
@router.post("/api/ingest/bulk")
async def bulk_ingest(user_id: str, documents: List[Dict]):
    """
    Bulk ingest multiple documents
    Use for initial data migration
    """
    # Disable HNSW temporarily for faster indexing
    await qdrant_client.update_collection(
        collection_name="user_documents",
        hnsw_config={"m": 0}  # Disable
    )
    
    results = []
    batch_size = 100
    
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        
        # Generate embeddings in parallel
        embeddings = await asyncio.gather(*[
            generate_embedding(doc['content']) for doc in batch
        ])
        
        # Prepare points
        points = [
            PointStruct(
                id=doc['document_id'],
                vector=emb,
                payload={...}
            )
            for doc, emb in zip(batch, embeddings)
        ]
        
        # Batch upsert
        qdrant_client.upsert(
            collection_name="user_documents",
            points=points
        )
        
        results.extend([{"document_id": doc['document_id'], "success": True} for doc in batch])
    
    # Re-enable HNSW
    await qdrant_client.update_collection(
        collection_name="user_documents",
        hnsw_config={"m": 16, "ef_construct": 128}
    )
    
    return {"ingested": len(results), "results": results}
```

---

## Monitoring & Observability

### Metrics to Track

**Ingestion Metrics:**
- Ingestion success rate
- Average ingestion latency
- Embeddings generated per minute
- Queue depth (pending retries)
- Token usage for embeddings

**Implementation:**
```python
from prometheus_client import Counter, Histogram

ingestion_total = Counter('ingestion_total', 'Total ingestion attempts', ['status'])
ingestion_latency = Histogram('ingestion_latency_seconds', 'Ingestion latency')
embedding_tokens = Counter('embedding_tokens_total', 'Total tokens used')

@router.post("/api/ingest")
async def ingest_document(request: IngestionRequest):
    start = time.time()
    
    try:
        # ... ingestion logic ...
        ingestion_total.labels(status='success').inc()
        embedding_tokens.inc(tokens_used)
        return result
    except Exception as e:
        ingestion_total.labels(status='failed').inc()
        raise
    finally:
        ingestion_latency.observe(time.time() - start)
```

### Alerts

**Critical:**
- Ingestion success rate < 95% for 5 minutes
- Queue depth > 1000 documents
- Embedding API errors > 10/minute

**Warning:**
- Ingestion latency p95 > 2 seconds
- Queue depth > 500 documents

---

## Data Consistency

### Eventual Consistency

**Accepted Behavior:**
- Task created in PostgreSQL is immediately visible to user
- Vector indexed in Qdrant within 1-2 seconds
- RAG queries may not find brand new tasks (< 2s old)
- This is acceptable for MVP

### Orphaned Data Handling

**Orphaned Vectors:** Vector in Qdrant but task deleted from PostgreSQL

**Detection:**
```python
# Daily cleanup job
async def cleanup_orphaned_vectors():
    # Get all document IDs from Qdrant
    qdrant_ids = set(await get_all_qdrant_document_ids())
    
    # Get all task/event IDs from PostgreSQL
    postgres_ids = set(await get_all_postgres_ids())
    
    # Find orphans
    orphans = qdrant_ids - postgres_ids
    
    if orphans:
        logger.warning(f"Found {len(orphans)} orphaned vectors")
        # Delete from Qdrant
        await qdrant_client.delete(
            collection_name="user_documents",
            points_selector={"ids": list(orphans)}
        )
```

**Missing Vectors:** Task in PostgreSQL but no vector in Qdrant

**Re-ingestion:**
```python
# Weekly reconciliation
async def reindex_missing():
    postgres_ids = set(await get_all_postgres_ids())
    qdrant_ids = set(await get_all_qdrant_document_ids())
    
    missing = postgres_ids - qdrant_ids
    
    if missing:
        logger.warning(f"Re-indexing {len(missing)} missing documents")
        for doc_id in missing:
            doc = await fetch_document(doc_id)
            await ingest_document(doc)
```

---

## Best Practices

1. **Idempotency:** Use upsert (not insert) so re-indexing same document is safe
2. **Async:** Never block user operations waiting for ingestion
3. **Retry:** Queue failed ingestions for background retry
4. **Monitor:** Track success rates and alert on failures
5. **Cleanup:** Run daily job to remove orphaned vectors
6. **Reconcile:** Weekly check for missing vectors and re-index

---

## Security Considerations

**Authentication:**
- Require internal API key for ingestion endpoint
- Validate user_id ownership before ingestion
- Never allow ingesting documents for other users

**Input Validation:**
```python
def validate_ingestion_request(request: IngestionRequest):
    # Validate content length
    if len(request.content) > 10000:
        raise ValueError("Content too long (max 10KB)")
    
    # Validate document type
    if request.document_type not in ['task', 'event', 'note']:
        raise ValueError(f"Invalid document type: {request.document_type}")
    
    # Sanitize content
    request.content = sanitize_text(request.content)
```

**Rate Limiting:**
- Limit ingestion requests per user (e.g., 100/minute)
- Prevent abuse from malicious bulk uploads
- Use same rate limiting as query endpoints

---

## Summary

**Document ingestion is the bridge between PostgreSQL (source of truth) and Qdrant (RAG search index)**

**Key Points:**
- Node.js calls Python `/api/ingest` after creating/updating documents
- Python generates embeddings and stores in Qdrant
- Failures are queued for retry (non-blocking)
- Daily cleanup removes orphaned data
- Weekly reconciliation re-indexes missing documents

**MVP Implementation Time:** 1-2 days
