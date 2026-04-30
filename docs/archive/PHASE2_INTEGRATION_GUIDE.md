# Phase 2 Integration Guide: Queue Infrastructure & Fallback Chain

**Status:** Implementation complete (Phase 2 MVP)  
**Created:** 2026-04-25  
**Files:** 4 new modules + 1 migration  

---

## What's Implemented

### Phase 2 Deliverables

#### 1. **src/guppy/inference/queue_executor.py** (420 lines)
Core job execution engine with persistent retry tracking.

**Key classes:**
- `QueueExecutor` — Manages job dequeuing, execution, retry scheduling, and metrics persistence
  - `process_next_job()` — Dequeue, execute, and update job status with exponential backoff
  - `enqueue()` — Create new inference request in queue
  - `get_job_status()` — Poll current job state
  - `get_attempt_history()` — Retrieve retry audit trail

**Key features:**
- Dequeues by (status='queued', priority ASC, created_at ASC)
- Executes via ProviderRegistry with fallback chain
- On timeout/failure: calculates next_retry_at = last_attempt + (backoff_multiplier ^ retry_count)
- Returns job to 'queued' status if retries available
- On max retries exceeded: marks as 'failed' with final error
- Records all attempts in inference_queue_attempts table for audit
- Returns (success/failure, response_text, InferenceMetadata)

#### 2. **src/guppy/inference/queue_scheduler.py** (360 lines)
Background task management for continuous queue processing.

**Key classes:**
- `QueueScheduler` — Monitors queue and coordinates job processing
  - `start()` — Long-running daemon loop (continuous processing)
  - `process_ready_jobs(limit=10)` — Batch processing mode (call periodically)
  - `reschedule_timeout_jobs()` — Transition 'timeout' status back to 'queued'
  - `cleanup_stuck_jobs(max_age_seconds=3600)` — Recover abandoned jobs
  - `get_queue_metrics()` — Queue health dashboard

- `QueueSchedulerDaemon` — Convenience wrapper for managed task lifecycle

**Key features:**
- Configurable poll interval (default 5 seconds)
- Graceful shutdown via `stop()` method
- Automatic stuck job detection and recovery
- Real-time queue health metrics (queued/executing/success/failed counts, avg latency, total cost)
- Per-status job accounting with age tracking

#### 3. **src/guppy/_db_models.py** (160 lines)
SQLAlchemy ORM models mapping to Alembic migrations.

**Models:**
- `ProviderConfig` — Provider registry (mirrors migration 0002)
- `InferenceMetrics` — Per-inference metrics table (mirrors migration 0002)
- `InferenceQueue` — Persistent job queue with retry metadata (mirrors migration 0003)
- `InferenceQueueAttempt` — Retry audit trail (mirrors migration 0003)

**Key features:**
- Relationships: InferenceQueue ↔ InferenceQueueAttempt (one-to-many)
- All indices from migrations are defined as SQLAlchemy Index objects
- Foreign key: job_id → inference_queue.id with CASCADE delete
- Datetime defaults use `datetime.utcnow` (UTC timestamp capture)

#### 4. **src/guppy/api/routes_queue.py** (300 lines)
REST API endpoints for queue management.

**Endpoints:**
- `POST /api/queue/enqueue` — Enqueue inference request
  - Input: {prompt, system_prompt, task_type, preferred_provider, max_retries, priority}
  - Output: {job_id, status, poll_url}
  
- `GET /api/queue/job/{job_id}` — Poll job status
  - Output: {job_id, status, response, error, provider_used, latency_ms, cost_usd, retry_count, next_retry_at, ...}
  
- `GET /api/queue/job/{job_id}/history` — Get retry attempt history
  - Output: {job_id, attempts: [{attempt_number, provider, model, latency_ms, success, error, ...}]}
  
- `GET /api/queue/status` — Overall queue health
  - Output: {status: 'healthy|degraded|overloaded', metrics: {...}}
  
