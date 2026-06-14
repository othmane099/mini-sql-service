from __future__ import annotations

import json
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from typing import Annotated

import httpx
from langchain_core.tools import BaseTool, tool
from langgraph.graph.state import CompiledStateGraph

from connections.service import ConnectionService
from queries.prompt import format_schema

CHARTS_DIR = Path("charts")


class _Encoder(json.JSONEncoder):
    def default(self, o: object) -> object:
        if isinstance(o, (datetime, date, time)):
            return o.isoformat()
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, uuid.UUID):
            return str(o)
        return super().default(o)


def make_tools(
    service: ConnectionService,
    sql_graph: CompiledStateGraph,
    chart_graph: CompiledStateGraph,
) -> list[BaseTool]:
    """Build agent tools with services and subgraphs captured in closures."""

    @tool
    async def list_connections() -> str:
        """List all available database connections the user can query."""
        connections = await service.list_connections()
        if not connections:
            return "No connections available."
        lines = [f"- {c.name} (id: {c.id})" for c in connections]
        return "Available connections:\n" + "\n".join(lines)

    @tool
    async def get_schema(connection_id: Annotated[str, "UUID of the connection"]) -> str:
        """Get the database schema for a given connection."""
        from connections.exceptions import ConnectionNotFoundError, IntrospectionError

        try:
            schema = await service.get_schema(uuid.UUID(connection_id))
            return format_schema(schema)
        except ConnectionNotFoundError:
            return f"Connection {connection_id} not found."
        except IntrospectionError as exc:
            return f"Could not read schema: {exc}"
        except Exception as exc:
            return f"Unexpected error reading schema: {exc}"

    @tool
    async def run_sql(
        connection_id: Annotated[str, "UUID of the connection"],
        question: Annotated[str, "Natural language question to answer with SQL"],
    ) -> str:
        """Generate and execute a SQL query from a natural language question.

        Automatically retries with error feedback if execution fails (up to 3 attempts).
        Returns JSON with columns, rows, and the final SQL on success, or an error message.
        """
        from connections.exceptions import ConnectionNotFoundError

        try:
            schema = await service.get_schema(uuid.UUID(connection_id))
            conn = await service.get_connection(uuid.UUID(connection_id))
        except ConnectionNotFoundError:
            return f"Connection {connection_id} not found."
        except Exception as exc:
            return f"Could not retrieve connection info: {exc}"

        result = await sql_graph.ainvoke(
            {
                "connection_id": connection_id,
                "question": question,
                "schema": format_schema(schema),
                "db_type": conn.db_type.value,
                "sql": "",
                "attempts": 0,
                "error": "",
                "columns": [],
                "rows": [],
                "messages": [],
            }
        )

        if result["error"]:
            return f"SQL execution failed after {result['attempts']} attempt(s): {result['error']}"

        return json.dumps(
            {
                "columns": result["columns"],
                "rows": result["rows"],
                "sql": result["sql"],
            },
            cls=_Encoder,
        )

    @tool
    async def generate_chart(
        columns: Annotated[list[str], "Column names from the query result"],
        rows: Annotated[list[list], "Row data from the query result"],
        description: Annotated[str, "Natural language description of the chart the user wants"],
        chart_id: Annotated[
            str | None,
            "ID of an existing chart to update. Pass this when the user asks to modify or "
            "refine a previously generated chart — it overwrites the same file so the URL "
            "stays the same. Omit (or pass null) to create a new chart.",
        ] = None,
    ) -> str:
        """Generate or update a Chart.js HTML page from query results.

        - To create a new chart: omit chart_id.
        - To modify an existing chart: pass the chart_id from the previous generate_chart result.
          The file is overwritten and the same URL remains valid.
        """
        result = await chart_graph.ainvoke(
            {
                "columns": columns,
                "rows": rows,
                "description": description,
                "chart_id": chart_id,
                "plan": "",
                "html": "",
                "attempts": 0,
                "validation_errors": [],
                "final_chart_id": "",
                "chart_url": "",
                "error": "",
            }
        )

        if result["error"]:
            return result["error"]

        return f"chart_id={result['final_chart_id']} url={result['chart_url']}"

    @tool
    async def read_chart(
        chart_id: Annotated[str, "ID of the chart to read, from a previous generate_chart result"],
    ) -> str:
        """Read the current HTML of an existing chart.

        Call this before generate_chart when the user asks to modify or refine a chart,
        so the existing HTML can be included in the modification request.
        """
        path = CHARTS_DIR / f"{chart_id}.html"
        if not path.exists():
            return f"Chart {chart_id} not found."
        return path.read_text(encoding="utf-8")

    @tool
    async def fetch_chartjs_docs(
        section: Annotated[
            str,
            "Chart.js docs section path. Examples: 'charts/line', 'charts/bar', 'charts/pie', "
            "'charts/doughnut', 'charts/scatter', 'charts/bubble', 'charts/radar', "
            "'charts/polar-area', 'configuration/animations', 'configuration/tooltip', "
            "'configuration/legend', 'configuration/layout', 'general/colors', "
            "'general/responsive', 'general/performance'",
        ],
    ) -> str:
        """Fetch Chart.js v4 documentation for a specific section to look up available
        options, properties, and examples before generating a chart."""

        class _TextExtractor(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self._parts: list[str] = []
                self._skip = False

            def handle_starttag(self, tag: str, attrs: object) -> None:
                if tag in ("script", "style", "nav", "header", "footer"):
                    self._skip = True

            def handle_endtag(self, tag: str) -> None:
                if tag in ("script", "style", "nav", "header", "footer"):
                    self._skip = False

            def handle_data(self, data: str) -> None:
                if not self._skip:
                    text = data.strip()
                    if text:
                        self._parts.append(text)

            def get_text(self) -> str:
                return "\n".join(self._parts)

        url = f"https://www.chartjs.org/docs/latest/{section.strip('/')}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, follow_redirects=True)
            if response.status_code != 200:
                return (
                    f"Could not fetch '{section}' (HTTP {response.status_code}). "
                    "Check the section path."
                )
            extractor = _TextExtractor()
            extractor.feed(response.text)
            text = extractor.get_text()
            return text[:4000] + "\n[truncated]" if len(text) > 4000 else text
        except Exception as exc:
            return f"Failed to fetch docs: {exc}"

    return [
        list_connections,
        get_schema,
        run_sql,
        generate_chart,
        read_chart,
        fetch_chartjs_docs,
    ]
