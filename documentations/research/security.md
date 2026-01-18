# Security

## Overview

Security implementation for the Pixie AI service covering API key management, authentication, rate limiting, data isolation, and input validation.

---

## API Key Management

### Storage Strategy

**Environment Variables**
- Store all API keys in environment variables
- Never commit keys to version control
- Use `.env` files for local development
- Add `.env` to `.gitignore`

**Production Secrets**
- Use managed secrets services:
  - AWS: Secrets Manager or Parameter Store
  - GCP: Secret Manager
  - Railway/Render: Built-in environment variables
- Rotate keys quarterly or after suspected exposure
- Implement separate keys per environment (dev/staging/prod)

**Python Implementation**
```python
import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
```

---

## Authentication & Authorization

### Token Validation

**Request Flow**
1. Node.js backend validates user JWT token
2. Passes validated user_id to Python service
3. Python service trusts Node.js validation
4. No direct user authentication in Python service

**Inter-Service Security**
- Use shared secret for service-to-service communication
- Validate requests originate from Node.js backend
- Consider setting up internal network isolation

---

## Rate Limiting

### Strategy

**Per-User Limits**
- Track request count per user_id
- Implement sliding window algorithm
- Default: 100 requests per hour per user

**Implementation Approach**
```python
from collections import defaultdict
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_requests=100, window_hours=1):
        self.max_requests = max_requests
        self.window = timedelta(hours=window_hours)
        self.requests = defaultdict(list)
    
    def is_allowed(self, user_id):
        now = datetime.now()
        cutoff = now - self.window
        
        # Remove old requests
        self.requests[user_id] = [
            ts for ts in self.requests[user_id] if ts > cutoff
        ]
        
        if len(self.requests[user_id]) < self.max_requests:
            self.requests[user_id].append(now)
            return True
        return False
```

**Production Alternative**
- Use Redis for distributed rate limiting
- Enables horizontal scaling across multiple instances

---

## Prompt Injection Defense

### Overview

Prompt injection is the #1 security risk for LLM applications per OWASP LLM Top 10. Attackers manipulate LLM behavior by crafting malicious inputs that override system instructions.

### Attack Types

**Direct Prompt Injection**
- User attempts to override system prompts
- Jailbreaking attempts to bypass safety guardrails
- Requests to reveal system instructions

**Indirect Prompt Injection**
- Malicious instructions embedded in retrieved documents
- Hidden commands in user data processed by RAG
- External content manipulation

### Defense Strategies

**System Prompt Isolation**
- Use clear delimiters between system instructions and user input
- Explicitly instruct LLM to treat user input as data, not commands
- Include hardened instructions against prompt disclosure

**Input Validation Pattern Detection**
```python
import re

PROMPT_INJECTION_PATTERNS = [
    r'ignore (previous|above) (instructions|prompt)',
    r'system prompt',
    r'you are now',
    r'new instructions',
    r'disregard',
]

def detect_prompt_injection(query: str) -> bool:
    query_lower = query.lower()
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, query_lower):
            return True
    return False
```

**Output Filtering**
- Never expose system prompts in responses
- Filter outputs for leaked instructions
- Validate tool calls match user permissions

**Human-in-the-Loop**
- Require approval for high-impact actions
- Flag suspicious queries for review

---

## Input Validation & Sanitization

### User Input

**Query Validation**
- Maximum query length: 1000 characters
- Strip HTML tags and special characters
- Reject queries containing SQL injection patterns
- Validate against NoSQL injection attempts
- Check for prompt injection patterns

**Implementation**
```python
import re
from typing import Optional

def sanitize_query(query: str) -> Optional[str]:
    if not query or len(query) > 1000:
        return None
    
    # Check for prompt injection attempts
    if detect_prompt_injection(query):
        return None
    
    # Remove HTML tags
    query = re.sub(r'<[^>]+>', '', query)
    
    # Remove potentially dangerous characters
    query = re.sub(r'[;$\{\}]', '', query)
    
    return query.strip()
```

### LLM Output Validation

**Response Sanitization**
- Validate JSON structure before returning to frontend
- Strip any PII inadvertently included by LLM
- Validate tool call parameters match expected schema
- Implement output length limits
- Never trust LLM output as safe - always validate

---

## RAG Security

### Data Poisoning Risks

