# Function Calling & Tool Definitions

## What is CRUD?

**CRUD** = **C**reate, **R**ead, **U**pdate, **D**elete

The four basic operations for managing data:

| Operation | What it does | Example |
|-----------|--------------|---------|
| **Create** | Add new data | Create a task: "Fix login bug" |
| **Read** | Retrieve data | List all tasks for Avenue project |
| **Update** | Modify existing data | Mark task as completed |
| **Delete** | Remove data | Delete cancelled task |

**For Pixie:**
- Create task/event
- Read (list/search) tasks/events
- Update task status/priority
- Delete task/event

---

## What is Function Calling?

**Function calling** lets the LLM trigger backend functions instead of just returning text.

### Without Function Calling:
```
User: "Add task to fix login bug"
LLM: "I'll add a task called 'Fix login bug' for you"
```
You'd have to **parse this text** with regex - unreliable!

### With Function Calling:
```
User: "Add task to fix login bug"
LLM: {
  "function": "create_task",
  "arguments": {
    "title": "Fix login bug",
    "status": "pending"
  }
}
```
**Structured, reliable, type-safe!**

---

## Tool Schema

A **tool schema** defines what the LLM can do - like an API specification.

### Complete Tool Schema Example:

```python
{
    "type": "function",
    "function": {
        "name": "create_task",
        "description": "Create a new task for the user. Use this when user wants to add, create, or remember a task.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short task title"
                },
                "description": {
                    "type": "string",
                    "description": "Detailed task description (optional)"
                },
                "project": {
                    "type": "string",
                    "description": "Project name (e.g., 'Avenue', 'Pixie')"
                },
                "priority": {
                    "type": "string",
                    "enum": ["LOW", "MEDIUM", "HIGH", "URGENT"],
                    "description": "Task priority level"
                },
                "due_date": {
                    "type": "string",
                    "format": "date-time",
                    "description": "ISO 8601 date when task is due"
                }
            },
            "required": ["title"]
        }
    }
}
```

### Schema Breakdown:

**1. name:** Function identifier
```python
"name": "create_task"
```

**2. description:** Tells LLM when to use this tool
```python
"description": "Create a new task for the user. Use this when user wants to add, create, or remember a task."
```
Make it specific! LLM uses this to decide which tool to call.

**3. parameters:** JSON Schema for arguments
```python
"parameters": {
    "type": "object",
    "properties": {...},
    "required": ["title"]
}
```

**4. properties:** Each parameter with type and description
```python
"title": {
    "type": "string",
    "description": "Short task title"
}
```

**5. required:** Which fields are mandatory
```python
"required": ["title"]
```

---

## Parameter Specifications

### Types:

```python
# String
"title": {"type": "string"}

# Number
"estimated_hours": {"type": "number"}

# Integer
"priority_level": {"type": "integer"}

# Boolean
"is_urgent": {"type": "boolean"}

# Enum (restricted values)
"status": {
    "type": "string",
    "enum": ["PENDING", "IN_PROGRESS", "COMPLETED"]
}

# Date/Time
"due_date": {
    "type": "string",
    "format": "date-time"  # ISO 8601: 2026-01-17T15:00:00Z
}

# Array
"tags": {
    "type": "array",
    "items": {"type": "string"}
}

# Object (nested)
"location": {
    "type": "object",
    "properties": {
        "address": {"type": "string"},
        "coordinates": {"type": "object"}
    }
}
```

### Best Practices:

**1. Clear descriptions:**
```python
# Bad
"d": {"type": "string", "description": "desc"}

# Good
"description": {
    "type": "string",
    "description": "Detailed task description with context and requirements"
}
```

**2. Use enums for fixed choices:**
```python
"priority": {
    "type": "string",
    "enum": ["LOW", "MEDIUM", "HIGH", "URGENT"],
    "description": "Task priority level"
}
```