- `GET /api/queue/metrics` — Detailed performance metrics
  - Output: {total_jobs, queued_count, success_rate, retry_rate, avg_latency_ms, total_cost_usd, ...}

**Key features:**
- All endpoints require rate limit auth via `ctx.require_rate_limit()`
- Health status determination: 'degraded' if queued > 20 or oldest age > 600s; 'overloaded' if queued > 50
- Automatic success_rate and retry_rate calculation

#### 5. **migrations/0003_inference_queue.py** (SQL Schema)
Database schema for persistent queue (already created in Phase 1).

---

## Integration Checklist

### Step 1: Database Setup
```bash
# Run Alembic migration to create queue tables
alembic upgrade head

# Verify tables created:
sqlite3 guppy.db ".tables"
# Should show: inference_queue, inference_queue_attempts
```

### Step 2: Import ORM Models
In your application's database initialization (e.g., `src/guppy/api/server.py`):

```python
from src.guppy._db_models import (
    ProviderConfig,
    InferenceMetrics,
    InferenceQueue,
    InferenceQueueAttempt,
)

# Ensure models are registered with SQLAlchemy before creating engine
# Models auto-register via declarative_base when imported
```

### Step 3: Wire Queue Router into FastAPI
In `src/guppy/api/server.py` (or wherever routes are registered):

```python
from src.guppy.api.routes_queue import build_queue_router

# In app startup:
queue_router = build_queue_router(ctx)
app.include_router(queue_router)
```

### Step 4: Start Queue Scheduler
In your FastAPI startup event:

```python
from src.guppy.inference.queue_scheduler import QueueSchedulerDaemon
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

@app.on_event("startup")
async def startup():
    # Create async session factory
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    
    # Create scheduler daemon
    db_session = session_factory()
    scheduler_daemon = QueueSchedulerDaemon(db_session, poll_interval_seconds=5.0)
    
    # Start scheduler task
    app.state.scheduler_task = asyncio.create_task(scheduler_daemon.run())
    app.state.scheduler = scheduler_daemon

@app.on_event("shutdown")
async def shutdown():
    # Graceful scheduler shutdown
    if hasattr(app.state, 'scheduler'):
        await app.state.scheduler.stop(timeout_seconds=10.0)
```

### Step 5: Update Chat Endpoint (Optional)
To use queue for all inference (instead of direct execution):

```python
# In routes_realtime.py or chat endpoint:

from src.guppy.inference.queue_executor import QueueExecutor

@router.post("/chat/message")
async def chat_message(request: ChatRequest, ctx: ServerContext):
    executor = QueueExecutor(ctx.db, get_provider_registry())
    
    # Enqueue instead of direct inference
    job_id = await executor.enqueue(
        prompt=request.message,
        system_prompt=request.system_prompt,
        task_type="complex",
        user_id=ctx.user_id,
        session_id=request.session_id,
    )
    
    # Return job ID to client
    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Inference request queued",
    }

# Client polls: GET /api/queue/job/{job_id}
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI REST API                         │
├─────────────────────────────────────────────────────────────┤
│  routes_queue.py (endpoints)                                │
│  ├─ POST /api/queue/enqueue                                 │
│  ├─ GET  /api/queue/job/{id}                                │
│  ├─ GET  /api/queue/job/{id}/history                        │
│  ├─ GET  /api/queue/status                                  │
│  └─ GET  /api/queue/metrics                                 │
└─────────────────────────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────────────────────────┐
│         Queue Executor & Scheduler (Async)                  │
├─────────────────────────────────────────────────────────────┤
│  QueueExecutor                 QueueScheduler               │
│  ├─ enqueue()                  ├─ start() [daemon]           │
│  ├─ process_next_job()         ├─ process_ready_jobs()       │
│  ├─ get_job_status()           ├─ get_queue_metrics()        │
│  ├─ get_attempt_history()      ├─ cleanup_stuck_jobs()       │
│  └─ _record_attempt()          └─ reschedule_timeout_jobs()  │
└─────────────────────────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────────────────────────┐
│         Provider Registry (Fallback Chain)                  │
├─────────────────────────────────────────────────────────────┤
│  ProviderRegistry              LocalProviderClient          │
│  ├─ infer_with_fallback()      ├─ infer() [Ollama HTTP]      │
│  ├─ build_fallback_chain()     ├─ health_check()             │
│  ├─ health_check_all()         └─ list_models()              │
│  └─ get_client()                                             │
└─────────────────────────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────────────────────────┐
│              SQLite Database (persistent)                   │
├─────────────────────────────────────────────────────────────┤
│  inference_queue               inference_queue_attempts     │
│  ├─ id (PK)                    ├─ id (PK)                    │
│  ├─ status                     ├─ job_id (FK)                │
│  ├─ priority                   ├─ attempt_number             │
│  ├─ prompt                     ├─ provider                   │
│  ├─ next_retry_at              ├─ latency_ms                 │
│  ├─ response                   ├─ success                    │
│  ├─ error_message              └─ cost_usd                   │
│  └─ cost_usd                                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Execution Flow

### Enqueue → Process → Retry Example

```
1. CLIENT REQUEST
   POST /api/queue/enqueue { prompt: "...", task_type: "complex" }
   ↓
   QueueExecutor.enqueue() creates InferenceQueue record with:
   - status = 'queued'
   - retry_count = 0
   - created_at = now
   ↓
   Returns: job_id = "abc-123-..."

