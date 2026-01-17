# Error Handling & Retry Logic for Pixie AI Service

## Overview

Robust error handling and retry logic are critical for production AI systems. LLM APIs can fail due to rate limits, timeouts, transient network issues, or service outages. This document outlines strategies to build resilient systems that gracefully handle failures.

---

## 1. LLM API Failures

### Common Failure Types

**Rate Limits (429)**
- Most common with OpenAI and Anthropic APIs
- Occurs when exceeding requests per minute (RPM) or tokens per minute (TPM)
- Solution: Exponential backoff with jitter

**Timeouts (504/408)**
- Long-running inference can timeout
- Network latency or server load issues
- Solution: Configurable timeout values, retry with backoff

**Service Unavailable (503)**
- Temporary service outages
- API maintenance windows
- Solution: Retry with exponential backoff, circuit breaker

**Invalid Requests (400)**
- Malformed input, context too long, invalid parameters
- DO NOT retry - fix the request
- Solution: Validate inputs before API call, handle gracefully

**Authentication (401/403)**
- Invalid API keys, expired tokens
- DO NOT retry automatically
- Solution: Alert monitoring, manual intervention

### Retry Strategy

**CRITICAL: Check Retry-After Header First**

When handling 429 rate limit errors, ALWAYS check for the `Retry-After` header in the API response before using exponential backoff:

1. **Check for `Retry-After` header** - OpenAI and Anthropic include this in 429 responses
2. **Use exact wait time** - The header specifies precisely how long to wait
3. **Fall back to exponential backoff** - Only if header is not present

This is MORE ACCURATE than guessing with exponential backoff and prevents premature retries.

**Exponential Backoff with Jitter (Fallback Strategy)**

Use when Retry-After header is not available:
- First retry: 1-2 seconds
- Second retry: 2-4 seconds  
- Third retry: 4-8 seconds
- Maximum retries: 3-5 attempts
- Add random jitter (±20%) to prevent thundering herd

**Recommended Libraries**

Python:
- **tenacity** - Powerful retry library with exponential backoff, jitter, conditional retries
- **backoff** - Lightweight alternative with decorator-based syntax
- Note: OpenAI and Anthropic SDKs have built-in retry logic with configurable `max_retries`

Node.js:
- **axios-retry** - Automatic retry for HTTP requests
- **async-retry** - Simple retry with exponential backoff

**When to Retry**
- YES: Rate limits (429) - respect Retry-After header
- YES: Timeouts (504, 408)
- YES: Service unavailable (503)
- YES: Network errors (connection reset)
- NO: Invalid requests (400)
- NO: Authentication errors (401, 403)
- NO: Content policy violations

---

## 2. Fallback Strategies Between Models

### Model Tier System

**Primary → Secondary → Tertiary**
```
GPT-4o → GPT-4o-mini → Claude Haiku
(if primary fails) → (if secondary fails) → (final fallback)
```

**Strategy:**
1. Try primary model (GPT-4o for complex tasks)
2. If fails with timeout/503: retry once with backoff
3. If still fails: downgrade to GPT-4o-mini
4. If that fails: fallback to Claude Haiku
5. If all fail: return graceful error to user

### When to Use Fallbacks

**Cost-Based Fallback**
- If GPT-4o rate limit hit → use GPT-4o-mini for remaining requests
- Track daily budget, auto-downgrade when approaching limit

**Performance-Based Fallback**
- If latency > 15 seconds on GPT-4o → switch to faster model
- Monitor p95 latency and adjust routing

**Feature-Based Fallback**
- If model doesn't support required feature (e.g., vision) → route to capable model
- Maintain feature matrix per model

---

## 3. Graceful Degradation Patterns

### Progressive Feature Degradation

**Level 1: Full Functionality**
- RAG with semantic search
- Multi-turn conversation with context
- Tool calling for CRUD operations

**Level 2: Degraded Mode**
- Disable RAG, use only recent context
- Reduce context window (save tokens)
- Simpler tool schemas (fewer parameters)

