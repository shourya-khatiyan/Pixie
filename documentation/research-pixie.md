# Pixie



## Product Overview

Pixie is an AI-powered assistant leveraging large language models (LLMs) and vector databases to provide persistent, contextual memory for personal productivity. Unlike traditional CRUD applications, Pixie uses natural language processing (NLP) and semantic search to create a conversational interface over structured data.

**Core Architecture:** Next.js frontend + Node.js backend + Python AI service + PostgreSQL + Vector DB

---

## Technical Flow (Request Lifecycle)

### User Interaction Example:
```
User: "I need to fix the auth bug in the Avenue project by Friday"
Pixie: "Done! I've added that task. Due Friday, Jan 17"
```

### Backend Process (Step-by-Step):

**1. Message Reception (WebSocket)**
- User sends message via Socket.io WebSocket connection
- Real-time bidirectional communication (no HTTP polling)
- Message authenticated via JWT from Clerk
- Maintains persistent connection for instant updates

**2. Context Assembly**
- Fetch last 10-20 chat messages from PostgreSQL (conversation history)
- Query vector database for relevant memories (semantic search)
- Build context window for LLM (typically 3000-8000 tokens)

**3. LLM Intent Recognition**
- Send assembled context to LLM API (OpenAI GPT-4o or Anthropic Claude)
- LLM parses natural language and identifies:
  - **Intent**: Create task vs query vs update
  - **Entities**: Project name, deadline, priority
  - **Function to call**: create_task, fetch_events, search_memory, etc.

**AI/ML Concept - Function Calling:**
Modern LLMs can return structured JSON indicating which backend function to execute and with what parameters. This replaces regex parsing or intent classification models. The LLM essentially acts as a natural language to API translator.

**4. Tool Execution**
- Backend receives function call from LLM
- Executes corresponding service method
  - **create_task**: Insert into PostgreSQL tasks table
  - **fetch_tasks**: SELECT query with filters
  - **search_memory**: Vector similarity search in Qdrant
- Return execution result to LLM for response formulation

**5. Memory Storage (Embedding Generation)**
- Extract key text: task title + description
- Send to embedding model (OpenAI text-embedding-3-small)
- Receive 1536-dimensional vector representation
- Store vector in Qdrant with metadata (user_id, type, timestamp)

**AI/ML Concept - Embeddings:**
An embedding is a numerical vector representation of text where semantically similar phrases have similar vectors. "Fix auth bug" and "Repair authentication issue" will have vectors close in 1536-dimensional space, even with no shared keywords. This enables semantic search.

**6. Response Delivery**
- LLM generates natural language response
- Backend emits response via WebSocket
- Frontend updates chat UI + task list in real-time
- Total latency: 200-1500ms depending on query complexity

---

## RAG Architecture (Retrieval-Augmented Generation)

**What is RAG?**
RAG combines information retrieval (searching a database) with text generation (LLM response). Instead of relying solely on the LLM's training data, we augment its context with user-specific information retrieved in real-time.

### Our RAG Implementation:

**Traditional Approach (No RAG):**
```
User Query → LLM → Response
Problem: LLM has no knowledge of user's specific tasks/events
```

**Pixie's Approach (With RAG):**
```
User Query → Generate Embedding → Vector Search → Retrieved Context → 
LLM (with context) → Response
```

### Detailed RAG Flow:

**1. Indexing Phase (When User Creates Content)**
- User creates task: "Review Sprint 24 retrospective notes"
- Backend stores in PostgreSQL (structured data: id, title, due_date, etc.)
- Simultaneously:
  - Text sent to embedding API
  - Returns 1536-float vector
  - Vector stored in Qdrant with payload: {user_id, type: "task", task_id, created_at}
  
**2. Retrieval Phase (When User Queries)**
- User asks: "What was I supposed to review for the sprint?"
- Query embedded using same model (ensures vector space consistency)
- Vector search in Qdrant:
  - Cosine similarity search (finds nearest vectors)
  - Filtered by user_id (isolation)
  - Returns top 5 most relevant items with similarity scores (0.0-1.0)

**AI/ML Concept - Vector Similarity Search:**
Qdrant uses HNSW (Hierarchical Navigable Small World) algorithm for approximate nearest neighbor search. Think of it as an optimized spatial index in 1536 dimensions. Search time: O(log N) instead of O(N) for linear scan.

