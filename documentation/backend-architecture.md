# Backend Architecture: Node.js + Python Hybrid

## Recommended: Keep the Hybrid Architecture

### Database Migration Management

**Simple answer:** PostgreSQL migrations happen entirely in Node.js using Prisma. Python never touches PostgreSQL, so there's no migration coordination needed.

**How it works:**

- Node.js backend owns PostgreSQL (all CRUD operations for tasks, events, users)
- Python service only accesses Qdrant (vector database)
- When you need to change the database schema, you run `npx prisma migrate dev` in the Node.js backend
- Python service doesn't need to know about schema changes - it just receives HTTP requests and returns JSON responses

---

## Service Responsibilities

### Node.js Backend:

- PostgreSQL database operations (Prisma ORM)
- WebSocket connections (Socket.io)
- Authentication (Clerk)
- Business logic and API routes
- Calls Python service via HTTP when AI is needed

### Python FastAPI Service:

- LLM orchestration (Claude/GPT API calls)
- Embedding generation (OpenAI embeddings API)
- Vector search (Qdrant)
- Stateless - no database, no sessions, just pure AI processing

---

## Communication Flow

1. User sends message → Node.js receives via WebSocket
2. Node.js fetches context from PostgreSQL (chat history, tasks)
3. Node.js calls Python: `POST http://localhost:8000/llm/process` with message + context
4. Python processes with LLM, returns response + tool calls
5. Node.js executes tool calls (create task, etc.) in PostgreSQL
6. Node.js sends response back to user via WebSocket

---

## Document Ingestion Flow

**How user data becomes searchable in RAG:**

1. User creates task → Node.js saves to PostgreSQL
2. Node.js calls Python: `POST http://localhost:8000/api/ingest`
3. Python generates embedding (OpenAI API)
4. Python stores vector in Qdrant with user_id filter
5. Document now searchable for future RAG queries

**See [document-ingestion.md](file:///mnt/F/AI-ML/Pixie/documentation/document-ingestion.md) for complete implementation**

---

## Real-Time Response Streaming

**Challenge:** LLM generation takes 1-5 seconds - users expect real-time updates

**Solution:** Server-Sent Events (SSE) from Python to Node.js

### Streaming Flow

```
User sends message
    ↓
Node.js receives via WebSocket
    ↓
Node.js calls Python /api/generate-stream (SSE endpoint)
    ↓
Python streams LLM tokens as they generate
    ↓
Node.js forwards tokens to user via WebSocket (real-time typing)
    ↓
Final response includes tool calls for execution
    ↓
Node.js executes tools and sends confirmation
```

### Python SSE Endpoint

```python
from fastapi.responses import StreamingResponse

@app.post("/api/generate-stream")
async def generate_stream(request: GenerateRequest):
    async def event_generator():
        async for token in llm_client.stream(request.message):
            yield f"data: {json.dumps({'token': token})}\n\n"
        
        # Final response with tool calls
        yield f"data: {json.dumps({'done': True, 'tool_calls': [...]})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### Node.js SSE Consumer

```javascript
const EventSource = require('eventsource');

function streamLLMResponse(userId, message) {
  const es = new EventSource(`${PYTHON_AI_URL}/api/generate-stream`, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, message }),
    headers: { 'Content-Type': 'application/json' }
  });
  
  es.on('message', (event) => {
    const data = JSON.parse(event.data);
    
    if (data.token) {
      // Forward token to user via WebSocket
      io.to(userId).emit('llm-token', data.token);
    }
    
    if (data.done) {
      // Execute tool calls and send final response
      executeToo lCalls(data.tool_calls);
      es.close();
    }
  });
}
```

---

## Failure Scenarios

### Python Service Down

**Symptoms:**
- Connection refused or timeout on HTTP requests
- Node.js cannot reach Python service

**Handling:**

```javascript
async function callPythonWithFallback(endpoint, data) {
  const maxRetries = 3;
  
  for (let i = 0; i < maxRetries; i++) {
    try {
      const response = await fetch(`${PYTHON_AI_URL}${endpoint}`, {
        method: 'POST',
        body: JSON.stringify(data),
        timeout: 10000  // 10 second timeout
      });
      return await response.json();
    } catch (error) {
      logger.error(`Python service error (attempt ${i + 1})`, { error });
      
      if (i < maxRetries - 1) {
        await sleep(1000 * (i + 1));  // 1s, 2s, 3s backoff
        continue;
      }
      
      // All retries failed - return fallback
      return {
        response: "I'm temporarily unable to process AI requests. Please try again in a moment.",
        tool_calls: [],
        error: "service_unavailable"
      };
    }
  }
}
```

**User Experience:**
- Graceful degradation message
- User can still access manual task creation
- Requests queued for later processing (optional)

### Partial LLM Failure

**Scenario:** Primary LLM model fails, but others available

**Handling:**
- Python service automatically falls back to secondary model
- See [error-handling-retry.md](file:///mnt/F/AI-ML/Pixie/documentation/error-handling-retry.md) for details

**Node.js doesn't need special handling** - Python manages model fallback internally

### Database Connection Lost

**PostgreSQL Down:**
- Node.js handles directly (database layer)
- Return cached data or error message
- Not Python's concern

**Qdrant Down:**
- Python RAG search fails
- Fallback: LLM responds without context
- User gets response but may be less informed

```python
async def search_context(user_id, query):
    try:
        results = await qdrant_client.search(...)
        return results
    except QdrantException:
        logger.error("Qdrant unavailable", extra={"user_id": user_id})
        # Return empty context - LLM responds without RAG
        return []
```

### Health Check Implementation

**Node.js periodically checks Python health:**

```javascript
async function checkPythonHealth() {
  try {
    const response = await fetch(`${PYTHON_AI_URL}/health`, {
      timeout: 5000
    });
    
    if (response.ok) {
      pythonServiceHealthy = true;
      return true;
    }
  } catch (error) {
    pythonServiceHealthy = false;
    logger.error('Python service health check failed', { error });
  }
  
  return false;
}

// Check every 30 seconds
setInterval(checkPythonHealth, 30000);
```

---

## Why Not Full Python?

**Technical trade-offs:**

| Aspect | Node.js + Python | Full Python |
|--------|-----------------|-------------|
| WebSocket handling | Excellent (Socket.io) | Adequate (SocketIO or WebSockets) |
| Type safety | TypeScript + Pydantic | Pydantic only |
| Database ORM | Prisma (best DX, auto-migrations) | SQLAlchemy + Alembic (more manual) |
| AI libraries | Call Python service | Native |
| Scalability | Scale each service independently | Scale monolith |
| Complexity | Two services | One service |

**Bottom line:** The hybrid approach gives you best-in-class tools for each concern. Node.js excels at I/O-heavy operations (WebSockets, HTTP), Python excels at AI/ML. Keep them separate.

---

## Migration Workflow

```bash
# Only place you run migrations
cd pixie-backend
npx prisma migrate dev --name add_field

# Python service requires no changes
```

That's it. Python is a stateless microservice that doesn't participate in database management.
