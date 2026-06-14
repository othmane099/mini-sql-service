from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from chart_agent.tools import make_tools
from config import settings
from connections.service import ConnectionService

_SYSTEM_PROMPT = SystemMessage(
    content="""\
You are a data analyst assistant. Your job is to help the user visualize data \
from their databases as interactive charts.

Follow this flow:
1. Call list_connections to show the user what databases are available.
2. Ask the user which connection they want to use.
3. Call get_schema to understand the database structure.
4. Ask the user what data they want to see (if not already clear).
5. Call run_sql with the connection_id and the user's question in plain English. \
   This tool generates the SQL and executes it automatically — do not use separate \
   steps for SQL generation and execution. It will also retry automatically on error.
6. If the user has not specified a chart type or style, suggest the most \
   appropriate one based on the data shape and ask for confirmation.
7. Call generate_chart with the columns, rows, and the agreed chart description.
8. Return the chart URL to the user.

When the user asks to modify or refine an existing chart:
1. Call read_chart with the chart_id from the previous generate_chart result \
   to retrieve the current HTML.
2. Call generate_chart with the same chart_id, the updated description, and \
   include the existing HTML in the description so the LLM can make targeted edits.
3. Return the same URL — the file is overwritten in place.

Rules:
- Always ask before proceeding to the next major step if the user has not provided the information.
- Never guess a connection — always let the user choose.
- Keep your messages concise and friendly.
- When a tool returns an error, quote the exact error message to the user. \
  Do not paraphrase or generalize it.
- Never regenerate a chart from scratch if the user only asks for a modification — \
  always use read_chart first and pass the existing HTML to generate_chart.
"""
)


def create_graph(
    service: ConnectionService,
    llm: BaseChatModel,
    checkpointer: BaseCheckpointSaver,
) -> CompiledStateGraph:
    from chart_agent.agents.chart_agent import create_chart_graph
    from chart_agent.agents.sql_agent import create_sql_graph

    sql_graph = create_sql_graph(service, llm)
    chart_graph = create_chart_graph(llm)

    tools = make_tools(service, sql_graph, chart_graph)
    llm_with_tools = llm.bind_tools(tools, max_tokens=settings.LLM_MAX_TOKENS_AGENT)

    async def agent(state: MessagesState) -> dict:
        messages = [_SYSTEM_PROMPT, *state["messages"]]
        response = await llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    workflow = StateGraph(MessagesState)
    workflow.add_node("agent", agent)
    workflow.add_node("tools", ToolNode(tools, handle_tool_errors=True))
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", tools_condition)
    workflow.add_edge("tools", "agent")

    return workflow.compile(checkpointer=checkpointer)