2. BACKGROUND SCHEDULER (continuous loop every 5s)
   QueueScheduler.start() / process_next_job()
   ↓
   SELECT * FROM inference_queue
   WHERE status='queued'
   ORDER BY priority ASC, created_at ASC
   LIMIT 1
   ↓
   Found job_id="abc-123"
   Update: status='executing', last_attempt_at=now
   ↓
   Execute: registry.infer_with_fallback(
       prompt=job.prompt,
       task_type=job.task_type,
       preferred_model=job.preferred_provider
   )

3a. SUCCESS PATH
    Response received from provider
    ↓
    Update job:
    - status = 'success'
    - response = "..."
    - provider_used = "anthropic"
    - execution_ms = 245.5
    - cost_usd = 0.0125
    - completed_at = now
    ↓
    Insert InferenceQueueAttempt record
    - attempt_number = 1
    - success = 1
    ↓
    CLIENT POLLS: GET /api/queue/job/abc-123
    Returns: status='success', response='...'

3b. FAILURE PATH (timeout or error)
    Exception caught from provider
    ↓
    Check: retry_count (0) < max_retries (3)?
    ↓
    YES → Reschedule
    Update job:
    - retry_count = 1
    - next_retry_at = last_attempt_at + (2.0 ^ 1 * 2.0) = now + 4 seconds
    - status = 'queued'  ← Return to queue
    ↓
    Insert InferenceQueueAttempt record
    - attempt_number = 1
    - success = 0
    - error = "timeout"
    ↓
    [Wait 4 seconds]
    Loop: process_next_job() finds job again
    ↓
    ATTEMPT 2: Try next provider in fallback chain
    (e.g., if local failed, try anthropic)
    ↓
    If success → mark 'success', completed
    If failure → reschedule (next_retry_at + 8 seconds)

3c. MAX RETRIES EXCEEDED
    retry_count (3) >= max_retries (3)
    ↓
    Update job:
    - status = 'failed'
    - completed_at = now
    ↓
    Final failure recorded
    CLIENT POLLS: GET /api/queue/job/abc-123
    Returns: status='failed', error='...'
