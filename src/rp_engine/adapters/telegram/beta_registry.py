import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


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
        self._rejected_path = Path(base_path) / "telegram" / "beta_rejected"
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

    async def list_requests(self) -> list[TelegramBetaRequest]:
        async with self._lock:
            if not self._requests_path.exists():
                return []

            requests = await asyncio.to_thread(self._load_requests)
            requests.sort(key=self._request_sort_key)
            return requests

    async def get_request(self, *, telegram_id: int) -> TelegramBetaRequest | None:
        async with self._lock:
            request_path = self._request_path(telegram_id=telegram_id)
            if not request_path.exists():
                return None
            return await asyncio.to_thread(self._read_request_from_path, request_path)

    async def remove_request(self, *, telegram_id: int) -> bool:
        async with self._lock:
            request_path = self._request_path(telegram_id=telegram_id)
            if not request_path.exists():
                return False

            await asyncio.to_thread(request_path.unlink)
            return True

    async def archive_rejection(
        self,
        *,
        telegram_id: int,
        rejected_by_telegram_id: int,
        reason: str | None,
    ) -> TelegramBetaRequest | None:
        async with self._lock:
            request_path = self._request_path(telegram_id=telegram_id)
            if not request_path.exists():
                return None

            request = await asyncio.to_thread(self._read_request_from_path, request_path)
            payload = {
                "telegram_id": request.telegram_id,
                "username": request.username,
                "first_name": request.first_name,
                "last_name": request.last_name,
                "requested_at": request.requested_at,
                "status": "rejected",
                "rejected_at": datetime.now(tz=UTC).isoformat(),
                "rejected_by_telegram_id": rejected_by_telegram_id,
            }
            if reason:
                payload["rejection_reason"] = reason

            self._rejected_path.mkdir(parents=True, exist_ok=True)
            rejected_file = self._rejected_path / f"{telegram_id}.json"
            await asyncio.to_thread(self._write_payload, rejected_file, payload)
            await asyncio.to_thread(request_path.unlink)
            return request

    def _request_path(self, *, telegram_id: int) -> Path:
        return self._requests_path / f"{telegram_id}.json"

    def _load_requests(self) -> list[TelegramBetaRequest]:
        requests: list[TelegramBetaRequest] = []
        for file_path in self._requests_path.glob("*.json"):
            try:
                requests.append(self._read_request_from_path(file_path))
            except (json.JSONDecodeError, OSError, ValueError, TypeError):
                continue
        return requests

    @staticmethod
    def _request_sort_key(request: TelegramBetaRequest) -> tuple[datetime, int]:
        return (TelegramBetaRegistry._parse_requested_at(request.requested_at), request.telegram_id)

    @staticmethod
    def _parse_requested_at(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return datetime.min.replace(tzinfo=UTC)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed

    @staticmethod
    def _read_request_from_path(path: Path) -> TelegramBetaRequest:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        return TelegramBetaRegistry._request_from_payload(payload)

    @staticmethod
    def _request_from_payload(payload: dict[str, Any]) -> TelegramBetaRequest:
        return TelegramBetaRequest(
            telegram_id=int(payload["telegram_id"]),
            username=payload.get("username"),
            first_name=payload.get("first_name"),
            last_name=payload.get("last_name"),
            requested_at=str(payload.get("requested_at", "")),
            status=str(payload.get("status", "waiting_for_beta_seat")),
        )

    @staticmethod
    def _write_payload(path: Path, payload: dict[str, Any]) -> None:
        with path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=True, indent=2)

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
