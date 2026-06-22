"""JSON file storage for memory persistence."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime objects."""

    def default(self, obj: Any) -> Any:
        """Encode datetime objects as ISO format strings.

        Args:
            obj: Object to encode

        Returns:
            JSON-serializable representation
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class JSONStore:
    """Manages JSON file storage for sessions, worlds, and characters."""

    @staticmethod
    def save(filepath: Path, data: Any) -> None:
        """Save data to JSON file.

        Args:
            filepath: Path to save to
            data: Data to save (typically a dict or Pydantic model)
        """
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Handle Pydantic models
        if hasattr(data, "model_dump"):
            data_dict = data.model_dump()
        else:
            data_dict = data

        with open(filepath, "w") as f:
            json.dump(data_dict, f, indent=2, cls=DateTimeEncoder)

    @staticmethod
    def load(filepath: Path) -> dict[str, Any]:
        """Load data from JSON file.

        Args:
            filepath: Path to load from

        Returns:
            Loaded data as dictionary

        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If file is not valid JSON
        """
        with open(filepath) as f:
            try:
                return cast(dict[str, Any], json.load(f))
            except json.JSONDecodeError as e:
                raise json.JSONDecodeError(
                    f"Failed to parse {filepath}: {e.msg}",
                    e.doc,
                    e.pos,
                ) from e

    @staticmethod
    def exists(filepath: Path) -> bool:
        """Check if file exists.

        Args:
            filepath: Path to check

        Returns:
            True if file exists
        """
        return filepath.exists()
