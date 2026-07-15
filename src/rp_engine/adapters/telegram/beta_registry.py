import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TelegramBetaRequest:
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    requested_at: str
    status: str


class TelegramBetaRegistry:
    def __init__(self, base_path: Path | str = "data") -> None:
        self._requests_path = Path(base_path) / "telegram" / "beta_requests"
        self._lock = asyncio.Lock()

    async def create_request(
        self,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> bool:
        async with self._lock:
            request_path = self._request_path(telegram_id=telegram_id)
            if request_path.exists():
                return False

            request = TelegramBetaRequest(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                requested_at=datetime.now(tz=UTC).isoformat(),
                status="waiting_for_beta_seat",
            )
            request_path.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(self._write_request, request_path, request)
            return True

    def _request_path(self, *, telegram_id: int) -> Path:
        return self._requests_path / f"{telegram_id}.json"

    @staticmethod
    def _write_request(path: Path, request: TelegramBetaRequest) -> None:
        payload = {
            "telegram_id": request.telegram_id,
            "username": request.username,
            "first_name": request.first_name,
            "last_name": request.last_name,
            "requested_at": request.requested_at,
            "status": request.status,
        }
        with path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=True, indent=2)