**3. Augmentation Phase**
- Retrieved results: ["Review Sprint 24 retrospective notes", similarity: 0.89]
- Fetch full task objects from PostgreSQL using task_ids
- Construct enriched context:
  ```
  User history: [last 10 messages]
  Relevant tasks: [
    {title: "Review Sprint 24 retrospective notes", status: "pending", due: "2026-01-17"}
  ]
  User query: "What was I supposed to review for the sprint?"
  ```

**4. Generation Phase**
- Send enriched context to LLM (Claude 3.5 Sonnet for complex queries)
- LLM generates response based on:
  - Its training (general knowledge)
  - Retrieved context (user-specific data)
  - Conversation history (continuity)
- Response: "You need to review the Sprint 24 retrospective notes, it's due this Friday."

### RAG vs Pure LLM:

| Aspect | Pure LLM | RAG (Our Approach) |
|--------|----------|-------------------|
| Knowledge cutoff | Fixed at training time | Real-time user data |
| Hallucinations | Higher risk | Lower (grounded in facts) |
| Personalization | None | Full user history |
| Cost | Lower | ~30% higher (embeddings) |
| Accuracy | Lower for specific info | Higher for factual recall |

---

## Why No Fine-Tuning (Yet)?

**What is Fine-Tuning?**
Fine-tuning takes a pre-trained LLM (like GPT-4) and continues training it on custom data to specialize its behavior. It adjusts the model's weights to better handle domain-specific tasks.

### Fine-Tuning Would Look Like:
- Collect 1000+ examples: User queries → Expected function calls
- Submit to OpenAI fine-tuning API
- Wait days for training completion
- Deploy custom model ID
- Result: Slightly better at parsing Pixie-specific requests

### Why We're NOT Fine-Tuning for MVP:

**1. Data Requirements**
- Need: 1000+ high-quality labeled examples
- Current: Zero real user data (pre-launch)
- Risk: Fine-tuning on synthetic data creates bad habits

**2. Base Models Are Already Excellent**
- GPT-4 and Claude have seen billions of examples of task management
- Function calling works out-of-the-box with good prompts
- Accuracy: ~95% intent recognition with zero-shot prompting
- Fine-tuning might improve to ~97% - not worth complexity

**3. Flexibility**
- Prompts can be changed instantly (git commit)
- Fine-tuned models require:
  - New training run: $0.5K-10K + 24-72 hours
  - Version management complexity
  - A/B testing becomes harder

**4. Model Improvements**
- Base models improve monthly (GPT-4.5, Claude 4, etc.)
- Fine-tuned model stays frozen at training checkpoint
- We'd need to re-fine-tune every model update

**5. Cost-Benefit Analysis**

| Approach | Initial Cost | Per-Query Cost | Latency | Maintenance |
|----------|--------------|----------------|---------|-------------|
| Base model + RAG | $0 | $0.02 | 500ms | Low (prompts) |
| Fine-tuned model | $10K | $0.01 | 400ms | High (retraining) |

At 10K users × 20 queries/day = 200K queries/day:
- Savings: $2K/month
- Break-even: 5 months
- But: Have to collect 6+ months of data first

### When We WOULD Fine-Tune:

**Phase 2 Criteria (6-12 months post-launch):**
- Have 100K+ real user interactions
- Identified specific failure patterns (e.g., project name extraction)
- LLM costs exceed $10K/month
- ROI calculation shows 3-month payback

**Use Case for Fine-Tuning:**
- Specialist model for entity extraction ("Avenue project" → {project: "Avenue"})
- Keep base model for complex reasoning
- Hybrid: Route simple queries to fine-tuned, complex to base
- Result: 40-50% cost reduction at scale

---

## System Architecture (Technical Detail)

### Frontend Stack

**Framework: Next.js 15 (App Router)**
- React 19 with React Server Components
- Server-side rendering for SEO + initial load performance
- API routes co-located with frontend (monorepo pattern)
- Streaming responses for real-time chat

**State Management:**
- React Context for auth state
- TanStack Query (React Query) for server state caching
- Optimistic updates for instant UI feedback
- WebSocket state separate from HTTP state

**Real-Time: Socket.io Client**
- Maintains persistent WebSocket connection
- Auto-reconnection with exponential backoff
- Binary protocol for efficiency
- Rooms for user-specific broadcasts

