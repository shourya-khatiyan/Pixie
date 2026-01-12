# Pixie - Implementation Plan
## From Scratch to Production-Ready

---

## Overview

This document outlines a **comprehensive, step-by-step implementation plan** to build Pixie from initial setup to a production-ready AI secretary application. The plan is organized into logical phases, each building upon the previous one, with clear milestones and verification steps.

**Estimated Timeline**: 12-16 weeks for MVP, 20-24 weeks for production-ready v1

---

## Phase 1: Foundation & Setup (Week 1-2)

### 1.1 Project Initialization

#### **Frontend Setup**
```bash
# Initialize Next.js 15 project with TypeScript
npx create-next-app@latest pixie-frontend --typescript --app --tailwind
cd pixie-frontend
npm install socket.io-client @clerk/nextjs react-query zod
```

**Project Structure:**
```
pixie-frontend/
├── app/
│   ├── (auth)/
│   │   ├── sign-in/
│   │   └── sign-up/
│   ├── (dashboard)/
│   │   ├── chat/
│   │   ├── tasks/
│   │   └── calendar/
│   ├── api/
│   ├── layout.tsx
│   └── page.tsx
├── components/
│   ├── chat/
│   ├── tasks/
│   └── ui/
├── lib/
│   ├── api.ts
│   ├── socket.ts
│   └── utils.ts
└── styles/
```

#### **Backend Setup (Node.js)**
```bash
# Install CLI version 8.5.x from homebrew repository with git repository update interval adjustment and cache rebuilding enabled, update all first-level third-party Golang packages before applying security fixes to image formats
mkdir pixie-backend && cd pixie-backend
npm init -y
npm install express typescript @types/express @types/node
npm install socket.io cors helmet express-rate-limit
npm install prisma @prisma/client dotenv
npm install winston pino bullmq ioredis
npx tsc --init
```

**Project Structure:**
```
pixie-backend/
├── src/
│   ├── server.ts
│   ├── routes/
│   │   ├── auth.ts
│   │   ├── chat.ts
│   │   ├── tasks.ts
│   │   └── events.ts
│   ├── services/
│   │   ├── llm-service.ts
│   │   ├── memory-service.ts
│   │   ├── task-service.ts
│   │   └── event-service.ts
│   ├── websocket/
│   │   └── chat-handler.ts
│   ├── middleware/
│   │   ├── auth.ts
│   │   └── error.ts
│   └── utils/
├── prisma/
│   ├── schema.prisma
│   └── migrations/
├── tests/
└── package.json
```

#### **AI Service Setup (Python/FastAPI)**
```bash
mkdir pixie-ai-service && cd pixie-ai-service
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install fastapi uvicorn openai anthropic
pip install qdrant-client sentence-transformers
pip install pydantic python-dotenv
```

**Project Structure:**
```
pixie-ai-service/
├── app/
│   ├── main.py
│   ├── routers/
│   │   ├── llm.py
│   │   ├── embeddings.py
│   │   └── memory.py
│   ├── services/
│   │   ├── llm_orchestrator.py
│   │   ├── vector_service.py
│   │   └── embedding_service.py
│   └── models/
│       └── schemas.py
├── tests/
└── requirements.txt
```

### 1.2 Database Setup

