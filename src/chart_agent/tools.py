from __future__ import annotations

import json
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from typing import Annotated, cast

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool, tool

from config import settings
from connections.service import ConnectionService
from queries.executor import PostgreSQLQueryExecutor
from queries.prompt import format_schema, sql_prompt
from queries.schemas import QueryResponse

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


_CHART_SYSTEM = """\
You are an expert data visualization engineer specializing in Chart.js v4.
Given a dataset and a chart description, generate a complete, self-contained HTML page \
that renders a polished, production-quality chart.

## Output rules
- Output ONLY raw HTML. No markdown, no code fences, no explanation, no comments outside the HTML.
- The page must be fully self-contained — only external dependency allowed is Chart.js from CDN.
- Use: <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
- Embed all data directly as JavaScript variables inside a <script> tag.
- The page must end with </html>.

## Chart type selection
Choose the most appropriate type for the data and description:
- **bar** — comparisons across categories (use `indexAxis: 'y'` for horizontal bars)
- **line** — trends over time; set `tension: 0.4` for smooth curves, `fill: true` for area charts
- **pie / doughnut** — part-to-whole relationships (doughnut is more readable)
- **scatter** — correlations between two numeric variables
- **bubble** — three-variable relationships (x, y, size)
- **radar** — multivariate comparisons across a common scale
- **polarArea** — similar to pie but each segment has equal angle, area encodes value
- Mixed charts are allowed: combine bar + line by setting `type` per dataset

## Styling requirements
- Page: white background (`#ffffff`), centered layout, generous padding (48px),
  `font-family: 'Segoe UI', system-ui, sans-serif`
- Canvas container: max-width 860px, margin auto,
  box-shadow `0 4px 24px rgba(0,0,0,0.08)`, border-radius 16px, padding 32px
- Use a modern color palette — avoid default grey. Suggested palette:
  `['#6366f1','#f59e0b','#10b981','#3b82f6','#ef4444','#8b5cf6','#ec4899','#14b8a6']`
- For line/area charts: set `borderWidth: 2`, `pointRadius: 4`, `pointHoverRadius: 6`
- For bar charts: set `borderRadius: 6` on datasets for rounded bars
- Background colors should be the same hue at 15-20% opacity for fill areas

## Plugin configuration (always include)
```
plugins: {
  legend: {
    position: 'bottom',
    labels: { padding: 20, usePointStyle: true, font: { size: 13 } }
  },
  title: {
    display: true,
    text: '<descriptive title matching the user request>',
    font: { size: 18, weight: 'bold' },
    padding: { bottom: 24 }
  },
  tooltip: {
    backgroundColor: 'rgba(17,24,39,0.9)',
    titleFont: { size: 13 },
    bodyFont: { size: 12 },
    padding: 12,
    cornerRadius: 8
  }
}
```

## Scale configuration (for cartesian charts)
- Enable gridlines with low opacity: `grid: { color: 'rgba(0,0,0,0.06)' }`
- Use `ticks: { font: { size: 12 }, color: '#6b7280' }` on both axes
- Add axis titles when column names are not self-explanatory

## Animation
- Enable default animations (do not disable them)
- For large datasets (>100 points), set `animation: false` for performance

## Responsiveness
- Always set `responsive: true` and `maintainAspectRatio: true` on the chart options
- Set the canvas container to `width: 100%`"""


def make_tools(service: ConnectionService, llm: BaseChatModel) -> list[BaseTool]:
    """Build agent tools with services captured in closures."""
    CHARTS_DIR.mkdir(exist_ok=True)

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
    async def generate_sql(
        connection_id: Annotated[str, "UUID of the connection"],
        question: Annotated[str, "Natural language question to answer with SQL"],
    ) -> str:
        """Generate a SELECT SQL query from a natural language question."""
        schema = await service.get_schema(uuid.UUID(connection_id))
        conn = await service.get_connection(uuid.UUID(connection_id))
        chain = sql_prompt | llm.bind(
            max_tokens=settings.LLM_MAX_TOKENS_SQL
        ).with_structured_output(QueryResponse)
        result = cast(
            QueryResponse,
            await chain.ainvoke(
                {
                    "db_type": conn.db_type.value,
                    "schema": format_schema(schema),
                    "question": question,
                }
            ),
        )
        return result.sql

    @tool
    async def execute_sql(
        connection_id: Annotated[str, "UUID of the connection"],
        sql: Annotated[str, "SELECT SQL query to execute"],
    ) -> str:
        """Execute a SELECT SQL query and return results as JSON."""
        from queries.exceptions import QueryExecutionError

        try:
            conn = await service.get_connection(uuid.UUID(connection_id))
            executor = PostgreSQLQueryExecutor(conn)
            result = await executor.execute(sql)
            return json.dumps(
                {
                    "columns": result.columns,
                    "rows": result.rows,
                    "truncated": result.truncated,
                },
                cls=_Encoder,
            )
        except QueryExecutionError as exc:
            return f"Query failed: {exc}"
        except Exception as exc:
            return f"Unexpected error executing query: {exc}"

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
        dataset = json.dumps({"columns": columns, "rows": rows}, indent=2)
        prompt = f"Chart description: {description}\n\nDataset:\n{dataset}"
        response = await llm.ainvoke(
            [
                SystemMessage(content=_CHART_SYSTEM),
                HumanMessage(content=prompt),
            ]
        )
        content = response.content
        raw = content if isinstance(content, str) else content[0]

        idx = raw.lower().rfind("</html>")
        if idx == -1:
            return (
                "Chart generation failed: response was truncated before the HTML "
                "could be completed. Try again."
            )
        html = raw[: idx + len("</html>")].strip()

        cid = chart_id if chart_id else uuid.uuid4().hex
        (CHARTS_DIR / f"{cid}.html").write_text(html, encoding="utf-8")
        return f"chart_id={cid} url={settings.BASE_URL}/api/v1/agent/charts/{cid}"

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
        generate_sql,
        execute_sql,
        generate_chart,
        read_chart,
        fetch_chartjs_docs,
    ]