### Backend Stack

**Primary API: Node.js + Express**
- TypeScript for type safety
- RESTful endpoints for CRUD operations
- WebSocket server (Socket.io) for real-time
- Why Node: Best Socket.io support, unified JS stack, high concurrency

**AI Service: Python + FastAPI**
- Async-first (handles concurrent embedding requests)
- Why Python: Superior AI/ML library ecosystem (transformers, qdrant-client)
- Communicates with Node backend via HTTP
- Isolated service for AI-specific workloads

**ORM: Prisma**
- Schema-first approach with generated TypeScript client
- Automatic migrations
- Type-safe query builder
- Connection pooling

### Database Architecture

**PostgreSQL 16 (Primary Database)**
- Structured data: users, tasks, events, chat_messages
- ACID compliance for transactional integrity
- Indexes: userId + status, userId + dueAt
- Row-level security ready for multi-tenancy

**Qdrant (Vector Database)**
- Stores 1536-dim embeddings
- Collection: "user_memory"
- Filtering: user_id (mandatory), type (optional)
- Distance metric: Cosine similarity
- Hardware: In-memory for speed, disk for scale

**Redis (Cache + Session Store)**
- Session storage (JWT validation cache)
- API response caching (task lists, 60s TTL)
- Rate limiting counters
- Socket.io adapter for horizontal scaling

### AI/ML Components

**LLM Orchestration:**
- **Primary**: Anthropic Claude 3.5 Sonnet
  - Use for: Complex reasoning, long context (200K tokens)
  - Cost: $3/1M input tokens, $15/1M output
  
- **Secondary**: OpenAI GPT-4o
  - Use for: Quick responses, simple queries
  - Cost: $2.50/1M input tokens, $10/1M output

**Routing Logic:**
- Query complexity heuristic (length, keywords, history)
- Simple queries (>70%) → GPT-4o
- Complex queries (<30%) → Claude
- Fallback: If one fails, try the other

**Embedding Model: OpenAI text-embedding-3-small**
- Output: 1536 dimensions
- Cost: $0.02/1M tokens
- Latency: ~100ms per request
- Batch processing: Up to 100 texts per API call

**Function Calling (Tool Use):**
- Defined tools: create_task, list_tasks, create_event, search_memory
- LLM returns JSON with tool name + arguments
- Backend executes tool and returns result
- Optional: Multi-turn if LLM needs more info

---

## Current Capabilities (MVP Scope)

### Features Implemented:

**1. Natural Language Task Management**
- Parsing: Dates ("by Friday"), priorities ("urgent"), projects ("Avenue")
- CRUD: Create, read, update, complete, delete tasks
- **Technical Detail**: Uses LLM function calling to extract structured data from unstructured text
- Status tracking: pending, in_progress, completed, cancelled

**2. Calendar/Event Management**
- Time parsing: Relative ("tomorrow 3pm") and absolute ("Jan 17, 2026 15:00")
- Conflict detection: O(log N) query with date range overlap check
- **Technical Detail**: PostgreSQL btree index on startAt for fast range queries

**3. Semantic Memory Search**
- Vector similarity search with metadata filtering
- Hybrid retrieval: Dense vectors + structured filters
- **Technical Detail**: HNSW graph in Qdrant, ~10ms search time for 10K vectors
- Re-ranking: Optional cross-encoder for top 5 results

**4. Proactive Daily Summaries**
- Cron job: 7:00 AM user local time
- Query: today's events + pending tasks + overdue items
- LLM generates natural language summary
- Delivery: Email (SendGrid) or push notification

### Performance Metrics:

**Latency:**
- Simple query (cached): 50-150ms
- Complex query (RAG + LLM): 500-1500ms
- Embedding generation: 100-200ms
- Vector search: 5-20ms

**Throughput:**
- WebSocket connections: 10K concurrent
- API requests: 1000 req/sec per instance
- Database: 5K queries/sec (with indexes)

**Accuracy:**
- Intent recognition: ~95% (GPT-4 function calling)
- Date parsing: ~98% (LLM temporal reasoning)
- Semantic search recall@5: ~85% (embedding quality)

---

## Technical Roadmap

### Phase 2: Enhanced AI Features (3-6 months)

