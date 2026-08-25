from collections.abc import Awaitable, Callable
from uuid import UUID

from fastapi import APIRouter, HTTPException

from rp_engine.adapters.api.admin_models import AdminMessageResponse, AdminPlayTurnRequest
from rp_engine.application.services.admin_service import AdminService
from rp_engine.application.services.chat_service import ChatService, SessionBusyError
from rp_engine.core.llm.errors import LLMError
from rp_engine.core.memory.models import ConversationIdentity


def create_play_router(admin_service: AdminService, chat_service: ChatService) -> APIRouter:
    """Advance a story from the admin panel.

    Identity is the session id in the path, not a signed-in player. The panel already knows
    whose story it is, because the operator walked user -> sessions -> this one. That is the
    same operator exception S015 made for `override_persona`, and it is why these routes sit
    on the admin prefix instead of adding a second unauthenticated way in.

    The engine work is all upstream: every route here is a thin call into `ChatService`,
    which Telegram has been driving since S014.
    """
    router = APIRouter(prefix="/admin")

    async def _require_live_session(session_id: UUID) -> None:
        session = await admin_service.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.is_deleted:
            # A superseded session keeps a readable transcript and has no future (S016).
            # Sending a turn into one would either fail deeper down or quietly revive a
            # story the player already replaced.
            raise HTTPException(
                status_code=409, detail="This story is retired. It can be read, not continued."
            )

    async def _stored_reply(session_id: UUID) -> AdminMessageResponse:
        """Read back the narrator turn that was just written.

        The service returns the reply text alone. The panel needs the turn number and the
        finish reason with it, because the finish reason is what decides whether Continue
        offers to finish a cut-off sentence. One read here beats making every client refetch
        the whole transcript after every turn.
        """
        messages = await admin_service.get_session_transcript(session_id)
        if not messages:
            raise HTTPException(status_code=500, detail="The reply was generated but not stored.")
        return AdminMessageResponse.from_message(messages[-1])

    async def _advance(session_id: UUID, run: Callable[[], Awaitable[str]]) -> AdminMessageResponse:
        await _require_live_session(session_id)
        try:
            await run()
        except SessionBusyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            # The service writes these for the player, not for a log: "Last message is not a
            # character reply. Regenerate is not available yet." Pass the sentence through.
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except LLMError as exc:
            # The model failed, not the request. Say so with 502 so the panel can show a
            # reason instead of a bare 500.
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return await _stored_reply(session_id)

    @router.post("/sessions/{session_id}/turn")
    async def send_turn(session_id: UUID, payload: AdminPlayTurnRequest) -> AdminMessageResponse:
        return await _advance(
            session_id,
            lambda: chat_service.send_message(
                conversation_identity=ConversationIdentity.for_session(str(session_id)),
                message=payload.message,
            ),
        )

    @router.post("/sessions/{session_id}/continue")
    async def continue_turn(session_id: UUID) -> AdminMessageResponse:
        return await _advance(
            session_id,
            lambda: chat_service.continue_story(
                conversation_identity=ConversationIdentity.for_session(str(session_id)),
            ),
        )

    @router.post("/sessions/{session_id}/retry")
    async def retry_turn(session_id: UUID) -> AdminMessageResponse:
        return await _advance(
            session_id,
            lambda: chat_service.regenerate_last_response(
                conversation_identity=ConversationIdentity.for_session(str(session_id)),
            ),
        )

    return router