**Level 3: Fallback Mode**
- No RAG, minimal context
- Read-only operations (no writes)
- Pre-cached responses for common queries

**Level 4: Maintenance Mode**
- Static responses only
- "AI is temporarily unavailable, try again in X minutes"
- Log requests for later processing

### User Communication

**Transparent Error Messages**
- "I'm experiencing high load right now. Let me try a faster approach..."
- "The AI service is temporarily unavailable. Your request has been saved."
- "Error 503: Service Unavailable"
- "An unexpected error occurred"

**Partial Results**
- If RAG search succeeds but LLM fails → show raw results
- If only 2/5 tool calls succeed → show partial data with warning
- Better to show something than nothing

---

## 4. Circuit Breaker Implementation

### Concept

Prevent cascading failures by "opening the circuit" when error rate exceeds threshold.

**States:**
1. **Closed** (normal): All requests go through
2. **Open** (tripped): All requests fail fast, no API calls
3. **Half-Open** (testing): Allow limited requests to test recovery

### Configuration

**Thresholds:**
- Failure rate: 50% errors over 10 requests → open circuit
- Timeout: Keep circuit open for 60 seconds
- Success threshold: 3 consecutive successes → close circuit

**Per-Service Breakers:**
- OpenAI circuit breaker (separate from Anthropic)
- Qdrant circuit breaker (vector search)
- Database circuit breaker

**Benefits:**
- Prevents wasted API calls during outages
- Faster failure response (no waiting for timeouts)
- Automatic recovery when service returns

---

## 5. User-Facing Error Messages

### Error Message Guidelines

**Be Human, Not Technical**
```
BAD: "LLM API returned 429 status code"
GOOD: "I'm getting too many requests right now. Give me a moment..."

BAD: "Vector search timeout after 5000ms"
GOOD: "Searching through your data is taking longer than expected..."

BAD: "Tool execution failed with exception: NullPointerError"
GOOD: "I couldn't complete that action. Let me try a different approach."
```

**Provide Context and Next Steps**
```
"I couldn't send that email right now. 
• Your message has been saved as a draft
• I'll try again in 2 minutes
• You can also send it manually from your drafts folder"
```

**Show Progress During Retries**
```
"Hmm, that didn't work. Let me try again..." (1st retry)
"Still having trouble, one more attempt..." (2nd retry)
"I'm experiencing technical difficulties. Try again in a few minutes." (failure)
```

### Error Message Templates

**Rate Limit Hit:**
> "I'm handling a lot of requests right now. Your query is important, so I'm using a faster model to respond quickly."

**Timeout:**
> "That's taking longer than expected. Let me try a simpler approach..."

**Service Outage:**
> "The AI service is temporarily unavailable. I've saved your request and will process it as soon as service is restored."

**Invalid Input:**
> "I'm having trouble understanding that request. Could you rephrase it?"

**Context Too Long:**
> "You have a lot of data! I'm focusing on the most recent information to keep things fast."

---

## 6. Implementation Checklist

### Essential Components

- **Retry wrapper** with exponential backoff for all LLM API calls
- **Model fallback logic** (GPT-4o → 4o-mini → Claude)
- **Circuit breaker** for each external service (OpenAI, Anthropic, Qdrant)
- **Timeout configuration** per model (GPT-4o: 30s, GPT-4o-mini: 15s)
- **Error logging** with structured metadata (model, retry count, error type)
- **User-facing error messages** (mapped from status codes)
- **Graceful degradation** modes (full → degraded → fallback)
- **Health check endpoint** to monitor service status
- **Alerting** for high error rates (>10% over 5 minutes)

### Testing Scenarios

- Simulate rate limit (429) → verify retry with backoff
- Simulate timeout → verify fallback to faster model
- Simulate service outage → verify circuit breaker opens
- Invalid API key → verify alert sent, no retries
- Context too long (>X tokens) → verify truncation strategy
- Partial tool execution failure → verify graceful handling

