"""
Admin AI testing service.

This module provides functions for creating virtual users and testing
AI characters through the admin panel.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from models.profile import Profile
from models.contact import Contact
from models.ai import AIRelationshipScore
from crud.user import user
from crud.profile import profile
from crud.contact import contact
from enums import UserType, ContactType
from services.ai import process_conversation, get_character_info
from utils.logging import get_logger

logger = get_logger(__name__)


async def create_virtual_user(
    db: AsyncSession,
    admin_id: int,
    character_qiao_id: str,
    session_name: str,
    user_profile: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Create virtual user for AI testing.

    Args:
        db: Database session
        admin_id: Admin user ID
        character_qiao_id: AI character to test with
        session_name: Test session name
        user_profile: Optional user profile data

    Returns:
        Virtual user information or None if failed
    """
    try:
        # Generate unique qiao_id for virtual user
        from utils.snowflake import generate_qiao_id

        timestamp = int(datetime.now().timestamp())
        virtual_user_qiao_id = f"virtual_admin_{admin_id}_{timestamp}"

        # Create virtual user record
        virtual_user = await user.create(
            db,
            obj_in={
                "qiao_id": virtual_user_qiao_id,
                "username": f"虚拟用户_{session_name}",
                "user_type": UserType.VIRTUAL,
                "phone": None,  # Virtual users don't have phone numbers
                "password_hash": None,  # Virtual users don't have passwords
                "status": 1,
            },
        )

        # Create virtual user profile
        profile_data = user_profile or {}
        virtual_profile = await profile.create(
            db,
            obj_in={
                "qiao_id": virtual_user_qiao_id,
                "nickname": profile_data.get("nickname", f"测试用户_{session_name}"),
                "gender": profile_data.get("gender", 1),
                "bio": profile_data.get("bio", "这是一个用于AI测试的虚拟用户"),
                "avatar_url": profile_data.get("avatar_url"),
                "birth_date": profile_data.get("birth_date"),
                "location": profile_data.get("location"),
                "occupation": profile_data.get("occupation"),
                "interests": profile_data.get("interests"),
            },
        )

        # Create contact relationship with AI character
        await contact.create(
            db,
            obj_in={
                "user_qiao_id": virtual_user_qiao_id,
                "contact_qiao_id": character_qiao_id,
                "contact_type": ContactType.AI_CHARACTER,
                "status": 1,  # Active
                "remark": f"AI测试角色 - {session_name}",
            },
        )

        # Initialize relationship scores
        initial_scores = {
            "friendship": 100,  # Start with basic friendship
            "romance": 0,  # No romance initially
            "trust": 50,  # Moderate trust
            "interest": 75,  # Some interest
        }

        for dimension, score in initial_scores.items():
            await ai_relationship_score.create(
                db,
                obj_in={
                    "user_qiao_id": virtual_user_qiao_id,
                    "character_qiao_id": character_qiao_id,
                    "dimension_name": dimension,
                    "score": score,
                },
            )

        logger.info(
            "virtual_user_created",
            virtual_user_qiao_id=virtual_user_qiao_id,
            character_qiao_id=character_qiao_id,
            session_name=session_name,
            admin_id=admin_id,
        )

        return {
            "qiao_id": virtual_user_qiao_id,
            "username": virtual_user.username,
            "session_name": session_name,
            "character_qiao_id": character_qiao_id,
            "profile": {
                "nickname": virtual_profile.nickname,
                "gender": virtual_profile.gender,
                "bio": virtual_profile.bio,
                "avatar_url": virtual_profile.avatar_url,
            },
            "initial_scores": initial_scores,
            "created_at": virtual_user.created_at,
        }

    except Exception as e:
        logger.error(
            "create_virtual_user_error",
            error=str(e),
            admin_id=admin_id,
            character_qiao_id=character_qiao_id,
            session_name=session_name,
        )
        return None


