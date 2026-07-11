import re

SENTENCE_ENDINGS = {".", "!", "?", "…", ":"}
PARAGRAPH_BOUNDARY = re.compile(r"\n{2,}")


def split_message(text: str, max_length: int) -> list[str]:
    if max_length < 1:
        raise ValueError("max_length must be greater than zero.")

    if text == "":
        return []

    chunks: list[str] = []
    start = 0
    text_length = len(text)

    while text_length - start > max_length:
        window_end = start + max_length
        split_index = _find_split_index(text, start, window_end)
        if split_index <= start:
            split_index = window_end

        chunks.append(text[start:split_index])
        start = split_index

    chunks.append(text[start:])
    return chunks


def _find_split_index(text: str, start: int, window_end: int) -> int:
    paragraph_split = _find_paragraph_split(text, start, window_end)
    if paragraph_split is not None:
        return paragraph_split

    newline_split = text.rfind("\n", start + 1, window_end)
    if newline_split != -1:
        return newline_split + 1

    sentence_split = _find_sentence_split(text, start, window_end)
    if sentence_split is not None:
        return sentence_split

    whitespace_split = _find_whitespace_split(text, start, window_end)
    if whitespace_split is not None:
        return whitespace_split

    return window_end


def _find_paragraph_split(text: str, start: int, window_end: int) -> int | None:
    selected: int | None = None
    for match in PARAGRAPH_BOUNDARY.finditer(text, start, window_end):
        split_index = match.end()
        if split_index <= start:
            continue
        selected = split_index
    return selected


def _find_sentence_split(text: str, start: int, window_end: int) -> int | None:
    selected: int | None = None

    for index in range(start + 1, window_end):
        previous = text[index - 1]
        current = text[index]
        if previous in SENTENCE_ENDINGS and current.isspace():
            selected = index

    if window_end > start and text[window_end - 1] in SENTENCE_ENDINGS:
        selected = window_end

    return selected


def _find_whitespace_split(text: str, start: int, window_end: int) -> int | None:
    for index in range(window_end, start, -1):
        if text[index - 1].isspace():
            return index
    return None