---

## 7. Monitoring & Alerting

### Key Metrics to Track

**Error Rates**
- Percentage of failed LLM calls per model
- Types of errors (rate limit, timeout, 5xx, 4xx)
- Trigger alert if >10% error rate over 5 minutes

**Retry Statistics**
- Average retry count per request
- Success rate after 1st, 2nd, 3rd retry
- Identify patterns (certain queries always timeout?)

**Circuit Breaker Events**
- When circuits open/close
- Duration in open state
- Frequency of tripping (too often = underlying issue)

**Fallback Usage**
- How often falling back to cheaper models
- Cost savings from fallbacks
- Quality impact (monitor user satisfaction)

### Alert Configuration

**Critical (Immediate Notification)**
- All models failing (circuit breakers all open)
- Error rate >50% over 2 minutes
- API authentication failures

**Warning (Review Within Hour)**
- Error rate >20% over 10 minutes
- Circuit breaker in open state >5 minutes
- Fallback usage >30% of requests

**Info (Daily Summary)**
- Total retry count
- Most common error types
- Cost savings from fallbacks

---

## 8. Best Practices

### Design Principles

**Fail Fast for Invalid Inputs**
- Validate requests before calling expensive APIs
- Check context length, required parameters, authentication
- Return clear error immediately

**Fail Slow for Transient Errors**
- Retry with backoff for rate limits, timeouts
- Give services time to recover
- Don't give up after first failure

**Always Have a Fallback**
- Never let user see raw error messages
- Provide degraded functionality over no functionality
- Cache common responses for offline mode

### Idempotency Keys for Write Operations

**Critical for Retries on State-Changing Operations**

When retrying operations that modify state (create task, send email, delete event), use idempotency keys to prevent duplicate actions:

**How It Works:**
1. Generate unique key per user request (UUID or hash of request params)
2. Include key in API call or database operation
3. On retry, use same key
4. System detects duplicate key and returns original result instead of re-executing

**Example Scenarios:**
- Creating a task via LLM tool call
- Sending an email on behalf of user
- Deleting or updating events
- Any operation that shouldn't happen twice

**Without Idempotency:**
- Retry creates duplicate task
- User gets same email multiple times
- Data corruption from double-delete

**With Idempotency:**
- Retry safely returns success without duplicating
- User gets predictable behavior
- Safe to retry as many times as needed

### Cost Optimization

**Smart Retry Logic**
- Don't retry expensive long calls infinitely
- Track retry costs, set max budget per request
- For expensive models, fail over to cheap models faster

**Batch Retries**
- If many requests failing due to rate limit → queue and batch
- Process queue with controlled rate
- Prevents wasted retry attempts

### User Experience

**Set Expectations**
- Show loading states during retries
- "This might take a moment..." for complex queries
- Progress indicators for multi-step operations

**Learn from Failures**
- Log failed queries for analysis
- Identify patterns (certain query types always fail?)
- Proactively warn users about problematic requests

### Structured Output Validation & Retry

**For Tool Calling and JSON Responses**

When expecting structured output (JSON for tool calls, function parameters), validate and retry on malformed responses:

**Validation Strategy:**
1. Define schema for expected output (JSON schema, Pydantic model, TypeScript interface)
2. After LLM responds, validate against schema
3. If validation fails:
   - Retry with schema re-attached (remind LLM of format)
   - Include error message explaining what was wrong
   - Limit to 2-3 validation retries
4. If still fails after retries, log error and fall back gracefully

**Common Validation Failures:**
- Missing required fields in tool call parameters
- Wrong data types (string instead of number)
- Invalid enum values
- Malformed JSON (unclosed brackets, trailing commas)

**Retry Pattern:**
```
First attempt: LLM returns malformed JSON
  → Validate: FAIL (missing 'date' field)
  
First retry: Re-send with schema + error message
  → "Your previous response was missing the required 'date' field. 
     Please provide valid JSON matching this schema: {...}"
  → Validate: SUCCESS ✓
```

