from __future__ import annotations

import operator
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from config import settings
from connections.service import ConnectionService
from queries.executor import PostgreSQLQueryExecutor
from queries.prompt import _SYSTEM as _SQL_SYSTEM_TEMPLATE
from queries.prompt import sql_prompt
from queries.schemas import QueryResponse


class SQLAgentState(TypedDict):
    connection_id: str
    question: str
    schema: str  # pre-formatted by format_schema()
    db_type: str
    sql: str
    attempts: int
    error: str  # empty string on success
    columns: list[str]
    rows: list[list]
    messages: Annotated[list[dict], operator.add]  # grows with each retry


def _make_generate_node(
    service: ConnectionService, llm: BaseChatModel
) -> Callable[[SQLAgentState], Awaitable[dict]]:
    sql_llm = llm.bind(temperature=0, max_tokens=settings.LLM_MAX_TOKENS_SQL)

    async def generate(state: SQLAgentState) -> dict:
        if state["messages"]:
            # Retry path: inject prior SQL + error as conversation context
            system_content = _SQL_SYSTEM_TEMPLATE.format(
                db_type=state["db_type"], schema=state["schema"]
            )
            msgs = [
                SystemMessage(content=system_content),
                *[
                    HumanMessage(content=m["content"])
                    if m["role"] == "user"
                    else SystemMessage(content=m["content"])
                    for m in state["messages"]
                ],
                HumanMessage(content=f"<question>{state['question']}</question>"),
            ]
            result = await sql_llm.with_structured_output(QueryResponse).ainvoke(msgs)
        else:
            # First attempt: use the standard sql_prompt template
            chain = sql_prompt | sql_llm.with_structured_output(QueryResponse)
            result = await chain.ainvoke(
                {
                    "db_type": state["db_type"],
                    "schema": state["schema"],
                    "question": state["question"],
                }
            )
        return {"sql": result.sql}

    return generate


def _make_execute_node(service: ConnectionService) -> Callable[[SQLAgentState], Awaitable[dict]]:
    async def execute(state: SQLAgentState) -> dict:
        from queries.exceptions import QueryExecutionError

        try:
            conn = await service.get_connection(uuid.UUID(state["connection_id"]))
            executor = PostgreSQLQueryExecutor(conn)
            result = await executor.execute(state["sql"])
            return {
                "columns": result.columns,
                "rows": result.rows,
                "error": "",
            }
        except QueryExecutionError as exc:
            return {
                "error": str(exc),
                "attempts": state["attempts"] + 1,
                "columns": [],
                "rows": [],
            }
        except Exception as exc:
            return {
                "error": str(exc),
                "attempts": state["attempts"] + 1,
                "columns": [],
                "rows": [],
            }

    return execute


def _reflect(state: SQLAgentState) -> dict:
    feedback = (
        f"The SQL you generated failed:\n\n"
        f"SQL:\n{state['sql']}\n\n"
        f"Error:\n{state['error']}\n\n"
        f"Please fix the SQL to correctly answer the original question."
    )
    return {"messages": [{"role": "user", "content": feedback}]}


def _route_after_execute(state: SQLAgentState) -> str:
    if not state["error"]:
        return END
    if state["attempts"] >= 3:
        return END
    return "reflect"


def create_sql_graph(service: ConnectionService, llm: BaseChatModel) -> CompiledStateGraph:
    workflow = StateGraph(SQLAgentState)
    workflow.add_node("generate", _make_generate_node(service, llm))
    workflow.add_node("execute", _make_execute_node(service))
    workflow.add_node("reflect", _reflect)
    workflow.set_entry_point("generate")
    workflow.add_edge("generate", "execute")
    workflow.add_conditional_edges(
        "execute",
        _route_after_execute,
        {"reflect": "reflect", END: END},
    )
    workflow.add_edge("reflect", "generate")
    return workflow.compile()
