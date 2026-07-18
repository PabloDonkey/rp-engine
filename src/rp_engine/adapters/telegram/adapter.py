import logging
from datetime import UTC, datetime
from typing import Any, Protocol

from telegram import BotCommand, Update
from telegram.ext import Application as TelegramApplication
from telegram.ext import ContextTypes, MessageHandler, filters

from rp_engine.adapters.telegram.authorization import TelegramAuthorization
from rp_engine.adapters.telegram.beta_registry import TelegramBetaRegistry, TelegramBetaRequest
from rp_engine.adapters.telegram.commands import (
    TELEGRAM_MENU_COMMANDS,
    build_help_message,
    parse_transport_message,
)
from rp_engine.adapters.telegram.feedback import TelegramProcessingFeedbackFactory
from rp_engine.adapters.telegram.invocation_policy import should_process_message
from rp_engine.adapters.telegram.models import TelegramCommand
from rp_engine.adapters.telegram.splitter import split_message
from rp_engine.application.services.character_service import CharacterSelectionResult
from rp_engine.application.services.chat_service import ChatService
from rp_engine.application.services.commands import SelectCharacterCommand
from rp_engine.core.group.group import Group
from rp_engine.core.llm.errors import LLMConnectionError, LLMGenerationError, LLMTimeoutError
from rp_engine.core.memory.models import ConversationIdentity
from rp_engine.core.session.session import Session
from rp_engine.core.user.user import User

logger = logging.getLogger(__name__)

AUTHORIZED_START_MESSAGE = (
    "Welcome. I am ready to roleplay.\n"
    "Use /chat <message> to talk to the active character (especially in groups).\n"
    "Commands: /chat, /continue, /regenerate, /clear."
)

AUTHORIZED_START_PRIVATE_MESSAGE = (
    "\nIn private chats, you can also send normal messages directly."
)

UNAUTHORIZED_START_MESSAGE = (
    "Welcome. This bot is currently in closed beta.\n"
    "You are not authorized yet.\n"
    "Use /beta to request a seat.\n"
    "If you request access, your Telegram username and ID are recorded for admin review."
)

BETA_REGISTERED_MESSAGE = (
    "Thanks. You are already on the closed beta waiting list. "
    "Please wait for admin approval."
)

BETA_CREATED_MESSAGE = (
    "Thanks. Your beta request was recorded. "
    "An administrator will review it and contact you if approved."
)


class IdentityResolverPort(Protocol):
    async def resolve_identity(
        self,
        *,
        provider: str,
        external_id: str,
        display_name: str,
        metadata: dict[str, str] | None = None,
    ) -> User: ...


class CharacterServicePort(Protocol):
    async def select_character_for_user(
        self,
        *,
        user_id: Any,
        command: SelectCharacterCommand,
    ) -> CharacterSelectionResult: ...

    async def select_character_for_group(
        self,
        *,
        group_id: Any,
        actor_user_id: Any,
        command: SelectCharacterCommand,
    ) -> CharacterSelectionResult: ...

    async def ensure_active_session_for_user(self, *, user_id: Any) -> Session: ...

    async def ensure_active_session_for_group(
        self,
        *,
        group_id: Any,
        actor_user_id: Any,
    ) -> Session: ...

    async def describe_session_entry(self, *, session: Session) -> str | None: ...


class GroupIdentityResolverPort(Protocol):
    async def resolve_identity(
        self,
        *,
        provider: str,
        external_id: str,
        display_name: str,
        metadata: dict[str, str] | None = None,
    ) -> Group: ...


class CharacterCommandServicePort(Protocol):
    async def start_creation(self, *, user_id: Any) -> Any: ...

    async def start_edit(self, *, user_id: Any, character_name: str) -> Any: ...

    async def show_character(self, *, user_id: Any, character_name: str) -> Any: ...

    async def validate_character(self, *, user_id: Any, character_name: str) -> Any: ...

    async def cancel(self, *, user_id: Any) -> Any: ...

    async def has_active_workflow(self, *, user_id: Any) -> bool: ...

    async def handle_user_input(self, *, user_id: Any, text: str) -> Any | None: ...


