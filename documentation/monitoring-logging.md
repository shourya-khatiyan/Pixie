# Monitoring & Logging for Pixie AI Service

## Overview

Effective monitoring and logging are essential for maintaining production AI systems. This guide covers tracking costs, performance, errors, and user analytics to ensure Pixie runs reliably and cost-effectively.

---

## 1. Cost Tracking (Token Usage)

### Why Track Costs

LLM API costs are based on token usage:
- OpenAI: $0.15 per 1M input tokens, $0.60 per 1M output tokens (GPT-4o-mini)
- Anthropic: $0.25 per 1M input tokens, $1.25 per 1M output tokens (Claude Haiku)

Without tracking, costs can spiral unexpectedly.

### Key Metrics to Track

**Per Request:**
- Prompt tokens (input)
- Completion tokens (output)
- Total tokens
- Model used
- Cost estimate

**Aggregated:**
- Daily token usage by user
- Daily token usage by model
- Monthly cost projections
- Cost per conversation
- Most expensive queries

### Implementation

**Log Token Usage:**

```python
import logging
from datetime import datetime

def log_llm_usage(user_id, model, prompt_tokens, completion_tokens, cost):
    logger.info({
        "event": "llm_usage",
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "estimated_cost_usd": cost
    })
```

**Calculate Costs:**

```python
PRICING = {
    "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
    "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
    "claude-haiku": {"input": 0.25 / 1_000_000, "output": 1.25 / 1_000_000}
}

def calculate_cost(model, prompt_tokens, completion_tokens):
    pricing = PRICING.get(model, PRICING["gpt-4o-mini"])
    input_cost = prompt_tokens * pricing["input"]
    output_cost = completion_tokens * pricing["output"]
    return input_cost + output_cost
```

### Storage Options

**Database Table:**
```sql
CREATE TABLE llm_usage (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP,
    user_id VARCHAR(255),
    model VARCHAR(50),
    prompt_tokens INT,
    completion_tokens INT,
    cost_usd DECIMAL(10, 6)
);
```

**Time-Series Database (Better for Analytics):**
- InfluxDB
- TimescaleDB (PostgreSQL extension)
- Better for aggregations and trends

### Cost Alerts

**Set Budget Thresholds:**
- Daily limit: $10
- Weekly limit: $50
- Per-user daily limit: $2

**Alert Triggers:**
- When 80% of daily budget consumed
- When single query costs > $1
- When user exceeds their quota

---

## 2. Performance Metrics

### Latency Tracking

**Critical Metrics:**

**End-to-End Latency:**
- Total time from request to response
- Target: < 3 seconds for 95% of requests (p95)

**Component Latency:**
- RAG search time (Qdrant)
- LLM inference time
- Tool execution time
- Database queries

**Percentiles to Track:**
- p50 (median) - typical performance
- p95 - experience for most users
- p99 - worst case handling

### Implementation

```python
import time
from contextlib import contextmanager

@contextmanager
def track_latency(operation_name):
    start = time.time()
    try:
        yield
    finally:
        duration = (time.time() - start) * 1000  # milliseconds
        logger.info({
            "event": "performance",
            "operation": operation_name,
            "duration_ms": duration
        })

# Usage
with track_latency("qdrant_search"):
    results = qdrant_client.search(...)

with track_latency("llm_inference"):
    response = openai_client.chat.completions.create(...)
```

### Throughput Metrics

**Requests Per Second (RPS):**
- Current load
- Peak load
- Average load by hour

**Concurrent Requests:**
- How many requests processing simultaneously
- Queue depth if using task queue

### Resource Utilization

**Memory:**
- Current usage
- Peak usage
- Trend over time
- Alert when > 85%

**CPU:**
- Average utilization
- Peak utilization
- Per-process breakdown

**Disk I/O (if Qdrant on-disk):**
- Read/write operations per second
- I/O wait time

---

## 3. Error Logging and Alerting

### Structured Logging

**Use JSON format for easy parsing:**

```python
import logging
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        if hasattr(record, 'user_id'):
            log_data["user_id"] = record.user_id
            
        return json.dumps(log_data)

# Configure logger
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger = logging.getLogger("pixie")
logger.addHandler(handler)
logger.setLevel(logging.INFO)
```

### Log Levels

**DEBUG:** Detailed diagnostic information
- Token counts before/after optimization
- Retrieved document IDs from Qdrant
- LLM tool call decisions

**INFO:** General informational events
- Request received
- LLM model selected
- Response sent
- Token usage

**WARNING:** Potentially harmful situations
- Rate limit approaching
- Slow query (> 5 seconds)
- Fallback model used