#### **PostgreSQL Schema (Prisma)**
```prisma
// prisma/schema.prisma
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

generator client {
  provider = "prisma-client-js"
}

model User {
  id           String   @id @default(uuid())
  clerkId      String   @unique
  email        String   @unique
  firstName    String?
  lastName     String?
  createdAt    DateTime @default(now())
  updatedAt    DateTime @updatedAt
  
  tasks        Task[]
  events       Event[]
  memories     Memory[]
  chatMessages ChatMessage[]
}

model Task {
  id          String    @id @default(uuid())
  userId      String
  user        User      @relation(fields: [userId], references: [id], onDelete: Cascade)
  
  title       String
  description String?
  project     String?
  status      TaskStatus @default(PENDING)
  priority    Priority?
  dueAt       DateTime?
  completedAt DateTime?
  
  createdAt   DateTime  @default(now())
  updatedAt   DateTime  @updatedAt
  
  @@index([userId, status])
  @@index([userId, dueAt])
}

model Event {
  id          String    @id @default(uuid())
  userId      String
  user        User      @relation(fields: [userId], references: [id], onDelete: Cascade)
  
  title       String
  description String?
  location    String?
  startAt     DateTime
  endAt       DateTime
  isAllDay    Boolean   @default(false)
  recurrence  String?   // RRULE format
  
  createdAt   DateTime  @default(now())
  updatedAt   DateTime  @updatedAt
  
  @@index([userId, startAt])
}

model Memory {
  id          String   @id @default(uuid())
  userId      String
  user        User     @relation(fields: [userId], references: [id], onDelete: Cascade)
  
  content     String
  type        MemoryType
  metadata    Json?
  vectorId    String   @unique  // References Qdrant vector ID
  
  createdAt   DateTime @default(now())
  
  @@index([userId, type])
}

model ChatMessage {
  id        String   @id @default(uuid())
  userId    String
  user      User     @relation(fields: [userId], references: [id], onDelete: Cascade)
  
  role      MessageRole
  content   String
  metadata  Json?
  
  createdAt DateTime @default(now())
  
  @@index([userId, createdAt])
}

enum TaskStatus {
  PENDING
  IN_PROGRESS
  COMPLETED
  CANCELLED
}

enum Priority {
  LOW
  MEDIUM
  HIGH
  URGENT
}

enum MemoryType {
  TASK
  EVENT
  NOTE
  CONVERSATION
}

enum MessageRole {
  USER
  ASSISTANT
  SYSTEM
}
```

**Initialize Database:**
```bash
cd pixie-backend
npx prisma migrate dev --name init
npx prisma generate
```

#### **Vector Database Setup (Qdrant)**
```bash
# Using Docker for local development
docker run -p 6333:6333 qdrant/qdrant

# Or use Qdrant Cloud for production
```

**Collection Creation:**
```python
# In pixie-ai-service/app/services/vector_service.py
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient(url="http://localhost:6333")

# Create collection for user memories
client.create_collection(
    collection_name="user_memory",
    vectors_config=VectorParams(
        size=1536,  # OpenAI ada-002 embedding size
        distance=Distance.COSINE
    )
)
```

### 1.3 Environment Configuration

**Frontend (.env.local):**
```env
NEXT_PUBLIC_API_URL=http://localhost:3001
NEXT_PUBLIC_WS_URL=http://localhost:3001
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
```

**Backend (.env):**
```env
NODE_ENV=development
PORT=3001
DATABASE_URL=postgresql://user:password@localhost:5432/pixie
REDIS_URL=redis://localhost:6379
CLERK_SECRET_KEY=sk_test_...
AI_SERVICE_URL=http://localhost:8000
```

**AI Service (.env):**
```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=  # Optional for cloud
```

### 1.4 Verification

- [ ] All projects initialize without errors
- [ ] TypeScript compiles successfully
- [ ] Database migrations run successfully
- [ ] Can connect to PostgreSQL and Redis
- [ ] Qdrant collection created successfully
- [ ] Environment variables loaded correctly

---

## Phase 2: Core Backend Implementation (Week 3-5)

### 2.1 Authentication Integration (Clerk)

**Middleware Setup:**
```typescript
// src/middleware/auth.ts
import { ClerkExpressRequireAuth } from '@clerk/clerk-sdk-node';

export const requireAuth = ClerkExpressRequireAuth();

export const getUserId = (req: any): string => {
  return req.auth.userId;
};
```

**User Sync:**
```typescript
// src/services/user-service.ts
import { prisma } from '../lib/prisma';
import { clerkClient } from '@clerk/clerk-sdk-node';

export async function syncUserFromClerk(clerkId: string) {
  const clerkUser = await clerkClient.users.getUser(clerkId);
  
  return await prisma.user.upsert({
    where: { clerkId },
    update: {
      email: clerkUser.emailAddresses[0].emailAddress,
      firstName: clerkUser.firstName,
      lastName: clerkUser.lastName,
    },
    create: {
      clerkId,
      email: clerkUser.emailAddresses[0].emailAddress,
      firstName: clerkUser.firstName,
      lastName: clerkUser.lastName,
    },
  });
}
```

