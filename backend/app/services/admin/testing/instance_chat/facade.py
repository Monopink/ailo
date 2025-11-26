"""
AI Instance Chat Test Service - Facade

This module provides a unified interface for AI instance chat testing,
combining validation, user matching, and execution services following
the facade pattern for clean separation of concerns.
"""

from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from .validation import validation_service, ValidationError
from .user_matcher import user_matcher_service, UserMatcherError
from .executor import executor_service, ExecutorError
from utils.logging import get_logger
from crud.contact import contact as contact_crud
from schemas.contact import ContactCreate
from enums import ContactType
from models.base import generate_conv_id
from services.ai.types import InstanceContext

logger = get_logger(__name__)


class AIInstanceChatTestError(Exception):
    """Main exception for AI instance chat test service"""

    def __init__(
        self, message: str, error_code: str = "CHAT_TEST_ERROR", suggestions: Optional[list] = None
    ):
        self.message = message
        self.error_code = error_code
        self.suggestions = suggestions or []
        super().__init__(message)


class AIInstanceChatTestService:
    """
    Facade service for AI instance chat testing.

    Orchestrates the complete test flow: validation -> user matching -> execution
    while maintaining stateless design and clear error handling.
    """

    async def prepare_and_execute_test(
        self,
        db: AsyncSession,
        instance_id: int,
        llm_config_name: str,
        test_message: str,
        mock_overrides: Optional[Dict[str, Any]] = None,
        persist: bool = True,
    ) -> Dict[str, Any]:
        """
        Complete test flow: validate prerequisites, match test user, and execute test.

        Args:
            db: Database session
            instance_id: AI instance ID
            llm_config_name: LLM configuration name
            test_message: Test message content

        Returns:
            Dictionary containing test results and all relevant information

        Raises:
            AIInstanceChatTestError: If any step fails
        """
        try:
            # Step 1: Validate all prerequisites
            logger.info("ai_chat_test_validation_start", instance_id=instance_id)
            validation_result = await validation_service.validate_instance_test_prerequisites(
                db=db, instance_id=instance_id
            )

            # Step 2: Find and validate test user
            logger.info("ai_chat_test_user_matching_start", instance_id=instance_id)
            user_match_result = await user_matcher_service.find_test_user_for_instance(
                db=db,
                instance_context=validation_result["instance"],
            )
            if not user_match_result["test_user"]:
                raise AIInstanceChatTestError(
                    "归属用户非测试类型",
                    error_code="TEST_USER_REQUIRED",
                    suggestions=["确认实例归属用户是 user_type=virtual"],
                )

            selection_locked = bool(user_match_result.get("test_user_selection_locked"))
            locked_user_qiao_id = user_match_result.get("locked_test_user_qiao_id")

            ensured_contact = await self._ensure_virtual_contact(
                db=db,
                user_id=user_match_result["test_user"]["id"],
                user_qiao_id=user_match_result["test_user"]["qiao_id"],
                instance_context=validation_result["instance"],
            )
            contact_for_response = self._serialize_contact(ensured_contact)
            user_match_result["contact"] = contact_for_response
            user_match_result["test_user"]["conversation_id"] = ensured_contact.conv_id

            # Step 3: Execute test with main conversation logic
            logger.info(
                "ai_chat_test_execution_start",
                instance_id=instance_id,
                test_user_qiao_id=user_match_result["test_user"]["qiao_id"],
            )
            execution_result = await executor_service.execute_instance_chat_test(
                db=db,
                instance_qiao_id=validation_result["instance"]["instance_qiao_id"],
                user_qiao_id=user_match_result["test_user"]["qiao_id"],
                llm_config_name=llm_config_name,
                test_message=test_message,
                request_overrides={"provider_overrides": mock_overrides} if mock_overrides else None,
                persist=persist,
                contact_conv_id=(ensured_contact.conv_id if persist else None),
            )

            # Combine all results for comprehensive response
            # Get latest relationship scores after execution
            try:
                from services.ai.relationship_scoring import get_relationship_scores

                latest_scores = (
                    await get_relationship_scores(
                        db=db,
                        instance_qiao_id=validation_result["instance"]["instance_qiao_id"],
                        auto_initialize=False,
                    )
                    or []
                )
            except Exception:
                latest_scores = []

            # Also compute selected relationship after update for immediate feedback
            try:
                from services.ai.relationship_scoring import determine_relationship_type as _determine

                selected_rel = None
                if latest_scores:
                    rel_info = await _determine(db, validation_result["instance"], latest_scores)
                    if rel_info and rel_info.get("relationship"):
                        r = rel_info["relationship"]
                        selected_rel = {
                            "id": r.id,
                            "name": getattr(r, "name", None),
                            "display_name": getattr(r, "display_name", None),
                        }
            except Exception:
                selected_rel = None

            complete_result = {
                "test_execution": execution_result,
                "validation_info": {
                    "instance": validation_result["instance"],
                    "instance_profile": validation_result["instance_profile"],
                    "style": validation_result["style"],
                    "personality": validation_result["personality"],
                    "relationship_scores": validation_result["relationship_scores"],
                },
                "test_user_info": {
                    "test_user": user_match_result["test_user"],
                    "test_user_profile": user_match_result["test_user_profile"],
                    "contact": contact_for_response,
                    "available_contacts": user_match_result.get("available_contacts", []),
                    "available_test_users": user_match_result.get("available_test_users", []),
                    "test_user_selection_locked": selection_locked,
                    "locked_test_user_qiao_id": locked_user_qiao_id,
                },
                "available_contacts": user_match_result.get("available_contacts", []),
                "available_test_users": user_match_result.get("available_test_users", []),
                "test_user_selection_locked": selection_locked,
                "locked_test_user_qiao_id": locked_user_qiao_id,
                "available_llm_configs": validation_result["llm_configs"],
                "relationship_scores_after": latest_scores,
                "selected_relationship_after": selected_rel,
            }

            logger.info(
                "ai_chat_test_complete_success",
                instance_id=instance_id,
                response_time_ms=execution_result["performance"]["response_time_ms"],
            )

            return complete_result

        except ValidationError as e:
            logger.error("ai_chat_test_validation_failed", instance_id=instance_id, error=str(e))
            raise AIInstanceChatTestError(
                f"测试校验失败：{e.message}", error_code=e.error_code, suggestions=e.suggestions
            )

        except UserMatcherError as e:
            logger.error("ai_chat_test_user_matching_failed", instance_id=instance_id, error=str(e))
            raise AIInstanceChatTestError(
                f"测试用户匹配失败：{e.message}",
                error_code=e.error_code,
                suggestions=e.suggestions,
            )

        except ExecutorError as e:
            logger.error("ai_chat_test_execution_failed", instance_id=instance_id, error=str(e))
            raise AIInstanceChatTestError(
                f"测试执行失败：{e.message}",
                error_code=e.error_code,
            )

        except Exception as e:
            logger.error(
                "ai_chat_test_unexpected_error", instance_id=instance_id, error=str(e), exc_info=True
            )
            raise AIInstanceChatTestError(
                f"测试过程中出现未知错误：{str(e)}", error_code="UNEXPECTED_ERROR"
            )

    async def validate_test_readiness(self, db: AsyncSession, instance_id: int) -> Dict[str, Any]:
        """
        Check test readiness without executing the test.

        Args:
            db: Database session
            instance_id: AI instance ID

        Returns:
            Dictionary containing validation status and prerequisites info

        Raises:
            AIInstanceChatTestError: If validation fails
        """
        try:
            # Validate prerequisites
            validation_result = await validation_service.validate_instance_test_prerequisites(
                db=db, instance_id=instance_id
            )

            # Check test user availability
            user_match_result = await user_matcher_service.find_test_user_for_instance(
                db=db, instance_context=validation_result["instance"]
            )
            contacts_for_response = user_match_result.get("recomputed_contacts") or user_match_result.get(
                "available_contacts", []
            )
            selected_user = user_match_result.get("test_user")
            if not selected_user:
                logger.warning(
                    "test_readiness_multiple_contacts",
                    instance_id=instance_id,
                    contacts=len(contacts_for_response),
                )

            # Get response JSON schema for this instance (used by main flow)
            try:
                from services.ai.conversation_prompt import build_response_schema

                response_schema = build_response_schema(validation_result["instance"])
            except Exception:
                response_schema = None

            # Fetch instance dimensions for detailed display (score/position/offsets)
            try:
                from crud.ai.instance_dimension import get_by_instance as _get_instance_dims

                instance_dimensions = await _get_instance_dims(
                    db, validation_result["instance"]["instance_id"]
                )
            except Exception:
                instance_dimensions = []

            test_user_summary = None
            if selected_user:
                test_user_summary = {
                    "qiao_id": selected_user["qiao_id"],
                    "username": selected_user["username"],
                    "nickname": (user_match_result["test_user_profile"] or {}).get("nickname"),
                }

            instance_ai_type = validation_result["instance"].get("ai_type")
            ai_type_display = (
                instance_ai_type["display_name"]
                if isinstance(instance_ai_type, dict) and instance_ai_type.get("display_name")
                else None
            )

            return {
                "ready": True,
                "instance_info": {
                    "qiao_id": validation_result["instance"]["instance_qiao_id"],
                    "ai_type_display": ai_type_display,
                    "ai_type": instance_ai_type,
                    "style": validation_result["style"]["display_name"],
                    "personality": validation_result["personality"]["display_name"],
                },
                # Full profiles for richer UI (non-breaking addition)
                "instance_profile": validation_result["instance_profile"],
                "test_user_profile": user_match_result["test_user_profile"],
                # Raw style/personality objects for advanced info panel
                "style": validation_result["style"],
                "personality": validation_result["personality"],
                # Current relationship from instance data
                "current_relationship": validation_result.get("current_relationship"),
                # Instance settings snapshot needed by UI
                "instance_settings": {
                    "memory": validation_result["instance"].get("memory"),
                    "prompt_variables": validation_result["instance"].get("prompt_variables"),
                },
                "test_user_info": test_user_summary,
                "available_contacts": contacts_for_response,
                "available_test_users": user_match_result.get("available_test_users", []),
                "test_user_selection_locked": user_match_result.get("test_user_selection_locked", False),
                "locked_test_user_qiao_id": user_match_result.get("locked_test_user_qiao_id"),
                "relationship_scores": validation_result["relationship_scores"],
                "available_llm_configs": validation_result["llm_configs"],
                "response_schema": response_schema,
                "instance_dimensions": instance_dimensions,
            }

        except (ValidationError, UserMatcherError) as e:
            return {
                "ready": False,
                "error_code": e.error_code,
                "error_message": e.message,
                "suggestions": getattr(e, "suggestions", []),
            }

        except Exception as e:
            logger.error("test_readiness_check_error", instance_id=instance_id, error=str(e))
            return {
                "ready": False,
                "error_code": "SYSTEM_ERROR",
                "error_message": f"自检失败：{str(e)}",
                "suggestions": ["查看系统日志", "联系管理员"],
            }

    async def archive_all_test_conversations(self, db: AsyncSession, instance_id: int) -> Dict[str, Any]:
        """
        Archive all conversation items for test instance and test user.

        Args:
            db: Database session
            instance_id: AI instance ID

        Returns:
            Dictionary with archived count

        Raises:
            AIInstanceChatTestError: If archiving fails
        """
        try:
            validation_result = await validation_service.validate_instance_test_prerequisites(
                db=db, instance_id=instance_id
            )
            user_match_result = await user_matcher_service.find_test_user_for_instance(
                db=db, instance_context=validation_result["instance"]
            )

            from services.ai.queries.transactions import archive_all_conversation_items

            archived_count = await archive_all_conversation_items(
                db=db,
                user_qiao_id=user_match_result["test_user"]["qiao_id"],
                instance_qiao_id=validation_result["instance"]["instance_qiao_id"],
            )

            return {"success": True, "archived_count": archived_count}

        except Exception as e:
            logger.error("archive_test_conversations_failed", instance_id=instance_id, error=str(e))
            raise AIInstanceChatTestError(f"归档对话失败：{str(e)}", error_code="ARCHIVE_FAILED")

    async def _ensure_virtual_contact(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        user_qiao_id: str,
        instance_context: InstanceContext,
    ):
        """Create or restore contact relationship for virtual test user."""
        existing = await contact_crud.get_user_contact_including_deleted(
            db,
            user_qiao_id=user_qiao_id,
            contact_qiao_id=instance_context["instance_qiao_id"],
        )

        if existing:
            if getattr(existing, "is_deleted", 0) == 0:
                return existing
            restored = await contact_crud.restore_contact(
                db,
                contact=existing,
                alias=None,
                tags=None,
            )
            logger.info(
                "virtual_contact_restored_for_test",
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_context["instance_qiao_id"],
                conv_id=restored.conv_id,
            )
            return restored

        contact_input = ContactCreate(
            contact_type=ContactType.AI,
            contact_qiao_id=instance_context["instance_qiao_id"],
            alias=None,
            custom_avatar_url=None,
            tags=None,
            remark=None,
            source="admin_test",
        )
        conv_id = generate_conv_id()
        contact = await contact_crud.create_with_user(
            db,
            obj_in=contact_input,
            user_qiao_id=user_qiao_id,
            user_id=user_id,
            conv_id=conv_id,
        )
        contact.contact_id = instance_context["instance_id"]
        db.add(contact)
        await db.flush()
        await db.commit()
        await db.refresh(contact)

        logger.info(
            "virtual_contact_created_for_test",
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_context["instance_qiao_id"],
            conv_id=contact.conv_id,
        )
        return contact

    @staticmethod
    def _serialize_contact(contact: Optional[Any]) -> Optional[Dict[str, Any]]:
        """Normalize contact object/dict to JSON-serializable dict."""
        if contact is None:
            return None
        if isinstance(contact, dict):
            return contact
        try:
            return contact.to_dict()
        except AttributeError:
            return {
                "conv_id": getattr(contact, "conv_id", None),
                "user_qiao_id": getattr(contact, "user_qiao_id", None),
                "contact_qiao_id": getattr(contact, "contact_qiao_id", None),
            }


# Global instance for dependency injection
ai_instance_chat_test_service = AIInstanceChatTestService()