**ERROR:** Error events that might still allow execution
- LLM API timeout with retry
- Qdrant connection issue with fallback
- Tool execution failure

**CRITICAL:** Very severe error events
- All LLM providers failed
- Database connection lost
- Service cannot start

### Error Types to Track

**LLM API Errors:**
- Rate limits (429)
- Timeouts
- Invalid requests
- Authentication failures

**Vector Search Errors:**
- Qdrant connection failures
- Search timeouts
- Index not found

**Application Errors:**
- Uncaught exceptions
- Validation errors
- Tool execution failures

### Alerting Strategy

**Critical Alerts (Immediate Notification):**
- Error rate > 50% over 2 minutes
- Service down (health check failing)
- All LLM providers failing

**Warning Alerts (Review Within Hour):**
- Error rate > 20% over 10 minutes
- Latency p95 > 5 seconds
- Cost exceeding 80% of daily budget

**Info Alerts (Daily Summary):**
- Total requests processed
- Top errors by type
- Cost summary

### Tools for Alerting

**Sentry:**
- Automatic error tracking
- Stack traces with context
- Issue grouping
- Email/Slack notifications

**PagerDuty:**
- On-call rotation
- Escalation policies
- Incident management

**Custom Webhooks:**
- Send to Slack/Discord
- Trigger automation
- Custom escalation logic

---

## 4. Dashboard Setup

### Essential Dashboards

**Real-Time Operations Dashboard:**

Metrics:
- Current RPS
- Active requests
- Error rate (last 5 min)
- Average latency
- LLM API status

Visualizations:
- Line chart: RPS over time
- Gauge: Error percentage
- Line chart: p50/p95/p99 latency
- Status indicators: Service health

**Cost Dashboard:**

Metrics:
- Today's spend
- Weekly/monthly trends
- Spend by model
- Spend by user
- Token usage trends

Visualizations:
- Bar chart: Cost per day (last 30 days)
- Pie chart: Cost by model
- Table: Top 10 users by cost
- Line chart: Token usage trend

**Error Dashboard:**

Metrics:
- Error count by type
- Error rate percentage
- Top error messages
- Errors by endpoint

Visualizations:
- Heatmap: Errors by hour/day
- Bar chart: Errors by type
- Table: Recent errors with context

**User Analytics Dashboard:**

Metrics:
- Active users (DAU/MAU)
- Queries per user
- Average session length
- Feature usage (tool calls)

Visualizations:
- Line chart: Daily active users
- Histogram: Queries per user distribution
- Bar chart: Most used features

### Dashboard Platforms

**Grafana (Recommended):**
- Open source
- Connects to multiple data sources
- Highly customizable
- Alerting built-in
- Self-hosted or cloud

**DataDog:**
- Commercial solution
- All-in-one monitoring
- APM tracing
- Log aggregation
- Higher cost

**Railway Built-in:**
- Basic metrics (CPU, Memory, Network)
- Request counts
- Good for MVP
- Limited customization

**Custom Dashboard:**
- Build with React/Next.js
- Query your database directly
- Full control over UI
- Maintenance overhead

### Dashboard Best Practices

**Keep it simple:**
- 5-7 key metrics per dashboard
- Clear titles and labels
- Consistent time ranges

**Actionable insights:**
- Metrics should drive decisions
- Include thresholds/targets
- Color code (green/yellow/red)

**Real-time updates:**
- Refresh every 10-30 seconds for operational dashboards
- Hourly for cost/analytics dashboards

---

## 5. User Analytics

### Usage Patterns

**Track User Behavior:**
- Total queries per user
- Query frequency (queries/day)
- Most common query types
- Time of day usage
- Features used (tasks, events, notes)

**Retention Metrics:**
- Daily active users (DAU)
- Weekly active users (WAU)
- Monthly active users (MAU)
- DAU/MAU ratio (stickiness)

**Engagement Metrics:**
- Average session length
- Queries per session
- Tool call success rate
- Return user rate

### Privacy Considerations

**What to Track:**
- Query metadata (timestamp, length, model)
- Feature usage counts
- Performance metrics
- Error occurrences

**What NOT to Track:**
- Full user message content
- Personal information
- Task/event details
- Sensitive data

**Anonymization:**
- Hash user IDs in analytics
- Aggregate data for reporting
- Retention policies (delete old analytics)

### Implementation

```python
def track_user_analytics(user_id, event_type, metadata=None):
    analytics_event = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id_hash": hash_user_id(user_id),  # Anonymize
        "event_type": event_type,  # "query", "create_task", "search"
        "metadata": metadata or {}
    }
    
    # Store in analytics database
    analytics_db.insert(analytics_event)
```

