from rp_engine.adapters.telegram.models import ParsedTransportMessage


def should_process_message(chat_type: str | None, parsed_message: ParsedTransportMessage) -> bool:
    del chat_type
    del parsed_message
    return True