**Benefits:**
- Dramatically improves tool calling reliability
- LLM can self-correct minor formatting errors
- Reduces need for manual intervention
- Better user experience (fewer "tool execution failed" errors)

---

## 8. Complete Service Failure Scenarios

### All LLM Providers Down

**Worst Case:** OpenAI AND Anthropic both unavailable

**Detection:**
```python
async def check_all_providers_health():
    providers_status = {
        "openai": await check_openai_health(),
        "anthropic": await check_anthropic_health()
    }
    
    all_down = all(not status for status in providers_status.values())
    
    if all_down:
        logger.critical("ALL LLM PROVIDERS DOWN", extra=providers_status)
        return False
    
    return True
```

**Fallback Strategy:**

**1. Semantic Cache Fallback**
```python
async def handle_complete_llm_failure(user_id, query):
    # Try semantic cache first
    query_embedding = await get_embedding(query)  # This might still work
    cached_response = await semantic_cache.get_similar(user_id, query_embedding, threshold=0.85)
    
    if cached_response:
        logger.info("Served from cache during LLM outage")
        return {
            "response": cached_response["response"],
            "source": "cache",
            "note": "AI temporarily unavailable, showing similar previous response"
        }
    
    # No cache match - use static fallback
    return get_static_fallback_response(query)
```

**2. Static Fallback Response**
```python
def get_static_fallback_response(query):
    """Pattern-match common queries to static responses"""
    query_lower = query.lower()
    
    if any(word in query_lower for word in ["task", "todo"]):
        return {
            "response": "I'm temporarily unavailable. You can manually create tasks using the form above.",
            "fallback_ui": "task_creation_form"
        }
    
    if any(word in query_lower for word in ["event", "meeting", "calendar"]):
        return {
            "response": "I'm temporarily unavailable. You can manually add events to your calendar.",
            "fallback_ui": "calendar_view"
        }
    
    # Generic fallback
    return {
        "response": "I'm temporarily unavailable due to high demand. Your request has been saved and I'll process it when service resumes. In the meantime, you can use the manual tools above.",
        "fallback_ui": "manual_mode"
    }
```

**3. Request Queuing**
```python
import redis

async def queue_for_later_processing(user_id, query, context):
    """Store request for processing when service recovers"""
    request_data = {
        "user_id": user_id,
        "query": query,
        "context": context,
        "timestamp": datetime.now().isoformat(),
        "retry_count": 0
    }
    
    # Store in Redis list
    await redis_client.lpush("queued_requests", json.dumps(request_data))
    
    logger.info("Request queued for later", extra={"user_id": user_id})
    
    return {
        "queued": True,
        "message": "Your request is saved. We'll notify you when it's processed."
    }
```

**4. Background Queue Processor**
```python
async def process_queued_requests():
    """Run every 5 minutes to process queued requests"""
    while True:
        try:
            # Check if services are back up
            if not await check_all_providers_health():
                await asyncio.sleep(300)  # Wait 5 minutes
                continue
            
            # Process queue
            while True:
                request_json = await redis_client.rpop("queued_requests")
                if not request_json:
                    break
                
                request = json.loads(request_json)
                
                try:
                    # Process the queued request
                    response = await process_llm_query(
                        user_id=request["user_id"],
                        query=request["query"],
                        context=request["context"]
                    )
                    
                    # Notify user
                    await notify_user(request["user_id"], response)
                    
                except Exception as e:
                    # Re-queue if still failing
                    request["retry_count"] += 1
                    if request["retry_count"] < 3:
                        await redis_client.lpush("queued_requests", json.dumps(request))
                    else:
                        logger.error("Failed to process queued request after 3 retries")
        
        except Exception as e:
            logger.error("Queue processor error", extra={"error": str(e)})
        
        await asyncio.sleep(300)  # Check every 5 minutes
```

### Cross-Service Idempotency

