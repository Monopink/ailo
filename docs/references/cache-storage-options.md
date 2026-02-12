# Cache Storage: Redis vs PostgreSQL UNLOGGED

**Decision**: Use Redis (NOT PostgreSQL UNLOGGED tables)

**Related Docs**: [login-security.md](../spec/auth/login-security.md), [websocket-provider.md](../tasks/2026-02-10-test-websocket-provider.md), [STATISTICS.md](../data-dict/STATISTICS.md)

---

## Quick Comparison

| Feature | Redis | PG UNLOGGED |
|---------|-------|-------------|
| PubSub | ✅ Native | ❌ No (LISTEN/NOTIFY limited) |
| Atomic ops | ✅ Native | ⚠️ Needs locking |
| TTL | ✅ Native | ❌ Manual cleanup |
| Crash recovery | ⚠️ Configurable | ❌ **All data lost** |
| Replication | ✅ Yes | ❌ No |
| Latency | 0.05-0.1ms | 0.5-3ms |

---

## Project-Specific Requirements

Current codebase ([auth.py](../../backend/app/api/v1/auth.py), [security/](../../backend/app/services/security/)):

| Use Case | Data Loss OK? | Needs |
|----------|---------------|-------|
| SMS codes | ✅ Yes | TTL (5min) |
| Rate limiting | ❌ **No** (security) | Atomic ops, TTL |
| Auth failures | ❌ **No** (security) | Atomic ops, TTL |
| WebSocket broadcast | ❌ **No** | **PubSub** |
| Celery queue | ❌ **No** | Redis required |

**Key Issue**: 5/7 use cases cannot tolerate data loss or need PubSub.

---

## Why NOT PostgreSQL UNLOGGED

### Critical Blockers

1. **No PubSub** → WebSocket multi-instance blocked
   - Doc quote: "多 worker/多实例需引入 Hub（例如 Redis PubSub）保证广播可达"
   - `LISTEN/NOTIFY` cannot span multiple DB instances

2. **Crash = Data Loss** → Security controls reset
   - UNLOGGED tables **TRUNCATE** on crash recovery
   - Rate limits reset → attackers bypass protection
   - Auth failures reset → brute-force protection disabled

3. **No Replication** → Cannot scale
   - UNLOGGED tables excluded from WAL
   - Cannot use standby servers

### Missing Features

```python
# Redis: Native TTL
redis.setex("code:13800138000", 300, "123456")

# PostgreSQL: Manual cleanup needed
await db.execute("DELETE FROM codes WHERE expires_at < NOW()")
# Risk: Memory leak if cleanup fails
```

```python
# Redis: Atomic increment
redis.incr("failures:192.168.1.1:user@example.com")

# PostgreSQL: Needs locking
UPDATE auth_failures SET count = count + 1
WHERE identifier = '...' RETURNING count;
# Risk: Deadlocks under load
```

---

## Why Redis Is Required

### Hard Requirements (No Alternative)

1. **WebSocket PubSub** - Multi-instance broadcast
2. **Celery** - Task queue (already planned in STATISTICS.md)
3. **Security** - Rate limiting cannot tolerate data loss

### When UNLOGGED Makes Sense (Not This Project)

✅ Use UNLOGGED only if **ALL** true:
- Single instance (no scaling)
- Low traffic (< 1000 QPS)
- Data loss acceptable (e.g., analytics cache)
- No atomic operations needed
- No PubSub needed

Example: Analytics cache (recomputable, low frequency)

---

## Implementation

### Phase 1: Current (MVP)
In-memory dict → Keep as-is for single instance

### Phase 2: Pre-Production
```yaml
# docker-compose.yml
redis:
  image: redis:7-alpine
  command: redis-server --appendonly yes
```

Migrate:
- SMS codes → `SETEX`
- Rate limiting → Sorted sets (`ZADD` + `ZREMRANGEBYSCORE`)

### Phase 3: Production
Redis Sentinel/Cluster for HA

---

## Common Mistakes

❌ "UNLOGGED is as fast as Redis" → Redis is 10-100x faster
❌ "UNLOGGED safe for rate limiting" → Crash resets all limits
❌ "LISTEN/NOTIFY = PubSub" → 8KB limit, single instance only
❌ "Avoid Redis complexity" → Already needed for Celery + WebSocket

---

## Decision Rule

**If need ANY of**: PubSub, atomic ops, replication, crash safety → **Use Redis**

**This project**: Redis required (PubSub + Celery + security)