**Threat Model**
- Attackers inject malicious content into knowledge base
- Poisoned documents manipulate LLM responses
- Embedded instructions in retrieved context
- Knowledge corruption attacks

### Mitigation Strategies

**Document Validation**
- Verify source of all ingested documents
- Implement content review pipeline
- Scan for embedded malicious instructions
- Limit document sources to trusted origins

**Retrieval Security**
- Validate retrieved content before sending to LLM
- Implement anomaly detection for unusual retrievals
- Monitor for suspicious query patterns
- Log all document retrievals for audit

**Access Control on Retrieval**
- Enforce user_id filtering at query time
- Never retrieve documents user lacks permission for
- Validate ACLs during retrieval process

**Vector Database Integrity**
- Regular backups of vector collections
- Monitor for unauthorized modifications
- Implement versioning for document updates
- Audit trail for all data ingestion

---

## Object-Level Authorization

### OWASP API1:2023 - Broken Object Level Authorization

Most critical API security risk. Must validate authorization for every data access.

**Implementation Requirements**
- Validate user_id on every request
- Check ownership before returning any data
- Never trust client-provided IDs without verification
- Implement server-side authorization checks

**Tool Call Authorization**
```python
def validate_tool_call(user_id: str, tool_name: str, params: dict) -> bool:
    # Validate user owns the resources in params
    if tool_name in ["update_task", "delete_task", "get_task"]:
        task_id = params.get("task_id")
        if not verify_task_ownership(user_id, task_id):
            return False
    
    return True
```

---

## Data Isolation

### User Data Separation

**Qdrant Collections**
- Implement user_id as payload filter in all queries
- Never return documents without user_id match
- Consider separate collections per user for strict isolation

**Mandatory User Filtering**
```python
def search_user_documents(user_id: str, query_vector: list):
    # CRITICAL: Always enforce user_id filter
    results = qdrant_client.search(
        collection_name="user_documents",
        query_vector=query_vector,
        query_filter={
            "must": [
                {"key": "user_id", "match": {"value": user_id}}
            ]
        },
        limit=5
    )
    return results
```

### Qdrant Security Configuration

**API Key Authentication**
- Enable API key requirement for all Qdrant access
- Use read-only keys for query operations
- Rotate Qdrant API keys quarterly

**TLS Encryption**
- Enable TLS for all Qdrant connections
- Never transmit API keys over unencrypted connections
```python
from qdrant_client import QdrantClient

client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY"),
    https=True  # Enforce TLS
)
```

**JWT-Based RBAC (Advanced)**
- Implement JWT tokens for granular collection access
- Define roles with specific privileges
- Restrict access to sensitive endpoints

### Database Access

**Principle of Least Privilege**
- Python service only needs read access to PostgreSQL
- Use read-only database credentials
- Node.js backend handles all write operations

---

## CORS Configuration

### Policy

**Allowed Origins**
- Development: `http://localhost:3000`
- Production: Specific frontend domain only
- Never use wildcard `*` in production