**3. Provide examples in descriptions:**
```python
"project": {
    "type": "string",
    "description": "Project name (e.g., 'Avenue', 'Pixie', 'ClientPortal')"
}
```

---

## Complete Tool Set for Pixie

```python
TOOLS = [
    # Task Management
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a new task",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "project": {"type": "string"},
                    "priority": {
                        "type": "string",
                        "enum": ["LOW", "MEDIUM", "HIGH", "URGENT"]
                    },
                    "due_date": {"type": "string", "format": "date-time"}
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "Get user's tasks with optional filters",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["PENDING", "IN_PROGRESS", "COMPLETED"]
                    },
                    "project": {"type": "string"},
                    "due_before": {"type": "string", "format": "date"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Update an existing task",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "status": {"type": "string", "enum": ["PENDING", "IN_PROGRESS", "COMPLETED"]},
                    "priority": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "URGENT"]}
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": "Delete a task",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"}
                },
                "required": ["task_id"]
            }
        }
    },
    
    # Event Management
    {
        "type": "function",
        "function": {
            "name": "create_event",
            "description": "Create a calendar event",
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
        }
    },
    
    # Memory/Search
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "Search through user's historical data using semantic search",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "description": "Max results", "default": 5}
                },
                "required": ["query"]
            }
        }
    }
]
```

---

## Tool Response Formatting

After executing a tool, format the response for the LLM.

### Response Structure:

```python
{
    "tool": "create_task",
    "success": True,
    "result": {
        "id": "task-123",
        "title": "Fix login bug",
        "status": "pending",
        "created_at": "2026-01-12T23:00:00Z"
    }
}
```

### For Error Cases:

```python
{
    "tool": "create_task",
    "success": False,
    "error": "Database connection failed",
    "error_type": "DatabaseError"
}
```

### Implementation:

```python
# In Node.js backend
async function executeToolCall(toolCall, userId):
    try:
        if toolCall.name == 'create_task':
            task = await taskService.createTask(userId, toolCall.arguments)
            return {
                "tool": "create_task",
                "success": True,
                "result": task
            }
    except Exception as e:
        return {
            "tool": toolCall.name,
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }
```

---

## Multi-Turn Tool Usage

Sometimes the LLM needs multiple back-and-forth exchanges.

### Example Flow:

**Turn 1: User Query**
```
User: "Schedule a meeting with John tomorrow"
```

**Turn 2: LLM Needs Info**
```python
LLM: {
    "content": "What time should I schedule the meeting?",
    "tool_calls": []  # No tools yet, asking for clarification
}
```

**Turn 3: User Provides Info**
```
User: "3pm"
```

**Turn 4: LLM Creates Event**
```python
LLM: {
    "content": "I've scheduled the meeting",
    "tool_calls": [{
        "name": "create_event",
        "arguments": {
            "title": "Meeting with John",
            "start_time": "2026-01-13T15:00:00Z",
            "end_time": "2026-01-13T16:00:00Z"
        }
    }]
}
```

### Implementation Pattern:

```python
async def process_with_tools(message, history, user_id):
    # Step 1: Call LLM with tools
    response = await llm.chat(message, history, tools=TOOLS)
    
    # Step 2: If LLM called tools, execute them
    if response.tool_calls:
        tool_results = []
        for tool_call in response.tool_calls:
            result = await execute_tool(tool_call, user_id)
            tool_results.append(result)
        
        # Step 3: Send results back to LLM for final response
        final_response = await llm.chat(
            message=f"Tool results: {tool_results}",
            history=history + [response],
            tools=TOOLS
        )
        return final_response
    
    # No tools needed, return direct response
    return response
```

### Multi-Tool Execution:

LLM can call multiple tools in one turn:

```python
# User: "Add task to fix bug and schedule review meeting tomorrow"

LLM returns:
{
    "tool_calls": [
        {
            "name": "create_task",
            "arguments": {"title": "Fix bug"}
        },
        {
            "name": "create_event",
            "arguments": {
                "title": "Review meeting",
                "start_time": "2026-01-13T15:00:00Z"
            }
        }
    ]
}

# Execute both tools, send results back to LLM
```

