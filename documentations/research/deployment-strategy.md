# Deployment Strategy for Pixie AI Service

## Overview

This guide covers deploying the Python AI service with integration considerations for the Node.js backend. The architecture uses separate services communicating via HTTP/REST APIs.

---

## 1. Architecture Overview

### Service Separation

**Python AI Service (Your Responsibility):**
- LLM communication (OpenAI, Anthropic)
- Vector search (Qdrant)
- RAG pipeline
- Embedding generation
- AI decision-making

**Node.js Backend (Other Developer):**
- REST API endpoints
- User authentication
- Database operations (PostgreSQL)
- Business logic
- Frontend communication

### Integration Pattern

**Communication Flow:**
```
User Request → Node.js → Python AI Service → Node.js → User Response
```

**Key Principle:** Services are independent, communicate via REST APIs, and can be deployed/scaled separately.

---

## 2. Recommended MVP Deployment: Railway

### Why Railway for MVP

**Strongly Recommended for Pixie MVP Launch**

Railway is the ideal choice for your initial deployment:

✅ **Simplicity:** Git push to deploy - no complex configuration
✅ **Cost:** $5-20/month for MVP scale (vs $50-200 on AWS)
✅ **Speed:** Deploy in 5 minutes vs hours on cloud providers
✅ **Services:** Built-in PostgreSQL, Redis, monitoring
✅ **SSL:** Automatic HTTPS certificates
✅ **Both Stacks:** Python AND Node.js supported equally well

**Perfect For:**
- MVP launch and early validation
- Small teams without DevOps expertise
- Fast iteration and testing
- Budget-conscious projects

**When to Migrate:**
- After reaching ~50K+ users
- When needing advanced AWS/GCP services
- Enterprise compliance requirements
- Multi-region deployment needs

### Railway Deployment Steps

**1. Install Railway CLI:**
```bash
npm install -g @railway/cli
railway login
```

**2. Initialize Project:**
```bash
# In your Python AI service directory
railway init

# Link to GitHub repo
railway link
```

**3. Configure Services:**
```bash
# Add PostgreSQL (for Node.js backend)
railway add --database postgresql

# Add Redis (for caching)
railway add --database redis

# Note: Qdrant should be deployed separately or use Qdrant Cloud
```

**4. Set Environment Variables:**
```bash
# Set via CLI
railway variables set OPENAI_API_KEY=sk-...
railway variables set ANTHROPIC_API_KEY=sk-ant-...
railway variables set QDRANT_HOST=your-qdrant-instance.com

# Or use Railway dashboard (recommended for sensitive data)
```

**5. Deploy:**
```bash
# Automatic deployment from GitHub
git push origin main

# Railway automatically:
# - Detects Dockerfile
# - Builds image
# - Deploys to production
# - Issues SSL certificate
# - Provides public URL

# Manual deployment
railway up
```

**6. Get Service URL:**
```bash
railway status
# Returns: https://python-ai-production.up.railway.app
```

**7. Configure Node.js to Call Python Service:**
```javascript
// In Node.js backend .env
PYTHON_AI_URL=https://python-ai-production.up.railway.app

// Or use Railway's internal networking (private)
PYTHON_AI_URL=http://python-ai.railway.internal:8000
```

### Railway Configuration File

Create `railway.json` in project root:

```json
{
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile"
  },
  "deploy": {
    "numReplicas": 1,
    "sleepApplication": false,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### Qdrant Deployment Options

**Option 1: Qdrant Cloud (Recommended)**
- Managed service: https://cloud.qdrant.io
- Free tier available
- Automatic backups
- No maintenance

**Option 2: Railway Deployment**
- Deploy Qdrant as separate Railway service
- Use official Docker image: `qdrant/qdrant`
- Add persistent volume for data

```bash
# Deploy Qdrant on Railway
railway run qdrant/qdrant

