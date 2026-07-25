from uuid import UUID

from fastapi import APIRouter, HTTPException

from rp_engine.adapters.api.admin_models import (
    AdminMessageResponse,
    AdminSessionResponse,
    AdminTraceResponse,
    AdminUserResponse,
)
from rp_engine.adapters.telegram.authorization import TelegramAuthorization
from rp_engine.application.services.admin_service import AdminService
from rp_engine.core.user.user import User


def _telegram_id(user: User) -> str | None:
    return next(
        (identity.external_id for identity in user.identities if identity.provider == "telegram"),
        None,
    )


def create_admin_router(
    admin_service: AdminService,
    telegram_authorization: TelegramAuthorization | None,
) -> APIRouter:
    router = APIRouter(prefix="/admin")

    def _is_blocked(telegram_external_id: str | None) -> bool:
        if telegram_authorization is None or telegram_external_id is None:
            return False
        return not telegram_authorization.has_explicit_private_user(telegram_external_id)

    @router.get("/users")
    async def list_users() -> list[AdminUserResponse]:
        summaries = await admin_service.list_users()
        return [
            AdminUserResponse.from_summary(
                summary, is_blocked=_is_blocked(_telegram_id(summary.user))
            )
            for summary in summaries
        ]

    @router.get("/users/{user_id}/sessions")
    async def list_user_sessions(user_id: UUID) -> list[AdminSessionResponse]:
        user = await admin_service.get_user(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        sessions = await admin_service.list_user_sessions(user_id)
        return [AdminSessionResponse.from_session(session) for session in sessions]

    @router.get("/sessions/{session_id}")
    async def get_session(session_id: UUID) -> AdminSessionResponse:
        session = await admin_service.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        transcript = await admin_service.get_session_transcript(session_id)
        return AdminSessionResponse.from_session(session, message_count=len(transcript))

    @router.get("/sessions/{session_id}/transcript")
    async def get_session_transcript(session_id: UUID) -> list[AdminMessageResponse]:
        session = await admin_service.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        messages = await admin_service.get_session_transcript(session_id)
        return [AdminMessageResponse.from_message(message) for message in messages]

    @router.get("/sessions/{session_id}/traces")
    async def get_session_traces(session_id: UUID) -> list[AdminTraceResponse]:
        session = await admin_service.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        traces = await admin_service.get_session_traces(session_id)
        return [AdminTraceResponse(record=record) for record in traces]

    @router.delete("/sessions/{session_id}")
    async def delete_session(session_id: UUID) -> dict[str, str]:
        session = await admin_service.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        await admin_service.delete_session(session_id)
        return {"status": "deleted"}

    @router.post("/users/{user_id}/block")
    async def block_user(user_id: UUID) -> AdminUserResponse:
        if telegram_authorization is None:
            raise HTTPException(status_code=503, detail="Telegram authorization not configured")
        user = await admin_service.get_user(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        telegram_id = _telegram_id(user)
        if telegram_id is None:
            raise HTTPException(status_code=400, detail="User has no Telegram identity to block")
        telegram_authorization.remove_private_user(telegram_id)
        telegram_authorization.persist()
        sessions = await admin_service.list_user_sessions(user_id)
        return AdminUserResponse(
            id=user.id,
            display_name=user.display_name,
            telegram_external_id=telegram_id,
            session_count=len(sessions),
            is_blocked=True,
        )

    @router.post("/users/{user_id}/unblock")
    async def unblock_user(user_id: UUID) -> AdminUserResponse:
        if telegram_authorization is None:
            raise HTTPException(status_code=503, detail="Telegram authorization not configured")
        user = await admin_service.get_user(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        telegram_id = _telegram_id(user)
        if telegram_id is None:
            raise HTTPException(status_code=400, detail="User has no Telegram identity to unblock")
        telegram_authorization.add_private_user(telegram_id)
        telegram_authorization.persist()
        sessions = await admin_service.list_user_sessions(user_id)
        return AdminUserResponse(
            id=user.id,
            display_name=user.display_name,
            telegram_external_id=telegram_id,
            session_count=len(sessions),
            is_blocked=False,
        )

    return router
