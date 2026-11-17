import json


def _text_schema() -> dict:
    return {"type": "string", "minLength": 1, "pattern": r"\S"}


CV_FIELD_SCHEMAS = {
    "education": {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["degree", "school", "year"],
            "properties": {
                "degree": _text_schema(),
                "school": _text_schema(),
                "year": {"type": "integer", "minimum": 1},
            },
        },
    },
    "experience": {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["title", "company", "duration_months"],
            "properties": {
                "title": _text_schema(),
                "company": _text_schema(),
                "duration_months": {"type": "integer", "minimum": 0},
            },
        },
    },
    "skills": {
        "type": "array",
        "minItems": 1,
        "items": _text_schema(),
    },
    "certifications_awards": {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["title", "year"],
            "properties": {
                "title": _text_schema(),
                "year": {"type": "integer", "minimum": 1},
            },
        },
    },
}

CV_DOCUMENT_SCHEMA = {
    "type": "object",
    "required": list(CV_FIELD_SCHEMAS),
    "properties": CV_FIELD_SCHEMAS,
}

_SQLITE_ITEM_FIELDS = {
    "education": {"degree": "text", "school": "text", "year": "integer"},
    "experience": {"title": "text", "company": "text", "duration_months": "integer"},
    "certifications_awards": {"title": "text", "year": "integer"},
}
_TRIGGER_NAMES = (
    "trg_cv_profiles_validate_insert",
    "trg_cv_profiles_validate_update",
    "trg_custom_cvs_validate_insert",
    "trg_custom_cvs_validate_update",
    "trg_applications_validate_insert",
    "trg_applications_validate_update",
)


def _mysql_literal(value: dict) -> str:
    encoded = json.dumps(value, separators=(",", ":"), ensure_ascii=True)
    return "'" + encoded.replace("\\", "\\\\").replace("'", "''") + "'"


def _mysql_trigger(name: str, table: str, event: str, columns: dict[str, dict],
                   changed_columns: tuple[str, ...] = ()) -> str:
    lines = [f"CREATE TRIGGER {name} BEFORE {event} ON {table} FOR EACH ROW", "BEGIN"]
    if changed_columns:
        changed = " AND ".join(f"NEW.{column} <=> OLD.{column}" for column in changed_columns)
        lines.append(f"  IF NOT ({changed}) THEN")
    indent = "    " if changed_columns else "  "
    for column, schema in columns.items():
        lines.extend((
            f"{indent}IF NEW.{column} IS NULL OR "
            f"NOT JSON_SCHEMA_VALID({_mysql_literal(schema)}, NEW.{column}) THEN",
            f"{indent}  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CV thiếu thông tin bắt buộc';",
            f"{indent}END IF;",
        ))
    if changed_columns:
        lines.append("  END IF;")
    lines.append("END")
    return "\n".join(lines)


def mysql_trigger_statements() -> list[str]:
    document = {"cv_data": CV_DOCUMENT_SCHEMA}
    return [
        _mysql_trigger("trg_cv_profiles_validate_insert", "candidate_profiles", "INSERT",
                       CV_FIELD_SCHEMAS),
        _mysql_trigger("trg_cv_profiles_validate_update", "candidate_profiles", "UPDATE",
                       CV_FIELD_SCHEMAS, ("education", "experience", "skills", "certifications_awards")),
        _mysql_trigger("trg_custom_cvs_validate_insert", "custom_cvs", "INSERT", {"data": CV_DOCUMENT_SCHEMA}),
        _mysql_trigger("trg_custom_cvs_validate_update", "custom_cvs", "UPDATE",
                       {"data": CV_DOCUMENT_SCHEMA}, ("data",)),
        _mysql_trigger("trg_applications_validate_insert", "applications", "INSERT", document),
        _mysql_trigger("trg_applications_validate_update", "applications", "UPDATE", document, ("cv_data",)),
    ]


def _sqlite_array_source(document: str | None, field: str) -> str:
    return f"NEW.{field}" if document is None else f"json_extract(NEW.{document}, '$.{field}')"