# Get internal URL
railway variables set QDRANT_HOST=qdrant.railway.internal
railway variables set QDRANT_PORT=6333
```

### Cost Estimate (Railway)

**Monthly Cost Breakdown:**
- Python AI Service: $5-10 (512MB-1GB RAM)
- Node.js Backend: $5-10 (managed by other dev)
- PostgreSQL: $5 (Railway managed)
- Redis: $5 (Railway managed)
- Qdrant (if on Railway): $10
- **Total: ~$30-40/month for full stack**

**Scales with usage - only pay for what you use**

---

## 3. Alternative Platforms (Post-MVP)

### When Railway Isn't Enough

Consider migration when:
- User base > 50K active users
- Need multi-region deployment
- Require enterprise SLAs
- Advanced networking/security requirements

### AWS (Production Scale)

**Best For:** Enterprise production

**Setup Complexity:** High (1-2 weeks)

**Cost:** $100-500/month

**Services:**
- ECS Fargate (containers)
- RDS PostgreSQL
- ElastiCache Redis
- Application Load Balancer

### GCP Cloud Run

**Best For:** Serverless workloads

**Setup Complexity:** Medium (2-3 days)

**Cost:** Pay-per-use ($50-200/month typical)

**Benefits:**
- Automatic scaling to zero
- Good for variable traffic
- AI/ML service integration

---

## 4. Docker Containerization

### Why Docker for Python AI Service

**Benefits:**
- Consistent environment across dev/staging/prod
- Easy to share with Node.js developer (they can run your service locally)
- Portable across hosting platforms
- Isolates dependencies

### .dockerignore File

**Critical for reducing image size and build time.** Create `.dockerignore` in project root:

```
# Git
.git
.gitignore
.gitattributes

# Python cache
__pycache__
*.py[cod]
*$py.class
*.so
.Python

# Virtual environments
venv/
env/
ENV/
.venv

# IDE
.vscode/
.idea/
*.swp
*.swo

# Testing
.pytest_cache/
.coverage
htmlcov/
*.log

# Documentation
*.md
README.md
docs/

# Environment files
.env
.env.*

# Docker
Dockerfile
docker-compose.yml
.dockerignore

# OS
.DS_Store
Thumbs.db
```

**Benefits:**
- Reduces Docker context size (faster builds)
- Prevents sensitive files (.env) from entering image
- Smaller final image size
- Better security (no git history in production)

### Basic Dockerfile Structure

```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Multi-Stage Build (Production Recommended)

**Reduces final image size by 50-70%** by separating build dependencies from runtime.

```dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Copy only installed packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser . .

# Set PATH for user-installed packages
ENV PATH=/home/appuser/.local/bin:$PATH

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Benefits:**
- Build tools (gcc, build-essential) not in final image
- Final image only contains runtime dependencies
- Runs as non-root user (security best practice)
- Typical size reduction: 800MB → 300MB

### Docker Compose for Local Development

Create `docker-compose.yml` for running full stack locally:

```yaml
version: '3.8'

services:
  python-ai:
    build: ./python-service
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - QDRANT_HOST=qdrant
      - QDRANT_PORT=6333
    depends_on:
      - qdrant

  qdrant:
    image: qdrant/qdrant
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

  # Node.js backend (managed by other developer)
  nodejs-backend:
    build: ./nodejs-backend
    ports:
      - "3000:3000"
    environment:
      - PYTHON_AI_URL=http://python-ai:8000
      - DATABASE_URL=${DATABASE_URL}
    depends_on:
      - python-ai

volumes:
  qdrant_data:
```

**Integration Benefit:** Other developer can run entire stack with `docker-compose up`

### Security Best Practices

**Run as Non-Root User:**

Never run containers as root in production. Multi-stage build above shows proper implementation.

```dockerfile
# Create user with specific UID
RUN useradd -m -u 1000 appuser

# Change ownership
RUN chown -R appuser:appuser /app

# Switch to user
USER appuser
```

**Image Security Scanning:**

Integrate security scanning in CI/CD pipeline:

```yaml
# .github/workflows/security.yml
- name: Scan Docker image
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: 'python-ai:latest'
    format: 'sarif'
    severity: 'CRITICAL,HIGH'
```

**Secrets Management:**

- NEVER hardcode secrets in Dockerfile or code
- Use environment variables for all sensitive data
- In production, use platform secret managers:
  - Railway: Environment variables (encrypted at rest)
  - AWS: Secrets Manager or Parameter Store
  - GCP: Secret Manager

```python
# Good: Load from environment
import os
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Bad: Hardcoded (NEVER do this)
OPENAI_API_KEY = 'sk-...'  # NO!
```

**Base Image Security:**

- Use official images only (python:3.11-slim)
- Pin specific versions (not 'latest')
- Regularly update base images
- Scan for vulnerabilities

```dockerfile
# Good: Specific version
FROM python:3.11.7-slim

