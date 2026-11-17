"""Sinh lại database/schema.sql từ backend/models.py (dùng khi sửa models).

Chạy từ thư mục gốc: python -m scripts.export_schema
"""
import os
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")  # chỉ cần metadata, không kết nối MySQL

from alembic.script import ScriptDirectory  # noqa: E402
from sqlalchemy.dialects import mysql  # noqa: E402
from sqlalchemy.schema import CreateIndex, CreateTable  # noqa: E402

from backend import models  # noqa: E402,F401
from backend.migrate import alembic_config  # noqa: E402
from backend.database import Base  # noqa: E402
from backend.cv_database import mysql_trigger_statements  # noqa: E402
from backend.job_database import mysql_trigger_statements as mysql_job_trigger_statements  # noqa: E402

HEADER = """-- Schema MySQL cho TalentFit (sinh từ backend/models.py; backend cũng tự tạo bảng và bổ sung cột khi khởi động)
-- Tạo lại file này sau khi sửa models.py: python -m scripts.export_schema
CREATE DATABASE IF NOT EXISTS recruitment_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE recruitment_ai;
"""


def build() -> str:
    dialect = mysql.dialect()
    parts = [HEADER]
    for table in Base.metadata.sorted_tables:
        parts.append(str(CreateTable(table).compile(dialect=dialect)).strip() + " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
        parts += [str(CreateIndex(ix).compile(dialect=dialect)).strip() + ";"
                  for ix in sorted(table.indexes, key=lambda i: i.name)]
        parts.append("")
    parts.append("DELIMITER //")
    parts += [f"{statement}//" for statement in mysql_trigger_statements() + mysql_job_trigger_statements()]
    parts += ["DELIMITER ;", ""]
    # Đánh dấu schema đã ở phiên bản mới nhất để backend không chạy lại migration khi khởi động
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    parts += [
        "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, "
        "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;",
        f"INSERT INTO alembic_version (version_num) VALUES ('{head}');",
        "",
    ]
    return "\n".join(parts)


if __name__ == "__main__":
    target = Path(__file__).resolve().parent.parent / "database" / "schema.sql"
    target.write_text(build(), encoding="utf-8")
    print(f"Đã ghi {target}")
