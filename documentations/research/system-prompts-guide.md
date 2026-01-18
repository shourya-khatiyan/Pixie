# System Prompts Guide

## What Are System Prompts?

**Definition:** Instructions you (the developer) write that define how Pixie behaves.

**Key points:**
- Hidden from users
- Set once in your code
- Sent with every LLM query
- Control personality, tone, and behavior

### System Prompts vs Context Setting

**System Prompt:**
- Instructions that define AI's identity and behavior
- One component of the overall context
- Example: "You are Pixie, an AI productivity assistant..."

**Context Setting (broader):**
- System prompt + RAG context + conversation history + current query
- Everything the LLM needs to understand the situation

**Simple difference:** System prompt defines WHO the AI is. Context setting provides ALL information the AI needs (including the system prompt).

---

## Cost Impact

System prompts are sent with EVERY query, so length directly affects costs.

| Prompt Length | Tokens | Cost/Query | Cost/Month (200K queries/day) |
|--------------|--------|------------|-------------------------------|
| Verbose | 100 | $0.000015 | $90 |
| Concise | 25 | $0.0000037 | $22 |
| **Savings** | **75%** | **$0.000011** | **$68** |

**Recommendation:** Keep system prompts under 50 tokens.

---

## Effective System Prompt Structure

```python
SYSTEM_PROMPT = """
# Identity
You are Pixie, an AI productivity assistant.

# Purpose
Help users manage tasks, events, and conversations efficiently.

# Behavior
- Be concise and friendly
- Use natural, conversational language
- Proactively suggest relevant actions
- Don't repeat information already shown

# Tool Usage
Use provided functions for all data operations.
Never simulate data creation - always use actual tools.

# Constraints
- Ask for clarification when needed
- Don't make assumptions about task details
- Respect user privacy
"""
```

---

## Pixie System Prompt (Recommended)

```python
SYSTEM_PROMPT = """
You are Pixie, an AI productivity assistant for task and event management.

Behavior:
- Be friendly and concise (1-2 sentence responses when possible)
- Acknowledge user input before acting
- Use natural language ("I'll create that task" not "Task will be created")
- Proactively suggest next steps

Tool Usage:
- Use provided functions for all CRUD operations
- Never simulate or bypass tool calls
- Don't repeat details the user just provided

Boundaries:
- Ask for clarification if task details are unclear
- Don't make assumptions about priorities or deadlines
"""
# Tokens: ~75
```

---

## Personality and Tone

### Tone Options:

**Professional:**
```python
"Be professional and efficient. Use clear, business-appropriate language."
```

**Friendly (Recommended for Pixie):**
```python
"Be warm and conversational. Use casual language while remaining helpful."
```

### Behavioral Guidelines:

```python
"""
Do:
- Confirm actions ("I'll create that task")
- Suggest relevant next steps
- Remember conversation context

Don't:
- Apologize excessively
- Ask unnecessary questions
- Provide unsolicited advice
- Repeat information
"""
```

---

## Few-Shot Examples

**What:** Example interactions that show the LLM ideal behavior.

**When to use:** New users or complex edge cases only (expensive to send every time).

```python
FEW_SHOT_EXAMPLES = [
    {
        "role": "user",
        "content": "Add task to fix login bug by Friday"
    },
    {
        "role": "assistant",
        "content": "I'll add that task with a Friday deadline.",
        "tool_calls": [{
            "name": "create_task",
            "arguments": {"title": "Fix login bug", "due_date": "2026-01-17"}
        }]
    }
]

# Include conditionally
if is_first_interaction or is_complex_query:
    messages = [system_prompt] + FEW_SHOT_EXAMPLES + [user_message]
```

**Cost:** ~100 tokens per example pair.

---

## Context Window Management

### Problem:
LLMs have token limits (128K for GPT-4o). Long conversations can exceed limits.

### Context Breakdown:
- System prompt: 25-100 tokens
- Conversation history: ~50 tokens/message
- Few-shot examples: 100-200 tokens
- RAG context: 200-500 tokens
- Tool definitions: 50 tokens/tool

### Solution 1: Truncate Old Messages

```python
def prepare_conversation(messages: list, max_messages: int = 20):
    """Keep only recent messages"""
    if len(messages) > max_messages:
        return [messages[0]] + messages[-(max_messages-1):]
    return messages
```

### Solution 2: Summarize Old Context

```python
if len(history) > 30:
    summary = await llm.summarize(history[:20])
    messages = [system_prompt, summary] + history[20:]
```

### Solution 3: Dynamic Tool Selection

```python
def get_relevant_tools(message: str, all_tools: list) -> list:
    """Only include tools likely to be used"""
    if "task" in message.lower():
        return [t for t in all_tools if "task" in t["function"]["name"]]
    return all_tools
```

**Target:** Keep total context under 4K tokens for most queries.

---

## Prompt Versioning and Testing

### Version Control:

```python
SYSTEM_PROMPTS = {
    "v1": "You are Pixie, a productivity assistant...",
    "v2": "You are Pixie. Help users manage tasks...",
    "v3": "You are Pixie, an AI assistant for tasks and events..."
}

current_version = os.getenv("PROMPT_VERSION", "v3")
SYSTEM_PROMPT = SYSTEM_PROMPTS[current_version]
```

### A/B Testing:

```python
def get_system_prompt(user_id: str) -> str:
    """A/B test different prompts"""
    variant = hash(user_id) % 2
    return SYSTEM_PROMPT_A if variant == 0 else SYSTEM_PROMPT_B
```

### Metrics to Track:
- Tool call success rate
- Clarification questions needed
- Average response length
- User satisfaction (thumbs up/down)

---

## Best Practices

### DO:
- Keep prompts under 50 tokens
- Be specific about capabilities
- Use bullet points (easier to parse)
- Include tool usage instructions
- Version your prompts

### DON'T:
- Write long paragraphs
- Include examples in system prompt (use few-shot)
- Repeat obvious information
- Overexplain basic concepts

---

## Implementation Example

```python
# app/services/llm_orchestrator.py

SYSTEM_PROMPT = """
You are Pixie, an AI productivity assistant for task and event management.

Behavior:
- Be friendly and concise
- Acknowledge before acting
- Suggest next steps

Tool Usage:
- Use provided functions for all CRUD operations
- Never simulate tool calls

Boundaries:
- Ask for clarification when needed
- Don't assume priorities or deadlines
"""

class LLMOrchestrator:
    def __init__(self):
        self.system_prompt = SYSTEM_PROMPT
    
    async def process_message(self, message, history, tools):
        messages = [
            {"role": "system", "content": self.system_prompt},
            *history,
            {"role": "user", "content": message}
        ]
        
        # Truncate if too long
        if len(messages) > 20:
            messages = [messages[0]] + messages[-19:]
        
        response = await self.llm.chat(messages, tools=tools)
        return response
```

---

## Summary

**System prompts:**
- Define Pixie's behavior (for developers, not users)
- Cost scales with length (keep concise)
- Should be versioned and tested
- Manage context window carefully

**Recommended approach:**
1. Start with 50-token concise prompt
2. Use few-shot examples sparingly
3. Truncate conversation history to last 20 messages
4. Version and A/B test improvements
5. Monitor metrics and iterate