# Risky: Always latest
FROM python:latest
```

---

## 4. Environment Management

### Environment Separation

**Development:**
- Local machines
- Fake/test API keys where possible
- Mock data in Qdrant
- Fast iteration

**Staging:**
- Mirror of production
- Real API keys (separate accounts)
- Test data
- Pre-deployment validation

**Production:**
- Live user data
- Production API keys
- Monitoring enabled
- Strict access control

### Environment Variables

**Python AI Service Requirements:**

```bash
# LLM APIs
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Vector Database
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_API_KEY=optional-if-cloud

# Service Configuration
ENVIRONMENT=production  # dev, staging, production
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
PORT=8000

# Integration
ALLOWED_ORIGINS=https://yourdomain.com,https://api.yourdomain.com
```

### Configuration Management

**Option 1: .env Files (Development)**
```
.env.development
.env.staging
.env.production
```

**Option 2: Platform Secrets (Production)**
- Railway: Environment variables in dashboard
- AWS: Systems Manager Parameter Store
- GCP: Secret Manager

**Security Best Practices:**
- NEVER commit .env files with real keys
- Use platform secret managers in production
- Rotate API keys regularly
- Separate keys per environment

---

## 5. Integration Architecture

### REST API Endpoints

**Python AI Service Exposes:**

```
POST /generate
- Input: { "user_id": "123", "message": "create task..." }
- Output: { "response": "...", "actions": [...] }

POST /embed
- Input: { "texts": ["text1", "text2"] }
- Output: { "embeddings": [[...], [...]] }

POST /search
- Input: { "user_id": "123", "query": "...", "limit": 5 }
- Output: { "results": [...] }

