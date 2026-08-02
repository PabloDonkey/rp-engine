import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

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
from rp_engine.adapters.telegram.models import TelegramCommand
from rp_engine.adapters.telegram.narrator_store import TelegramNarratorStore
from rp_engine.adapters.telegram.pending_persona_store import TelegramPendingPersonaStore
from rp_engine.adapters.telegram.splitter import split_message
from rp_engine.application.services.chat_service import ChatService
from rp_engine.application.services.playthrough_service import PlaythroughStart
from rp_engine.core.conversation.builder import ConversationBuilder
from rp_engine.core.group.group import Group
from rp_engine.core.llm.errors import (
    EmptyGenerationError,
    LLMConnectionError,
    LLMGenerationError,
    LLMTimeoutError,
)
from rp_engine.core.memory.models import ConversationIdentity
from rp_engine.core.prompts.templates import resolve_templates
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.scenario_session import ScenarioSession, SessionOwnerKind
from rp_engine.core.scenario.session_directives import (
    SUPPORTED_LANGUAGES,
    ScenarioRule,
    SessionDirectives,
    language_name,
    normalize_language,
)
from rp_engine.core.scenario.user_persona import parse_persona_reply
from rp_engine.core.user.user import User

logger = logging.getLogger(__name__)

AUTHORIZED_START_NO_PLAY_MESSAGE = (
    "Welcome back. You don't have an adventure in progress.\n"
    "Browse the library with /scenarios, then begin one with /play <id>."
)

AUTHORIZED_START_RESUME_MESSAGE = "Resuming your adventure...\n\n"

AUTHORIZED_START_RESUME_FALLBACK = (
    "You're in the middle of an adventure. Send a message to continue, "
    "or /restart to begin again."
)

NO_ACTIVE_PLAYTHROUGH_MESSAGE = (
    "You don't have an adventure in progress.\n"
    "Use /scenarios to browse, then /play <id> to begin."
)

GROUP_ADMIN_ONLY_MESSAGE = "Only group administrators can use this command."

EMPTY_GENERATION_MESSAGE = (
    "The model spent its whole budget thinking and didn't write a reply.\n"
    "Nothing was saved — send your message again, or use /continue."
)

# Session-directive commands (S014). They all operate on the active playthrough.
DIRECTIVE_COMMANDS: frozenset[TelegramCommand] = frozenset(
    {
        TelegramCommand.DIRECTOR,
        TelegramCommand.RULE,
        TelegramCommand.RULES,
        TelegramCommand.LANGUAGE,
    }
)

DIRECTOR_USAGE_MESSAGE = (
    "Usage: /director <instruction>\n\n"
    "Example: /director have someone interrupt the conversation.\n"
    "It shapes the next reply only, and the story never mentions it.\n"
    "Send it again to queue more notes for that same reply."
)

RULE_USAGE_MESSAGE = (
    "Usage:\n"
    "/rule add <rule> - Add a rule for the rest of this adventure\n"
    "/rule remove <id> - Remove one of your rules\n"
    "/rules - List your rules"
)

NO_RULES_MESSAGE = (
    "You haven't set any rules for this adventure.\nAdd one with /rule add <rule>."
)

# S015 — persona capture. The prompt replaces the story intro for a brand-new session; the
# intro is sent once the player has answered (or skipped).
PERSONA_PROMPT_MESSAGE = (
    "Before we begin — who are you playing?\n\n"
    "Send one message with your character's name on the first line, and a description of "
    "what they are and their likes/dislikes underneath.\n\n"
    "For example:\n"
    "Sera Vane\n"
    "A wary courier who trusts machines more than people. Loves rain, hates crowds.\n\n"
    "This cannot be changed once the adventure starts — /clear is the way to start over "
    "with a different character.\n"
    "Send /skip to use your Telegram name with no description."
)

PERSONA_NAME_REQUIRED_MESSAGE = (
    "I need a name on the first line to know who you're playing.\n"
    "Send it again, or /skip to use your Telegram name."
)

PERSONA_PROMPT_EXPIRED_MESSAGE = (
    "That character couldn't be applied — the adventure has moved on since I asked.\n"
    "Use /start to pick up where you are, or /clear to start over."
)