```

---

## Configuration

### Environment Variables
Add to `.env.local` (or `GUPPY_*` settings):

```bash
# Queue settings
QUEUE_POLL_INTERVAL_SECONDS=5.0
QUEUE_MAX_STUCK_JOB_AGE_SECONDS=3600
QUEUE_DEGRADED_THRESHOLD=20  # Jobs in queue before "degraded"
QUEUE_OVERLOADED_THRESHOLD=50  # Jobs in queue before "overloaded"
```

### Database Connection
Queue requires async SQLAlchemy session. Ensure your engine is created with:

```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    "sqlite+aiosqlite:///guppy.db",
    echo=False,  # Set True for SQL debug logging
)
```

---

## Monitoring & Debugging

### Check Queue Health
```bash
# From web UI:
GET /api/queue/status
→ Returns: health status + queue metrics

# Or directly in Python:
scheduler = QueueScheduler(db_session)
metrics = await scheduler.get_queue_metrics()
print(metrics)
```

### View Job Details
```bash
# Poll job status:
GET /api/queue/job/{job_id}

# View all retry attempts:
GET /api/queue/job/{job_id}/history
→ Returns: list of all attempts with provider, model, latency, error, etc.
```

### Detect Stuck Jobs
```python
# Run cleanup task manually:
cleaned = await scheduler.cleanup_stuck_jobs(max_age_seconds=3600)
print(f"Cleaned up {cleaned} stuck jobs")
```

---

## Testing

### Unit Tests (Recommended)
Create `tests/integration/test_queue_executor.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.guppy.inference.queue_executor import QueueExecutor
from src.guppy.inference.provider_registry import ProviderRegistry

@pytest.mark.asyncio
async def test_enqueue_and_process(db_session: AsyncSession):
    executor = QueueExecutor(db_session, registry)
    
    # Enqueue
    job_id = await executor.enqueue(
        prompt="Hello",
        task_type="simple",
    )
    assert job_id is not None
    
    # Check status
    status = await executor.get_job_status(job_id)
    assert status["status"] == "queued"
    
    # Process (will execute via local provider)
    processed = await executor.process_next_job()
    assert processed is True
    
    # Check result
    status = await executor.get_job_status(job_id)
    assert status["status"] in ["success", "failed"]
```

### Manual Testing
```bash
# 1. Enqueue a request
curl -X POST http://127.0.0.1:8081/api/queue/enqueue \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is 2+2?",
    "task_type": "simple",
    "max_retries": 3
  }'
# Returns: { "job_id": "abc-123-...", "status": "queued" }

# 2. Poll status (in loop)
curl http://127.0.0.1:8081/api/queue/job/abc-123

# 3. View history
curl http://127.0.0.1:8081/api/queue/job/abc-123/history

# 4. Check queue health
curl http://127.0.0.1:8081/api/queue/status
```

---

## Next Steps

### Immediate
1. ✅ Run `alembic upgrade head` to create queue tables
2. ✅ Import _db_models.py in your app's db setup
3. ✅ Wire routes_queue.py into FastAPI app
4. ✅ Start QueueScheduler in app startup
5. Test via curl/Postman

### Follow-up
1. Integrate into chat endpoint (optional, can run both direct and queue modes)
2. Add web UI components to display queue status/job results
3. Create monitoring dashboard (GET /api/queue/metrics)
4. Set up alerts for queue degradation (metrics.queued_count > threshold)

---

## Known Limitations & Future Work

- **Metrics persistence**: inference_metrics table is created but metrics recording in queue_executor._record_metrics() is TODO. Recommend recording after job completion.
- **Cloud provider clients**: LocalProviderClient fully implemented; CloudProviderClient subclasses (Anthropic, OpenAI, etc.) are stubs from Phase 1. These will be implemented in Phase 3.
- **Queue prioritization**: Currently uses simple priority_order + created_at. Could add dynamic priority boosting for aged jobs in future.
- **Distributed queue**: Current design assumes single-machine scheduler. For distributed deployment, recommend adding distributed task queue (Celery, RQ) in Phase 4.

---

**Phase 2 Status:** ✅ Complete  
**Phase 3 Targets:** Cloud provider client implementations + monitoring dashboard  
**Phase 4 Targets:** Distributed queue + advanced prioritization + cost optimization
