"""Application configuration management."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration."""

    # LM Studio API
    LM_STUDIO_API_URL: str = os.getenv(
        "LM_STUDIO_API_URL", "http://localhost:1234/v1"
    )

    # Web API server
    API_PORT: str = os.getenv("API_PORT", "5000")

    # Data directories
    BASE_DIR: Path = Path(__file__).parent.parent
    SESSION_DIR: Path = BASE_DIR / os.getenv("SESSION_DIR", "data/sessions")
    WORLDS_DIR: Path = BASE_DIR / os.getenv("WORLDS_DIR", "data/worlds")
    CHARACTERS_DIR: Path = BASE_DIR / os.getenv(
        "CHARACTERS_DIR", "data/characters"
    )

    def __init__(self) -> None:
        """Initialize config and create necessary directories."""
        self.SESSION_DIR.mkdir(parents=True, exist_ok=True)
        self.WORLDS_DIR.mkdir(parents=True, exist_ok=True)
        self.CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)


# Singleton instance
config: Config = Config()
