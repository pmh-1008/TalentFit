_TRIGGER_NAMES = (
    "trg_jobs_validate_jd_insert",
    "trg_jobs_validate_jd_update",
)

_MYSQL_VALIDATION = """
NEW.title IS NULL OR CHAR_LENGTH(TRIM(NEW.title)) < 2
OR NEW.description IS NULL OR CHAR_LENGTH(TRIM(NEW.description)) = 0
OR COALESCE(JSON_TYPE(NEW.requirements), '') <> 'OBJECT'
OR COALESCE(JSON_TYPE(JSON_EXTRACT(NEW.requirements, '$.text')), '') <> 'STRING'
OR CHAR_LENGTH(TRIM(COALESCE(JSON_UNQUOTE(JSON_EXTRACT(NEW.requirements, '$.text')), ''))) = 0
""".strip()

_SQLITE_VALIDATION = """
NEW.title IS NULL OR length(trim(NEW.title)) < 2
OR NEW.description IS NULL OR length(trim(NEW.description)) = 0
OR COALESCE(json_type(NEW.requirements), '') <> 'object'
OR COALESCE(json_type(NEW.requirements, '$.text'), '') <> 'text'
OR length(trim(COALESCE(json_extract(NEW.requirements, '$.text'), ''))) = 0
""".strip()


def _mysql_trigger(name: str, event: str, update: bool = False) -> str:
    lines = [f"CREATE TRIGGER {name} BEFORE {event} ON jobs FOR EACH ROW", "BEGIN"]
    if update:
        lines.append(
            "  IF NOT (NEW.title <=> OLD.title AND NEW.description <=> OLD.description "
            "AND NEW.requirements <=> OLD.requirements) THEN"
        )
    indent = "    " if update else "  "
    lines.extend((
        f"{indent}IF {_MYSQL_VALIDATION} THEN",
        f"{indent}  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = "
        "'JD cần có chức danh, mô tả công việc và yêu cầu đối với ứng viên';",
        f"{indent}END IF;",
    ))
    if update:
        lines.append("  END IF;")
    lines.append("END")
    return "\n".join(lines)


def mysql_trigger_statements() -> list[str]:
    return [
        _mysql_trigger("trg_jobs_validate_jd_insert", "INSERT"),
        _mysql_trigger("trg_jobs_validate_jd_update", "UPDATE", update=True),
    ]


def _sqlite_trigger(name: str, event: str, update_of: str | None = None) -> str:
    event_clause = f"UPDATE OF {update_of}" if update_of else event
    return (
        f"CREATE TRIGGER {name} BEFORE {event_clause} ON jobs FOR EACH ROW "
        f"BEGIN SELECT CASE WHEN {_SQLITE_VALIDATION} "
        "THEN RAISE(ABORT, 'JD cần có chức danh, mô tả công việc và yêu cầu đối với ứng viên') "
        "END; END"
    )


def sqlite_trigger_statements() -> list[str]:
    return [
        _sqlite_trigger("trg_jobs_validate_jd_insert", "INSERT"),
        _sqlite_trigger(
            "trg_jobs_validate_jd_update",
            "UPDATE",
            "title, description, requirements",
        ),
    ]


def create_trigger_statements(dialect: str) -> list[str]:
    if dialect == "sqlite":
        return sqlite_trigger_statements()
    if dialect == "mysql":
        return mysql_trigger_statements()
    raise RuntimeError(f"JD database constraints are not implemented for {dialect}.")


def drop_trigger_statements(dialect: str) -> list[str]:
    if dialect not in ("sqlite", "mysql"):
        raise RuntimeError(f"JD database constraints are not implemented for {dialect}.")
    return [f"DROP TRIGGER IF EXISTS {name}" for name in reversed(_TRIGGER_NAMES)]
