# System Configs Unit Modification Plan

## Executive Summary

This document outlines the problems with current `system_configs` table naming conventions and provides a detailed migration plan to improve clarity, maintainability, and AI-assisted development accuracy.

**Status**: 🟢 Completed – Config naming refactor deployed on 2025-11-15

### Implementation Summary (2025-11-15)

- Added Alembic migration `20251115_config_units` to rename all affected keys, convert unit values (seconds → days/minutes/hours), and purge legacy duplicates (for example `contact_request_expiry_days`).
- Regenerated required-data SQL files so fresh environments ship with the new unit-suffixed keys.
- Refactored backend services (JWT issuance, contact requests, rate limiter, auth tracker, AI archive worker, admin tooling) to rely solely on the new keys, converting units explicitly in code via helpers like `_get_jwt_expiration_seconds` and `_get_contact_expiration_days`.
- Updated documentation and admin prototypes to reference the final key names. No fallback or rollback logic remains; configuration mistakes now surface immediately rather than being masked by defaults.

**Impact**: High - Affects configuration readability, maintenance, and AI code generation accuracy

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [Root Cause Analysis](#root-cause-analysis)
- [Modification Principles](#modification-principles)
- [Detailed Modification Plan](#detailed-modification-plan)
- [Migration Strategy](#migration-strategy)
- [Implementation Checklist](#implementation-checklist)

---

## Problem Statement

### Current Issues

1. **Inconsistent Naming Convention**
   - Some configs have unit suffixes (`message_buffer_normal_wait_ms`)
   - Some configs don't have unit suffixes (`jwt_token_expires_in`)
   - Original rule "all time values in seconds without suffix" is already broken

2. **Poor Human Readability**
   - ❌ `jwt_token_expires_in = 1209600` (What unit? How long?)
   - ❌ `token_cleanup_after = 2592000` (Need calculator to understand)
   - ❌ `auth_rate_limit_window = 3600` (Seconds? Minutes? Hours?)

3. **AI Development Issues**

- AI must guess units, leading to incorrect code generation
- AI needs extra context to understand config semantics
- AI-generated code may use wrong time units (seconds vs milliseconds)

4. **Maintenance Burden**

- New developers must check documentation or comments
- Easy to make mistakes when configuring
- Hard to validate if values are reasonable

---

## Root Cause Analysis

### Why Current Design Fails

**Original Assumption**: "All time values in seconds, no suffix needed"

**Reality**:

- ❌ Rule already broken (some configs use `_ms`, `_days`)
- ❌ Large second values (1209600) are not human-friendly
- ❌ Different time scales need different units (milliseconds for delays, days for expiration)
- ❌ "No suffix" principle conflicts with "self-documenting code" principle

**Fundamental Principle Violation**:
> Code should be self-explanatory, not dependent on comments or documentation.

---

## Modification Principles

### Principle 1: Choose Human-Friendly Units

- ❌ Bad: 1209600 seconds (requires mental calculation)
- ✅ Good: 14 days (immediately clear)
- ❌ Bad: 3600 seconds (need conversion)
- ✅ Good: 1 hour (intuitive)

### Principle 2: Select Units Based on Value Magnitude

| Time Range | Recommended Unit | Example |
|------------|------------------|---------|
| < 60 seconds | seconds or milliseconds | `sms_code_expires_in_seconds = 300` |
| Minutes | minutes | `auth_lockout_duration_minutes = 15` |
| Hours/Days | hours or days | `jwt_token_expires_in_days = 14` |

### Principle 3: Maintain Consistency Within Categories

- ✅ Good: All rate_limit_window configs use seconds
```
api_rate_limit_window_seconds = 60
sms_rate_limit_window_seconds = 60
message_rate_limit_short_window_seconds = 10
```
- ✅ Good: All lockout_duration configs use minutes
```
auth_lockout_duration_minutes = 15
admin_auth_lockout_duration_minutes = 30
```

### Principle 4: Always Include Unit Suffix

- ❌ Bad: typing_speed (What unit?)
- ✅ Good: typing_speed_wpm (Words per minute, clear)
- ❌ Bad: max_message_length (Characters? Bytes?)
- ✅ Good: max_message_length_chars (Characters, explicit)

---

## Detailed Modification Plan

### Priority Levels

- 🔴 **High Priority**: Large values in seconds, completely unintuitive
- 🟡 **Medium Priority**: Medium values in seconds, requires conversion
- 🟢 **Low Priority**: Missing unit suffix, but value is reasonable

---

### 🔴 High Priority Modifications

These configs have large second values that are completely unintuitive and must be changed.

#### 1. JWT & Token Configs

| Current Config | Current Value | Issue | New Config | New Value | New Unit |
|----------------|---------------|-------|------------|-----------|----------|
| `jwt_token_expires_in` | 1209600 | 1209600 seconds = ? | `jwt_token_expires_in_days` | 14 | days |
| `jwt_sliding_window` | 604800 | 604800 seconds = ? | `jwt_sliding_window_days` | 7 | days |
| `token_cleanup_after` | 2592000 | 2592000 seconds = ? | `token_cleanup_after_days` | 30 | days |

**Rationale**: Token expiration is naturally thought of in days ("14-day token"), not seconds.

#### 2. Archive & Cleanup Configs

| Current Config | Current Value | Issue | New Config | New Value | New Unit |
|----------------|---------------|-------|------------|-----------|----------|
| `ai_conversation_archive_time` | 604800 | 604800 seconds = ? | `ai_conversation_archive_time_days` | 7 | days |

**Rationale**: Archive periods are naturally thought of in days ("keep 7 days of history").

#### 3. Business Logic Configs

| Current Config | Current Value | Issue | New Config | New Value | New Unit |
|----------------|---------------|-------|------------|-----------|----------|
| `contact_request_expiration` | 259200 | 259200 seconds = ? | `contact_request_expiration_days` | 3 | days |

**Rationale**: Friend request expiration is naturally thought of in days ("expires in 3 days").

**⚠️ Note**: Historical duplicate `contact_request_expiry_days` has been removed (merged into `contact_request_expiration_days`).

---

### 🟡 Medium Priority Modifications

These configs have medium-sized second values that require mental conversion.

#### 1. Security Lockout Configs

| Current Config | Current Value | Issue | New Config | New Value | New Unit |
|----------------|---------------|-------|------------|-----------|----------|
| `admin_auth_lockout_duration` | 1800 | 1800 seconds = 30 minutes | `admin_auth_lockout_duration_minutes` | 30 | minutes |
| `auth_lockout_duration` | 900 | 900 seconds = 15 minutes | `auth_lockout_duration_minutes` | 15 | minutes |

**Rationale**: Lockout duration is naturally thought of in minutes ("locked out for 15 minutes").

#### 2. Rate Limit Window Configs

| Current Config | Current Value | Issue | New Config | New Value | New Unit |
|----------------|---------------|-------|------------|-----------|----------|
| `auth_rate_limit_window` | 3600 | 3600 seconds = 1 hour | `auth_rate_limit_window_hours` | 1 | hours |

**Alternative**: Could use `auth_rate_limit_window_minutes = 60` if you prefer consistency with other rate limit windows.

**Rationale**: 1 hour is more intuitive than 3600 seconds.

---

### 🟢 Low Priority Modifications

These configs are missing unit suffixes but have reasonable values. Adding suffixes improves clarity.

#### 1. Rate Limit Window Configs (Add Suffix)

| Current Config | Current Value | New Config | New Value | Unit |
|----------------|---------------|------------|-----------|------|
| `admin_auth_rate_limit_window` | 60 | `admin_auth_rate_limit_window_seconds` | 60 | seconds |
| `api_rate_limit_window` | 60 | `api_rate_limit_window_seconds` | 60 | seconds |
| `message_rate_limit_long_window` | 60 | `message_rate_limit_long_window_seconds` | 60 | seconds |
| `message_rate_limit_short_window` | 10 | `message_rate_limit_short_window_seconds` | 10 | seconds |
| `sms_rate_limit_window` | 60 | `sms_rate_limit_window_seconds` | 60 | seconds |
| `square_rate_limit_window` | 10 | `square_rate_limit_window_seconds` | 10 | seconds |

**Rationale**: Consistency - all rate limit windows should have explicit unit suffix.

#### 2. SMS Configs (Add Suffix)

| Current Config | Current Value | New Config | New Value | Unit |
|----------------|---------------|------------|-----------|------|
| `sms_code_expires_in` | 300 | `sms_code_expires_in_seconds` | 300 | seconds |
| `sms_code_length` | 6 | `sms_code_length_digits` | 6 | digits |

**Rationale**: 300 seconds (5 minutes) is reasonable, but suffix makes it explicit.

#### 3. Business Configs (Add Suffix)

| Current Config | Current Value | New Config | New Value | Unit |
|----------------|---------------|------------|-----------|------|
| `max_message_length` | 49 | `max_message_length_chars` | 49 | characters |

**Rationale**: Clarify it's character count, not byte count.

#### 4. Captcha Configs (Add Suffix)

| Current Config | Current Value | New Config | New Value | Unit |
|----------------|---------------|------------|-----------|------|
| `admin_captcha_threshold` | 1 | `admin_captcha_threshold_failures` | 1 | failures |
| `captcha_threshold` | 3 | `captcha_threshold_failures` | 3 | failures |

**Rationale**: Clarify it's counting failures, not attempts.

---

### ✅ Configs That Don't Need Changes

These configs are already well-named or don't have units:

#### Already Have Unit Suffixes

- `message_buffer_normal_wait_ms = 3000` ✅
- `message_buffer_typing_end_wait_ms = 1000` ✅
- `message_buffer_typing_total_wait_ms = 10000` ✅
- `message_buffer_no_typing_wait_ms = 2000` ✅
- `contact_request_expiry_days = 3` ✅

#### No Units (Counts, Limits, Enums)

- `token_max_active_per_device = 1` ✅
- `default_contact_limit = 3` ✅
- `default_search_display_limit = 20` ✅
- `square_page_size = 20` ✅
- All `*_rate_limit_requests` configs ✅
- All `*_max_failures` configs ✅
- All provider/mode/algorithm configs ✅

---

## Migration Strategy

> **Update (2025-11-15):** All phases below were executed together during a single cutover. No transitional fallbacks were retained per product directive; the section remains for historical context.

### Phase 1: High Priority (Immediate)

**Goal**: Fix the most problematic configs (large second values)

**Steps**:

1. Create migration script to add new configs
2. Convert values to appropriate units
3. Update code to read from the new configs only (no fallback)
4. Test thoroughly
5. Mark old configs as deprecated in description

**Timeline**: Sprint 1

### Phase 2: Medium Priority (Next Sprint)

**Goal**: Fix medium-sized second values

**Steps**:

1. Add new configs with better units
2. Update code references (remove old key usage immediately)
3. Deprecate old configs

**Timeline**: Sprint 2

### Phase 3: Low Priority (Gradual)

**Goal**: Add unit suffixes to all remaining configs

**Steps**:

1. Add new configs with suffixes
2. Update code references gradually
3. Remove old configs when all references updated

**Timeline**: Sprint 3-4

### Phase 4: Cleanup

**Goal**: Remove all deprecated configs

**Steps**:

1. Verify no code references old configs
2. Delete old config entries from database
3. Update documentation

**Timeline**: Sprint 5

---

## Implementation Checklist

### Database Migration & Seed Updates

- Alembic revision `backend/alembic/versions/20251115_config_unit_names.py` renames every affected key, converts stored values into human-readable units, and removes the historical `contact_request_expiry_days` duplicate before re-keying.
- Seed scripts (`backend/database/init/02_required_data*.sql`) now ship only the new keys so local/test/prod environments stay aligned.
- No `[DEPRECATED]` placeholders remain; lookups fail fast if a required config is missing.

### Code Update Pattern

Instead of juggling old/new keys, production code now reads the canonical config once, converts to the internal unit, and fails loudly if the key is missing.

```python
# backend/app/api/v1/auth.py

async def _get_jwt_expiration_seconds(db: AsyncSession) -> int:
    expires_in_days = await system_configs.get_config_value(db, "jwt_token_expires_in_days")
    if expires_in_days is None:
        raise HTTPException(status_code=500, detail="系统配置缺失")
    return int(expires_in_days) * 86400

expires_in_seconds = await _get_jwt_expiration_seconds(db)
jwt_token = generate_jwt_token(
    user_id=user.id,
    qiao_id=user.qiao_id,
    device_type=DeviceType.MINI_PROGRAM,
    expires_in_seconds=expires_in_seconds,
)
expires_at = calculate_token_expiry(expires_in_seconds)
```

The same pattern is used for contact requests, rate limits, lockouts, and AI archival windows—each helper returns a typed value (days/minutes/hours) and the business logic converts to seconds only when necessary.

### Helper Functions

- `_get_jwt_expiration_seconds` and `_get_contact_expiration_days` centralize conversions and ensure misconfigurations raise `HTTPException` immediately.
- `RATE_LIMIT_WINDOW_KEYS`, `RATE_LIMIT_REQUEST_KEYS`, and `LOCKOUT_DURATION_KEYS` map every group to its new key plus multiplier, eliminating string concatenation tricks that previously produced bad lookups.
Testing Checklist
### Unit Tests
- Test config reading with new keys
- Test unit conversion accuracy (days/minutes/hours → seconds)
- Verify missing configs raise the correct exceptions instead of silently defaulting
- Test edge cases (zero, negative, very large values)
### Integration Tests
- Test JWT token expiration with new config
- Test rate limiting with new config
- Test lockout duration with new config
- Test archive process with new config
- Test SMS code expiration with new config
### Manual Testing
- Verify admin panel displays new configs correctly
- Confirm only the new keys are visible (no legacy entries)
- Verify system behavior unchanged (same effective values)
- Verify logs show correct time values
Documentation Updates
Files Updated / To Update
- `docs/prototype/admin-panel.md`: renamed business configs (`contact_request_expiration_days`, `max_message_length_chars`).
- Any developer-facing guides that reference timing configs should describe the unit suffix policy and list canonical key names only.
- Admin/README snippets must no longer suggest `[DEPRECATED]` entries or fallback behavior.
Admin Panel Updates
### Admin Panel Updates
Update Starlette Admin to:
- Group related configs together
- Show unit in field label
- Add helpful descriptions with examples
Example:
```python
class SystemConfigAdmin(ModelView):
    form_args = {
        "jwt_token_expires_in_days": {
            "label": "JWT Token Expiration (days)",
            "description": "Token expiration time in days. Common values: 7, 14, 30",
        },
        "jwt_token_expires_in": {
            "label": "JWT Token Expiration (seconds) [DEPRECATED]",
            "description": "⚠️ DEPRECATED: Use jwt_token_expires_in_days instead",
        },
    }
```
Impact on AI Development
### Before (Current State)
# AI sees this config
```python
jwt_token_expires_in = 1209600
```
# AI must guess:
- What unit? (seconds? milliseconds?)
- How long? (need calculator)
- May generate wrong code:
```python
expiry = datetime.now() + timedelta(milliseconds=1209600)  # ❌ Wrong!
```
### After (Improved State)
# AI sees this config
```python
jwt_token_expires_in_days = 14
```
# AI immediately understands:
- Unit is days (explicit in name)
- Value is 14 days (clear)
- Generates correct code:
```python
expiry = datetime.now() + timedelta(days=14)  # ✅ Correct!
```
Result: AI-generated code will be more accurate and require less human review.
Success Criteria
### Metrics
- 100% of time configs have explicit unit suffixes
- 0 configs with values > 1000 in seconds (should use larger units)
- 0 ambiguous config names
- AI code generation accuracy improved (measure via code review)
- Developer onboarding time reduced (measure via survey)
### Validation
- All tests pass
- No production incidents related to config changes
- Positive feedback from development team
- Documentation complete and accurate
### FAQ
**Q: Why not keep everything in seconds for consistency?**
**A:** Consistency is good, but readability is more important. 1209600 seconds is not readable. 14 days is readable. The cost of conversion is negligible compared to the cost of human confusion.
**Q: Won't this break existing code?**
**A:** No. All touchpoints were updated in the same deployment to read the new keys, and missing configs now raise explicit errors instead of silently falling back.
**Q: What about performance impact of unit conversion?**
**A:** Negligible. Config reading happens rarely (usually once at startup or cached). The conversion is a simple arithmetic operation.
**Q: Should we convert all existing values immediately?**
**A:** Yes. The production migration converted and re-keyed every value at once (seconds → human units), then removed the legacy rows to prevent drift.
**Q: What if we need to add new configs in the future?**
**A:** Follow the naming convention:
- Always include unit suffix for values with units
- Choose human-friendly units (days > seconds for large values)
- Be consistent within categories
### References
- System Configs Table Schema
- Config Service Implementation
- Original Discussion
### Approval & Sign-off
- Technical Lead Review
- Product Owner Approval
- QA Sign-off
- DevOps Review
Document Version: 1.1 Last Updated: 2025-11-15 Author: Development Team Status: 🟢 Implementation Complete