NOTHING_TO_SKIP_MESSAGE = "There's nothing to skip right now."

CLEAR_CONFIRM_MESSAGE = (
    "/clear starts this adventure completely over:\n\n"
    "• the story restarts from the beginning\n"
    "• you choose a new character\n"
    "• your language and rules go back to defaults\n\n"
    "The transcript so far is kept for the record, but you cannot play it further.\n"
    "Send /clear confirm to go ahead, or /restart to just replay the story with your "
    "current character and settings."
)

CLEAR_USAGE_MESSAGE = "Usage: /clear confirm"

UNAUTHORIZED_START_MESSAGE = (
    "Welcome. This bot is currently in closed beta.\n"
    "You are not authorized yet.\n"
    "Use /beta to request a seat.\n"
    "If you request access, your Telegram username and ID are recorded for admin review."
)


@dataclass(frozen=True, slots=True)
class _OwnerContext:
    owner_kind: SessionOwnerKind
    owner_id: UUID
    is_group: bool
    resolved_user: User
    resolved_group: Group | None

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


class PlaythroughServicePort(Protocol):
    async def list_scenarios(
        self, *, caller_group_chat_id: str | None = None
    ) -> list[ScenarioDefinition]: ...

    async def get_active(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: Any,
    ) -> ScenarioSession | None: ...

    async def start(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: Any,
        scenario_id: str,
        caller_group_chat_id: str | None = None,
    ) -> PlaythroughStart | None: ...

    async def restart(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: Any,
    ) -> PlaythroughStart | None: ...

    async def clear(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: Any,
    ) -> PlaythroughStart | None: ...

    async def set_persona(
        self,
        *,
        session_id: UUID,
        name: str,
        description: str = "",
    ) -> PlaythroughStart | None: ...

    async def resume_text(self, *, session: ScenarioSession) -> str | None: ...


class SessionDirectiveServicePort(Protocol):
    async def set_language(
        self, *, session: ScenarioSession, language: str
    ) -> SessionDirectives: ...

    async def add_rule(self, *, session: ScenarioSession, text: str) -> ScenarioRule: ...

    async def remove_rule(self, *, session: ScenarioSession, rule_id: str) -> bool: ...

    async def add_director_instruction(
        self, *, session: ScenarioSession, instruction: str
    ) -> SessionDirectives: ...


class GroupIdentityResolverPort(Protocol):
    async def resolve_identity(
        self,
        *,
        provider: str,
        external_id: str,
        display_name: str,
        metadata: dict[str, str] | None = None,
    ) -> Group: ...