### 2.2 Task Service Implementation

```typescript
// src/services/task-service.ts
import { prisma } from '../lib/prisma';

export class TaskService {
  async createTask(userId: string, data: CreateTaskInput) {
    const task = await prisma.task.create({
      data: {
        userId,
        title: data.title,
        description: data.description,
        project: data.project,
        priority: data.priority,
        dueAt: data.dueAt,
        status: 'PENDING',
      },
    });
    
    // Generate embedding for semantic search
    await this.generateTaskEmbedding(task);
    
    return task;
  }
  
  async getTasks(userId: string, filters?: TaskFilters) {
    return await prisma.task.findMany({
      where: {
        userId,
        status: filters?.status,
        dueAt: filters?.dueBefore ? {
          lte: filters.dueBefore
        } : undefined,
      },
      orderBy: {
        dueAt: 'asc',
      },
    });
  }
  
  private async generateTaskEmbedding(task: Task) {
    const text = `${task.title} ${task.description || ''}`.trim();
    const response = await fetch(`${process.env.AI_SERVICE_URL}/embeddings/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, metadata: { type: 'task', id: task.id } }),
    });
    
    return response.json();
  }
}
```

### 2.3 Event Service Implementation

```typescript
// src/services/event-service.ts
export class EventService {
  async createEvent(userId: string, data: CreateEventInput) {
    // Check for conflicts
    const conflicts = await this.checkConflicts(userId, data.startAt, data.endAt);
    
    const event = await prisma.event.create({
      data: {
        userId,
        title: data.title,
        description: data.description,
        location: data.location,
        startAt: data.startAt,
        endAt: data.endAt,
        isAllDay: data.isAllDay || false,
      },
    });
    
    await this.generateEventEmbedding(event);
    return { event, conflicts };
  }
  
  async getEventsInRange(userId: string, start: Date, end: Date) {
    return await prisma.event.findMany({
      where: {
        userId,
        startAt: { lte: end },
        endAt: { gte: start },
      },
      orderBy: {
        startAt: 'asc',
      },
    });
  }
  
  private async checkConflicts(userId: string, start: Date, end: Date) {
    return await prisma.event.findMany({
      where: {
        userId,
        OR: [
          {
            AND: [
              { startAt: { lte: start } },
              { endAt: { gte: start } },
            ],
          },
          {
            AND: [
              { startAt: { lte: end } },
              { endAt: { gte: end } },
            ],
          },
        ],
      },
    });
  }
}
```

### 2.4 Verification

- [ ] Task CRUD operations work correctly
- [ ] Event CRUD operations work correctly
- [ ] Conflict detection works for events
- [ ] Embeddings generated for tasks/events
- [ ] Authentication middleware blocks unauthorized requests
- [ ] Database queries optimized with proper indexes

---

## Phase 3: AI/LLM Integration (Week 6-8)

### 3.1 LLM Orchestration Service

```python
# app/services/llm_orchestrator.py
from anthropic import Anthropic
from openai import OpenAI
from typing import List, Dict, Any
import json

class LLMOrchestrator:
    def __init__(self):
        self.anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
    async def process_message(
        self,
        message: str,
        history: List[Dict[str, str]],
        user_id: str,
        tools: List[Dict]
    ) -> Dict[str, Any]:
        # Determine complexity and route to appropriate model
        complexity = self._estimate_complexity(message)
        
        if complexity > 7:
            return await self._call_claude(message, history, tools)
        else:
            return await self._call_gpt(message, history, tools)
    
    async def _call_claude(self, message: str, history: List, tools: List):
        messages = self._format_history(history)
        messages.append({"role": "user", "content": message})
        
        response = self.anthropic.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=messages,
            tools=tools,
        )
        
        return self._parse_response(response)
    
    async def _call_gpt(self, message: str, history: List, tools: List):
        messages = self._format_history(history)
        messages.append({"role": "user", "content": message})
        
        response = self.openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        
        return self._parse_response(response)
    
    def _estimate_complexity(self, message: str) -> int:
        # Simple heuristic: longer messages, keywords, etc.
        score = len(message) / 20
        keywords = ["code", "debug", "analyze", "complex", "detailed"]
        score += sum(3 for kw in keywords if kw in message.lower())
        return min(int(score), 10)
    
    def _parse_response(self, response) -> Dict:
        # Parse response and extract tool calls
        tool_calls = []
        content = ""
        
        # Handle both Claude and GPT response formats
        # ... parsing logic
        
        return {
            "content": content,
            "tool_calls": tool_calls,
            "model_used": response.model
        }
