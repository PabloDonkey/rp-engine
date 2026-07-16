from fastapi import APIRouter, HTTPException

from rp_engine.adapters.api.models import ChatRequest, ClearConversationRequest, ContinueRequest
from rp_engine.application.services.chat_service import ChatService


def create_router(chat_service: ChatService) -> APIRouter:
    router = APIRouter()

    @router.post("/chat")
    async def send_message(payload: ChatRequest) -> dict[str, str]:
        try:
            response = await chat_service.send_message(
                conversation_identity=payload.to_identity(),
                message=payload.message,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return {"response": response}

    @router.post("/continue")
    async def continue_story(payload: ContinueRequest) -> dict[str, str]:
        response = await chat_service.continue_story(
            conversation_identity=payload.to_identity(),
        )
        return {"response": response}

    @router.post("/memory/clear")
    async def clear_conversation(payload: ClearConversationRequest) -> dict[str, str]:
        await chat_service.clear_conversation(
            conversation_identity=payload.to_identity(),
        )
        return {"status": "cleared"}

    return router