**1. Multi-Modal Input**
- Speech-to-text: Whisper API integration
- Image processing: GPT-4o vision for screenshots
- **Technical**: Binary file upload → S3 → API call → Extract text/data

**2. Advanced RAG**
- Hybrid search: Dense + sparse vectors (BM25)
- Re-ranking layer: Cross-encoder model for top-K
- Query rewriting: LLM expands ambiguous queries
- **Impact**: Recall improvement from 85% → 92%

**3. Contextual Embeddings**
- Chunk-level embeddings for long documents
- Hierarchical retrieval: Document → Chunk
- Late interaction: Query-document attention mechanism

**4. Email Integration**
- IMAP/SMTP connection
- LLM-based email parsing (extract tasks, events, action items)
- Automatic task creation with email reference link

### Phase 3: Optimization & Scale (6-12 months)

**1. Caching Strategy**
- Embedding cache: Store common phrase embeddings
- LLM response cache: Semantic similarity on queries
- **Impact**: 30-40% cost reduction

**2. Fine-Tuned Specialist Model**
- Task: Entity extraction + intent classification
- Training data: 100K real user queries
- Deployment: Fine-tuned GPT-4o-mini
- **Impact**: 50% cost reduction, 20% faster

**3. Self-Hosted Embeddings**
- Model: sentence-transformers/all-MiniLM-L6-v2
- Deploy: AWS Lambda or ECS
- Cost: $0.0001/1K vs $0.02/1K (200x cheaper)
- Trade-off: Slightly lower quality (0.80 vs 0.85 recall)

**4. Horizontal Scaling**
- Load balancer: AWS ALB with sticky sessions
- Stateless app servers: Socket.io Redis adapter
- Database: Read replicas for query distribution
- **Capacity**: 100K+ concurrent users

---

## Cost Structure & Economics

### Per-User Monthly Cost (at 10K users):

| Component | Technology | Monthly | Per User |
|-----------|-----------|---------|----------|
| **LLM API calls** | GPT-4o + Claude | $800 | $0.080 |
| **Embeddings** | OpenAI | $100 | $0.010 |
| **Database (SQL)** | AWS RDS PostgreSQL | $150 | $0.015 |
| **Vector DB** | Qdrant Cloud | $95 | $0.0095 |
| **Cache** | ElastiCache Redis | $15 | $0.0015 |
| **Compute** | ECS Fargate | $120 | $0.012 |
| **Monitoring** | Datadog + Sentry | $150 | $0.015 |
| **CDN + misc** | CloudFront, etc | $150 | $0.015 |
| **Total** | - | **$1,580** | **$0.16** |

**Pricing:** $15/month per user  
**Gross Margin:** 98.9%

### Optimization at Scale (50K users):

| Optimization | Savings | Implementation |
|-------------|---------|----------------|
| Embedding cache | 30% | Redis with 7-day TTL |
| Response cache | 20% | Semantic similarity matching |
| Fine-tuned routing | 50% | Specialist model for simple queries |
| Self-hosted embeddings | 90% | Sentence transformers on GPU |
| **Total LLM cost reduction** | **60-70%** | Phased over 6-12 months |

**Result at 50K users:**  
- Current cost: $0.16/user → Optimized: $0.06/user
- Annual savings: $60K → Funds 1 additional engineer

---

## Security & Privacy (Technical)

### Authentication Flow (Clerk)
- OAuth 2.0 / OIDC protocols
- JWT tokens (15-min expiry)
- Refresh tokens (30-day expiry, rotation)
- Multi-factor authentication (TOTP, SMS)

### Data Protection
- **In Transit**: TLS 1.3, WSS for WebSockets
- **At Rest**: AES-256 encryption (RDS, S3)
- **Secrets**: AWS Secrets Manager, rotation every 90 days

### AI Provider Privacy
- OpenAI: Zero data retention (enterprise agreement)
- Anthropic: No training on user data
- Embeddings: Stored locally, never re-sent

### Isolation
- Database: Row-level security (user_id filtering)
- Vector DB: Mandatory user_id filter on all searches
- Redis: Namespaced keys per user

---

## Risks & Mitigations

### Technical Risks:

**1. LLM Provider Outage**
- **Mitigation**: Multi-provider strategy (OpenAI + Anthropic)
- **Failover**: Automatic retry with alternate provider
- **Fallback**: Simplified responses from cached patterns