class NoOpCharacterCommandService:
    async def start_creation(self, *, user_id: Any) -> Any:
        del user_id
        return _SimpleWorkflowResponse(message="Character workflows are not configured.")

    async def start_edit(self, *, user_id: Any, character_name: str) -> Any:
        del user_id
        del character_name
        return _SimpleWorkflowResponse(message="Character workflows are not configured.")

    async def show_character(self, *, user_id: Any, character_name: str) -> Any:
        del user_id
        del character_name
        return _SimpleWorkflowResponse(message="Character workflows are not configured.")

    async def validate_character(self, *, user_id: Any, character_name: str) -> Any:
        del user_id
        del character_name
        return _SimpleWorkflowResponse(message="Character workflows are not configured.")

    async def cancel(self, *, user_id: Any) -> Any:
        del user_id
        return _SimpleWorkflowResponse(message="No active operation to cancel.")

    async def has_active_workflow(self, *, user_id: Any) -> bool:
        del user_id
        return False

    async def handle_user_input(self, *, user_id: Any, text: str) -> Any | None:
        del user_id
        del text
        return None


class _SimpleWorkflowResponse:
    def __init__(self, *, message: str) -> None:
        self.message = message


class TelegramAdapter:
    def __init__(
        self,
        chat_service: ChatService,
        identity_resolver: IdentityResolverPort,
        group_identity_resolver: GroupIdentityResolverPort,
        character_service: CharacterServicePort,
        authorization: TelegramAuthorization,
        unauthorized_message: str,
        message_max_length: int,
        character_command_service: CharacterCommandServicePort | None = None,
        admin_telegram_user_id: str = "",
        processing_feedback_factory: TelegramProcessingFeedbackFactory | None = None,
        beta_registry: TelegramBetaRegistry | None = None,
    ) -> None:
        self._chat_service = chat_service
        self._identity_resolver = identity_resolver
        self._group_identity_resolver = group_identity_resolver
        self._character_service = character_service
        self._character_command_service = character_command_service or NoOpCharacterCommandService()
        self._authorization = authorization
        self._admin_telegram_user_id = admin_telegram_user_id
        self._unauthorized_message = unauthorized_message
        self._message_max_length = message_max_length
        self._processing_feedback_factory = (
            processing_feedback_factory or TelegramProcessingFeedbackFactory()
        )
        self._beta_registry = beta_registry or TelegramBetaRegistry()

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None or message.text is None:
            return

        user = update.effective_user
        user_id = str(user.id) if user is not None else "anonymous"
        chat = update.effective_chat
        chat_type = chat.type if chat is not None else None
        parsed_message = parse_transport_message(message.text)

        if parsed_message.command in {
            TelegramCommand.ADMIN_BETA_LIST,
            TelegramCommand.ADMIN_BETA_ACCEPT,
            TelegramCommand.ADMIN_BETA_REJECT,
        }:
            await self._handle_admin_command(
                parsed_command=parsed_message.command,
                argument=parsed_message.argument,
                user=user,
                message=message,
                context=context,
            )
            return

        if parsed_message.command == TelegramCommand.START:
            if self._is_authorized(chat_type=chat_type, user_id=user_id, chat=chat):
                welcome = AUTHORIZED_START_MESSAGE
                if chat_type == "private":
                    welcome = f"{welcome}{AUTHORIZED_START_PRIVATE_MESSAGE}"
                await self._reply_with_split(message=message, text=welcome)
                return

            await self._reply_with_split(message=message, text=UNAUTHORIZED_START_MESSAGE)
            return

        if parsed_message.command == TelegramCommand.BETA:
            if user is None:
                await self._reply_with_split(
                    message=message,
                    text="Unable to register a beta request for an unknown user.",
                )
                return

            created = await self._beta_registry.create_request(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
            )
            await self._reply_with_split(
                message=message,
                text=BETA_CREATED_MESSAGE if created else BETA_REGISTERED_MESSAGE,
            )
            return

        if not self._is_authorized(chat_type=chat_type, user_id=user_id, chat=chat):
            logger.info(
                "Telegram request denied",
                extra={"user_id": user_id, "chat_type": chat_type},
            )
            await self._reply_with_split(message=message, text=self._unauthorized_message)
            return

        resolved_user = await self._identity_resolver.resolve_identity(
            provider="telegram",
            external_id=user_id,
            display_name=self._resolve_user_display_name(user=user),
            metadata={
                "username": user.username or "",
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
            }
            if user is not None
            else {},
        )

        if not should_process_message(chat_type, parsed_message):
            return

        if parsed_message.command == TelegramCommand.CANCEL:
            cancel_response = await self._character_command_service.cancel(user_id=resolved_user.id)
            await self._reply_with_split(message=message, text=cancel_response.message)
            return

        if (
            not parsed_message.is_command
            and await self._character_command_service.has_active_workflow(
                user_id=resolved_user.id
            )
        ):
            workflow_response = await self._character_command_service.handle_user_input(
                user_id=resolved_user.id,
                text=parsed_message.text,
            )
            if workflow_response is not None:
                await self._reply_with_split(message=message, text=workflow_response.message)
                return

        is_group_chat = chat_type in {"group", "supergroup"}
        resolved_group: Group | None = None
        if is_group_chat:
            group_external_id = str(chat.id) if chat is not None else ""
            resolved_group = await self._group_identity_resolver.resolve_identity(
                provider="telegram",
                external_id=group_external_id,
                display_name=self._resolve_group_display_name(chat=chat),
                metadata={"chat_type": chat_type or "unknown"},
            )

        if parsed_message.command == TelegramCommand.CHARACTER:
            character_name = parsed_message.argument
            if character_name is None:
                await self._reply_with_split(
                    message=message,
                    text=(
                        "Usage:\n"
                        "/character <name>\n"
                        "/character create\n"
                        "/character edit <character>\n"
                        "/character show <character>\n"
                        "/character validate <character>"
                    ),
                )
                return

            subcommand, subcommand_arg = self._split_character_subcommand(character_name)
            if subcommand == "create":
                create_response = await self._character_command_service.start_creation(
                    user_id=resolved_user.id
                )
                await self._reply_with_split(message=message, text=create_response.message)
                return

            if subcommand == "edit":
                edit_response = await self._character_command_service.start_edit(
                    user_id=resolved_user.id,
                    character_name=subcommand_arg or "",
                )
                await self._reply_with_split(message=message, text=edit_response.message)
                return

            if subcommand == "show":
                show_response = await self._character_command_service.show_character(
                    user_id=resolved_user.id,
                    character_name=subcommand_arg or "",
                )
                await self._reply_with_split(message=message, text=show_response.message)
                return

            if subcommand == "validate":
                validate_response = await self._character_command_service.validate_character(
                    user_id=resolved_user.id,
                    character_name=subcommand_arg or "",
                )
                await self._reply_with_split(message=message, text=validate_response.message)
                return

            try:
                if resolved_group is None:
                    selection = await self._character_service.select_character_for_user(
                        user_id=resolved_user.id,
                        command=SelectCharacterCommand(character_name=character_name),
                    )
                else:
                    selection = await self._character_service.select_character_for_group(
                        group_id=resolved_group.id,
                        actor_user_id=resolved_user.id,
                        command=SelectCharacterCommand(character_name=character_name),
                    )
            except ValueError as exc:
                await self._reply_with_split(message=message, text=str(exc))
                return

            if selection.status == "already_active":
                await self._reply_with_split(
                    message=message,
                    text=f"Character '{selection.session.character_id}' is already active.",
                )
                return

            session_entry = await self._character_service.describe_session_entry(
                session=selection.session
            )
            await self._reply_with_split(
                message=message,
                text=session_entry
                or (
                    f"Active character set to '{selection.session.character_id}' in "
                    f"world '{selection.session.world_id}'."
                ),
            )
            return

        if resolved_group is None:
            active_session = await self._character_service.ensure_active_session_for_user(
                user_id=resolved_user.id
            )
        else:
            active_session = await self._character_service.ensure_active_session_for_group(
                group_id=resolved_group.id,
                actor_user_id=resolved_user.id,
            )
        conversation_identity = ConversationIdentity.for_session(str(active_session.id))

        logger.info(
            "Telegram message received",
            extra={"memory_key": conversation_identity.to_memory_key().value},
        )

        group_user_id = str(resolved_user.id) if is_group_chat else None
        group_username = user.username if user is not None and is_group_chat else None
        group_display_name = user.full_name if user is not None and is_group_chat else None

        try:
            if parsed_message.command == TelegramCommand.HELP:
                await self._reply_with_split(message=message, text=build_help_message())
                return

            if parsed_message.command == TelegramCommand.CONTINUE:
                if chat_type in {"group", "supergroup"} and not await self._is_group_admin(
                    context=context,
                    update=update,
                ):
                    await self._reply_with_split(
                        message=message,
                        text="Only group administrators can use this command.",
                    )
                    return
                response = await self._chat_service.continue_story(
                    conversation_identity=conversation_identity,
                    processing_feedback=self._processing_feedback_factory.create(
                        context=context,
                        source_message=message,
                    ),
                )
                await self._reply_with_split(message=message, text=response)
                return

            if parsed_message.command == TelegramCommand.REGENERATE:
                if chat_type in {"group", "supergroup"} and not await self._is_group_admin(
                    context=context,
                    update=update,
                ):
                    await self._reply_with_split(
                        message=message,
                        text="Only group administrators can use this command.",
                    )
                    return
                response = await self._chat_service.regenerate_last_response(
                    conversation_identity=conversation_identity,
                    processing_feedback=self._processing_feedback_factory.create(
                        context=context,
                        source_message=message,
                    ),
                )
                await self._reply_with_split(message=message, text=response)
                return

            if parsed_message.command == TelegramCommand.CLEAR:
                if chat_type in {"group", "supergroup"} and not await self._is_group_admin(
                    context=context,
                    update=update,
                ):
                    await self._reply_with_split(
                        message=message,
                        text="Only group administrators can use this command.",
                    )
                    return
                await self._chat_service.clear_conversation(
                    conversation_identity=conversation_identity,
                )
                await self._reply_with_split(message=message, text="Conversation memory cleared.")
                return

            outgoing_message = parsed_message.text
            if parsed_message.command == TelegramCommand.CHAT:
                if parsed_message.argument is None:
                    await self._reply_with_split(
                        message=message,
                        text="Usage: /chat <message>",
                    )
                    return
                outgoing_message = parsed_message.argument

            if parsed_message.is_command and parsed_message.command != TelegramCommand.CHAT:
                await self._reply_with_split(
                    message=message,
                    text="Unsupported command. Use /help to see available commands.",
                )
                return

            response = await self._chat_service.send_message(
                conversation_identity=conversation_identity,
                message=outgoing_message,
                user_id=group_user_id,
                username=group_username,
                display_name=group_display_name,
                processing_feedback=self._processing_feedback_factory.create(
                    context=context,
                    source_message=message,
                ),
            )
        except ValueError as exc:
            logger.warning(
                "Telegram failure",
                extra={"reason": "invalid_message", "user_id": user_id},
            )
            error_text = str(exc).strip() or "Please send a non-empty message."
            await self._reply_with_split(message=message, text=error_text)
            return
        except LLMConnectionError:
            logger.exception(
                "Telegram failure",
                extra={"reason": "llm_connection_error", "user_id": user_id},
            )
            await self._reply_with_split(
                message=message,
                text="LM backend is unavailable right now. Please try again in a moment.",
            )
            return
        except LLMTimeoutError:
            logger.exception(
                "Telegram failure",
                extra={"reason": "llm_timeout_error", "user_id": user_id},
            )
            await self._reply_with_split(
                message=message,
                text="The model took too long to reply. Please try again.",
            )
            return
        except LLMGenerationError:
            logger.exception(
                "Telegram failure",
                extra={"reason": "llm_generation_error", "user_id": user_id},
            )
            await self._reply_with_split(
                message=message,
                text="The model failed to generate a reply. Please try again.",
            )
            return
        except Exception:
            logger.exception(
                "Telegram failure",
                extra={"reason": "unexpected_error", "user_id": user_id},
            )
            await self._reply_with_split(
                message=message,
                text="Sorry, I could not process your message right now.",
            )
            return

        await self._reply_with_split(message=message, text=response)

    async def _handle_admin_command(
        self,
        *,
        parsed_command: TelegramCommand,
        argument: str | None,
        user: Any,
        message: Any,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self._is_admin_sender(user=user):
            return

        if parsed_command == TelegramCommand.ADMIN_BETA_LIST:
            requests = await self._beta_registry.list_requests()
            if not requests:
                await self._reply_with_split(
                    message=message,
                    text="There are no pending beta requests.",
                )
                return

            await self._reply_with_split(
                message=message,
                text=self._format_pending_requests(requests=requests),
            )
            return

        if parsed_command == TelegramCommand.ADMIN_BETA_ACCEPT:
            if argument is None:
                await self._reply_with_split(
                    message=message,
                    text="Usage: /admin_beta_accept <telegram_id|list_index>",
                )
                return

            target_request, resolve_error = await self._resolve_beta_request_target(
                argument=argument
            )
            if target_request is None:
                await self._reply_with_split(
                    message=message,
                    text=resolve_error or "No pending beta request matched the provided value.",
                )
                return

            target_id = str(target_request.telegram_id)
            if self._authorization.has_explicit_private_user(target_id):
                cleaned = await self._beta_registry.remove_request(
                    telegram_id=target_request.telegram_id
                )
                suffix = " and removed the pending request." if cleaned else "."
                await self._reply_with_split(
                    message=message,
                    text=f"Telegram ID {target_id} is already authorized{suffix}",
                )
                return

            self._authorization.add_private_user(target_id)
            self._authorization.persist()
            await self._beta_registry.remove_request(telegram_id=target_request.telegram_id)
            await self._reply_with_split(
                message=message,
                text=f"Approved Telegram ID {target_id} and updated authorization.",
            )

            await self._notify_approved_user(
                context=context,
                telegram_id=target_request.telegram_id,
            )
            return

        if parsed_command == TelegramCommand.ADMIN_BETA_REJECT:
            if argument is None:
                await self._reply_with_split(
                    message=message,
                    text="Usage: /admin_beta_reject <telegram_id|list_index> [reason]",
                )
                return

            target, reason = self._split_admin_target_and_reason(argument=argument)
            target_request, resolve_error = await self._resolve_beta_request_target(argument=target)
            if target_request is None:
                await self._reply_with_split(
                    message=message,
                    text=resolve_error or "No pending beta request matched the provided value.",
                )
                return

            if user is None:
                return

            archived = await self._beta_registry.archive_rejection(
                telegram_id=target_request.telegram_id,
                rejected_by_telegram_id=user.id,
                reason=reason,
            )
            if archived is None:
                await self._reply_with_split(
                    message=message,
                    text="No pending beta request matched the provided value.",
                )
                return

            await self._reply_with_split(
                message=message,
                text=f"Rejected Telegram ID {archived.telegram_id}.",
            )

    def _is_admin_sender(self, *, user: Any) -> bool:
        if user is None:
            return False
        return str(user.id) == self._admin_telegram_user_id

    async def _resolve_beta_request_target(
        self,
        *,
        argument: str,
    ) -> tuple[TelegramBetaRequest | None, str | None]:
        token = argument.strip().split(maxsplit=1)[0]
        try:
            raw_value = int(token)
        except ValueError:
            return None, "Expected a Telegram ID or list index as a number."

        requests = await self._beta_registry.list_requests()
        if not requests:
            return None, "There are no pending beta requests."

        for request in requests:
            if request.telegram_id == raw_value:
                return request, None

        if 1 <= raw_value <= len(requests):
            return requests[raw_value - 1], None

        return None, f"No pending beta request found for '{raw_value}'."

    @staticmethod
    def _split_admin_target_and_reason(*, argument: str) -> tuple[str, str | None]:
        pieces = argument.strip().split(maxsplit=1)
        target = pieces[0]
        reason = pieces[1].strip() if len(pieces) > 1 and pieces[1].strip() else None
        return target, reason

    async def _notify_approved_user(
        self,
        *,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_id: int,
    ) -> None:
        bot = getattr(context, "bot", None)
        if bot is None:
            return

        send_message = getattr(bot, "send_message", None)
        if send_message is None:
            return

        try:
            await send_message(
                chat_id=telegram_id,
                text=(
                    "Your beta request has been approved!\n\n"
                    "You can now use the bot.\n"
                    "Send /start to begin."
                ),
            )
        except Exception:
            logger.warning(
                "Failed to send beta approval notification",
                extra={"telegram_id": telegram_id},
            )

    def _format_pending_requests(self, *, requests: list[TelegramBetaRequest]) -> str:
        lines = ["Pending Beta Requests", ""]
        for index, request in enumerate(requests, start=1):
            username_value = request.username if request.username else "(none)"
            username = username_value if username_value.startswith("@") else f"@{username_value}"
            if username_value == "(none)":
                username = "(none)"

            full_name = " ".join(
                part.strip()
                for part in [request.first_name or "", request.last_name or ""]
                if part and part.strip()
            )
            name_value = full_name or "(unknown)"
            requested_at = self._format_requested_at(request.requested_at)
            lines.extend(
                [
                    f"{index}.",
                    f"Username: {username}",
                    f"Name: {name_value}",
                    f"Telegram ID: {request.telegram_id}",
                    f"Requested: {requested_at}",
                    "",
                ]
            )
            lines.append("-" * 40)
            lines.append("admin_beta_accept <telegram_id|list_index> - Approve the request")
            lines.append("admin_beta_reject <telegram_id|list_index> [reason] - Reject the request")
            lines.append("-" * 40)
        return "\n".join(lines).rstrip()

    @staticmethod
    def _format_requested_at(value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return value

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        normalized = parsed.astimezone(UTC)
        return normalized.strftime("%Y-%m-%d %H:%M UTC")

    def _is_authorized(self, *, chat_type: str | None, user_id: str, chat: Any) -> bool:
        if chat_type in {"group", "supergroup"}:
            group_id = str(chat.id) if chat is not None else ""
            return self._authorization.is_group_chat_authorized(group_id)
        return self._authorization.is_private_chat_authorized(user_id)

    async def _is_group_admin(
        self,
        *,
        context: ContextTypes.DEFAULT_TYPE,
        update: Update,
    ) -> bool:
        chat = update.effective_chat
        user = update.effective_user
        if chat is None or user is None:
            return False

        member = await context.bot.get_chat_member(chat_id=chat.id, user_id=user.id)
        return member.status in {"administrator", "creator"}

    async def _reply_with_split(self, *, message: Any, text: str) -> None:
        chunks = split_message(text, self._message_max_length)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Telegram message split",
                extra={
                    "characters": len(text),
                    "chunks": len(chunks),
                    "chunk_sizes": [len(chunk) for chunk in chunks],
                },
            )

        for chunk in chunks:
            await message.reply_text(chunk)

    @staticmethod
    def _resolve_group_display_name(*, chat: Any) -> str:
        if chat is not None:
            title = getattr(chat, "title", None)
            if isinstance(title, str) and title.strip():
                return title.strip()
            chat_id = getattr(chat, "id", None)
            if chat_id is not None:
                return f"Group {chat_id}"
        return "Group"

    @staticmethod
    def _resolve_user_display_name(*, user: Any) -> str:
        if user is not None:
            persona_display_name = getattr(user, "persona_display_name", None)
            if isinstance(persona_display_name, str) and persona_display_name.strip():
                return persona_display_name.strip()

            username = getattr(user, "username", None)
            if isinstance(username, str) and username.strip():
                return username.strip()

            first_name = getattr(user, "first_name", None)
            if isinstance(first_name, str) and first_name.strip():
                return first_name.strip()

            last_name = getattr(user, "last_name", None)
            if (
                isinstance(first_name, str)
                and first_name.strip()
                and isinstance(last_name, str)
                and last_name.strip()
            ):
                return f"{first_name.strip()} {last_name.strip()}"

            user_identifier = getattr(user, "id", None)
            if user_identifier is not None:
                return f"telegram_user_{user_identifier}"

        return "telegram_user_anonymous"

    @staticmethod
    def _split_character_subcommand(argument: str) -> tuple[str | None, str | None]:
        cleaned = argument.strip()
        if not cleaned:
            return None, None
        parts = cleaned.split(maxsplit=1)
        command = parts[0].strip().lower()
        if command not in {"create", "edit", "show", "validate"}:
            return None, None
        remainder = parts[1].strip() if len(parts) > 1 else None
        return command, remainder


class TelegramRuntime:
    def __init__(self, application: Any) -> None:
        self._application = application

    async def start(self) -> None:
        logger.info("Starting Telegram runtime")
        await self._application.initialize()
        await self._application.bot.set_my_commands(
            [
                BotCommand(command=name, description=description)
                for name, description in TELEGRAM_MENU_COMMANDS
            ]
        )
        await self._application.start()

        if self._application.updater is None:
            raise RuntimeError("Telegram updater is unavailable.")

        await self._application.updater.start_polling()
        logger.info("Telegram polling started")

    async def stop(self) -> None:
        logger.info("Stopping Telegram runtime")
        if self._application.updater is not None:
            await self._application.updater.stop()

        await self._application.stop()
        await self._application.shutdown()


def create_telegram_application(token: str, adapter: TelegramAdapter) -> Any:
    application = TelegramApplication.builder().token(token).http_version("2").build()
    handler = MessageHandler(filters.TEXT, adapter.handle_message)
    application.add_handler(handler)
    return application
