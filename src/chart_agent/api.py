from __future__ import annotations

import json

import structlog
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from chart_agent.graph import create_graph
from chart_agent.tools import CHARTS_DIR
from connections.service import ConnectionService

router = APIRouter(prefix="/agent", tags=["agent"])
logger = structlog.get_logger()


@router.get("/charts", response_model=list[str])
async def list_charts() -> list[str]:
    """Return the IDs of all generated charts."""
    return [
        f.stem
        for f in sorted(CHARTS_DIR.glob("*.html"), key=lambda f: f.stat().st_mtime, reverse=True)
    ]


@router.get("/charts/{chart_id}", response_class=HTMLResponse)
async def get_chart(chart_id: str) -> FileResponse:
    """Serve a generated chart HTML page."""
    path = CHARTS_DIR / f"{chart_id}.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Chart not found")
    return FileResponse(path, media_type="text/html")


@router.websocket("/chart")
@inject
async def chart_agent_ws(
    websocket: WebSocket,
    connection_service: ConnectionService = Depends(Provide["connection_service"]),
    llm: BaseChatModel = Depends(Provide["llm"]),
    checkpointer: AsyncPostgresSaver = Depends(Provide["checkpointer"]),
) -> None:
    await websocket.accept()
    graph = create_graph(connection_service, llm, checkpointer)
    logger.info("agent.connected")

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                session_id: str = data["session_id"]
                message: str = data["message"]
            except (json.JSONDecodeError, KeyError) as exc:
                await websocket.send_json(
                    {"type": "error", "content": f"Invalid message format: {exc}"}
                )
                continue

            config = {"configurable": {"thread_id": session_id}}

            async for event in graph.astream_events(
                {"messages": [HumanMessage(content=message)]},
                config=config,
                version="v2",
            ):
                await _handle_event(websocket, event)

            await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        logger.info("agent.disconnected")
    except Exception as exc:
        logger.error("agent.error", exc_info=exc)
        await websocket.send_json({"type": "error", "content": "An unexpected error occurred"})
        await websocket.close()


async def _handle_event(websocket: WebSocket, event: dict) -> None:
    kind = event["event"]
    node = event.get("metadata", {}).get("langgraph_node")

    if kind == "on_chat_model_end" and node == "agent":
        content = event["data"]["output"].content
        if content:
            await websocket.send_json({"type": "message", "content": content})

    elif kind == "on_tool_start":
        await websocket.send_json({"type": "tool_start", "name": event["name"]})

    elif kind == "on_tool_end":
        output = str(event["data"].get("output", ""))
        is_error = output.startswith(("Could not ", "Query failed:", "Unexpected error"))
        await websocket.send_json(
            {
                "type": "tool_error" if is_error else "tool_end",
                "name": event["name"],
                "content": output,
            }
        )