GET /health
- Output: { "status": "healthy", "version": "1.0.0" }
```

**Node.js Backend Calls Python Service:**

```javascript
// Example integration from Node.js
const response = await fetch('http://python-ai:8000/generate', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${INTERNAL_API_KEY}`
  },
  body: JSON.stringify({
    user_id: userId,
    message: userMessage
  })
});
```

### Authentication Between Services

**Internal API Key:**
- Generate shared secret for service-to-service auth
- Node.js includes in Authorization header
- Python validates before processing

```python
# Python service validates
if request.headers.get('Authorization') != f'Bearer {INTERNAL_API_KEY}':
    raise HTTPException(status_code=401)
```

**Network Security:**
- Services in same private network (no public exposure of Python service)
- OR use firewall rules to restrict access
- Only Node.js can reach Python service

### Error Handling Across Services

**Python Service Returns Structured Errors:**

```python
{
  "success": false,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "OpenAI rate limit hit",
    "retry_after": 60
  }
}
```

**Node.js Handles Gracefully:**
- Retry with backoff
- Return user-friendly message
- Log for debugging

---

## 6. SSL/TLS ConfigurationImplementation Plan


### Automatic SSL (Railway, Vercel)

**Railway:**
- Automatic SSL certificates via Let's Encrypt
- Auto-renewal
- No configuration needed
- Custom domains supported

**Setup:**
1. Deploy service
2. Add custom domain in dashboard
3. Update DNS (CNAME to Railway)
4. SSL certificate issued automatically

### Manual SSL (AWS, GCP, DigitalOcean)

**AWS (Application Load Balancer):**
1. Request certificate in AWS Certificate Manager (ACM)
2. Validate domain ownership
3. Attach certificate to load balancer
4. Configure listeners (HTTP → HTTPS redirect)

**Let's Encrypt (Self-Managed):**
```bash
# Using Certbot
certbot --nginx -d api.yourdomain.com
```

**Recommendation:** Use platform-managed SSL when possible (less maintenance)

---

## 7. Domain and DNS Setup

### Domain Structure

**Recommended:**
- Main app: `pixie.yourdomain.com`
- Node.js API: `api.yourdomain.com`
- Python AI (internal): `ai-internal.yourdomain.com` (or not exposed publicly)

### DNS Configuration

**For Railway:**
```
Type: CNAME
Name: api
Value: your-service.up.railway.app
TTL: 3600
```

**For AWS:**
```
Type: A (or ALIAS)
Name: api
Value: [Load Balancer IP/DNS]
TTL: 300
```

### Public vs Private Services

**Python AI Service Options:**

**Option 1: Internal Only (Recommended)**
- Not exposed to internet
- Only accessible from Node.js backend
- More secure
- Use private networking features

**Option 2: Public with Auth**
- Exposed to internet
- Requires API key authentication
- Use HTTPS only
- Rate limiting essential

---

## 8. Deployment Workflow

### Git-Based Deployment (Railway, Vercel)

1. Push code to GitHub
2. Railway detects changes
3. Builds Docker image
4. Deploys automatically
5. Health check passes
6. Traffic switches to new version

### CI/CD Pipeline (AWS, GCP)

```yaml
# .github/workflows/deploy.yml
name: Deploy Python AI Service

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Build Docker image
        run: docker build -t python-ai .
      - name: Push to registry
        run: docker push registry/python-ai
      - name: Deploy to production
        run: ./deploy.sh
```

### Deployment Checklist

Before deploying:
- Environment variables configured
- Health endpoint working
- Tests passing
- API documentation updated (for Node.js developer)
- Database migrations applied (if any)
- Qdrant collections initialized

After deploying:
- Health check returns 200
- Logs show no errors
- Test integration with Node.js service
- Monitor error rates
- Verify API response times

---

## 9. Monitoring and Health Checks

### Health Endpoint

```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "dependencies": {
            "openai": check_openai(),
            "qdrant": check_qdrant()
        }
    }
```

### Monitoring Setup

**Metrics to Track:**
- Request latency (p50, p95, p99)
- Error rate (5xx errors)
- LLM API success rate
- Qdrant search latency
- Memory/CPU usage

**Tools:**
- Railway: Built-in metrics
- AWS: CloudWatch
- GCP: Cloud Monitoring
- Third-party: DataDog, New Relic

---

## 10. Scaling Considerations

### Vertical Scaling

**When to scale up:**
- CPU usage > 80% sustained
- Memory usage > 85%
- Request latency increasing

**How:**
- Increase instance size
- More RAM for Qdrant caching
- More CPU for LLM processing

### Horizontal Scaling

**Python AI Service is Stateless:**
- Multiple instances can run in parallel
- Load balancer distributes traffic
- Each instance connects to shared Qdrant

**Configuration:**
- Railway: Adjust replica count
- AWS: Auto Scaling Group
- GCP: Instance count in Cloud Run

**Important:** Qdrant should be separate service (not bundled with Python app)

---

## 11. API Gateway & Service Mesh Guidance

### Do You Need an API Gateway?

**What It Does:**
- Single entry point for external clients
- Handles authentication, rate limiting, routing
- Request/response transformation
- Examples: Kong, Apigee, AWS API Gateway

**For Pixie MVP: NO**

Your architecture:
- 2 services (Node.js + Python AI)
- Node.js already acts as entry point for external clients
- Node.js handles authentication and routes to Python service
- Adding API gateway adds unnecessary complexity

**When You Would Need It:**
- 5+ microservices with different clients
- Complex routing rules across many services
- Need centralized rate limiting across all APIs
- Multiple client types (web, mobile, IoT) with different needs

### Do You Need a Service Mesh?

**What It Does:**
- Manages service-to-service communication
- Automatic mTLS encryption between services
- Circuit breaking, retries, timeouts
- Distributed tracing and observability
- Examples: Istio, Linkerd

**For Pixie MVP: NO**

Your architecture:
- Only 2 services communicating
- Simple HTTP REST calls
- Internal network (private communication)
- Can implement retry logic in application code

**When You Would Need It:**
- 10+ microservices with complex communication patterns
- Need zero-trust security (mTLS everywhere)
- Advanced traffic management (canary deployments, A/B testing)
- Polyglot environment needing uniform observability

**Important:** Service meshes are language-agnostic (work with Python + Node.js), but add operational complexity. Only adopt when managing complexity of existing system, not to prevent future complexity.

### Recommended Path for Pixie

**MVP (Now):**
- Direct HTTP calls: Node.js → Python AI
- Internal API key for authentication
- Application-level retry logic
- Simple and effective

**5-10 Services:**
- Consider API gateway if multiple client types
- Still no service mesh needed
- Use load balancers and application-level patterns

**10+ Services:**
- API gateway: Likely beneficial
- Service mesh: Evaluate based on needs
- Assess operational overhead vs benefits

---

## 12. Database Backups

### PostgreSQL Backups (Node.js Responsibility)

**Railway Automatic Backups:**
- Daily automated backups (last 7 days)
- Point-in-time recovery
- One-click restore from dashboard

**Manual Backup:**
```bash
# Backup from Railway
railway run pg_dump > backup_$(date +%Y%m%d).sql

# Restore
railway run psql < backup_20260117.sql
```

### Qdrant Backups (Your Responsibility)

**Daily Snapshot Script:**

```python
import schedule
from qdrant_client import QdrantClient
import boto3  # For S3 upload
from datetime import datetime

client = QdrantClient(host=QDRANT_HOST, port=6333)

async def backup_qdrant():
    """Create and upload Qdrant snapshot"""
    try:
        # Create snapshot
        snapshot_info = client.create_snapshot(
            collection_name="user_documents"
        )
        
        # Download snapshot
        snapshot_path = f"./backups/qdrant_{datetime.now().strftime('%Y%m%d')}.snapshot"
        client.download_snapshot(
            collection_name="user_documents",
            snapshot_name=snapshot_info.name,
            output_path=snapshot_path
        )
        
        # Upload to S3 (or other cloud storage)
        s3 = boto3.client('s3')
        s3.upload_file(
            snapshot_path,
            'pixie-backups',
            f "qdrant/{snapshot_info.name}"
        )
        
        logger.info(f"Qdrant backup completed: {snapshot_info.name}")
        
        # Cleanup old local backups
        cleanup_old_backups(days=7)
        
    except Exception as e:
        logger.error(f"Qdrant backup failed: {e}")
        await alert_ops_team("Qdrant backup failure", str(e))

# Run daily at 2 AM
schedule.every().day.at("02:00").do(backup_qdrant)
```

**Restore from Snapshot:**

```python
async def restore_qdrant_snapshot(snapshot_name):
    """Restore Qdrant from backup"""
    # Download from S3
    s3 = boto3.client('s3')
    local_path = f"./restore/{snapshot_name}"
    s3.download_file(
        'pixie-backups',
        f"qdrant/{snapshot_name}",
        local_path
    )
    
    # Restore to Qdrant
    client.recover_snapshot(
        collection_name="user_documents",
        snapshot_path=local_path
    )
    
    logger.info(f"Qdrant restored from {snapshot_name}")
```

### Backup Schedule

**Recommended:**
- **Daily:** Automated snapshots
- **Weekly:** Full backup to cloud storage (S3, GCS)
- **Monthly:** Archive for compliance (if needed)
- **Pre-Migration:** Manual backup before any schema changes

**Retention Policy:**
- Daily backups: 7 days
- Weekly backups: 4 weeks
- Monthly backups: 12 months

### Disaster Recovery Plan

**RTO (Recovery Time Objective):** 1 hour
**RPO (Recovery Point Objective):** 24 hours

**Recovery Steps:**
1. Deploy new Qdrant instance
2. Restore from latest snapshot (< 5 minutes)
3. Update environment variables with new Qdrant URL
4. Restart Python AI service
5. Verify search functionality

---

## 13. Best Practices Summary

**Integration:**
- Clear API contract between services
- Comprehensive API documentation
- Versioned endpoints (/v1/generate)
- Structured error responses

**Security:**
- Internal API keys for service-to-service
- HTTPS everywhere
- Don't expose Python service publicly if possible
- Environment-specific secrets

**Deployment:**
- Docker for consistency
- Automated deployments
- Zero-downtime deployments (health checks)
- Rollback plan

**Monitoring:**
- Health checks on all services
- Error alerting
- Performance metrics
- Log aggregation

---

## 13. Quick Start: Railway Deployment

**Step 1: Prepare Repository**
```
pixie-python-ai/
├── Dockerfile
├── requirements.txt
├── main.py
└── .railwayignore
```

**Step 2: Create Railway Project**
1. Connect GitHub repository
2. Railway detects Dockerfile
3. Configure environment variables
4. Deploy

**Step 3: Configure in Node.js Backend**
```javascript
const PYTHON_AI_URL = process.env.PYTHON_AI_URL;
// Railway provides internal URL
```

**Step 4: Test Integration**
- Health check from Node.js
- Test API endpoint
- Verify logs

**Total Time:** 15-30 minutes for first deployment

---

## Summary

**For Pixie MVP:**

1. **Hosting:** Railway (both Python AI and Node.js)
2. **Docker:** Yes (consistent environments)
3. **Environments:** Dev (local), Staging, Production
4. **SSL:** Automatic via Railway
5. **Integration:** REST API with internal auth
6. **Monitoring:** Railway built-in + health checks

**Key Integration Points:**
- Python service exposes REST API
- Node.js calls Python service for AI operations
- Services communicate via HTTP in private network
- Shared environment variables for configuration
- Health checks ensure service availability

This architecture allows independent development and deployment while maintaining clean integration between services.