---

## Error Handling for Tool Execution

### Types of Errors:

**1. Validation Errors**
```python
# Missing required field
{
    "tool": "create_task",
    "success": False,
    "error": "Missing required field: title",
    "error_type": "ValidationError"
}
```

**2. Database Errors**
```python
{
    "tool": "create_task",
    "success": False,
    "error": "Failed to save task to database",
    "error_type": "DatabaseError"
}
```

**3. Not Found Errors**
```python
{
    "tool": "update_task",
    "success": False,
    "error": "Task with id task-999 not found",
    "error_type": "NotFoundError"
}
```

### LLM Handling:

When tool execution fails, send error back to LLM:

```python
# Tool failed
error_result = {
    "success": False,
    "error": "Task not found"
}

# LLM processes error and responds to user
final_response = await llm.chat(
    message=f"Tool execution failed: {error_result}",
    history=history
)

# LLM says: "I couldn't find that task. Could you provide more details?"
```

---

## Complete Example Flow

### User Message:
```
"Add urgent task to fix Avenue login bug by Friday"
```

### Step 1: LLM Receives Request
```python
Input to LLM:
{
    "messages": [
        {"role": "system", "content": "You are Pixie..."},
        {"role": "user", "content": "Add urgent task to fix Avenue login bug by Friday"}
    ],
    "tools": TOOLS  # All available tools
}
```

### Step 2: LLM Returns Tool Call
```python
LLM Response:
{
    "content": "I'll add that task for you",
    "tool_calls": [{
        "id": "call_abc123",
        "name": "create_task",
        "arguments": {
            "title": "Fix Avenue login bug",
            "project": "Avenue",
            "priority": "URGENT",
            "due_date": "2026-01-17T23:59:59Z"
        }
    }]
}
```

### Step 3: Backend Executes Tool
```python
# Node.js backend receives tool call
result = await taskService.createTask(userId, {
    title: "Fix Avenue login bug",
    project: "Avenue",
    priority: "URGENT",
    due_date: "2026-01-17T23:59:59Z"
})

# Result:
{
    "id": "task-456",
    "title": "Fix Avenue login bug",
    "status": "PENDING",
    "priority": "URGENT",
    "project": "Avenue",
    "due_at": "2026-01-17T23:59:59Z"
}
```

### Step 4: Send Result Back to User
```python
# Backend sends to user
{
    "message": "I'll add that task for you",
    "task_created": {
        "id": "task-456",
        "title": "Fix Avenue login bug",
        "due_date": "Friday, Jan 17"
    }
}
```

---

## Best Practices

### 1. Clear Tool Descriptions
```python
# Bad
"description": "Creates task"

# Good
"description": "Create a new task for the user. Use this when user wants to add, create, remember, or note down a task."
```

### 2. Use Enums for Consistency
```python
"priority": {
    "type": "string",
    "enum": ["LOW", "MEDIUM", "HIGH", "URGENT"]
}
```

### 3. Return Useful Data
```python
# Return what user needs to see
{
    "id": "task-123",
    "title": "Fix bug",
    "due_date": "2026-01-17"  # Human readable in response
}
```

### 4. Handle Partial Data
```python
# LLM might extract partial info
{
    "title": "Fix bug",
    # No project, no priority - use defaults
}
```

### 5. Validate Strictly
```python
# Validate before execution
if not tool_args.get("title"):
    return {"success": False, "error": "Title is required"}
```

---

## Summary

**Function calling enables:**
- Structured LLM outputs (no text parsing)
- Reliable CRUD operations
- Multi-step workflows
- Error handling

**Key components:**
- **Tool schemas** - Define what LLM can do
- **Parameter specs** - Type-safe arguments
- **Tool execution** - Backend handles logic
- **Response formatting** - Results back to LLM
- **Multi-turn** - Complex workflows

