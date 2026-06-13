from __future__ import annotations

import sqlglot
import sqlglot.expressions as exp

from connections.models import DBType
from queries.exceptions import QueryExecutionError

_SQLGLOT_DIALECT: dict[DBType, str] = {
    DBType.POSTGRESQL: "postgres",
    # add new DBType members here as the enum grows
}


def validate_select_only(sql: str, db_type: DBType) -> None:
    """Raise QueryExecutionError if sql is not a single, plain SELECT statement."""
    dialect = _SQLGLOT_DIALECT[db_type]
    try:
        statements = [s for s in sqlglot.parse(sql, dialect=dialect) if s is not None]
    except sqlglot.errors.ParseError as exc:
        raise QueryExecutionError(f"Invalid SQL: {exc}") from exc

    if not statements:
        raise QueryExecutionError("SQL statement is empty")

    if len(statements) > 1:
        raise QueryExecutionError("Only a single SELECT statement is allowed")

    statement = statements[0]

    if not isinstance(statement, exp.Select):
        raise QueryExecutionError(
            f"Only SELECT statements are allowed, got: {type(statement).__name__}"
        )

    # SELECT INTO creates a table in PostgreSQL — block it despite being a Select node.
    if statement.args.get("into"):
        raise QueryExecutionError("SELECT INTO is not allowed")