```

### 3.2 Function/Tool Definitions

```python
# app/models/tools.py
AVAILABLE_TOOLS = [
    {
        "name": "create_task",
        "description": "Create a new task for the user",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title"},
                "description": {"type": "string", "description": "Detailed description"},
                "project": {"type": "string", "description": "Project name"},
                "priority": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "URGENT"]},
                "due_date": {"type": "string", "format": "date-time"}
            },
            "required": ["title"]
        }
    },
    {
        "name": "list_tasks",
        "description": "Retrieve user's tasks with optional filters",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["PENDING", "IN_PROGRESS", "COMPLETED"]},
                "due_before": {"type": "string", "format": "date-time"},
                "project": {"type": "string"}
            }
        }
    },
    {
        "name": "create_event",
        "description": "Create a new calendar event",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start_time": {"type": "string", "format": "date-time"},
                "end_time": {"type": "string", "format": "date-time"},
                "location": {"type": "string"}
            },
            "required": ["title", "start_time", "end_time"]
        }
    },
    {
        "name": "search_memory",
        "description": "Semantic search through user's historical data",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 5}
            },
            "required": ["query"]
        }
    }
]
```

### 3.3 Vector/Memory Service

```python
# app/services/vector_service.py
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer

class VectorService:
    def __init__(self):
        self.client = QdrantClient(url=os.getenv("QDRANT_URL"))
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')  # Lightweight model
        
    async def upsert_memory(
        self,
        user_id: str,
        content: str,
        memory_type: str,
        metadata: Dict = None
    ) -> str:
        # Generate embedding
        vector = self.encoder.encode(content).tolist()
        
        # Create unique ID
        memory_id = str(uuid.uuid4())
        
        # Upsert to Qdrant
        self.client.upsert(
            collection_name="user_memory",
            points=[
                PointStruct(
                    id=memory_id,
                    vector=vector,
                    payload={
                        "user_id": user_id,
                        "content": content,
                        "type": memory_type,
                        "created_at": datetime.now().isoformat(),
                        **(metadata or {})
                    }
                )
            ]
        )
        
        return memory_id
    
    async def search_memory(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
        memory_type: str = None
    ) -> List[Dict]:
        # Generate query embedding
        query_vector = self.encoder.encode(query).tolist()
        
        # Build filter
        filter_conditions = [
            FieldCondition(key="user_id", match=MatchValue(value=user_id))
        ]
        if memory_type:
            filter_conditions.append(
                FieldCondition(key="type", match=MatchValue(value=memory_type))
            )
        
        # Search
        results = self.client.search(
            collection_name="user_memory",
            query_vector=query_vector,
            query_filter=Filter(must=filter_conditions),
            limit=limit,
            with_payload=True
        )
        
        return [
            {
                "id": hit.id,
                "content": hit.payload["content"],
                "type": hit.payload["type"],
                "score": hit.score,
                "metadata": hit.payload
            }
            for hit in results
        ]
```

### 3.4 Backend Integration with AI Service

```typescript
// src/services/llm-service.ts
export class LLMService {
  private aiServiceUrl = process.env.AI_SERVICE_URL;
  
