from __future__ import annotations

from dependency_injector import containers, providers

from db import db_resource
from uow import UnitOfWorkImpl


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(packages=[])

    session_factory = providers.Resource(db_resource)

    unit_of_work = providers.Factory(UnitOfWorkImpl, session_factory=session_factory)