**Problem:** Node.js retries Python call, causing duplicate operations

**Example:**
- Node.js calls Python to generate task via LLM
- Python generates response with `create_task` tool call
- Node.js timeout occurs before receiving response
- Node.js retries → Python processes again → Duplicate task created

**Solution: Request ID Deduplication**

**Node.js Implementation:**
```javascript
const { v4: uuidv4 } = require('uuid');

async function callPythonWithIdempotency(endpoint, data) {
  // Generate unique request ID
  const requestId = uuidv4();
  
  const response = await fetch(`${PYTHON_AI_URL}${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Request-ID': requestId,  // Include in header
      'Authorization': `Bearer ${INTERNAL_API_KEY}`
    },
    body: JSON.stringify({ ...data, request_id: requestId })
  });
  
  return response.json();
}
```

**Python Implementation:**
```python
import redis
from fastapi import Header, HTTPException

redis_client = redis.Redis(host='localhost', port=6379, db=0)

@app.post("/api/generate")
async def generate(
    request: GenerateRequest,
    x_request_id: str = Header(None)
):
    if not x_request_id:
        raise HTTPException(400, "Missing X-Request-ID header")
    
    # Check if we've already processed this request
    cache_key = f"request:{x_request_id}"
    cached_response = redis_client.get(cache_key)
    
    if cached_response:
        logger.info("Returning cached response for duplicate request",
                   extra={"request_id": x_request_id})
        return json.loads(cached_response)
    
    # Process request
    response = await process_llm_query(
        user_id=request.user_id,
        query=request.query
    )
    
    # Cache response for 5 minutes (prevents duplicates)
    redis_client.setex(
        cache_key,
        300,  # 5 minutes
        json.dumps(response)
    )
    
    return response
```

**Benefits:**
- Retry-safe: Same request_id returns same response
- Prevents duplicate tool executions
- 5-minute window handles typical retry scenarios
- Automatic cleanup (Redis TTL)

---

## 9. Production Recommendations

### Configuration Values (Recommended)

| Setting | Value | Rationale |
|---------|-------|-----------|
| Max retries | 3 | Balance reliability vs latency |
| Initial backoff | 1 second | Quick recovery for transient errors |
| Max backoff | 16 seconds | Prevent indefinite waiting |
| Request timeout (GPT-4o) | 30 seconds | Complex reasoning needs time |
| Request timeout (GPT-4o-mini) | 15 seconds | Faster model, shorter timeout |
| Circuit breaker threshold | 50% errors over 10 requests | Avoid premature tripping |
| Circuit breaker timeout | 60 seconds | Allow time for recovery |
| Daily error rate alert | >10% | Early warning of issues |

### Logging Best Practices

**Structured Logging**
```json
{
  "timestamp": "2026-01-13T10:19:49Z",
  "level": "error",
  "service": "llm-service",
  "model": "gpt-4o",
  "error_type": "rate_limit",
  "status_code": 429,
  "retry_count": 2,
  "user_id": "user_123",
  "query_id": "q_456",
  "fallback_used": "gpt-4o-mini"
}
```

**Privacy Considerations**
- Never log full user messages (PII concerns)
- Log query metadata only (length, type, model used)
- Anonymize user IDs in logs

---

## Summary

**Key Takeaways:**

1. **Expect failures** - LLM APIs will fail, plan for it from day one
2. **Retry intelligently** - Exponential backoff for transient errors, fail fast for permanent errors
3. **Use fallbacks** - Multiple models provide redundancy and cost optimization
4. **Degrade gracefully** - Partial functionality > complete failure
5. **Monitor everything** - Error rates, retry counts, fallback usage
6. **Communicate clearly** - User-friendly error messages, set expectations
7. **Circuit breakers** - Prevent cascading failures, automatic recovery
8. **Test thoroughly** - Simulate all failure modes before production

With robust error handling, Pixie can maintain >99% uptime even when underlying LLM services have issues.
