from sqlglot import exp, parse
from sqlglot.errors import ParseError

from app.models import (
    DBMSSQLTestPackage,
    DBMSSQLValidationResponse,
    DBMSSQLValidationResult,
)


_ALLOWED_STATEMENTS = (
    exp.Select,
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Merge,
    exp.Values,
    exp.Union,
    exp.Intersect,
    exp.Except,
)
_ALLOWED_DDL_OBJECTS = {"TABLE", "INDEX", "VIEW", "SEQUENCE"}
_SAFE_FUNCTIONS = {
    "abs",
    "array_agg",
    "avg",
    "cast",
    "ceil",
    "ceiling",
    "char_length",
    "coalesce",
    "concat",
    "count",
    "date_trunc",
    "dense_rank",
    "extract",
    "floor",
    "generate_series",
    "greatest",
    "json_agg",
    "jsonb_agg",
    "jsonb_build_object",
    "lag",
    "last_value",
    "least",
    "length",
    "lead",
    "lower",
    "max",
    "min",
    "nullif",
    "ntile",
    "now",
    "md5",
    "rank",
    "regexp_replace",
    "replace",
    "row_number",
    "round",
    "string_agg",
    "substring",
    "sum",
    "to_char",
    "to_json",
    "to_jsonb",
    "trim",
    "translate",
    "upper",
}
_SQL_FIELDS = ("setup_sql", "data_sql", "test_sql", "cleanup_sql")


def parse_and_validate_sql(
    package: DBMSSQLTestPackage,
) -> tuple[dict[str, list[exp.Expression]], list[str]]:
    statements: dict[str, list[exp.Expression]] = {}
    errors: list[str] = []
    for field in _SQL_FIELDS:
        sql = getattr(package, field)
        if not sql.strip():
            statements[field] = []
            continue
        try:
            parsed = [item for item in parse(sql, read="postgres") if item]
        except ParseError as exc:
            statements[field] = []
            errors.append(f"{field}: invalid PostgreSQL SQL: {exc}")
            continue
        statements[field] = parsed
        if field == "test_sql" and not parsed:
            errors.append("test_sql: at least one SQL statement is required")
            continue
        for index, statement in enumerate(parsed, 1):
            errors.extend(
                f"{field} statement {index}: {message}"
                for message in _validate_statement(statement)
            )
    return statements, errors


def validate_dbms_sql_tests(
    packages: list[DBMSSQLTestPackage],
) -> DBMSSQLValidationResponse:
    results = []
    for package in packages:
        _, errors = parse_and_validate_sql(package)
        results.append(
            DBMSSQLValidationResult(
                test_id=package.test_id,
                scenario_id=package.scenario_id,
                valid=not errors,
                errors=errors,
            )
        )
    return DBMSSQLValidationResponse(
        valid=all(result.valid for result in results),
        results=results,
    )


def _validate_statement(statement: exp.Expression) -> list[str]:
    errors: list[str] = []
    if not isinstance(statement, _ALLOWED_STATEMENTS):
        return [
            f"statement type {type(statement).__name__} is not allowed"
        ]

    if isinstance(statement, (exp.Create, exp.Drop)):
        kind = str(statement.args.get("kind", "")).upper()
        if kind not in _ALLOWED_DDL_OBJECTS:
            errors.append(f"DDL object type {kind or 'unknown'} is not allowed")
    if isinstance(statement, exp.Alter):
        kind = str(statement.args.get("kind", "")).upper()
        if kind not in {"TABLE", "INDEX"}:
            errors.append(f"ALTER target {kind or 'unknown'} is not allowed")

    for table in statement.find_all(exp.Table):
        if table.args.get("catalog") or table.args.get("db"):
            errors.append(
                f"cross-database or schema-qualified table "
                f"{table.sql(dialect='postgres')} is not allowed"
            )

    for function in statement.find_all(exp.Func):
        function_name = function.sql_name().lower()
        if isinstance(function, exp.Anonymous):
            function_name = function.name.lower()
        if (
            isinstance(function.parent, exp.Dot)
            and function.parent.expression is function
        ):
            errors.append(
                f"schema-qualified function {function_name} is not allowed"
            )
        if function_name not in _SAFE_FUNCTIONS:
            errors.append(f"function {function_name} is not in the safe allowlist")

    return errors