class TelegramAdapter:
    def __init__(
        self,
        chat_service: ChatService,
        identity_resolver: IdentityResolverPort,
        group_identity_resolver: GroupIdentityResolverPort,
        playthrough_service: PlaythroughServicePort,
        session_directive_service: SessionDirectiveServicePort,
        authorization: TelegramAuthorization,
        unauthorized_message: str,
        message_max_length: int,
        admin_telegram_user_id: str = "",
        processing_feedback_factory: TelegramProcessingFeedbackFactory | None = None,
        beta_registry: TelegramBetaRegistry | None = None,
        narrator_store: TelegramNarratorStore | None = None,
        pending_persona_store: TelegramPendingPersonaStore | None = None,
    ) -> None:
        self._chat_service = chat_service
        self._identity_resolver = identity_resolver
        self._group_identity_resolver = group_identity_resolver
        self._playthrough_service = playthrough_service
        self._session_directive_service = session_directive_service
        self._authorization = authorization
        self._admin_telegram_user_id = admin_telegram_user_id
        self._unauthorized_message = unauthorized_message
        self._message_max_length = message_max_length
        self._processing_feedback_factory = (
            processing_feedback_factory or TelegramProcessingFeedbackFactory()
        )
        self._beta_registry = beta_registry or TelegramBetaRegistry()
        self._narrator_store = narrator_store or TelegramNarratorStore()
        self._pending_persona_store = pending_persona_store or TelegramPendingPersonaStore()

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

        authorized = self._is_authorized(chat_type=chat_type, user_id=user_id, chat=chat)

        # /start — state-aware entry point.
        if parsed_message.command == TelegramCommand.START:
            if not authorized:
                await self._reply_with_split(message=message, text=UNAUTHORIZED_START_MESSAGE)
                return
            owner = await self._resolve_owner(user=user, chat=chat, chat_type=chat_type)
            active = await self._playthrough_service.get_active(
                owner_kind=owner.owner_kind, owner_id=owner.owner_id
            )
            if active is None:
                await self._reply_with_split(
                    message=message, text=AUTHORIZED_START_NO_PLAY_MESSAGE
                )
                return
            resume = await self._playthrough_service.resume_text(session=active)
            resume_text = (
                f"{AUTHORIZED_START_RESUME_MESSAGE}{resume}"
                if resume
                else AUTHORIZED_START_RESUME_FALLBACK
            )
            await self._reply_with_split(message=message, text=resume_text)
            return

        # /beta — available to everyone; it is how access is requested.
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

        # /help — available to everyone, tailored to the caller's access level.
        if parsed_message.command == TelegramCommand.HELP:
            await self._reply_with_split(
                message=message, text=build_help_message(authorized=authorized)
            )
            return

        if not authorized:
            logger.info(
                "Telegram request denied",
                extra={"user_id": user_id, "chat_type": chat_type},
            )
            await self._reply_with_split(message=message, text=self._unauthorized_message)
            return

        owner = await self._resolve_owner(user=user, chat=chat, chat_type=chat_type)
        # Scenario access is locked to Telegram group chats, so only group callers carry a
        # chat id; direct chats are outsiders for RESTRICTED scenarios.
        caller_group_chat_id = self._chat_id(chat) if owner.is_group else None

        # A pending persona prompt claims the *next plain-text message* (and /skip), but
        # deliberately blocks nothing else: an abandoned prompt must never wedge a chat, so
        # every other command falls through to its normal handler below.
        if parsed_message.command == TelegramCommand.SKIP or not parsed_message.is_command:
            handled = await self._try_handle_persona_reply(
                message=message,
                owner=owner,
                parsed_text=parsed_message.text,
                is_skip=parsed_message.command == TelegramCommand.SKIP,
            )
            if handled:
                return

        # /cancel — no scripted menus exist in this pass; acknowledge and move on.
        if parsed_message.command == TelegramCommand.CANCEL:
            await self._reply_with_split(message=message, text="Nothing to cancel.")
            return

        # /scenarios — browse the curated library.
        if parsed_message.command == TelegramCommand.SCENARIOS:
            scenarios = await self._playthrough_service.list_scenarios(
                caller_group_chat_id=caller_group_chat_id
            )
            await self._reply_with_split(
                message=message,
                text=self._format_scenarios(scenarios),
            )
            return

        # /play <id> — begin (or replace) a playthrough. Story control -> group admins only.
        if parsed_message.command == TelegramCommand.PLAY:
            if owner.is_group and not await self._is_group_admin(context=context, update=update):
                await self._reply_with_split(message=message, text=GROUP_ADMIN_ONLY_MESSAGE)
                return
            scenario_id = (parsed_message.argument or "").strip()
            if not scenario_id:
                scenarios = await self._playthrough_service.list_scenarios(
                    caller_group_chat_id=caller_group_chat_id
                )
                await self._reply_with_split(
                    message=message,
                    text="Usage: /play <id>\n\n" + self._format_scenarios(scenarios),
                )
                return
            started = await self._playthrough_service.start(
                owner_kind=owner.owner_kind,
                owner_id=owner.owner_id,
                scenario_id=scenario_id,
                caller_group_chat_id=caller_group_chat_id,
            )
            if started is None:
                await self._reply_with_split(
                    message=message,
                    text=f"No scenario '{scenario_id}'. Use /scenarios to see the library.",
                )
                return
            # A genuinely new personal playthrough asks who the player is *before* showing
            # the intro; resuming an existing one asks nothing, and group sessions have no
            # single player to ask (their `{{user}}` is the group itself).
            if not started.resumed and not owner.is_group:
                await self._prompt_for_persona(message=message, owner=owner, started=started)
                return
            await self._reply_with_split(
                message=message,
                text=self._format_start(started, user=owner.resolved_user),
            )
            return

        # The remaining commands operate on the active playthrough.
        active_session = await self._playthrough_service.get_active(
            owner_kind=owner.owner_kind, owner_id=owner.owner_id
        )
        if active_session is None:
            # Groups address the story only via /chat, so ignore their plain chatter.
            if owner.is_group and not parsed_message.is_command:
                return
            await self._reply_with_split(message=message, text=NO_ACTIVE_PLAYTHROUGH_MESSAGE)
            return
        conversation_identity = ConversationIdentity.for_session(str(active_session.id))
        logger.info(
            "Telegram message received",
            extra={"memory_key": conversation_identity.to_memory_key().value},
        )

        # /restart — story control -> group admins only. It carries the player's character,
        # language and rules into the new session (ADR-025), so it never re-asks for a
        # persona; /clear below is the tier that resets them.
        if parsed_message.command == TelegramCommand.RESTART:
            if owner.is_group and not await self._is_group_admin(context=context, update=update):
                await self._reply_with_split(message=message, text=GROUP_ADMIN_ONLY_MESSAGE)
                return
            restarted = await self._playthrough_service.restart(
                owner_kind=owner.owner_kind, owner_id=owner.owner_id
            )
            if restarted is None:
                await self._reply_with_split(message=message, text=NO_ACTIVE_PLAYTHROUGH_MESSAGE)
                return
            await self._reply_with_split(
                message=message,
                text=self._format_start(restarted, user=owner.resolved_user, restarted=True),
            )
            return

        # /clear — the full reset. It is the only command that destroys player-authored
        # configuration and sits one letter from /continue in the menu, so it confirms
        # first. Story control -> group admins only, like /restart.
        if parsed_message.command == TelegramCommand.CLEAR:
            if owner.is_group and not await self._is_group_admin(context=context, update=update):
                await self._reply_with_split(message=message, text=GROUP_ADMIN_ONLY_MESSAGE)
                return
            confirmation = (parsed_message.argument or "").strip().lower()
            if not confirmation:
                await self._reply_with_split(message=message, text=CLEAR_CONFIRM_MESSAGE)
                return
            if confirmation != "confirm":
                await self._reply_with_split(message=message, text=CLEAR_USAGE_MESSAGE)
                return
            cleared = await self._playthrough_service.clear(
                owner_kind=owner.owner_kind, owner_id=owner.owner_id
            )
            if cleared is None:
                await self._reply_with_split(message=message, text=NO_ACTIVE_PLAYTHROUGH_MESSAGE)
                return
            if not owner.is_group:
                await self._prompt_for_persona(message=message, owner=owner, started=cleared)
                return
            await self._reply_with_split(
                message=message,
                text=self._format_start(cleared, user=owner.resolved_user, restarted=True),
            )
            return

        # /director, /rule, /rules, /language — session directives. Like the other story
        # controls, groups restrict them to their administrators.
        if parsed_message.command in DIRECTIVE_COMMANDS:
            if owner.is_group and not await self._is_group_admin(context=context, update=update):
                await self._reply_with_split(message=message, text=GROUP_ADMIN_ONLY_MESSAGE)
                return
            await self._reply_with_split(
                message=message,
                text=await self._handle_directive_command(
                    command=parsed_message.command,
                    argument=parsed_message.argument,
                    session=active_session,
                ),
            )
            return

        group_user_id = str(owner.resolved_user.id) if owner.is_group else None
        group_username = user.username if user is not None and owner.is_group else None
        group_display_name = user.full_name if user is not None and owner.is_group else None

        try:
            # /continue and /retry — story control -> group admins only.
            if parsed_message.command in {TelegramCommand.CONTINUE, TelegramCommand.RETRY}:
                if owner.is_group and not await self._is_group_admin(
                    context=context, update=update
                ):
                    await self._reply_with_split(message=message, text=GROUP_ADMIN_ONLY_MESSAGE)
                    return
                feedback = self._processing_feedback_factory.create(
                    context=context, source_message=message
                )
                if parsed_message.command == TelegramCommand.CONTINUE:
                    response = await self._chat_service.continue_story(
                        conversation_identity=conversation_identity,
                        processing_feedback=feedback,
                    )
                    await self._send_narrator_reply(message=message, chat=chat, text=response)
                    return
                # /retry: regenerate, then replace the previous narrator message in place.
                response = await self._chat_service.regenerate_last_response(
                    conversation_identity=conversation_identity,
                    processing_feedback=feedback,
                )
                await self._delete_tracked_narrator(context=context, chat=chat)
                await self._send_narrator_reply(message=message, chat=chat, text=response)
                return

            # /chat <message> is the group interaction command; in private chats plain
            # messages are the primary way to play.
            if parsed_message.command == TelegramCommand.CHAT:
                if parsed_message.argument is None:
                    await self._reply_with_split(message=message, text="Usage: /chat <message>")
                    return
                outgoing_message = parsed_message.argument
            elif parsed_message.is_command:
                await self._reply_with_split(
                    message=message,
                    text="Unsupported command. Use /help to see available commands.",
                )
                return
            elif owner.is_group:
                # Ignore plain messages in groups; they must use /chat to address the story.
                return
            else:
                outgoing_message = parsed_message.text

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
        # Must precede the LLMGenerationError arm below — EmptyGenerationError subclasses it.
        except EmptyGenerationError as exc:
            logger.warning(
                "Telegram failure",
                extra={
                    "reason": "llm_empty_generation",
                    "user_id": user_id,
                    "finish_reason": exc.finish_reason,
                },
            )
            await self._reply_with_split(message=message, text=EMPTY_GENERATION_MESSAGE)
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

        await self._send_narrator_reply(message=message, chat=chat, text=response)

    async def _handle_directive_command(
        self,
        *,
        command: TelegramCommand | None,
        argument: str | None,
        session: ScenarioSession,
    ) -> str:
        """Apply one session-directive command and return the reply text.

        Parsing and wording live here; the directives themselves are owned by the domain,
        so this only translates between Telegram syntax and `SessionDirectiveService`.
        """
        if command == TelegramCommand.DIRECTOR:
            return await self._handle_director(session=session, argument=argument)
        if command == TelegramCommand.LANGUAGE:
            return await self._handle_language(session=session, argument=argument)
        if command == TelegramCommand.RULES:
            return self._format_rules(session.directives.rules)
        if command == TelegramCommand.RULE:
            return await self._handle_rule(session=session, argument=argument)
        return RULE_USAGE_MESSAGE

    async def _handle_director(
        self,
        *,
        session: ScenarioSession,
        argument: str | None,
    ) -> str:
        instruction = (argument or "").strip()
        if not instruction:
            pending = session.directives.director_instructions
            if pending:
                queued = "\n".join(f"- {note}" for note in pending)
                return (
                    f"{len(pending)} director note{'s' if len(pending) > 1 else ''} queued "
                    f"for the next reply:\n\n{queued}\n\n"
                    "Send /director <instruction> to add another."
                )
            return DIRECTOR_USAGE_MESSAGE

        directives = await self._session_directive_service.add_director_instruction(
            session=session,
            instruction=instruction,
        )
        # The count is the point: notes stack, so the player needs to see that the earlier
        # ones are still armed rather than assume this one replaced them.
        total = len(directives.director_instructions)
        if total == 1:
            return "Director note set. It shapes the next reply only."
        return f"Director note added — {total} queued. They shape the next reply only."

    async def _handle_language(
        self,
        *,
        session: ScenarioSession,
        argument: str | None,
    ) -> str:
        requested = (argument or "").strip()
        if not requested:
            current = session.directives.language
            return (
                f"Current language: {language_name(current)} ({current}).\n\n"
                f"Usage: /language <code>\n{self._supported_languages_text()}"
            )

        code = normalize_language(requested)
        if code is None:
            return (
                f"Unsupported language '{requested}'.\n\n{self._supported_languages_text()}"
            )

        await self._session_directive_service.set_language(session=session, language=code)
        if code == "auto":
            return "Language set to automatic. The story follows the scenario and your writing."
        return f"Language set to {language_name(code)}. Replies will be in {language_name(code)}."

    async def _handle_rule(
        self,
        *,
        session: ScenarioSession,
        argument: str | None,
    ) -> str:
        pieces = (argument or "").strip().split(maxsplit=1)
        subcommand = pieces[0].lower() if pieces else ""
        remainder = pieces[1].strip() if len(pieces) > 1 else ""

        if subcommand == "list":
            return self._format_rules(session.directives.rules)

        if subcommand == "add":
            if not remainder:
                return "Usage: /rule add <rule>"
            rule = await self._session_directive_service.add_rule(
                session=session, text=remainder
            )
            return f"Rule {rule.id} added: {rule.text}"

        if subcommand == "remove":
            rule_id = remainder.split(maxsplit=1)[0] if remainder else ""
            if not rule_id:
                return "Usage: /rule remove <id>"
            removed = await self._session_directive_service.remove_rule(
                session=session, rule_id=rule_id
            )
            if not removed:
                return f"No rule with id {rule_id}. Use /rules to see your rules."
            return f"Rule {rule_id} removed."

        return RULE_USAGE_MESSAGE

    @staticmethod
    def _format_rules(rules: tuple[ScenarioRule, ...]) -> str:
        if not rules:
            return NO_RULES_MESSAGE
        lines = ["Your rules for this adventure:", ""]
        lines.extend(f"{rule.id}. {rule.text}" for rule in rules)
        lines.append("")
        lines.append("Remove one with /rule remove <id>.")
        return "\n".join(lines)

    @staticmethod
    def _supported_languages_text() -> str:
        codes = ", ".join(SUPPORTED_LANGUAGES)
        return f"Supported codes: {codes}"

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

    async def _send_narrator_reply(self, *, message: Any, chat: Any, text: str) -> None:
        """Send a narrator (story) reply and remember its message ids for `/retry`."""
        chunks = split_message(text, self._message_max_length)
        if not chunks:
            logger.warning(
                "Refusing to send an empty narrator reply",
                extra={"chat_id": self._chat_id(chat)},
            )
            return
        message_ids: list[int] = []
        for chunk in chunks:
            sent = await message.reply_text(chunk)
            sent_id = getattr(sent, "message_id", None)
            if isinstance(sent_id, int):
                message_ids.append(sent_id)

        chat_id = self._chat_id(chat)
        if chat_id is not None and message_ids:
            await self._narrator_store.set(chat_id=chat_id, message_ids=message_ids)

    async def _delete_tracked_narrator(self, *, context: Any, chat: Any) -> None:
        """Best-effort delete the previously tracked narrator message(s) for this chat."""
        chat_id = self._chat_id(chat)
        if chat_id is None:
            return
        bot = getattr(context, "bot", None) if context is not None else None
        message_ids = await self._narrator_store.get(chat_id=chat_id)
        if bot is not None:
            for message_id in message_ids:
                try:
                    await bot.delete_message(chat_id=chat.id, message_id=message_id)
                except Exception:
                    logger.debug(
                        "Failed to delete previous narrator message",
                        extra={"chat_id": chat_id, "message_id": message_id},
                    )
        await self._narrator_store.clear(chat_id=chat_id)

    @staticmethod
    def _chat_id(chat: Any) -> str | None:
        if chat is None:
            return None
        chat_id = getattr(chat, "id", None)
        return str(chat_id) if chat_id is not None else None

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

    async def _resolve_owner(
        self,
        *,
        user: Any,
        chat: Any,
        chat_type: str | None,
    ) -> _OwnerContext:
        external_id = str(user.id) if user is not None else "anonymous"
        resolved_user = await self._identity_resolver.resolve_identity(
            provider="telegram",
            external_id=external_id,
            display_name=self._resolve_user_display_name(user=user),
            metadata={
                "username": user.username or "",
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
            }
            if user is not None
            else {},
        )

        is_group = chat_type in {"group", "supergroup"}
        if not is_group:
            return _OwnerContext(
                owner_kind="user",
                owner_id=resolved_user.id,
                is_group=False,
                resolved_user=resolved_user,
                resolved_group=None,
            )

        group_external_id = str(chat.id) if chat is not None else ""
        resolved_group = await self._group_identity_resolver.resolve_identity(
            provider="telegram",
            external_id=group_external_id,
            display_name=self._resolve_group_display_name(chat=chat),
            metadata={"chat_type": chat_type or "unknown"},
        )
        return _OwnerContext(
            owner_kind="group",
            owner_id=resolved_group.id,
            is_group=True,
            resolved_user=resolved_user,
            resolved_group=resolved_group,
        )

    @staticmethod
    def _format_scenarios(scenarios: list[ScenarioDefinition]) -> str:
        if not scenarios:
            return "No adventures are available yet. Check back soon."
        lines = ["Available adventures:", ""]
        for scenario in scenarios:
            summary = scenario.description.strip()
            lines.append(f"• {scenario.name}" + (f" — {summary}" if summary else ""))
            lines.append(f"  /play {scenario.id}")
        return "\n".join(lines)

    async def _prompt_for_persona(
        self,
        *,
        message: Any,
        owner: _OwnerContext,
        started: PlaythroughStart,
    ) -> None:
        """Ask who the player is, and remember which session the answer belongs to.

        Writing the pending state unconditionally is what makes an abandoned prompt
        harmless: a second `/play` or `/clear` overwrites the pointer, so the reply always
        lands on the session the player most recently started.
        """
        await self._pending_persona_store.set(
            owner_kind=owner.owner_kind,
            owner_id=str(owner.owner_id),
            session_id=started.session.id,
        )
        await self._reply_with_split(message=message, text=PERSONA_PROMPT_MESSAGE)

    async def _try_handle_persona_reply(
        self,
        *,
        message: Any,
        owner: _OwnerContext,
        parsed_text: str,
        is_skip: bool,
    ) -> bool:
        """Consume this message as a persona reply if one is owed. Returns whether it was
        handled, so the caller can fall through to normal dispatch when it wasn't."""
        if owner.is_group:
            return False

        pending_session_id = await self._pending_persona_store.get(
            owner_kind=owner.owner_kind, owner_id=str(owner.owner_id)
        )
        if pending_session_id is None:
            if is_skip:
                await self._reply_with_split(message=message, text=NOTHING_TO_SKIP_MESSAGE)
                return True
            return False

        if is_skip:
            name, description = owner.resolved_user.display_name, ""
        else:
            try:
                name, description = parse_persona_reply(parsed_text)
            except ValueError:
                # Ask again rather than guessing: a blank first line is not a skip, and the
                # pending state stays so the next message is still read as the answer.
                await self._reply_with_split(
                    message=message, text=PERSONA_NAME_REQUIRED_MESSAGE
                )
                return True

        started = await self._playthrough_service.set_persona(
            session_id=pending_session_id, name=name, description=description
        )
        await self._pending_persona_store.clear(
            owner_kind=owner.owner_kind, owner_id=str(owner.owner_id)
        )
        if started is None:
            await self._reply_with_split(message=message, text=PERSONA_PROMPT_EXPIRED_MESSAGE)
            return True

        await self._reply_with_split(
            message=message,
            text=(
                f"You are playing {started.session.user_persona_name}.\n\n"
                f"{self._format_start(started, user=owner.resolved_user)}"
            ),
        )
        return True

    @staticmethod
    def _format_start(
        start: PlaythroughStart,
        *,
        user: User,
        restarted: bool = False,
    ) -> str:
        if restarted:
            verb = "Restarted"
        elif start.resumed:
            verb = "Resuming"
        else:
            verb = "Starting"
        # Scenario text is stored with its `{{...}}` placeholders intact and resolved at
        # render time, so the opening the player reads names their persona exactly as the
        # prompt does.
        character = ConversationBuilder.resolve_active_character(
            scenario=start.scenario, session=start.session
        )
        opening = resolve_templates(
            start.opening,
            user_name=start.session.resolve_user_name(user.display_name),
            character_name=character.name if character is not None else "",
            world_name=start.scenario.world.name if start.scenario.world is not None else "",
        )
        return f"{verb}: {start.scenario.name}\n\n{opening}"


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
