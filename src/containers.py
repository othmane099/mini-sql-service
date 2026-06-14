from __future__ import annotations

from dependency_injector import containers, providers

from checkpointer import create_checkpointer
from connections.introspector import PostgreSQLIntrospector
from connections.service import ConnectionServiceImpl
from db import db_resource
from history.service import HistoryServiceImpl
from llm import create_llm
from queries.executor import PostgreSQLQueryExecutor
from queries.service import QueryServiceImpl
from uow import UnitOfWorkImpl


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        packages=["connections", "queries", "history", "chart_agent"]
    )

    session_factory = providers.Resource(db_resource)

    unit_of_work = providers.Factory(UnitOfWorkImpl, session_factory=session_factory)

    introspector_factory = providers.Factory(PostgreSQLIntrospector)

    connection_service = providers.Factory(
        ConnectionServiceImpl,
        unit_of_work=unit_of_work,
        introspector_factory=introspector_factory.provider,
    )

    llm = providers.Singleton(create_llm)

    checkpointer = providers.Resource(create_checkpointer)

    executor_factory = providers.Factory(PostgreSQLQueryExecutor)

    query_service = providers.Factory(
        QueryServiceImpl,
        connection_service=connection_service,
        unit_of_work=unit_of_work,
        llm=llm,
        executor_factory=executor_factory.provider,
    )

    history_service = providers.Factory(
        HistoryServiceImpl,
        unit_of_work=unit_of_work,
    )