**Headers**
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["Content-Type", "Authorization"],
)
```

---

## Network Security

### HTTPS/TLS

**Requirements**
- Enforce HTTPS in production
- Use Let's Encrypt for free SSL certificates
- Redirect all HTTP traffic to HTTPS
- Implement HSTS headers

**Service Communication**
- Use HTTPS for Node.js to Python API calls
- Consider VPC/private network for internal services
- Avoid exposing Python service to public internet

### Firewall Rules

**Recommended Setup**
- Only allow incoming traffic on port 443 (HTTPS)
- Restrict Python service to internal network only
- Whitelist only Node.js backend IP

---

## Logging & Monitoring

### Security Events

**Log These Events**
- Failed authentication attempts
- Rate limit violations
- Suspicious input patterns (prompt injection attempts)
- API key rotation events
- Unusual query patterns
- Anomalous RAG retrievals
- Tool call authorization failures
- Unusual error rates per user

**Avoid Logging**
- API keys or secrets
- Full user queries (PII concerns)
- Database credentials
- Session tokens
- LLM API responses containing user data

### Alerting

**Critical Alerts**
- Unusual spike in failed requests
- Rate limit threshold breaches
- API key rotation failures
- Service-to-service authentication failures
- Detected prompt injection attempts
- Suspicious RAG document retrievals
- Multiple authorization failures for same user

### Adversarial Testing

**Red Team Exercises**
- Regularly test against prompt injection patterns
- Simulate data poisoning attacks on RAG system
- Validate authorization bypass attempts fail
- Test rate limiting effectiveness
- Use tools like Promptfoo for automated testing

---

## Dependency Security

### Vulnerability Scanning

**Python Dependencies**
```bash
pip install pip-audit
pip-audit
```

**Automated Checks**
- Enable GitHub Dependabot
- Run security scans in CI/CD pipeline
- Update dependencies monthly

### Version Constraints

**Requirements Pinning**
- Pin major and minor versions
- Allow patch updates only
- Test thoroughly before major upgrades

---

## OWASP LLM Top 10 Coverage

**Implemented Mitigations**
- LLM01: Prompt Injection - Input validation, output filtering, system prompt isolation
- LLM02: Insecure Output Handling - Response validation, sanitization
- LLM03: Training Data Poisoning - Document validation, trusted sources (RAG security)
- LLM06: Sensitive Information Disclosure - PII filtering, output validation
- API1: Broken Object Level Authorization - User_id validation on all operations
- API4: Unrestricted Resource Consumption - Rate limiting implementation

---

## Security Incident Response

### Compromised API Key

**Detection:**
- Unusual API usage patterns
- API calls from unexpected locations
- Spike in error rates (invalid requests)
- GitHub commit scanner alerts
- Public leak reported

**Immediate Response (< 1 hour):**

1. **Rotate ALL affected keys immediately**
```bash
# Generate new keys
export NEW_OPENAI_KEY=$(generate_new_key)
export NEW_ANTHROPIC_KEY=$(generate_new_key)

# Update in all environments
kubectl set env deployment/python-ai OPENAI_API_KEY=$NEW_OPENAI_KEY
railway env set OPENAI_API_KEY=$NEW_OPENAI_KEY

# Revoke old keys in provider dashboards
```

2. **Audit recent API usage**
```python
async def audit_api_usage(since_timestamp):
    """Check for suspicious activity"""
    logs = await get_api_logs(since=since_timestamp)
    
    suspicious = []
    for log in logs:
        if log["ip"] not in KNOWN_IPS:
            suspicious.append(log)
        if log["user_agent"] != EXPECTED_UA:
            suspicious.append(log)
        if log["tokens_used"] > NORMAL_THRESHOLD * 10:
            suspicious.append(log)
    
    return suspicious
```

3. **Lock affected user accounts (if user-specific breach)**
```python
async def lock_compromised_accounts(user_ids):
    for user_id in user_ids:
        await db.update_user(user_id, {"account_status": "locked"})
        await send_security_notification(user_id)
```

4. **Notify stakeholders**
- Engineering team (Slack alert)
- Security team
- Affected users (within 24 hours)

**Post-Incident (< 24 hours):**
- Document what happened
- Calculate unauthorized usage cost
- Update security procedures
- Add detection for similar patterns

### DDoS Attack

**Detection:**
- Sudden traffic spike (10x normal)
- High rate of requests from few IPs
- Service degradation/timeouts
- Elevated error rates

**Mitigation Layers:**

**1. Rate Limiting (Already Implemented)**
```python
# Per-IP rate limiting
IP_RATE_LIMIT = (100, 60)  # 100 requests per minute

async def check_ip_rate_limit(request):
    client_ip = request.client.host
    
    # Track requests per IP
    key = f"ip_limit:{client_ip}"
    current = int(redis_client.get(key) or 0)
    
    if current >= IP_RATE_LIMIT[0]:
        raise HTTPException(429, "Too many requests from this IP")
    
    redis_client.incr(key)
    redis_client.expire(key, IP_RATE_LIMIT[1])
```

**2. CloudFlare/Railway Protection (Automatic)**
- Railway provides DDoS protection automatically
- CloudFlare (if using) has additional layer
- Enable "Under Attack" mode if needed

**3. Temporary Restrictions**
```python
DDOS_MODE_ACTIVE = False

async def enable_ddos_protection():
    global DDOS_MODE_ACTIVE
    DDOS_MODE_ACTIVE = True
    
    # Stricter rate limits
    USER_RATE_LIMIT = (10, 60)  # Reduce to 10 req/min
    IP_RATE_LIMIT = (50, 60)    # Reduce to 50 req/min
    
    logger.critical("DDoS protection enabled")