---

## 2026 Enhancements & Best Practices

### 1. Parallel Tool Execution

Execute multiple tools concurrently instead of sequentially for better performance.

**Before (Sequential):**
```python
# Slow: One at a time
tool_results = []
for tool_call in response.tool_calls:
    result = await execute_tool(tool_call, user_id)
    tool_results.append(result)
# Time: 500ms per tool × 2 tools = 1000ms
```

**After (Parallel):**
```python
import asyncio

# Fast: All at once
tool_results = await asyncio.gather(*[
    execute_tool(tc, user_id) for tc in response.tool_calls
])
# Time: max(500ms, 500ms) = 500ms (50% faster!)
```

**Benefits:**
- 50-70% faster for multi-tool queries
- Better user experience
- No additional cost

---

### 2. Structured Outputs (OpenAI)

Use OpenAI's structured outputs for guaranteed schema compliance.

**Function Calling (95% accuracy):**
```python
response = openai.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages,
    tools=tools  # ~95% schema compliance
)
```

**Structured Outputs (100% accuracy):**
```python
response = openai.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages,
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "task_creation",
            "strict": True,  # Enforces schema
            "schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "priority": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]}
                },
                "required": ["title"],
                "additionalProperties": False
            }
        }
    }
)
```

**Benefits:**
- 100% schema compliance
- Fewer errors and retries
- Slightly faster

**Note:** Claude doesn't support this yet - use function calling for Claude.

---

### 3. Input Validation Layer

Validate tool arguments before execution to catch errors early.

```python
def validate_tool_args(tool_name: str, args: dict) -> list[str]:
    """Validate tool arguments against schema"""
    errors = []
    
    # Define schemas
    schemas = {
        "create_task": {
            "required": ["title"],
            "types": {
                "title": str,
                "priority": str,
                "due_date": str
            },
            "enums": {
                "priority": ["LOW", "MEDIUM", "HIGH", "URGENT"]
            }
        }
    }
    
    schema = schemas.get(tool_name)
    if not schema:
        return [f"Unknown tool: {tool_name}"]
    
    # Check required fields
    for field in schema["required"]:
        if field not in args:
            errors.append(f"Missing required field: {field}")
    
    # Check types
    for field, expected_type in schema["types"].items():
        if field in args and not isinstance(args[field], expected_type):
            errors.append(f"Invalid type for {field}")
    
    # Check enums
    for field, valid_values in schema.get("enums", {}).items():
        if field in args and args[field] not in valid_values:
            errors.append(f"Invalid value for {field}: {args[field]}")
    
    return errors

# Usage
async def execute_tool_safely(tool_call, user_id):
    # Validate first
    errors = validate_tool_args(tool_call.name, tool_call.arguments)
    if errors:
        return {
            "success": False,
            "error": "; ".join(errors),
            "error_type": "ValidationError"
        }
    
    # Execute if valid
    return await execute_tool(tool_call, user_id)
```

**Benefits:**
- Catch errors before database calls
- Better error messages to user
- Prevents invalid data in database

---

### 4. Context Pollution Prevention

Don't send unnecessary data back to LLM - saves tokens and improves focus.

**Before (Verbose):**
```python
# Send full object back
result = await create_task(user_id, args)
llm.chat(f"Tool result: {json.dumps(result)}")
# Tokens: ~50
```

**After (Concise):**
```python
# Send only what LLM needs for response
result = await create_task(user_id, args)
summary = f"Created task '{result['title']}' (ID: {result['id']})"
llm.chat(f"Tool result: {summary}")
# Tokens: ~10 (80% reduction)
```

