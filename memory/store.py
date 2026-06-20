"""JSON file storage for memory persistence."""

import json
from pathlib import Path
from typing import Any


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
            json.dump(data_dict, f, indent=2)

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
        with open(filepath, "r") as f:
            return json.load(f)

    @staticmethod
    def exists(filepath: Path) -> bool:
        """Check if file exists.

        Args:
            filepath: Path to check

        Returns:
            True if file exists
        """
        return filepath.exists()
