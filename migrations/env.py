from logging.config import fileConfig

from alembic import context

from backend import models  # noqa: F401  (đăng ký bảng vào metadata)
from backend.config import settings
from backend.database import Base, engine

config = context.config
if config.config_file_name and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=settings.DATABASE_URL, target_metadata=target_metadata,
                      literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def _run(connection) -> None:
    # render_as_batch: SQLite không hỗ trợ ALTER đầy đủ; trên MySQL batch chạy ALTER thông thường
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")  # test có thể truyền kết nối riêng
    if connection is not None:
        _run(connection)
    else:
        with engine.connect() as connection:
            _run(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