@app. middleware("http")
async def ddos_protection_middleware(request, call_next):
    if DDOS_MODE_ACTIVE:
        # Require authentication for ALL endpoints
        if not request.headers.get("Authorization"):
            return JSONResponse(
                {"error": "Authentication required"},
                status_code=401
            )
        
        # Additional verification
        await verify_request_signature(request)
    
    return await call_next(request)
```

**4. IP Whitelisting (Emergency)**
```python
ALLOWED_IPS = [
    "node-backend-ip",
    "staging-server-ip",
    "admin-office-ip"
]

async def emergency_whitelist_mode(request):
    """Only allow known IPs during severe attack"""
    if request.client.host not in ALLOWED_IPS:
        raise HTTPException(403, "Service temporarily restricted")
```

**5. Scaling Response**
- Horizontal scaling (add instances)
- If legitimate traffic spike: scale up
- If attack: enable protections and maintain minimal service

**Recovery:**
```python
async def disable_ddos_mode():
    global DDOS_MODE_ACTIVE
    DDOS_MODE_ACTIVE = False
    
    # Restore normal rate limits
    USER_RATE_LIMIT = (100, 3600)
    IP_RATE_LIMIT = (100, 60)
    
    logger.info("DDoS protection disabled - service normal")
```

### Data Breach (User Data Exposed)

**Immediate Actions:**
1. Isolate affected systems
2. Determine scope (which users, what data)
3. Preserve evidence logs
4. Notify security team and legal

**User Notification (Required by Law):**
- Within 72 hours of discovery (GDPR)
- Explain what data was exposed
- What actions users should take
- What company is doing to prevent recurrence

**Template:**
```
Subject: Important Security Notice

We detected unauthorized access to a limited portion of our systems on [DATE]. 

What happened:
- [Brief description]

What data was affected:
- [Specific data types]

What we're doing:
- [Security measures]

What you should do:
- [User actions if any]

We take security seriously and have implemented additional measures to prevent this from happening again.
```

### Malicious Document Ingestion

**Scenario:** User uploads document containing prompt injection or malicious content

**Detection:**
```python
def scan_document_for_threats(content):
    """Screen user-uploaded content"""
    threats = []
    
    # Check for prompt injection patterns
    if detect_prompt_injection(content):
        threats.append("prompt_injection")
    
    # Check for excessive special characters
    special_char_ratio = len(re.findall(r'[^a-zA-Z0-9\s]', content)) / len(content)
    if special_char_ratio > 0.3:
        threats.append("suspicious_encoding")
    
    # Check for embedded scripts
    if re.search(r'<script|javascript:|onerror=', content, re.I):
        threats.append("script_injection")
    
    return threats
```

**Response:**
```python
async def ingest_with_screening(user_id, content):
    threats = scan_document_for_threats(content)
    
    if threats:
        logger.warning("Malicious content detected",
                      extra={"user_id": user_id, "threats": threats})
        
        # Block ingestion
        return {
            "success": False,
            "error": "Content failed security screening"
        }
    
    # Safe to ingest
    return await ingest_document(user_id, content)
```

---

## Implementation Checklist

### Critical (Immediate)
- [ ] Move all API keys to environment variables
- [ ] Implement prompt injection detection and filtering
- [ ] Add mandatory user_id filtering in all Qdrant queries
- [ ] Enable object-level authorization checks
- [ ] Configure read-only database credentials

### High Priority
- [ ] Implement rate limiting per user with Redis
- [ ] Add comprehensive input sanitization
- [ ] Set up HTTPS/TLS for all services
- [ ] Enable TLS for Qdrant connections
- [ ] Configure CORS with specific origins
- [ ] Implement LLM output validation

### Medium Priority
- [ ] Add security event logging
- [ ] Set up service-to-service authentication
- [ ] Enable dependency vulnerability scanning
- [ ] Implement RAG document validation pipeline
- [ ] Add anomaly detection for suspicious queries
- [ ] Configure Qdrant API key authentication

### Ongoing
- [ ] Conduct regular adversarial testing
- [ ] Quarterly API key rotation
- [ ] Monthly dependency updates
- [ ] Review and update prompt injection patterns