  async processMessage(input: ProcessMessageInput) {
    const response = await fetch(`${this.aiServiceUrl}/llm/process`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: input.message,
        history: input.history,
        user_id: input.userId,
        tools: this.getAvailableTools(),
      }),
    });
    
    const data = await response.json();
    
    // Execute tool calls
    if (data.tool_calls && data.tool_calls.length > 0) {
      const toolResults = await this.executeTools(data.tool_calls, input.userId);
      data.tool_results = toolResults;
    }
    
    return data;
  }
  
  private async executeTools(toolCalls: ToolCall[], userId: string) {
    const results = [];
    
    for (const tool of toolCalls) {
      switch (tool.name) {
        case 'create_task':
          const task = await new TaskService().createTask(userId, tool.args);
          results.push({ tool: 'create_task', result: task });
          break;
          
        case 'list_tasks':
          const tasks = await new TaskService().getTasks(userId, tool.args);
          results.push({ tool: 'list_tasks', result: tasks });
          break;
          
        case 'create_event':
          const event = await new EventService().createEvent(userId, tool.args);
          results.push({ tool: 'create_event', result: event });
          break;
          
        case 'search_memory':
          const memories = await this.searchMemory(userId, tool.args.query);
          results.push({ tool: 'search_memory', result: memories });
          break;
      }
    }
    
    return results;
  }
}
```

### 3.5 Verification

- [ ] LLM orchestrator routes queries correctly
- [ ] Both Claude and GPT integrations work
- [ ] Function calling executes correctly for all tools
- [ ] Vector embeddings generated and stored in Qdrant
- [ ] Semantic search returns relevant results
- [ ] Cost tracking implemented for LLM API calls
- [ ] Error handling for LLM API failures

---

## Phase 4: WebSocket & Real-Time Features (Week 9-10)

### 4.1 Socket.io Server Setup

```typescript
// src/server.ts
import express from 'express';
import { createServer } from 'http';
import { Server } from 'socket.io';
import { createAdapter } from '@socket.io/redis-adapter';
import { createClient } from 'redis';

const app = express();
const httpServer = createServer(app);
const io = new Server(httpServer, {
  cors: {
    origin: process.env.FRONTEND_URL,
    credentials: true
  }
});

// Redis adapter for horizontal scaling
const pubClient = createClient({ url: process.env.REDIS_URL });
const subClient = pubClient.duplicate();

Promise.all([pubClient.connect(), subClient.connect()]).then(() => {
  io.adapter(createAdapter(pubClient, subClient));
});

// Authentication middleware
io.use(async (socket, next) => {
  const token = socket.handshake.auth.token;
  try {
    const decoded = await verifyClerkToken(token);
    socket.data.userId = decoded.userId;
    next();
  } catch (err) {
    next(new Error('Authentication failed'));
  }
});

io.on('connection', (socket) => {
  const userId = socket.data.userId;
  console.log(`User connected: ${userId}`);
  
  // Join user's personal room
  socket.join(`user:${userId}`);
  
  // Handle chat messages
  socket.on('chat:message', async (data) => {
    await handleChatMessage(socket, data);
  });
  
  socket.on('disconnect', () => {
    console.log(`User disconnected: ${userId}`);
  });
});

httpServer.listen(3001, () => {
  console.log('Server running on port 3001');
});
```

### 4.2 Chat Message Handler

```typescript
// src/websocket/chat-handler.ts
import { Socket } from 'socket.io';
import { LLMService } from '../services/llm-service';
import { prisma } from '../lib/prisma';

export async function handleChatMessage(socket: Socket, data: { message: string }) {
  const userId = socket.data.userId;
  
  try {
    // Store user message
    await prisma.chatMessage.create({
      data: {
        userId,
        role: 'USER',
        content: data.message,
      },
    });
    
    // Get recent history
    const history = await prisma.chatMessage.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' },
      take: 20,
    });
    
    // Process with LLM
    const llmService = new LLMService();
    const response = await llmService.processMessage({
      message: data.message,
      history: history.reverse().map(m => ({
        role: m.role.toLowerCase(),
        content: m.content
      })),
      userId,
    });
    
    // Store assistant response
    await prisma.chatMessage.create({
      data: {
        userId,
        role: 'ASSISTANT',
        content: response.content,
        metadata: {
          model: response.model_used,
          tool_calls: response.tool_results
        }
      },
    });
    
    // Send response back
    socket.emit('chat:response', {
      content: response.content,
      tool_results: response.tool_results,
    });
    
  } catch (error) {
    console.error('Chat error:', error);
    socket.emit('chat:error', {
      message: 'Failed to process message'
    });
  }
}
```

### 4.3 Verification

- [ ] WebSocket connections established successfully
- [ ] Authentication middleware blocks unauthorized connections
- [ ] Chat messages sent and received in real-time
- [ ] Redis adapter enables message broadcasting across instances
- [ ] Reconnection works automatically
- [ ] Error handling for disconnections

---

## Phase 5: Frontend Implementation (Week 11-13)

### 5.1 Authentication Setup (Clerk)

```typescript
// app/layout.tsx
import { ClerkProvider } from '@clerk/nextjs';

