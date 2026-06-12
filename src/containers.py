from __future__ import annotations

from dependency_injector import containers, providers

from connections.introspector import PostgreSQLIntrospector
from connections.service import ConnectionServiceImpl
from db import db_resource
from uow import UnitOfWorkImpl


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(packages=["connections"])

    session_factory = providers.Resource(db_resource)

    unit_of_work = providers.Factory(UnitOfWorkImpl, session_factory=session_factory)

    introspector_factory = providers.Factory(PostgreSQLIntrospector)

    connection_service = providers.Factory(
        ConnectionServiceImpl,
        unit_of_work=unit_of_work,
        introspector_factory=introspector_factory.provider,
    )
