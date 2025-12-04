# Backend Optimization Report

**Author: Nikhil Kumar**

> Performance analysis and optimization recommendations for the Lia Chatbot Backend

**Date:** December 2025  
**Scope:** `backend/app/` - 15 core files across services, routes, database, and configuration

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Performance Issues](#2-performance-issues)
3. [Concurrency Issues](#3-concurrency-issues)
4. [Caching Improvements](#4-caching-improvements)
5. [Error Handling](#5-error-handling)
6. [API Design](#6-api-design)
7. [Resource Management](#7-resource-management)
8. [Implementation Roadmap](#8-implementation-roadmap)

---

## 1. Executive Summary

The codebase is **well-structured** with good async patterns, caching strategies, and error handling. This report identifies **optimization opportunities** across multiple categories.

### Priority Overview

| Priority | Count | Description |
|:--------:|:-----:|-------------|
| 🔴 **High** | 2 | Critical reliability and scalability issues |
| 🟡 **Medium** | 6 | Performance optimizations, concurrency fixes |
| 🟢 **Low** | 8 | Technical debt, minor improvements |

### Top 5 Recommendations

1. **Add pagination to conversation messages** (High)
2. **Implement retry logic for LLM calls** (High)
3. **Use Redis transactions for atomic cache operations** (Medium)
4. **Track background tasks with error callbacks** (Medium)
5. **Optimize database queries with eager loading** (Medium)

---

## 2. Performance Issues

### 2.1 N+1 Query Risk in Conversation Detail

| Attribute | Value |
|-----------|-------|
| **File** | `app/services/chat.py` |
| **Priority** | 🟡 Medium |
| **Impact** | Reduces database round-trips by 50% |

**Issue:** Two separate queries for conversation and messages.

```python
# Current: 2 database round-trips
conv_result = await db.execute(select(Conversation).where(...))
msg_result = await db.execute(select(Message).where(...))
```

**Solution:** Use `selectinload` for eager loading.

```python
# Optimized: Single query with eager loading
from sqlalchemy.orm import selectinload

result = await db.execute(
    select(Conversation)
    .options(selectinload(Conversation.messages))
    .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
)
conv = result.scalar_one_or_none()
# Messages available as conv.messages
```

---

### 2.2 Sequential Cache Operations with TTL

| Attribute | Value |
|-----------|-------|
| **File** | `app/services/cache.py` |
| **Priority** | 🟡 Medium |
| **Impact** | Reduces network round-trips by 80-90% for bulk operations |

**Issue:** Individual SET commands when TTL is specified.

```python
# Current: N network calls
if ttl:
    for key, value in mapping.items():
        await self._client.set(key, value, ex=ttl)
```

**Solution:** Use Redis pipeline for batch operations.

```python
# Optimized: Single pipeline
async with self._client.pipeline() as pipe:
    for key, value in mapping.items():
        pipe.set(key, value, ex=ttl)
    await pipe.execute()
```

---

### 2.3 Inefficient History Removal

| Attribute | Value |
|-----------|-------|
| **File** | `app/services/cache.py` |
| **Priority** | 🟡 Medium |
| **Impact** | Changes O(N) to O(log N) |

**Issue:** Iterates through all items in sorted set to find and remove one.

```python
# Current: O(N) - fetches all items
items = await self.zrange(key, 0, -1)
for item in items:
    if json.loads(item).get("id") == conversation_id:
        await self._client.zrem(key, item)
```

**Solution:** Store conversation ID as the sorted set member directly.

```python
# Optimized: O(log N) removal
# Store: ZADD history:{user_id} {timestamp} {conversation_id}
# Metadata in separate hash: HSET conv:{id}:meta ...
await self._client.zrem(key, conversation_id)
```

---

### 2.4 JSON Serialization in Hot Path

| Attribute | Value |
|-----------|-------|
| **File** | `app/services/chat.py` |
| **Priority** | 🟢 Low |
| **Impact** | ~10-20μs savings per SSE event |

**Issue:** Standard library `json.dumps` in SSE event generation.

```python
def sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
```

**Solution:** Use `orjson` for 2-3x faster serialization.

```python
import orjson

def sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {orjson.dumps(data).decode()}\n\n"
```

---

## 3. Concurrency Issues

### 3.1 Fire-and-Forget Tasks Untracked

| Attribute | Value |
|-----------|-------|
| **File** | `app/services/chat.py` |
| **Priority** | 🟡 Medium |
| **Impact** | Prevents silent failures and orphaned tasks |

**Issue:** Multiple `asyncio.create_task()` calls without error handling.

```python
# Current: Silent failures
asyncio.create_task(self.cache_service.set_user_messages(...))
```

**Solution:** Track tasks with error callbacks.

```python
def create_tracked_task(coro, name: str) -> asyncio.Task:
    task = asyncio.create_task(coro, name=name)
    task.add_done_callback(_log_task_exception)
    return task

def _log_task_exception(task: asyncio.Task) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Background task {task.get_name()} failed", error=str(e))
```

---

### 3.2 Non-Atomic Cache Operations

| Attribute | Value |
|-----------|-------|
| **File** | `app/services/cache.py` |
| **Priority** | 🟡 Medium |
| **Impact** | Prevents partial updates during concurrent operations |

**Issue:** Delete and RPUSH are not atomic.

```python
# Current: Race condition window
await self._client.delete(key)  # Gap here
await self._client.rpush(key, *messages)
await self._client.expire(key, ttl)
```

**Solution:** Use Redis transactions (MULTI/EXEC).

```python
# Optimized: Atomic operation
async with self._client.pipeline() as pipe:
    pipe.delete(key)
    pipe.rpush(key, *messages)
    pipe.expire(key, ttl)
    await pipe.execute()
```

---

### 3.3 Missing Sentiment Task Error Handling

| Attribute | Value |
|-----------|-------|
| **File** | `app/services/chat.py` |
| **Priority** | 🟡 Medium |
| **Impact** | Improves chat stream resilience |

**Issue:** Sentiment task failure could crash the stream.

```python
# Current: Unhandled exception
sentiment_task = asyncio.create_task(self.sentiment_service.analyze(...))
message_sentiment = await sentiment_task  # Could throw
```

**Solution:** Wrap with fallback to neutral sentiment.

```python
try:
    message_sentiment = await sentiment_task
except Exception as e:
    logger.warning("Sentiment analysis failed", error=str(e))
    message_sentiment = SentimentResult.neutral()
```

---

## 4. Caching Improvements

### 4.1 Over-Caching Static Data

| Attribute | Value |
|-----------|-------|
| **File** | `app/api/routes/chat.py` |
| **Priority** | 🟢 Low |
| **Impact** | Reduces unnecessary Redis calls |

**Issue:** Static data cached in Redis when it never changes at runtime.

```python
# Current: Caches static data
asyncio.create_task(cache.set_available_models(models))
asyncio.create_task(cache.set_sentiment_methods(methods))
```

**Solution:** Cache in-memory at startup.

```python
class LLMService:
    _cached_models: dict | None = None
    
    def get_all_models(self) -> dict:
        if self._cached_models is None:
            self._cached_models = self._build_models_dict()
        return self._cached_models
```

---

### 4.2 No Cache Warming Strategy

| Attribute | Value |
|-----------|-------|
| **File** | `app/main.py` |
| **Priority** | 🟢 Low |
| **Impact** | Eliminates cold-start cache misses |

**Issue:** Only LLM adapters pre-warmed at startup.

```python
# Current startup
llm_service.prewarm_adapters()
# Missing: static cache warming
```

**Solution:** Pre-populate caches during startup.

```python
# In lifespan startup
async def startup():
    cache = get_cache_service()
    llm = get_llm_service()
    sentiment = get_sentiment_service()
    
    if cache.is_available:
        await cache.set_available_models(llm.get_all_models())
        await cache.set_sentiment_methods(sentiment.get_available_methods())
```

---

## 5. Error Handling

### 5.1 Missing Retry Logic for LLM Calls 🔴

| Attribute | Value |
|-----------|-------|
| **File** | `app/services/llm.py` |
| **Priority** | 🔴 **High** |
| **Impact** | Significant improvement in reliability |

**Issue:** No retry on transient failures (5xx, timeouts).

```python
# Current: Single attempt
async for chunk in adapter.generate_stream(...):
    yield chunk  # No retry on failure
```

**Solution:** Implement exponential backoff with `tenacity`.

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class GeminiAdapter:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    )
    async def _make_request(self, ...):
        ...
```

---

### 5.2 Generic Exception Catching

| Attribute | Value |
|-----------|-------|
| **File** | `app/services/llm.py` |
| **Priority** | 🟡 Medium |
| **Impact** | Better error messages and handling |

**Issue:** Catching `Exception` masks specific errors.

```python
# Current: Loses error type
except Exception as e:
    raise LLMProviderError("gemini", str(e))
```

**Solution:** Catch specific exceptions.

```python
from google.api_core.exceptions import ResourceExhausted, InvalidArgument

try:
    ...
except ResourceExhausted:
    raise LLMProviderError("gemini", "Rate limit exceeded", retry_after=60)
except InvalidArgument as e:
    raise LLMProviderError("gemini", f"Invalid request: {e}")
except Exception as e:
    raise LLMProviderError("gemini", f"Unexpected error: {e}")
```

---

## 6. API Design

### 6.1 Missing Message Pagination 🔴

| Attribute | Value |
|-----------|-------|
| **File** | `app/services/chat.py`, `app/api/routes/chat.py` |
| **Priority** | 🔴 **High** |
| **Impact** | Critical for conversations with many messages |

**Issue:** Returns ALL messages without pagination.

```python
# Current: Could return 10,000+ messages
msg_result = await db.execute(
    select(Message)
    .where(Message.conversation_id == conversation_id)
    .order_by(Message.created_at.asc())
)
messages = msg_result.scalars().all()
```

**Solution:** Add pagination parameters.

```python
# Service layer
async def get_conversation_detail(
    self,
    user_id: int,
    conversation_id: str,
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> dict | None:
    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    ...

# Route layer
@router.get("/conversation/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ...
):
    ...
```

---

### 6.2 Large SSE Sentiment Payload

| Attribute | Value |
|-----------|-------|
| **File** | `app/services/chat.py` |
| **Priority** | 🟢 Low |
| **Impact** | Reduces bandwidth |

**Issue:** Full sentiment details sent in SSE events.

```python
yield sse_event("sentiment", {
    "message": message_sentiment.to_dict(),  # Full details
    "cumulative": cumulative_sentiment.to_dict(),
})
```

**Solution:** Send minimal data in stream; full details via API.

```python
yield sse_event("sentiment", {
    "message": {"score": 0.5, "label": "Positive"} if message_sentiment else None,
    "cumulative": {"score": 0.3, "label": "Neutral"} if cumulative_sentiment else None,
})
```

---

## 7. Resource Management

### 7.1 Connection Pool Tuning

| Attribute | Value |
|-----------|-------|
| **File** | `app/core/config.py` |
| **Priority** | 🟡 Medium |
| **Impact** | Better performance under load |

**Issue:** Default pool size may be insufficient for high concurrency.

```python
# Current defaults
db_pool_size: int = 5
db_max_overflow: int = 10
```

**Recommendation:** Tune based on deployment:

| Environment | Workers | Pool Size | Max Overflow |
|-------------|---------|-----------|--------------|
| Development | 1 | 5 | 5 |
| Production (2 workers) | 2 | 10 | 20 |
| Production (4 workers) | 4 | 5 | 15 |

**Rule of thumb:** `pool_size = connections_per_worker * workers`

---

### 7.2 Singleton Cleanup

| Attribute | Value |
|-----------|-------|
| **File** | Multiple service files |
| **Priority** | 🟢 Low |
| **Impact** | Better testability, prevents test pollution |

**Issue:** Global singletons never reset.

```python
_llm_service: LLMService | None = None

def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
```

**Solution:** Add cleanup functions for testing/hot-reload.

```python
def reset_llm_service() -> None:
    global _llm_service
    _llm_service = None

# In main.py lifespan shutdown
async def shutdown():
    reset_llm_service()
    reset_cache_service()
    reset_sentiment_service()
```

---

## 8. Implementation Roadmap

### Sprint 1: Critical Issues

| Issue | Priority | Effort | Files |
|-------|----------|--------|-------|
| Add message pagination | 🔴 High | 2-3 hrs | `chat.py`, `routes/chat.py` |
| Implement LLM retry logic | 🔴 High | 3-4 hrs | `llm.py` |

### Sprint 2: Important Optimizations

| Issue | Priority | Effort | Files |
|-------|----------|--------|-------|
| Atomic cache operations | 🟡 Medium | 2 hrs | `cache.py` |
| Track background tasks | 🟡 Medium | 1-2 hrs | `chat.py` |
| Sentiment task error handling | 🟡 Medium | 1 hr | `chat.py` |
| Specific LLM exception handling | 🟡 Medium | 2 hrs | `llm.py` |

### Sprint 3: Performance Tuning

| Issue | Priority | Effort | Files |
|-------|----------|--------|-------|
| Eager loading for queries | 🟡 Medium | 2 hrs | `chat.py` |
| History removal optimization | 🟡 Medium | 2 hrs | `cache.py` |
| Cache pipeline operations | 🟡 Medium | 1-2 hrs | `cache.py` |

### Technical Debt (When Time Permits)

| Issue | Priority | Effort | Files |
|-------|----------|--------|-------|
| In-memory caching for static data | 🟢 Low | 1 hr | `routes/chat.py` |
| Cache warming at startup | 🟢 Low | 1 hr | `main.py` |
| orjson for SSE events | 🟢 Low | 30 min | `chat.py` |
| Singleton cleanup functions | 🟢 Low | 1 hr | Multiple |
| Minimal SSE sentiment payload | 🟢 Low | 30 min | `chat.py` |

---

## Summary

### Quick Wins (< 1 hour each)

1. Add sentiment task error handling
2. Switch to orjson for SSE serialization
3. Add singleton cleanup functions

### High-Impact Changes

1. **Message pagination** - Prevents memory issues with long conversations
2. **LLM retry logic** - Dramatically improves reliability
3. **Atomic cache operations** - Prevents race conditions

### Metrics to Track

| Metric | Current | Target | How to Measure |
|--------|---------|--------|----------------|
| P95 Response Time | Unknown | < 500ms | APM/Logging |
| Error Rate | Unknown | < 0.1% | Error tracking |
| Cache Hit Rate | Unknown | > 80% | Redis metrics |
| LLM Success Rate | Unknown | > 99% | Provider metrics |

---

## Related Documentation

| Document | Description |
|----------|-------------|
| [README.md](./README.md) | Quick start & API reference |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System architecture |

---

*Last Updated: December 2025*