export default function RootLayout({ children }: { children: React.Node }) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body>{children}</body>
      </html>
    </ClerkProvider>
  );
}
```

```typescript
// app/(auth)/sign-in/page.tsx
import { SignIn } from '@clerk/nextjs';

export default function SignInPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <SignIn afterSignInUrl="/chat" />
    </div>
  );
}
```

### 5.2 Chat Interface

```typescript
// components/chat/ChatInterface.tsx
'use client';

import { useState, useEffect } from 'react';
import { useSocket } from '@/lib/socket';

export function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const { socket, isConnected } = useSocket();
  
  useEffect(() => {
    socket?.on('chat:response', (response) => {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: response.content,
        toolResults: response.tool_results
      }]);
    });
    
    return () => {
      socket?.off('chat:response');
    };
  }, [socket]);
  
  const sendMessage = () => {
    if (!input.trim()) return;
    
    setMessages(prev => [...prev, {
      role: 'user',
      content: input
    }]);
    
    socket?.emit('chat:message', { message: input });
    setInput('');
  };
  
  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4">
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}
      </div>
      
      <div className="border-t p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
            className="flex-1 px-4 py-2 border rounded-lg"
            placeholder="Ask me anything..."
          />
          <button
            onClick={sendMessage}
            disabled={!isConnected}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
```

### 5.3 Task Dashboard

```typescript
// app/(dashboard)/tasks/page.tsx
'use client';

import { useQuery, useMutation, useQueryClient } from 'react-query';
import { api } from '@/lib/api';

export default function TasksPage() {
  const queryClient = useQueryClient();
  
  const { data: tasks, isLoading } = useQuery('tasks', () =>
    api.get('/tasks').then(res => res.data)
  );
  
  const createTask = useMutation(
    (data: CreateTaskInput) => api.post('/tasks', data),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('tasks');
      }
    }
  );
  
  return (
    <div className="container mx-auto p-8">
      <h1 className="text-3xl font-bold mb-6">Tasks</h1>
      
      <div className="grid gap-4">
        {tasks?.map(task => (
          <TaskCard key={task.id} task={task} />
        ))}
      </div>
    </div>
  );
}
```

### 5.4 Verification

- [ ] User can sign in/sign up with Clerk
- [ ] Chat interface sends and receives messages
- [ ] Task list displays correctly
- [ ] Real-time updates work (new tasks appear immediately)
- [ ] Responsive design works on mobile
- [ ] Loading states and error handling implemented

---

## Phase 6: Production Deployment (Week 14-16)

### 6.1 Infrastructure Setup (AWS)

**Terraform Configuration:**
```hcl
# infrastructure/main.tf
provider "aws" {
  region = "us-east-1"
}

# VPC and Networking
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
  enable_dns_hostnames = true
  
  tags = {
    Name = "pixie-vpc"
  }
}

# RDS PostgreSQL
resource "aws_db_instance" "postgres" {
  identifier = "pixie-db"
  engine = "postgres"
  engine_version = "16.1"
  instance_class = "db.t4g.medium"
  allocated_storage = 100
  
  db_name = "pixie"
  username = "pixie_admin"
  password = var.db_password
  
  multi_az = true
  backup_retention_period = 7
  
  vpc_security_group_ids = [aws_security_group.db.id]
  db_subnet_group_name = aws_db_subnet_group.main.name
}

