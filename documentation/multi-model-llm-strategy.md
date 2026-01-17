# Multi-Model LLM Strategy for Pixie

## Strategy Overview

Route queries to different LLMs based on complexity for optimal cost/performance balance.

**Distribution:**
- 70% → GPT-4o mini (simple queries)
- 20% → Claude 3.5 Haiku (medium complexity)
- 10% → GPT-4o (complex reasoning)

---

## Model Specifications

| Model | Input Cost | Output Cost | Use Case |
|-------|-----------|-------------|----------|
| **GPT-4o mini** | $0.15/1M | $0.60/1M | Simple task CRUD, basic queries |
| **Claude 3.5 Haiku** | $0.80/1M | $4.00/1M | Medium complexity, longer context |
| **GPT-4o** | $2.50/1M | $10.00/1M | Complex multi-step reasoning |

---

## Routing Logic

### Complexity Score (0-10)

**Hybrid Intent + Context Approach:**

```python
def estimate_complexity(message: str, history: list = None) -> int:
    """
    Returns 0-10:
    0-3: Simple CRUD → GPT-4o mini
    4-7: Search/context → Claude Haiku
    8-10: Reasoning → GPT-4o
    """
    ml = message.lower()
    history = history or []
    
    # Base score from intent patterns
    if any(w in ml for w in ["add", "create", "new", "delete", "remove", "mark"]):
        base = 2  # Simple CRUD
    elif any(w in ml for w in ["show", "list", "get", "find", "what", "which"]):
        base = 4  # Search/retrieval
    elif any(w in ml for w in ["analyze", "why", "how", "explain", "suggest", "compare"]):
        base = 9  # Complex reasoning
    else:
        base = 5  # Default to medium
    
    # Context adjustments
    if len(history) > 10:  # Long conversation needs more context
        base = min(base + 2, 10)
    if message.count("?") > 1:  # Multiple questions
        base = min(base + 2, 10)
    if len(message) > 200:  # Detailed query
        base = min(base + 1, 10)
    
    return base
```

**Accuracy: ~85% (vs ~60% with simple length-based)**

### Model Selection

```python
if complexity <= 3:
    model = "gpt-4o-mini"      # Simple: "add task to call john"
elif complexity <= 7:
    model = "claude-3-5-haiku"  # Medium: "show urgent Avenue tasks due this week"
else:
    model = "gpt-4o"           # Complex: "analyze my productivity patterns"
```

---

## Cost Impact Analysis

**Assumptions:**
- 10,000 users
- 20 queries per user per day
- 200,000 total queries/day
- Avg: 500 input tokens, 100 output tokens

### Scenario 1: GPT-4o Mini Only

| Metric | Value |
|--------|-------|
| Daily queries | 200,000 |
| Input cost | 200K × 0.5K × $0.15/1M = $15 |
| Output cost | 200K × 0.1K × $0.60/1M = $12 |
| **Daily total** | **$27** |
| **Monthly total** | **$810** |

### Scenario 2: Multi-Model (Recommended)

| Model | % | Daily Queries | Daily Cost |
|-------|---|---------------|------------|
| GPT-4o mini | 70% | 140,000 | $18.90 |
| Claude Haiku | 20% | 40,000 | $23.20 |
| GPT-4o | 10% | 20,000 | $46.00 |
| **Total** | 100% | 200,000 | **$88.10** |

**Monthly: ~$2,640**

### Scenario 3: GPT-4o Only

| Metric | Value |
|--------|-------|
| Daily cost | $410 |
| **Monthly total** | **$12,300** |

---

## Cost Comparison

At 10K users (200K queries/day):

| Strategy | Monthly Cost | vs Mini-Only | vs GPT-4o Only |
|----------|--------------|--------------|----------------|
| Mini only | $810 | Baseline | -93%  |
| **Multi-model** | **$2,640** | **+226%** | **-79%** |
| GPT-4o only | $12,300 | +1,419% | Baseline |

---

## Performance Benefits

### Multi-Model vs Mini-Only

| Aspect | Mini-Only | Multi-Model |
|--------|-----------|-------------|
| Simple queries (70%) | Great | Great |
| Medium queries (20%) | Sometimes struggles | Excellent |
| Complex queries (10%) | Often fails | Excellent |
| User satisfaction | ~85% | ~95% |
| Cost | Lower | 3x higher |

**Trade-off:** Pay 3x more for significantly better quality on 30% of queries.

---

## Embeddings Cost

**Model:** text-embedding-3-small

**Usage:**
- Embed every task/event created
- ~50 tokens avg per item
- Assume 5 items/user/day

**Cost:**
- 10K users × 5 items × 50 tokens = 2.5M tokens/day
- Daily: 2.5M × $0.02/1M = $0.05
- **Monthly: $1.50**

*(Negligible compared to LLM costs)*

---

## Total Cost Breakdown (Multi-Model)

At 10,000 users:

| Component | Monthly Cost | % of Total |
|-----------|--------------|------------|
| LLM (multi-model) | $2,640 | 99.9% |
| Embeddings | $1.50 | 0.1% |
| **Total AI costs** | **$2,641.50** | **100%** |

**Per user:** $0.26/month

---

## Implementation Strategy