### Analytics Reports

**Weekly Report:**
- Total queries processed
- Active users
- Top features used
- Average response time
- Error summary

**Monthly Report:**
- User growth
- Retention metrics
- Cost analysis
- Feature adoption trends
- Top user feedback themes

---

## 6. Logging Best Practices

### Log What Matters

**Essential Logs:**
- Request start/end with ID
- LLM model and token usage
- Errors with full context
- Performance metrics
- User actions (tool calls)

**Avoid Logging:**
- Full user messages (PII)
- API keys or secrets
- Large request/response bodies
- Redundant information

### Correlation IDs

Use unique request IDs to trace through system:

```python
import uuid

def process_request(user_message):
    request_id = str(uuid.uuid4())
    
    logger.info({
        "request_id": request_id,
        "event": "request_start"
    })
    
    # Pass request_id through all operations
    qdrant_results = search_qdrant(query, request_id=request_id)
    llm_response = call_llm(prompt, request_id=request_id)
    
    logger.info({
        "request_id": request_id,
        "event": "request_end",
        "duration_ms": duration
    })
```

**Benefits:**
- Trace single request across logs
- Debug issues by following request ID
- Correlate errors with specific requests

### Log Retention

**Short-term (7-14 days):**
- DEBUG level logs
- High-volume INFO logs
- Development/staging logs

**Medium-term (30-90 days):**
- Production INFO logs
- WARNING logs
- Performance metrics

**Long-term (1 year+):**
- ERROR logs
- CRITICAL logs
- Cost/usage analytics
- Compliance/audit logs

**Storage:**
- Recent logs: Database or log aggregator
- Archive: S3, GCS (cheaper cold storage)
- Compress old logs

---

## 7. Recommended Tool Stack

### For MVP

**Logging:**
- Python logging module (structured JSON)
- Railway logs (built-in)
- Sentry (free tier for errors)

**Metrics:**
- Railway built-in metrics
- Custom metrics in PostgreSQL
- Simple Grafana on free tier

**Alerting:**
- Sentry error alerts
- Email notifications
- Slack webhooks

**Cost:** $0-20/month

### For Production

**Logging:**
- DataDog or New Relic (APM + Logs)
- OR ELK Stack (self-hosted)

**Metrics:**
- Prometheus + Grafana
- TimescaleDB for time-series data

**Alerting:**
- PagerDuty for on-call
- DataDog monitors
- Slack integrations

**Cost:** $100-500/month (depends on volume)

---

## 8. Implementation Checklist

**Logging:**
- Structured JSON logging
- Request correlation IDs
- Log levels properly set
- Sensitive data not logged
- Log rotation configured

**Cost Tracking:**
- Token usage logged per request
- Daily/weekly cost aggregations
- Budget alerts configured
- Per-user cost tracking

**Performance:**
- Latency tracking (p50, p95, p99)
- Component-level timing
- Resource utilization monitoring
- Performance baselines established

**Error Handling:**
- Sentry or equivalent integrated
- Error rate alerts
- Stack traces with context
- Error categorization

**Dashboards:**
- Operations dashboard (real-time)
- Cost dashboard (daily)
- Error dashboard
- User analytics

**Alerts:**
- Critical: Service down, high error rate
- Warning: Budget threshold, slow performance
- Info: Daily summaries

---

## 9. Monitoring Workflow

### Daily Checks

**Morning:**
- Review overnight error count
- Check cost vs budget
- Verify all services healthy
- Review any alerts

**Evening:**
- Daily cost summary
- High-level metrics review
- Plan for next day

### Weekly Reviews

- Cost trends
- Performance trends
- Top errors and patterns
- User growth/retention
- Capacity planning

### Monthly Reviews

- Total cost analysis
- Performance vs targets
- User analytics deep dive
- Infrastructure optimization opportunities
- Incident post-mortems

---

## Summary

**Key Takeaways:**

1. **Track costs obsessively** - LLM costs can surprise you
2. **Monitor latency at percentiles** - p95/p99 matter more than averages
3. **Structured logging** - JSON format for easy parsing and querying
4. **Alert on what matters** - Too many alerts = ignored alerts
5. **Dashboards for visibility** - Make metrics accessible to team
6. **Privacy first** - Don't log user content, only metadata
7. **Start simple, scale up** - MVP can use Railway + Sentry, expand later

**For Pixie MVP:**
- Railway built-in metrics
- Sentry for error tracking
- PostgreSQL for cost tracking
- Simple Grafana for dashboards
- Slack webhooks for alerts

With proper monitoring and logging, you'll maintain cost control, ensure performance, and quickly diagnose issues in production.