# ElastiCache Redis
resource "aws_elasticache_cluster" "redis" {
  cluster_id = "pixie-redis"
  engine = "redis"
  node_type = "cache.t4g.micro"
  num_cache_nodes = 1
  port = 6379
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "pixie-cluster"
}

# ... more resources
```

**Docker Configuration:**
```dockerfile
# Backend Dockerfile
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules

EXPOSE 3001
CMD ["node", "dist/server.js"]
```

```dockerfile
# AI Service Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 6.2 CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '20'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Run tests
        run: npm test
      
      - name: Run linter
        run: npm run lint

  build-and-deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v1
      
      - name: Build and push Docker image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/pixie-backend:$IMAGE_TAG .
          docker push $ECR_REGISTRY/pixie-backend:$IMAGE_TAG
      
      - name: Deploy to ECS
        run: |
          aws ecs update-service \
            --cluster pixie-cluster \
            --service pixie-backend \
            --force-new-deployment
```

### 6.3 Monitoring Setup

**Datadog Integration:**
```typescript
// src/monitoring/datadog.ts
import { StatsD } from 'hot-shots';

const statsd = new StatsD({
  host: 'localhost',
  port: 8125,
  prefix: 'pixie.',
});

export function trackLLMCall(model: string, tokens: number, duration: number) {
  statsd.increment('llm.calls', 1, [`model:${model}`]);
  statsd.gauge('llm.tokens', tokens, [`model:${model}`]);
  statsd.timing('llm.duration', duration, [`model:${model}`]);
}

export function trackTaskCreated() {
  statsd.increment('tasks.created');
}
```

**Sentry Integration:**
```typescript
// src/monitoring/sentry.ts
import * as Sentry from '@sentry/node';

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: 1.0,
});

export { Sentry };
```

### 6.4 Verification

- [ ] Docker images build successfully
- [ ] Application deploys to AWS ECS
- [ ] Database migrations run in production
- [ ] SSL certificates configured (HTTPS)
- [ ] Environment variables secured (AWS Secrets Manager)
- [ ] Monitoring dashboards set up in Datadog
- [ ] Error tracking active in Sentry
- [ ] CI/CD pipeline runs successfully
- [ ] Zero downtime deployment works
- [ ] Backup and recovery tested

---

## Phase 7: Testing & Quality Assurance (Ongoing)

### 7.1 Unit Tests

```typescript
// tests/services/task-service.test.ts
import { TaskService } from '../../src/services/task-service';

describe('TaskService', () => {
  let taskService: TaskService;
  
  beforeEach(() => {
    taskService = new TaskService();
  });
  
  describe('createTask', () => {
    it('should create a task successfully', async () => {
      const task = await taskService.createTask('user-123', {
        title: 'Test task',
        dueAt: new Date('2025-01-20'),
      });
      
      expect(task).toMatchObject({
        title: 'Test task',
        userId: 'user-123',
        status: 'PENDING',
      });
    });
    
    it('should generate embedding for the task', async () => {
      // ... test implementation
    });
  });
});
```

### 7.2 Integration Tests

```typescript
// tests/integration/chat-flow.test.ts
import { io as Client } from 'socket.io-client';

describe('Chat Flow Integration', () => {
  let clientSocket;
  
  beforeAll((done) => {
    clientSocket = Client('http://localhost:3001', {
      auth: { token: TEST_TOKEN }
    });
    clientSocket.on('connect', done);
  });
  
  afterAll(() => {
    clientSocket.close();
  });
  
  it('should create task via chat', (done) => {
    clientSocket.emit('chat:message', {
      message: 'Create a task to review PR by tomorrow'
    });
    
    clientSocket.on('chat:response', (response) => {
      expect(response.tool_results).toContainEqual(
        expect.objectContaining({
          tool: 'create_task',
          result: expect.objectContaining({
            title: expect.stringContaining('review PR')
          })
        })
      );
      done();
    });
  });
});
```

### 7.3 Load Testing

```javascript
// tests/load/chat.js (k6)
import { check } from 'k6';
import ws from 'k6/ws';

export let options = {
  stages: [
    { duration: '1m', target: 100 },
    { duration: '3m', target: 100 },
    { duration: '1m', target: 0 },
  ],
};