async def get_virtual_users(
    db: AsyncSession, admin_id: int, skip: int = 0, limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Get list of virtual users created by admin.

    Args:
        db: Database session
        admin_id: Admin user ID
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of virtual user information
    """
    try:
        # Get virtual users created by this admin
        virtual_users = await user.get_virtual_users_by_admin(db, admin_id=admin_id, skip=skip, limit=limit)

        result = []
        for virtual_user in virtual_users:
            # Get profile
            user_profile = await profile.get_by_qiao_id(db, qiao_id=virtual_user.qiao_id)

            # Get associated character (from contacts)
            user_contacts = await contact.get_by_user_qiao_id(db, user_qiao_id=virtual_user.qiao_id)
            character_qiao_id = None
            if user_contacts:
                character_qiao_id = user_contacts[0].contact_qiao_id

            result.append(
                {
                    "qiao_id": virtual_user.qiao_id,
                    "username": virtual_user.username,
                    "character_qiao_id": character_qiao_id,
                    "profile": (
                        {
                            "nickname": user_profile.nickname if user_profile else None,
                            "gender": user_profile.gender if user_profile else None,
                            "bio": user_profile.bio if user_profile else None,
                            "avatar_url": user_profile.avatar_url if user_profile else None,
                        }
                        if user_profile
                        else None
                    ),
                    "created_at": virtual_user.created_at,
                    "status": virtual_user.status,
                }
            )

        return result

    except Exception as e:
        logger.error("get_virtual_users_error", error=str(e), admin_id=admin_id)
        return []


async def delete_virtual_user(db: AsyncSession, admin_id: int, virtual_user_qiao_id: str) -> bool:
    """
    Delete virtual user and all related data.

    Args:
        db: Database session
        admin_id: Admin user ID
        virtual_user_qiao_id: Virtual user's qiao_id

    Returns:
        True if successful, False otherwise
    """
    try:
        # Verify this is a virtual user created by this admin
        virtual_user = await user.get_by_qiao_id(db, qiao_id=virtual_user_qiao_id)
        if not virtual_user or virtual_user.user_type != UserType.VIRTUAL:
            logger.warning(
                "invalid_virtual_user_delete_attempt",
                virtual_user_qiao_id=virtual_user_qiao_id,
                admin_id=admin_id,
            )
            return False

        # Check if this admin created this virtual user (based on qiao_id pattern)
        if not virtual_user_qiao_id.startswith(f"virtual_admin_{admin_id}_"):
            logger.warning(
                "unauthorized_virtual_user_delete_attempt",
                virtual_user_qiao_id=virtual_user_qiao_id,
                admin_id=admin_id,
            )
            return False

        # Delete related data
        # 1. Delete relationship scores
        await ai_relationship_score.delete_by_user_qiao_id(db, user_qiao_id=virtual_user_qiao_id)

        # 2. Delete contacts
        await contact.delete_by_user_qiao_id(db, user_qiao_id=virtual_user_qiao_id)

        # 3. Delete profile
        user_profile = await profile.get_by_qiao_id(db, qiao_id=virtual_user_qiao_id)
        if user_profile:
            await profile.remove(db, id=user_profile.id)

        # 4. Delete user
        await user.remove(db, id=virtual_user.id)

        logger.info("virtual_user_deleted", virtual_user_qiao_id=virtual_user_qiao_id, admin_id=admin_id)

        return True

    except Exception as e:
        logger.error(
            "delete_virtual_user_error",
            error=str(e),
            virtual_user_qiao_id=virtual_user_qiao_id,
            admin_id=admin_id,
        )
        return False


async def simulate_ai_chat(
    db: AsyncSession, admin_id: int, virtual_user_qiao_id: str, character_qiao_id: str, message: str
) -> Dict[str, Any]:
    """
    Simulate AI chat conversation.

    Args:
        db: Database session
        admin_id: Admin user ID
        virtual_user_qiao_id: Virtual user's qiao_id
        character_qiao_id: AI character's qiao_id
        message: User message

    Returns:
        AI response and metadata
    """
    try:
        # Verify virtual user belongs to this admin
        if not virtual_user_qiao_id.startswith(f"virtual_admin_{admin_id}_"):
            return {"success": False, "error": "Unauthorized access to virtual user", "response": None}

        # Process AI message
        result = await process_ai_message(
            db=db,
            user_qiao_id=virtual_user_qiao_id,
            character_qiao_id=character_qiao_id,
            message_content=message,
            message_type="text",
        )

        # Add test metadata
        result["test_metadata"] = {
            "admin_id": admin_id,
            "virtual_user_qiao_id": virtual_user_qiao_id,
            "character_qiao_id": character_qiao_id,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(
            "ai_chat_simulated",
            admin_id=admin_id,
            virtual_user_qiao_id=virtual_user_qiao_id,
            character_qiao_id=character_qiao_id,
            success=result["success"],
        )

        return result

    except Exception as e:
        logger.error(
            "simulate_ai_chat_error",
            error=str(e),
            admin_id=admin_id,
            virtual_user_qiao_id=virtual_user_qiao_id,
            character_qiao_id=character_qiao_id,
        )
        return {"success": False, "error": str(e), "response": None}


async def preview_system_prompt(
    db: AsyncSession, admin_id: int, virtual_user_qiao_id: str, character_qiao_id: str, message: str
) -> Dict[str, Any]:
    """
    Preview system prompt that would be generated for AI.

    Args:
        db: Database session
        admin_id: Admin user ID
        virtual_user_qiao_id: Virtual user's qiao_id
        character_qiao_id: AI character's qiao_id
        message: User message

    Returns:
        System prompt and context information
    """
    try:
        # Verify virtual user belongs to this admin
        if not virtual_user_qiao_id.startswith(f"virtual_admin_{admin_id}_"):
            return {"success": False, "error": "Unauthorized access to virtual user", "prompt": None}

        # Get character and user info
        from services.ai import get_character_info

        character_info = await get_character_info(db, character_qiao_id)
        if not character_info:
            return {"success": False, "error": "Character not found", "prompt": None}

        # Build context
        context = await build_conversation_context(db, virtual_user_qiao_id, character_qiao_id, message)

        # Get user info (simplified for virtual user)
        user_info = {"qiao_id": virtual_user_qiao_id, "nickname": "测试用户", "gender": 1}

        # Generate system prompt
        system_prompt = await generate_system_prompt(db, character_info, user_info, context)

        return {
            "success": True,
            "prompt": system_prompt,
            "context": {
                "character_info": character_info,
                "user_info": user_info,
                "conversation_context": context,
            },
            "test_metadata": {
                "admin_id": admin_id,
                "virtual_user_qiao_id": virtual_user_qiao_id,
                "character_qiao_id": character_qiao_id,
                "timestamp": datetime.now().isoformat(),
            },
        }

    except Exception as e:
        logger.error(
            "preview_system_prompt_error",
            error=str(e),
            admin_id=admin_id,
            virtual_user_qiao_id=virtual_user_qiao_id,
            character_qiao_id=character_qiao_id,
        )
        return {"success": False, "error": str(e), "prompt": None}
