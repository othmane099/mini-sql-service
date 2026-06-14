from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from typing import TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from chart_agent.tools import CHARTS_DIR
from config import settings

_CHART_PLAN_SYSTEM = """\
You are a data visualization planner. Analyze the provided dataset and output ONLY a \
JSON object (no markdown, no code fences, no explanation) with exactly these fields:
{
  "chart_type": "bar|line|pie|doughnut|scatter|bubble|radar|polarArea",
  "x_axis": "column name or null",
  "y_axis": "column name or list of column names",
  "label_column": "column for data labels or null",
  "color_by": "column for color grouping or null",
  "title": "descriptive chart title matching the user request",
  "use_horizontal": true or false,
  "is_time_series": true or false,
  "notes": "any important styling or configuration notes, or empty string"
}

Selection rules:
- bar: comparisons across categories; use use_horizontal=true when labels are long
- line: trends over time; set is_time_series=true
- pie/doughnut: part-to-whole (≤8 categories); prefer doughnut for readability
- scatter: correlation between two numeric columns
- bubble: three-variable relationship (x, y, bubble size)
- radar: multi-variable comparison across a common scale
- polarArea: similar to pie but equal angles, area encodes value

Output ONLY the JSON object. No prose, no markdown."""

_CHART_GENERATE_SYSTEM = """\
You are an expert data visualization engineer specializing in Chart.js v4.
Given a chart plan and dataset, generate a complete, self-contained HTML page \
that renders a polished, production-quality chart.

## Output rules
- Output ONLY raw HTML. No markdown, no code fences, no explanation, no comments outside the HTML.
- Do NOT wrap the output in ```html ... ``` or any other code fence. \
Start your response directly with `<!DOCTYPE html>` or `<html`.
- The page must be fully self-contained — only external dependency allowed is Chart.js from CDN.
- Use: <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
- Embed all data directly as JavaScript variables inside a <script> tag.
- The page must end with </html>.

## Chart type selection
Use the chart_type from the plan. Honour all other plan fields (x_axis, y_axis, title, etc.).
- bar — use `indexAxis: 'y'` when use_horizontal is true
- line — set `tension: 0.4` for smooth curves, `fill: true` for area charts
- pie / doughnut — part-to-whole relationships
- scatter — correlations between two numeric variables
- bubble — three-variable relationships (x, y, size)
- radar — multivariate comparisons across a common scale
- polarArea — similar to pie but each segment has equal angle
- Mixed charts: combine bar + line by setting `type` per dataset

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
    text: '<use the title from the plan>',
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


class ChartAgentState(TypedDict):
    columns: list[str]
    rows: list[list]
    description: str
    chart_id: str | None
    plan: str
    html: str
    attempts: int
    validation_errors: list[str]
    final_chart_id: str
    chart_url: str
    error: str


def _make_plan_node(llm: BaseChatModel) -> Callable[[ChartAgentState], Awaitable[dict]]:
    plan_llm = llm.bind(temperature=0, max_tokens=256)

    async def plan(state: ChartAgentState) -> dict:
        sample = json.dumps(state["rows"][:5], default=str)
        prompt = (
            f"User description: {state['description']}\n\n"
            f"Dataset columns: {state['columns']}\n\n"
            f"Sample rows (first 5):\n{sample}"
        )
        response = await plan_llm.ainvoke(
            [SystemMessage(content=_CHART_PLAN_SYSTEM), HumanMessage(content=prompt)]
        )
        content = response.content
        return {"plan": content if isinstance(content, str) else content[0]}

    return plan


def _make_generate_node(llm: BaseChatModel) -> Callable[[ChartAgentState], Awaitable[dict]]:
    gen_llm = llm.bind(temperature=0.3)

    async def generate(state: ChartAgentState) -> dict:
        dataset = json.dumps(
            {"columns": state["columns"], "rows": state["rows"]},
            indent=2,
            default=str,
        )
        prompt = (
            f"Chart plan:\n{state['plan']}\n\n"
            f"User description: {state['description']}\n\n"
            f"Dataset:\n{dataset}"
        )
        if state["validation_errors"]:
            prompt += (
                f"\n\nPrevious attempt failed these validation checks: "
                f"{', '.join(state['validation_errors'])}. "
                f"Fix all of these issues in this new attempt."
            )
        response = await gen_llm.ainvoke(
            [SystemMessage(content=_CHART_GENERATE_SYSTEM), HumanMessage(content=prompt)]
        )
        content = response.content
        return {"html": content if isinstance(content, str) else content[0]}

    return generate


def _strip_code_fence(html: str) -> str:
    """Remove markdown code fences the model sometimes wraps output in."""
    stripped = html.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1 :]
    if stripped.endswith("```"):
        stripped = stripped[: stripped.rfind("```")].rstrip()
    return stripped


def _validate(state: ChartAgentState) -> dict:
    html = _strip_code_fence(state["html"])
    errors: list[str] = []
    if "</html>" not in html.lower():
        errors.append("missing </html> closing tag")
    if "<canvas" not in html.lower():
        errors.append("missing <canvas> element")
    if "Chart(" not in html:
        errors.append("missing Chart.js instantiation (Chart()")
    if len(html) < 500:
        errors.append(f"HTML too short ({len(html)} chars, expected >500)")
    if "cdn.jsdelivr.net" not in html and "chart.js" not in html.lower():
        errors.append("missing Chart.js CDN script tag")
    return {"html": html, "validation_errors": errors, "attempts": state["attempts"] + 1}


async def _write(state: ChartAgentState) -> dict:
    CHARTS_DIR.mkdir(exist_ok=True)
    raw = state["html"]
    idx = raw.lower().rfind("</html>")
    html = raw[: idx + len("</html>")].strip()
    cid = state["chart_id"] if state["chart_id"] else uuid.uuid4().hex
    (CHARTS_DIR / f"{cid}.html").write_text(html, encoding="utf-8")
    return {
        "final_chart_id": cid,
        "chart_url": f"{settings.BASE_URL}/api/v1/agent/charts/{cid}",
        "error": "",
    }


def _fail(state: ChartAgentState) -> dict:
    summary = ", ".join(state["validation_errors"])
    return {
        "error": (
            f"Chart generation failed after {state['attempts']} attempt(s). "
            f"Validation checks that failed: {summary}."
        )
    }


def _route_after_validate(state: ChartAgentState) -> str:
    if not state["validation_errors"]:
        return "write"
    if state["attempts"] >= 2:
        return "fail"
    return "generate"


def create_chart_graph(llm: BaseChatModel) -> CompiledStateGraph:
    workflow = StateGraph(ChartAgentState)
    workflow.add_node("plan", _make_plan_node(llm))
    workflow.add_node("generate", _make_generate_node(llm))
    workflow.add_node("validate", _validate)
    workflow.add_node("write", _write)
    workflow.add_node("fail", _fail)
    workflow.set_entry_point("plan")
    workflow.add_edge("plan", "generate")
    workflow.add_edge("generate", "validate")
    workflow.add_conditional_edges(
        "validate",
        _route_after_validate,
        {"write": "write", "generate": "generate", "fail": "fail"},
    )
    workflow.add_edge("write", END)
    workflow.add_edge("fail", END)
    return workflow.compile()
