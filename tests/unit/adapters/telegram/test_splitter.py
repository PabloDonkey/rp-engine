import pytest

from rp_engine.adapters.telegram.splitter import split_message


def test_short_message_returns_single_chunk() -> None:
    text = "Hello, world!"

    chunks = split_message(text, max_length=3800)

    assert chunks == [text]


def test_prefers_paragraph_boundaries() -> None:
    text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."

    chunks = split_message(text, max_length=30)

    assert "\n\n" in chunks[0]
    assert "".join(chunks) == text
    assert all(len(chunk) <= 30 for chunk in chunks)


def test_prefers_sentence_boundaries_before_whitespace() -> None:
    text = "First sentence. Second sentence. Third sentence."

    chunks = split_message(text, max_length=25)

    assert chunks[0].endswith(".")
    assert "".join(chunks) == text
    assert all(len(chunk) <= 25 for chunk in chunks)


def test_avoids_word_splitting_when_possible() -> None:
    text = "alpha beta gamma delta"

    chunks = split_message(text, max_length=12)

    assert chunks == ["alpha beta ", "gamma delta"]
    assert "".join(chunks) == text


def test_preserves_formatting_and_blank_lines_exactly() -> None:
    text = "- item 1\n- item 2\n\n    indented\n\n> quoted\n"

    chunks = split_message(text, max_length=15)

    assert "".join(chunks) == text
    assert all(len(chunk) <= 15 for chunk in chunks)


def test_handles_unicode_and_emoji() -> None:
    text = "Hero 😄 enters the tavern. Привет мир. こんにちは世界。"

    chunks = split_message(text, max_length=20)

    assert "".join(chunks) == text
    assert all(len(chunk) <= 20 for chunk in chunks)


def test_handles_extremely_long_word_with_hard_split() -> None:
    text = "x" * 25

    chunks = split_message(text, max_length=10)

    assert chunks == ["x" * 10, "x" * 10, "x" * 5]
    assert "".join(chunks) == text


def test_supports_multiple_blank_lines_and_trailing_whitespace() -> None:
    text = "Line 1\n\n\nLine 2   "

    chunks = split_message(text, max_length=8)

    assert "".join(chunks) == text
    assert all(len(chunk) <= 8 for chunk in chunks)


def test_empty_message_returns_no_chunks() -> None:
    assert split_message("", max_length=10) == []


def test_invalid_max_length_raises_value_error() -> None:
    with pytest.raises(ValueError, match="max_length must be greater than zero"):
        split_message("hello", max_length=0)
