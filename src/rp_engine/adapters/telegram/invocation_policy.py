from rp_engine.adapters.telegram.models import ParsedTransportMessage


def should_process_message(chat_type: str | None, parsed_message: ParsedTransportMessage) -> bool:
    if chat_type in {"group", "supergroup"}:
        return parsed_message.command is not None
    return True
