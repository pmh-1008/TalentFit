"""Chạy migration Alembic (migrations/). Backend gọi upgrade() mỗi lần khởi động."""
from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parent.parent


def alembic_config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["configure_logger"] = False  # không đè cấu hình logging của uvicorn
    return cfg


def upgrade(revision: str = "head") -> None:
    command.upgrade(alembic_config(), revision)
