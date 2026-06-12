from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from connections.schemas import SchemaResponse

_SYSTEM = """\
You are an expert SQL assistant for {db_type} databases.
Given the database schema below, generate a syntactically correct SQL query \
that answers the user's question.

Rules:
- Only use tables and columns from the provided schema.
- Return valid {db_type} SQL.
- Respond with a JSON object with two fields:
    "sql": the generated SQL query (string)
    "explanation": a short plain-English explanation of what the query does (string)

Schema:
{schema}"""

sql_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", _SYSTEM),
        ("human", "{question}"),
    ]
)
# input variables: db_type, schema, question


def format_schema(schema: SchemaResponse) -> str:
    lines: list[str] = []
    for table in schema.tables:
        col_parts = []
        for col in table.columns:
            desc = f"{col.name} {col.data_type}"
            if col.is_primary_key:
                desc += " (PK)"
            if col.foreign_key:
                desc += f" (FK→{col.foreign_key})"
            col_parts.append(desc)
        lines.append(f"Table {table.name}: {', '.join(col_parts)}")
    return "\n".join(lines)