def _sqlite_array_check(source: str, fields: dict[str, str] | None = None) -> str:
    if fields is None:
        return (
            f"COALESCE(json_type({source}), '') <> 'array' "
            f"OR COALESCE(json_array_length({source}), 0) < 1 "
            f"OR EXISTS (SELECT 1 FROM json_each({source}) AS item "
            "WHERE item.type <> 'text' OR trim(item.value) = '')"
        )

    item_checks = ["COALESCE(json_type(item.value), '') <> 'object'"]
    for field, json_type in fields.items():
        path = f"'$.{field}'"
        item_checks.append(f"COALESCE(json_type(item.value, {path}), '') <> '{json_type}'")
        if json_type == "text":
            item_checks.append(f"trim(COALESCE(json_extract(item.value, {path}), '')) = ''")
        elif field == "year":
            item_checks.append(f"CAST(json_extract(item.value, {path}) AS INTEGER) < 1")
        elif field == "duration_months":
            item_checks.append(f"CAST(json_extract(item.value, {path}) AS INTEGER) < 0")
    return (
        f"COALESCE(json_type({source}), '') <> 'array' "
        f"OR EXISTS (SELECT 1 FROM json_each({source}) AS item "
        f"WHERE {' OR '.join(item_checks)})"
    )


def _sqlite_trigger(name: str, table: str, event: str, checks: list[tuple[str, str]],
                    update_of: str | None = None) -> str:
    event_clause = f"UPDATE OF {update_of}" if update_of else event
    statements = [
        f"SELECT CASE WHEN {condition} THEN RAISE(ABORT, '{message}') END;"
        for condition, message in checks
    ]
    return (
        f"CREATE TRIGGER {name} BEFORE {event_clause} ON {table} FOR EACH ROW "
        f"BEGIN {' '.join(statements)} END"
    )


def _sqlite_cv_checks(document: str | None) -> list[tuple[str, str]]:
    checks = []
    if document:
        checks.append((f"COALESCE(json_type(NEW.{document}), '') <> 'object'", "CV must be an object"))
    for field in CV_FIELD_SCHEMAS:
        source = _sqlite_array_source(document, field)
        item_fields = _SQLITE_ITEM_FIELDS.get(field)
        checks.append((_sqlite_array_check(source, item_fields), "CV thiếu thông tin bắt buộc"))
    return checks


def sqlite_trigger_statements() -> list[str]:
    return [
        _sqlite_trigger("trg_cv_profiles_validate_insert", "candidate_profiles", "INSERT",
                        _sqlite_cv_checks(None)),
        _sqlite_trigger("trg_cv_profiles_validate_update", "candidate_profiles", "UPDATE",
                        _sqlite_cv_checks(None), "education, experience, skills, certifications_awards"),
        _sqlite_trigger("trg_custom_cvs_validate_insert", "custom_cvs", "INSERT",
                        _sqlite_cv_checks("data")),
        _sqlite_trigger("trg_custom_cvs_validate_update", "custom_cvs", "UPDATE",
                        _sqlite_cv_checks("data"), "data"),
        _sqlite_trigger("trg_applications_validate_insert", "applications", "INSERT",
                        _sqlite_cv_checks("cv_data")),
        _sqlite_trigger("trg_applications_validate_update", "applications", "UPDATE",
                        _sqlite_cv_checks("cv_data"), "cv_data"),
    ]


def create_trigger_statements(dialect: str) -> list[str]:
    if dialect == "sqlite":
        return sqlite_trigger_statements()
    if dialect == "mysql":
        return mysql_trigger_statements()
    raise RuntimeError(f"CV database constraints are not implemented for {dialect}.")


def drop_trigger_statements(dialect: str) -> list[str]:
    if dialect not in ("sqlite", "mysql"):
        raise RuntimeError(f"CV database constraints are not implemented for {dialect}.")
    return [f"DROP TRIGGER IF EXISTS {name}" for name in reversed(_TRIGGER_NAMES)]
