# Known Issues & Solutions

## Docker

### DB init scripts not executed
**Symptom**: Empty database after docker-compose up
**Cause**: PostgreSQL volume exists, init scripts only run on first create
**Fix**:
```bash
docker-compose down -v  # Delete volume
docker-compose up -d
```

### Backend container fails to start
**Symptom**: `ModuleNotFoundError` or `ImportError`
**Troubleshoot**:
1. Check if requirements.txt updated → Rebuild image
2. Check PYTHONPATH → Should be /app
3. View logs: `docker logs backend_container`

### Container cannot connect to DB
**Symptom**: `could not connect to server`
**Cause**: Docker network or container startup order issue
**Fix**:
```bash
docker-compose restart backend
# or
docker-compose down && docker-compose up -d
```

---

## Database

### Alembic migration conflict
**Symptom**: `Target database is not up to date`
**Cause**: Multi-dev or multi-env version inconsistency
**Fix**:
```bash
# Check current version
alembic current
# Force mark as latest (use with caution)
alembic stamp head
```

### JSON field query performance poor
**Symptom**: JSONB column query slow
**Cause**: Missing GIN index
**Fix**:
```sql
CREATE INDEX idx_name ON table USING GIN (json_column);
```

### Foreign key constraint error
**Symptom**: `violates foreign key constraint`
**Cause**: Wrong deletion order or data inconsistency
**Troubleshoot**:
```sql
-- Find orphaned records
SELECT * FROM child_table
WHERE parent_id NOT IN (SELECT id FROM parent_table);
```

---

## LeanCloud

### Message send fails: 401 Unauthorized
**Symptom**: `Unauthorized` error
**Cause**: Wrong/expired App ID/Key config
**Check**: LEANCLOUD_* vars in backend/app/core/config.py

### Message delay >5 seconds
**Symptom**: Message arrives long after sent from Admin panel
**Cause**: LeanCloud CN node throttling or network issue
**Workaround**: Restart LeanCloud connection or switch node (contact user)

---

## MinIO / Object Storage

### Pre-signed URL fails in WeChat mini-program
**Symptom**: wx.uploadFile with pre-signed URL errors
**Cause**: WeChat env incomplete support for Query String signatures
**Fix**: Use backend proxy upload (/api/v1/media/upload)

### File uploaded but inaccessible
**Symptom**: 404 Not Found
**Cause**: Bucket policy not set to public-read
**Fix**:
```bash
# MinIO console: Set Bucket Policy to download
# Or use mc command
mc anonymous set download myminio/bucket-name
```

---

## WeChat Mini-Program

### wx.request returns empty data
**Symptom**: Network tab shows 200, but data empty
**Cause**: WeChat auto-parses JSON, backend returns wrong format
**Check**:
1. Content-Type must be application/json
2. Response body must be valid JSON

### Avatar shows in real device debug, not in preview
**Symptom**: Works in devtools, white screen on real device
**Cause**: Domain not in "request legal domains" config
**Fix**: WeChat Public Platform → Development → Dev Management → Dev Settings → Server Domains

### Page shows blank when using page-layout component
**Symptom**: Page displays blank after navigating (e.g., setup page after registration)
**Cause**: page-layout component references deleted ui-loading/ui-empty components
**Root Cause**: Incomplete TDesign migration in commit 6e30407 - page-layout.json not updated
**Fix**: Update page-layout to use t-loading/t-empty from TDesign (see commit fixing this issue)
**Impact**: 13 pages use page-layout component
**Prevention**: Before removing UI components, check all usages:
```bash
grep -r "component-name" frontend/wx-minipg/components/
grep -r "component-name" frontend/wx-minipg/pages/
```

### Custom TabBar TypeError: Cannot read property 'data' of undefined
**Symptom**: Pages with custom TabBar crash on load/show: `TypeError: Cannot read property 'data' of undefined at init (custom-tab-bar/index.js:28)`
**Root Cause**: Extracting `init` function reference and calling it loses `this` context
**Wrong Pattern**:
```typescript
const tabBar = this.getTabBar();
const initFn = tabBar.init;
initFn(); // ❌ this is undefined
```
**Fix**: Use `initTabBar()` utility from `utils/tab-bar.ts`
```typescript
import { initTabBar } from '../../utils/tab-bar';
Page({
  onShow() {
    initTabBar(this); // ✅ Correct
  }
});
```
**Architecture**: Type-safe wrapper with proper `this` binding. See `typings/custom-tab-bar.d.ts` for type definitions.
**Affected Files**: Any page using custom TabBar (index, square, profile)
**Documentation**: See AGENTS.md § Custom TabBar 使用规范

---

## AI Dialogue

### Doubao API timeout
**Symptom**: `TimeoutError` after 60s
**Cause**: Context too long or Doubao service fluctuation
**Fix**:
1. Check if ai_contexts too long (>10000 tokens)
2. Adjust timeout config (config.py: LLM_TIMEOUT)
3. Enable streaming response (stream=True)

### Relationship score not updating
**Symptom**: relationship_scores table data unchanged
**Cause**: AI response JSON missing relationship_changes field
**Troubleshoot**:
1. Check if LLM prompt includes relationship schema
2. View JSON validation errors in logs
3. Confirm services/ai/scoring.py logic correct
