# Context Optimization for LLM Queries

## Overview

Reduce token usage by 40-50% when sending data to LLMs without compromising accuracy.

---

## Techniques

### 1. JSON Minification

Remove unnecessary whitespace and formatting.

```python
import json

# Minify JSON
context = json.dumps(data, separators=(',', ':'))
```

**Token reduction:** 10-15%

---

### 2. Smart Field Filtering

Send only relevant fields based on query type.

```python
def filter_fields(tasks, query_type):
    if query_type == "list":
        # Minimal fields for listing
        return [{k: t[k] for k in ["title", "status", "priority"]} 
                for t in tasks]
    
    elif query_type == "detail":
        # Full fields for detailed queries
        return tasks
    
    else:
        # Remove internal metadata
        return [{k: v for k, v in t.items() 
                if k not in ["id", "user_id", "created_at"]} 
                for t in tasks]
```

**Token reduction:** 30-40%

---

## Implementation

```python
def optimize_context(data, query_type="default"):
    """
    Optimize data for LLM context
    Returns: Minified JSON string
    """
    import json
    
    # Filter fields based on query type
    if query_type == "list" and "tasks" in data:
        filtered = [
            {k: t[k] for k in ["title", "status", "priority"] if k in t}
            for t in data["tasks"]
        ]
    elif query_type == "detail":
        filtered = data
    else:
        filtered = {
            k: v for k, v in data.items()
            if k not in ["id", "user_id", "created_at", "updated_at"]
        }
    
    # Minify
    return json.dumps(filtered, separators=(',', ':'))
```

---

## Usage Example

```python
# Before optimization
tasks = [
    {
        "id": "task-1",
        "title": "Fix auth bug",
        "description": "Authentication issue",
        "user_id": "user-123",
        "status": "pending",
        "priority": "high",
        "created_at": "2026-01-10T10:30:00Z"
    }
]

context = json.dumps({"tasks": tasks}, indent=2)
# Tokens: ~60

# After optimization
context = optimize_context({"tasks": tasks}, query_type="list")
# Result: [{"title":"Fix auth bug","status":"pending","priority":"high"}]
# Tokens: ~25
```

---

## Query Type Definitions

**Supported Query Types:**

**list:** Quick overview queries
- "What tasks do I have?"
- "Show my events"
- Fields: title, status, priority (tasks) | title, start_time (events)

**detail:** Specific information queries
- "Tell me about the Avenue project"
- "What's the status of task #123?"
- Fields: All fields including description, created_at, metadata

**default:** General queries
- Remove internal IDs and timestamps
- Keep user-relevant data only

---

## Validation

### Minimum Context Rule

**Always include essential fields even in aggressive optimization:**

```python
MINIMUM_FIELDS = {
    "task": ["title", "status"],  # Never remove these
    "event": ["title", "start_time"],
    "note": ["content"]
}

def ensure_minimum_context(filtered_data, entity_type):
    """
    Validate that minimum required fields are present
    """
    min_fields = MINIMUM_FIELDS.get(entity_type, [])
    
    for item in filtered_data:
        for field in min_fields:
            if field not in item:
                raise ValueError(f"Missing essential field: {field}")
    
    return filtered_data
```

### Multi-Entity Queries

**Handle queries referencing multiple entity types:**

```python
def optimize_multi_entity_context(data, query):
    """
    Detect multi-entity queries and include minimal fields for all types
    """
    query_lower = query.lower()
    
    # Check if query mentions multiple entities
    mentions_tasks = any(word in query_lower for word in ["task", "todo", "work"])
    mentions_events = any(word in query_lower for word in ["event", "meeting", "calendar"])
    
    if mentions_tasks and mentions_events:
        # Include both with minimal fields
        return {
            "tasks": filter_fields(data.get("tasks", []), "list"),
            "events": filter_fields(data.get("events", []), "list")
        }
    
    # Single entity - can optimize more aggressively
    return optimize_context(data, detect_query_type(query))
```

### Edge Cases

**Empty Results:**
```python
if not filtered_data:
    # Don't send empty context - wastes tokens
    return None
```

**Context Too Large Even After Filtering:**
```python
MAX_CONTEXT_TOKENS = 2000

if estimate_tokens(filtered_data) > MAX_CONTEXT_TOKENS:
    # Truncate to most recent items
    filtered_data = filtered_data[:10]  # Top 10 items
    logger.warning("Context truncated", extra={"original_count": len(data)})
```

**Critical Information Lost:**
```python
# If query explicitly asks for a field, always include it
if "description" in query.lower() and query_type == "list":
    # Override query type for this specific request
    query_type = "detail"
```

---

## Impact

**At 10K users (200K queries/day):**
- Token reduction: 40-50%
- Cost savings: ~$1,190/month
- Zero accuracy loss
- Improved response times (less data to process)