**2. Vector Database Performance Degradation**
- **Risk**: Search latency increases with dataset size
- **Solution**: Sharding by user_id, HNSW graph optimization
- **Monitoring**: p95 latency alerts at >50ms

**3. WebSocket Connection Limits**
- **Risk**: Socket.io memory usage per connection (~100KB)
- **Solution**: Horizontal scaling with Redis adapter
- **Capacity**: 10K connections per instance

**4. Embedding Drift**
- **Risk**: OpenAI updates embedding model, breaks similarity
- **Solution**: Version pin embedding model, controlled migrations
- **Testing**: Cosine similarity benchmarks on migration

### AI/ML Risks:

**1. Hallucinations**
- **Risk**: LLM fabricates tasks or events that don't exist
- **Mitigation**: RAG grounds responses in database facts
- **Validation**: Cross-check tool calls against actual DB state

**2. Prompt Injection**
- **Risk**: User tricks LLM into ignoring instructions
- **Mitigation**: System prompts separate from user input, output validation
- **Defense**: Structured outputs via function calling (not free-form text)

**3. Context Window Limits**
- **Risk**: Chat history + retrieved context exceeds token limit
- **Solution**: Sliding window (last 20 msgs), summarization for older context
- **Claude**: 200K token window (far exceeds current needs)

---

## Success Metrics

### Technical KPIs:

**Performance:**
- API latency p50: <100ms, p95: <300ms
- LLM response p50: <800ms, p95: <2000ms
- Vector search p95: <20ms
- Uptime: 99.9% (8.76 hours/year downtime budget)

**AI Quality:**
- Intent recognition accuracy: >95%
- Function call success rate: >98%
- Semantic search recall@5: >85%
- User correction rate: <5%

**Infrastructure:**
- WebSocket connection stability: <1% disconnects/hour
- Database query performance: All queries <50ms
- Cache hit rate: >60%

### Product KPIs:
- Daily Active Users (DAU) / Monthly Active Users (MAU): >40%
- Tasks created per DAU: >3
- Messages per session: >5
- Retention D7: >60%, D30: >40%

---

## Timeline & Milestones

### Development Timeline:

**Weeks 1-4: Core Infrastructure**
- Frontend: Next.js app with Socket.io client
- Backend: Express API + WebSocket server
- Databases: PostgreSQL + Qdrant setup
- Auth: Clerk integration

**Weeks 5-8: AI Integration**
- LLM orchestration layer (Python FastAPI)
- RAG pipeline implementation
- Function calling for task/event CRUD
- Embedding generation + vector storage

**Weeks 9-12: Feature Completion**
- Task management UI
- Calendar interface
- Memory search
- Daily summaries (cron jobs)

**Weeks 13-16: Polish & Deploy**
- Performance optimization
- Security hardening
- CI/CD pipeline (GitHub Actions)
- Production deployment (AWS)

**Weeks 17-20: Beta Testing**
- 50-100 beta users
- Bug fixes + UX refinements
- Load testing + scaling validation

**Week 21: Launch**

---

## Bottom Line (Technical Summary)

**Architecture Philosophy:**
- Leverage best-in-class external services (OpenAI, Anthropic, Clerk)
- Build thin orchestration layer with strong typing (TypeScript, Prisma)
- RAG over fine-tuning for flexibility and data requirements
- Optimize for developer velocity in MVP, cost in scale phase

**AI Strategy:**
- Multi-LLM approach for redundancy and cost optimization
- Embeddings + vector search for semantic memory
- Function calling for structured outputs
- Defer fine-tuning until proven ROI with real data

**Trade-offs Accepted:**
- Higher per-query cost ($0.02 vs $0.002 for traditional CRUD) for superior UX
- Dependency on external AI providers vs self-hosted (faster time to market)
- WebSocket complexity vs HTTP polling (better real-time experience)

**What Makes This Viable in 2026:**
- LLM function calling maturity (GPT-4, Claude)
- Affordable embeddings ($0.02/1M tokens)
- Vector databases as mature products (Qdrant, Pinecone)
- Developer tooling (Prisma, Next.js 15)

**Competitive Moat:**
- User data accumulation (more data = better RAG recall)
- Multi-model orchestration expertise
- Real-time WebSocket infrastructure
- Domain-specific prompt engineering


