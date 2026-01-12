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