**Implementation:**
```python
def summarize_tool_result(tool_name: str, result: dict) -> str:
    """Create concise summaries for LLM"""
    if tool_name == "create_task":
        return f"Created task '{result['title']}'"
    elif tool_name == "list_tasks":
        return f"Found {len(result)} tasks"
    elif tool_name == "update_task":
        return f"Updated task to {result['status']}"
    else:
        return str(result)
```

---

### 5. Security: Input Sanitization

Prevent injection attacks and malicious inputs.

```python
import re
from html import escape

def sanitize_inputs(args: dict) -> dict:
    """Sanitize tool arguments"""
    sanitized = {}
    
    for key, value in args.items():
        if isinstance(value, str):
            # Remove potentially dangerous characters
            value = escape(value)  # HTML escape
            value = re.sub(r'[<>{}|\\]', '', value)  # Remove special chars
            value = value.strip()  # Trim whitespace
        
        sanitized[key] = value
    
    return sanitized

# Usage
async def execute_tool(tool_call, user_id):
    # Sanitize inputs
    safe_args = sanitize_inputs(tool_call.arguments)
    
    # Execute with sanitized data
    if tool_call.name == "create_task":
        return await task_service.createTask(user_id, safe_args)
```

**Protects against:**
- SQL injection (though ORMs help)
- XSS attacks
- Code injection
- Malformed data

---

## Complete Enhanced Implementation

```python
import asyncio
from typing import List, Dict

async def process_with_tools_enhanced(
    message: str,
    history: list,
    user_id: str,
    tools: list
):
    """Enhanced function calling with 2026 best practices"""
    
    # Step 1: Call LLM
    response = await llm.chat(message, history, tools=tools)
    
    # Step 2: If no tools, return response
    if not response.tool_calls:
        return response
    
    # Step 3: Validate all tool calls
    for tool_call in response.tool_calls:
        errors = validate_tool_args(tool_call.name, tool_call.arguments)
        if errors:
            return {
                "content": f"Invalid request: {'; '.join(errors)}",
                "error": True
            }
    
    # Step 4: Execute tools in parallel
    tool_results = await asyncio.gather(*[
        execute_tool_safely(tc, user_id) 
        for tc in response.tool_calls
    ])
    
    # Step 5: Summarize results (prevent context pollution)
    summaries = [
        summarize_tool_result(tc.name, result)
        for tc, result in zip(response.tool_calls, tool_results)
    ]
    
    # Step 6: Send concise summary back to LLM
    final_response = await llm.chat(
        message=f"Tool results: {'; '.join(summaries)}",
        history=history + [response],
        tools=tools
    )
    
    return final_response

async def execute_tool_safely(tool_call, user_id):
    """Execute with validation and sanitization"""
    # Sanitize inputs
    safe_args = sanitize_inputs(tool_call.arguments)
    
    # Execute tool
    try:
        if tool_call.name == "create_task":
            result = await task_service.createTask(user_id, safe_args)
            return {"success": True, "result": result}
        # ... other tools
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }
```

---

## Cost & Performance Impact

| Enhancement | Cost Impact | Performance Impact | Security Impact |
|-------------|-------------|-------------------|-----------------|
| Parallel execution | 0% (same tokens) | +50% faster | Neutral |
| Structured outputs | 0% (same tokens) | +10% faster, fewer errors | +Better |
| Validation | 0% | Prevents wasted calls | +Better |
| Context optimization | -80% tokens | Faster | Neutral |
| Input sanitization | 0% | Negligible | ++Much better |

**Overall:**
- **Cost:** 40-50% reduction (from context optimization)
- **Speed:** 50-70% faster (parallel + optimizations)
- **Reliability:** 95% → 99%+ (validation + structured outputs)
- **Security:** Significantly improved

---

## Summary

For Pixie, implement these enhancements:

**Must-Have (MVP):**
1.  Parallel tool execution
2.  Input validation
3.  Context optimization

**Should-Have (Launch):**
4.  Structured outputs (OpenAI only)
5.  Input sanitization

These improvements make Pixie faster, cheaper, and more secure with zero downside.