export default function () {
  const url = 'ws://localhost:3001';
  const params = { headers: { 'Authorization': `Bearer ${TOKEN}` } };
  
  const res = ws.connect(url, params, function (socket) {
    socket.on('open', () => {
      socket.send(JSON.stringify({
        type: 'chat:message',
        data: { message: 'List my tasks' }
      }));
    });
    
    socket.on('message', (data) => {
      check(data, {
        'response received': (msg) => msg.length > 0,
      });
    });
    
    socket.setTimeout(() => {
      socket.close();
    }, 5000);
  });
}
```

**Run Tests:**
```bash
# Unit tests
npm test

# Integration tests
npm run test:integration

# Load tests
k6 run tests/load/chat.js
```

### 7.4 Verification Checklist

- [ ] ≥80% code coverage for unit tests
- [ ] All critical user flows have integration tests
- [ ] Load testing shows acceptable performance under 1000 concurrent users
- [ ] No critical security vulnerabilities (OWASP Top 10 checked)
- [ ] Accessibility audit passed (WCAG 2.1 AA)
- [ ] Cross-browser testing completed (Chrome, Firefox, Safari, Edge)

---

## Post-Launch Checklist

### Technical
- [ ] Monitoring alerts configured (Datadog, Sentry)
- [ ] Database backup schedule verified (daily snapshots)
- [ ] Disaster recovery plan documented
- [ ] Secrets rotated and secured
- [ ] SSL certificates set to auto-renew
- [ ] Rate limiting tuned for production traffic
- [ ] CDN caching configured
- [ ] Database connection pooling optimized

### Business
- [ ] User onboarding flow tested
- [ ] Billing integration ready (Stripe - future)
- [ ] Terms of Service and Privacy Policy published
- [ ] Support documentation created
- [ ] Analytics tracking implemented (PostHog/Mixpanel)
- [ ] Email templates configured (transactional emails)

### Security
- [ ] Penetration testing completed
- [ ] Security headers configured (CSP, HSTS, etc.)
- [ ] DDoS protection enabled (CloudFlare)
- [ ] Vulnerability scanning automated (Snyk)
- [ ] Security incident response plan documented

---

## Rollout Strategy

### Phase 1: Alpha (Internal Testing)
- **Duration**: 1-2 weeks
- **Users**: Internal team (5-10 people)
- **Goals**: Catch critical bugs, validate core features

### Phase 2: Closed Beta
- **Duration**: 3-4 weeks
- **Users**: 50-100 invited users
- **Goals**: Gather feedback, stress test, refine UX

### Phase 3: Public Beta
- **Duration**: 4-6 weeks
- **Users**: Open registration with waitlist
- **Goals**: Scale testing, marketing buzz, feature validation

### Phase 4: General Availability
- **Launch**: Full public launch
- **Marketing**: Product Hunt launch, social media campaign
- **Monitoring**: 24/7 on-call rotation for first week

---

## Success Criteria

### MVP (Minimum Viable Product)
-  User authentication working
-  Chat interface functional
-  Task creation via natural language
-  Event scheduling
-  Basic memory/recall
-  Daily summaries
-  99% uptime

### V1 (Production Ready)
-  All MVP features +
-  Mobile responsive design
-  Calendar integration
-  Advanced search
-  Proactive suggestions
-  Sub-200ms API latency (p95)
-  99.9% uptime
-  Complete monitoring stack
-  Automated backups and recovery

---

## Maintenance & Iteration

### Weekly
- Review error logs (Sentry)
- Check performance metrics (Datadog)
- User feedback triage
- Security patch updates

### Monthly
- Feature planning and roadmap review
- Cost optimization review (AWS bill)
- LLM usage and cost analysis
- Database maintenance (vacuum, reindex)

### Quarterly
- Major feature releases
- Infrastructure scaling review
- Security audit
- User survey and NPS measurement

---

This implementation plan provides a clear, step-by-step roadmap from project initialization to production deployment. Each phase builds upon the previous, with clear verification steps to ensure quality at every stage. The timeline is aggressive but achievable with focused execution and proper resource allocation.