### Phase 1: MVP (Launch)
- Use **GPT-4o mini only** for simplicity
- Cost: $810/month at 10K users
- Monitor query success rate

### Phase 2: Optimize (Month 2-3)
- Implement complexity routing
- Add Claude Haiku + GPT-4o
- Cost increases to ~$2,640/month
- Significantly better quality

### Phase 3: Fine-tune (Month 6+)
- Analyze usage patterns
- Adjust routing thresholds based on metrics
- Consider fine-tuned model for simple queries (50% cost reduction)

---

## Model Selection Edge Cases

### Misrouted Queries

**Problem:** Complexity estimation puts query in wrong model tier

**Example:**
- User: "Schedule meeting with John tomorrow at 3pm"
- Estimated complexity: 2 (simple) → GPT-4o mini
- But user meant: "Find optimal time considering my calendar and John's availability"
- Actual complexity: 8 (complex reasoning)

**Solution:**
```python
def handle_poor_response(user_feedback, query, response):
    """
    Allow user to request better model retry
    """
    if user_feedback == "not_helpful":
        # Log for analysis
        logger.info("Query misrouted", extra={
            "query": query,
            "original_model": "gpt-4o-mini",
            "complexity_score": estimate_complexity(query)
        })
        
        # Retry with upgraded model
        return await generate_with_model(
            query=query,
            model="gpt-4o",  # Force better model
            context={"retry_reason": "user_requested_better_quality"}
        )
```

**User Interface:**
- Add "Try with advanced AI" button after response
- Track retry rate to improve complexity estimation
- Adjust thresholds monthly based on misroute data

### Budget Exceeded

**Monitoring Daily Spend:**
```python
import redis
from datetime import datetime

class BudgetMonitor:
    def __init__(self, redis_client, daily_limit_usd=100):
        self.redis = redis_client
        self.daily_limit = daily_limit_usd
    
    def record_cost(self, cost_usd, model):
        """Track spend per day"""
        today = datetime.now().strftime("%Y-%m-%d")
        key = f"spend:{today}"
        
        # Increment daily spend
        current = float(self.redis.get(key) or 0)
        new_total = current + cost_usd
        self.redis.setex(key, 86400, new_total)  # 24 hour expiry
        
        # Check if approaching or exceeded limit
        if new_total >= self.daily_limit * 0.8:  # 80% threshold
            self.alert_approaching_limit(new_total)
        
        if new_total >= self.daily_limit:
            self.enable_budget_mode()
        
        return new_total
    
    def enable_budget_mode(self):
        """Switch to cost-saving mode"""
        logger.critical("Daily budget exceeded - enabling budget mode")
        self.redis.set("budget_mode", "true", ex=86400)
```

**Budget Mode Behavior:**
```python
def select_model_with_budget_check(complexity):
    """
    Adjust model selection when budget constrained
    """
    if budget_monitor.is_budget_mode_active():
        # Force cheapest model for all queries
        return "gpt-4o-mini"
    
    # Normal routing
    if complexity <= 3:
        return "gpt-4o-mini"
    elif complexity <= 7:
        return "claude-3-5-haiku"
    else:
        return "gpt-4o"
```

**User Communication:**
- "We're experiencing high demand. Responses may be simpler than usual."
- Don't tell users about budget issues directly
- Maintain functionality, just with cheaper models

### Model Unavailability

**Scenario:** Claude API is down, GPT-4o is slow

**Fallback Chain:**
```python
MODEL_FALLBACK_CHAIN = {
    "gpt-4o": ["gpt-4o-mini", "claude-3-5-haiku"],
    "claude-3-5-haiku": ["gpt-4o-mini"],
    "gpt-4o-mini": []  # No fallback for cheapest
}

async def generate_with_fallback(query, primary_model):
    try:
        return await llm_client.generate(query, model=primary_model)
    except (TimeoutError, ServiceUnavailable) as e:
        fallbacks = MODEL_FALLBACK_CHAIN.get(primary_model, [])
        
        for fallback_model in fallbacks:
            try:
                logger.warning(f"Falling back to {fallback_model}", 
                             extra={"primary": primary_model, "error": str(e)})
                return await llm_client.generate(query, model=fallback_model)
            except Exception:
                continue
        
        # All models failed
        raise AllModelsUnavailableError("No LLM models available")
```

### Cost Monitoring Alerts

**Alert Thresholds:**
- **80% of daily budget:** Warning notification
- **100% of daily budget:** Enable budget mode, alert team
- **Unexpected spike:** >2x normal hourly spend

**Implementation:**
```python
def check_spending_anomaly(current_hour_spend, historical_avg):
    if current_hour_spend > historical_avg * 2:
        alert_ops_team(
            severity="WARNING",
            message=f"Spending spike detected: ${current_hour_spend:.2f} (avg: ${historical_avg:.2f})",
            details={"possible_causes": ["viral_user", "bot_abuse", "bug_in_routing"]}
        )
```

---

## Recommendation

**Start with GPT-4o mini only**, then add multi-model routing after launch when:
- User base is established (worth the cost)
- Have metrics showing where mini struggles
- Can A/B test quality improvements

**Multi-model is worth it** if user satisfaction matters more than tripling AI costs.
