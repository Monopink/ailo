"""
Admin users API routes.
Manages admin users CRUD operations with simplified 3-role system.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from core.database import get_db
from core.security import get_password_hash
from admin.models import AdminUser
from admin.core.auth import GetAdminUser
from admin.core.permissions import require_view_permission, require_super_admin
from admin.core.operation_log import create_operation_log
from admin.core.crud_base import AdminCRUDBase
from admin.schemas.base import Success, SuccessExtra
from admin.schemas.users import UserCreate, UserUpdate
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Create CRUD instance for admin users
admin_user_crud = AdminCRUDBase(AdminUser)


@router.get("/list", summary="Get admin users list")
@require_view_permission
async def list_users(
    page: int = Query(1, description="Page number"),
    page_size: int = Query(20, description="Items per page"),
    username: str = Query("", description="Username for search"),
    email: str = Query("", description="Email address"),
    role: Optional[str] = Query(None, description="User role"),
    current_admin: AdminUser = Depends(GetAdminUser),
    db: AsyncSession = Depends(get_db),
):
    """
    Get admin users list with pagination and filtering.
    """
    try:
        # Build query conditions
        conditions = []

        if username:
            conditions.append(
                or_(AdminUser.username.contains(username), AdminUser.real_name.contains(username))
            )

        if email:
            conditions.append(AdminUser.email.contains(email))

        if role:
            conditions.append(AdminUser.role == role)

        # Build base query
        base_query = select(AdminUser)

        if conditions:
            base_query = base_query.where(and_(*conditions))

        # Get total count
        count_query = select(func.count(AdminUser.id))
        if conditions:
            count_query = count_query.where(and_(*conditions))

        result = await db.execute(count_query)
        total = result.scalar()

        # Get paginated data
        data_query = (
            base_query.offset((page - 1) * page_size).limit(page_size).order_by(AdminUser.id.desc())
        )
        result = await db.execute(data_query)
        users = result.scalars().all()

        # Format response data
        data = []
        for user in users:
            user_dict = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "real_name": user.real_name,
                "phone": user.phone,
                "role": user.role,
                "role_display": user.role_display,
                "is_active": user.is_active,
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "login_count": user.login_count,
                "avatar_url": user.avatar_url,
                "position": user.position,
                "notes": user.notes,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None,
            }
            data.append(user_dict)

        return SuccessExtra(data=data, total=total, page=page, page_size=page_size)

    except Exception as e:
        logger.error("list_users_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get users list")


@router.get("/get", summary="Get admin user details")
@require_view_permission
async def get_user(
    user_id: int = Query(..., description="User ID"),
    current_admin: AdminUser = Depends(GetAdminUser),
    db: AsyncSession = Depends(get_db),
):
    """
    Get admin user details by ID.
    """
    try:
        result = await db.execute(select(AdminUser).where(AdminUser.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user_dict = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "real_name": user.real_name,
            "phone": user.phone,
            "role": user.role,
            "role_display": user.role_display,
            "is_active": user.is_active,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "login_count": user.login_count,
            "avatar_url": user.avatar_url,
            "position": user.position,
            "notes": user.notes,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        }

        return Success(data=user_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_user_error", user_id=user_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get user details")


@router.post("/create", summary="Create admin user")
@require_super_admin
async def create_user(
    user_in: UserCreate,
    current_admin: AdminUser = Depends(GetAdminUser),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """
    Create a new admin user.
    Only super admin can create new admin users.
    """
    try:
        # Check if username already exists
        existing_user = await db.execute(select(AdminUser).where(AdminUser.username == user_in.username))
        if existing_user.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Username already exists")

        # Check if email already exists (if provided)
        if user_in.email:
            existing_email = await db.execute(select(AdminUser).where(AdminUser.email == user_in.email))
            if existing_email.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Email already exists")

        # Hash password
        hashed_password = get_password_hash(user_in.password)

        # Prepare user data
        user_data = user_in.model_dump(exclude={"password"})
        user_data["password_hash"] = hashed_password
        user_data["created_by"] = current_admin.id

        # Create user
        new_user = await admin_user_crud.create(db, obj_in=user_data)

        # Log operation
        await create_operation_log(
            db=db,
            admin_user_id=current_admin.id,
            operation_type="CREATE",
            resource_type="admin_user",
            operation_desc=f"Created admin user: {new_user.username}",
            resource_id=str(new_user.id),
            resource_name=new_user.username,
            request=request,
        )

        return Success(data={"id": new_user.id, "username": new_user.username})

    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_user_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create user")


@router.post("/update", summary="Update admin user")
@require_super_admin
async def update_user(
    user_in: UserUpdate,
    current_admin: AdminUser = Depends(GetAdminUser),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """
    Update an admin user.
    Only super admin can update admin users.
    """
    try:
        # Get existing user
        existing_user = await admin_user_crud.get(db, user_in.id)
        if not existing_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Prevent super admin from being modified by others
        if existing_user.role == "super_admin" and current_admin.id != existing_user.id:
            raise HTTPException(status_code=403, detail="Cannot modify super admin user")

        # Check username uniqueness if changed
        if user_in.username and user_in.username != existing_user.username:
            username_check = await db.execute(
                select(AdminUser).where(AdminUser.username == user_in.username)
            )
            if username_check.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Username already exists")

        # Check email uniqueness if changed
        if user_in.email and user_in.email != existing_user.email:
            email_check = await db.execute(select(AdminUser).where(AdminUser.email == user_in.email))
            if email_check.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Email already exists")

        # Prepare update data
        update_data = user_in.model_dump(exclude_unset=True, exclude={"id", "password"})

        # Hash new password if provided
        if user_in.password:
            update_data["password_hash"] = get_password_hash(user_in.password)

        # Update user
        updated_user = await admin_user_crud.update(db, db_obj=existing_user, obj_in=update_data)

        # Log operation
        await create_operation_log(
            db=db,
            admin_user_id=current_admin.id,
            operation_type="UPDATE",
            resource_type="admin_user",
            operation_desc=f"Updated admin user: {updated_user.username}",
            resource_id=str(updated_user.id),
            resource_name=updated_user.username,
            request=request,
        )

        return Success(data={"id": updated_user.id, "username": updated_user.username})

    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_user_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update user")


@router.delete("/delete", summary="Delete admin user")
@require_super_admin
async def delete_user(
    user_id: int = Query(..., description="User ID"),
    current_admin: AdminUser = Depends(GetAdminUser),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """
    Delete an admin user.
    Only super admin can delete admin users.
    Cannot delete self or other super admins.
    """
    try:
        # Get user to delete
        user_to_delete = await admin_user_crud.get(db, user_id)
        if not user_to_delete:
            raise HTTPException(status_code=404, detail="User not found")

        # Prevent deleting self
        if user_to_delete.id == current_admin.id:
            raise HTTPException(status_code=403, detail="Cannot delete yourself")

        # Prevent deleting super admin
        if user_to_delete.role == "super_admin":
            raise HTTPException(status_code=403, detail="Cannot delete super admin user")

        # Store username for logging
        username = user_to_delete.username

        # Delete user
        await admin_user_crud.delete(db, id=user_id)

        # Log operation
        await create_operation_log(
            db=db,
            admin_user_id=current_admin.id,
            operation_type="DELETE",
            resource_type="admin_user",
            operation_desc=f"Deleted admin user: {username}",
            resource_id=str(user_id),
            resource_name=username,
            request=request,
        )

        return Success(data={"message": f"User {username} deleted successfully"})

    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_user_error", user_id=user_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete user")


@router.post("/reset_password", summary="Reset admin user password")
@require_super_admin
async def reset_password(
    user_id: int = Query(..., description="User ID"),
    current_admin: AdminUser = Depends(GetAdminUser),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """
    Reset admin user password to default (admin123).
    Only super admin can reset passwords.
    Cannot reset super admin password.
    """
    try:
        # Get user
        user = await admin_user_crud.get(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Prevent resetting super admin password
        if user.role == "super_admin":
            raise HTTPException(status_code=403, detail="Cannot reset super admin password")

        # Reset to default password
        default_password = "admin123"
        hashed_password = get_password_hash(default_password)

        # Update password
        await admin_user_crud.update(db, db_obj=user, obj_in={"password_hash": hashed_password})

        # Log operation
        await create_operation_log(
            db=db,
            admin_user_id=current_admin.id,
            operation_type="UPDATE",
            resource_type="admin_user",
            operation_desc=f"Reset password for admin user: {user.username}",
            resource_id=str(user.id),
            resource_name=user.username,
            request=request,
        )

        return Success(data={"message": f"Password reset for user {user.username}"})

    except HTTPException:
        raise
    except Exception as e:
        logger.error("reset_password_error", user_id=user_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to reset password")
