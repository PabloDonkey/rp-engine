from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException

from rp_engine.adapters.api.admin_models import (
    AdminDeletedMessageResponse,
    AdminMessageResponse,
    AdminSessionPersonaRequest,
    AdminSessionResponse,
    AdminTraceResponse,
    AdminUserResponse,
    ScenarioSummaryResponse,
)
from rp_engine.adapters.telegram.authorization import TelegramAuthorization
from rp_engine.application.services.admin_service import AdminService
from rp_engine.application.services.scenario_transfer_service import ScenarioTransferService
from rp_engine.core.user.user import User
from rp_engine.infrastructure.scenario_serialization import scenario_definition_to_payload


def _telegram_id(user: User) -> str | None:
    return next(
        (identity.external_id for identity in user.identities if identity.provider == "telegram"),
        None,
    )


def create_admin_router(
    admin_service: AdminService,
    telegram_authorization: TelegramAuthorization | None,
    scenario_transfer_service: ScenarioTransferService,
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

    @router.put("/sessions/{session_id}/persona")
    async def set_session_persona(
        session_id: UUID, payload: AdminSessionPersonaRequest
    ) -> AdminSessionResponse:
        """Set or replace a session's persona.

        The operator exception to ADR-025's set-once contract: `/clear` is still the only
        way a *player* can change a persona, but an admin looking at the whole session can
        correct one in place. Replacing a name changes how past turns render (transcripts
        store `{{user}}` unresolved), so the panel confirms before sending.
        """
        session = await admin_service.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        if not payload.name.strip():
            raise HTTPException(status_code=400, detail="Persona name must not be empty")
        if session.is_deleted:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This session was superseded by a restart or clear, so a persona would "
                    "never reach a prompt. Set it on the live session instead."
                ),
            )
        updated = await admin_service.set_session_persona(
            session_id, name=payload.name, description=payload.description
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Session not found")
        transcript = await admin_service.get_session_transcript(session_id)
        return AdminSessionResponse.from_session(updated, message_count=len(transcript))

    @router.delete("/sessions/{session_id}/messages/last")
    async def delete_last_message(session_id: UUID) -> AdminDeletedMessageResponse:
        """Remove the newest message only, together with its generation traces.

        Deleting turn N requires deleting N+1 first.
        """
        session = await admin_service.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        deleted = await admin_service.delete_last_message(session_id)
        if deleted is None:
            raise HTTPException(status_code=404, detail="Conversation is already empty")
        return AdminDeletedMessageResponse.from_deleted(deleted)

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

    @router.get("/scenarios")
    async def list_scenarios() -> list[ScenarioSummaryResponse]:
        scenarios = await admin_service.list_scenarios()
        return [ScenarioSummaryResponse.from_definition(scenario) for scenario in scenarios]

    @router.get("/scenarios/{scenario_id}")
    async def get_scenario(scenario_id: str) -> dict[str, Any]:
        scenario = await admin_service.get_scenario(scenario_id)
        if scenario is None:
            raise HTTPException(status_code=404, detail="Scenario not found")
        return scenario_definition_to_payload(scenario)

    @router.post("/scenarios", status_code=201)
    async def create_scenario(payload: dict[str, Any]) -> dict[str, Any]:
        scenario_id = payload.get("id")
        if not scenario_id:
            raise HTTPException(status_code=422, detail="Scenario payload must include an id")
        if await admin_service.get_scenario(scenario_id) is not None:
            raise HTTPException(status_code=409, detail=f"Scenario '{scenario_id}' already exists")
        scenario = await scenario_transfer_service.import_scenario_payload(payload)
        if scenario is None:
            raise HTTPException(status_code=422, detail="Scenario payload failed validation")
        return scenario_definition_to_payload(scenario)

    @router.put("/scenarios/{scenario_id}")
    async def update_scenario(scenario_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if await admin_service.get_scenario(scenario_id) is None:
            raise HTTPException(status_code=404, detail="Scenario not found")
        if payload.get("id") != scenario_id:
            raise HTTPException(
                status_code=400, detail="Scenario id in body must match the URL id"
            )
        scenario = await scenario_transfer_service.import_scenario_payload(payload)
        if scenario is None:
            raise HTTPException(status_code=422, detail="Scenario payload failed validation")
        return scenario_definition_to_payload(scenario)

    @router.post("/scenarios/import")
    async def import_scenario(payload: dict[str, Any]) -> dict[str, Any]:
        scenario = await scenario_transfer_service.import_scenario_payload(payload)
        if scenario is None:
            raise HTTPException(status_code=422, detail="Scenario payload failed validation")
        return scenario_definition_to_payload(scenario)

    @router.get("/sessions/{session_id}/export")
    async def export_session(session_id: UUID) -> dict[str, Any]:
        exported = await scenario_transfer_service.export_session(session_id)
        if exported is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return exported

    @router.post("/sessions/import")
    async def import_session(payload: dict[str, Any]) -> AdminSessionResponse:
        session = await scenario_transfer_service.import_session(payload)
        if session is None:
            raise HTTPException(status_code=422, detail="Session payload failed validation")
        return AdminSessionResponse.from_session(session)

    return router
