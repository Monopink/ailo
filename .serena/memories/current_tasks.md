# Ongoing Tasks

> **Note**: Delete section immediately after task completed
> **Format**: [Date] Task | Problem | Analysis | Solution | Status | Files

---

## Backend

*No ongoing tasks*

---

## Frontend

*No ongoing tasks*

---

## Database

*No ongoing tasks*

---

## Infrastructure

*No ongoing tasks*

---

## Example (Delete after reading)

### [2025-01-16] Avatar upload fails
- **Problem**: WeChat mini-program avatar upload returns 403
- **Analysis**: MinIO pre-signed URL signature verification fails in WeChat env
- **Solution**: Use backend proxy upload (POST /api/v1/media/upload)
- **Status**: Backend API implemented, waiting for frontend integration test
- **Files**:
  - backend/app/api/v1/media.py
  - backend/app/services/profile/avatar.py
  - frontend/wx-minipg/utils/media.ts
