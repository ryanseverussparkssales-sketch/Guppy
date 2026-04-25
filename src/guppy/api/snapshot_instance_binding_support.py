from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable

from fastapi import Depends, FastAPI

from src.guppy.api._server_fragment_models import (
    ConnectorActionRequest,
    InstanceConfigRequest,
    InstanceConnectorBindingRequest,
    InstanceGovernanceRequest,
    InstanceQueryRequest,
)


def bind_instance_exports(
    *,
    bind_runtime_service: Callable[[Callable[..., Any]], Callable[..., Any]],
    services_instances_module: Any,
    snapshot_instances_support_module: Any,
) -> SimpleNamespace:
    """Assemble the snapshot's instance-oriented bound service exports."""

    return SimpleNamespace(
        _ensure_m2_instance_scaffold=bind_runtime_service(
            services_instances_module.ensure_m2_instance_scaffold
        ),
        _load_instances_config=bind_runtime_service(
            services_instances_module.load_instances_config
        ),
        _load_instance_state=bind_runtime_service(
            services_instances_module.load_instance_state
        ),
        _save_instance_state=bind_runtime_service(
            services_instances_module.save_instance_state
        ),
        _save_instances_config=bind_runtime_service(
            services_instances_module.save_instances_config
        ),
        _load_normalized_instance_bundle=bind_runtime_service(
            services_instances_module.load_normalized_instance_bundle
        ),
        _get_active_instance_context=bind_runtime_service(
            services_instances_module.get_active_instance_context
        ),
        _build_instance_list_response=bind_runtime_service(
            snapshot_instances_support_module.build_instance_list_response
        ),
        _create_or_update_instance_response=bind_runtime_service(
            snapshot_instances_support_module.create_or_update_instance_response
        ),
        _save_instance_governance_response=bind_runtime_service(
            snapshot_instances_support_module.save_instance_governance_response
        ),
        _list_connectors_response=bind_runtime_service(
            snapshot_instances_support_module.list_connectors_response
        ),
        _run_connector_action_response=bind_runtime_service(
            snapshot_instances_support_module.run_connector_action_response
        ),
        _list_instance_connectors_response=bind_runtime_service(
            snapshot_instances_support_module.list_instance_connectors_response
        ),
        _save_instance_connector_binding_response=bind_runtime_service(
            snapshot_instances_support_module.save_instance_connector_binding_response
        ),
        _activate_instance_response=bind_runtime_service(
            snapshot_instances_support_module.activate_instance_response
        ),
        _delete_instance_response=bind_runtime_service(
            snapshot_instances_support_module.delete_instance_response
        ),
        _build_instance_logs_response=bind_runtime_service(
            snapshot_instances_support_module.build_instance_logs_response
        ),
    )


def register_instance_routes(
    app: FastAPI,
    *,
    require_rate_limit,
    build_instance_list_response,
    create_or_update_instance_response,
    save_instance_governance_response,
    list_connectors_response,
    run_connector_action_response,
    list_instance_connectors_response,
    save_instance_connector_binding_response,
    activate_instance_response,
    delete_instance_response,
    build_instance_logs_response,
    query_instance_response,
) -> SimpleNamespace:
    """Register the snapshot's instance and connector route family."""

    @app.get("/instances")
    async def list_instances(_user_id: str = Depends(require_rate_limit)):
        """Contract-first M2 endpoint: list configured instances with lightweight runtime state."""
        return build_instance_list_response()

    @app.post("/instances")
    async def create_or_update_instance(
        request: InstanceConfigRequest,
        _user_id: str = Depends(require_rate_limit),
    ):
        return create_or_update_instance_response(request)

    @app.post("/instances/{name}/governance")
    async def save_instance_governance(
        name: str,
        request: InstanceGovernanceRequest,
        _user_id: str = Depends(require_rate_limit),
    ):
        return save_instance_governance_response(name, request)

    @app.get("/connectors")
    async def list_connectors(_user_id: str = Depends(require_rate_limit)):
        return list_connectors_response()

    @app.post("/connectors/{connector_id}/verify")
    async def verify_connector(
        connector_id: str,
        request: ConnectorActionRequest,
        _user_id: str = Depends(require_rate_limit),
    ):
        return run_connector_action_response(connector_id, "verify", request)

    @app.post("/connectors/{connector_id}/connect")
    async def connect_connector(
        connector_id: str,
        request: ConnectorActionRequest,
        _user_id: str = Depends(require_rate_limit),
    ):
        return run_connector_action_response(connector_id, "connect", request)

    @app.post("/connectors/{connector_id}/reconnect")
    async def reconnect_connector(
        connector_id: str,
        request: ConnectorActionRequest,
        _user_id: str = Depends(require_rate_limit),
    ):
        return run_connector_action_response(connector_id, "reconnect", request)

    @app.post("/connectors/{connector_id}/disconnect")
    async def disconnect_connector(
        connector_id: str,
        request: ConnectorActionRequest,
        _user_id: str = Depends(require_rate_limit),
    ):
        return run_connector_action_response(connector_id, "disconnect", request)

    @app.get("/instances/{name}/connectors")
    async def list_instance_connectors(
        name: str,
        _user_id: str = Depends(require_rate_limit),
    ):
        return list_instance_connectors_response(name)

    @app.post("/instances/{name}/connectors/{connector_id}")
    async def save_instance_connector_binding(
        name: str,
        connector_id: str,
        request: InstanceConnectorBindingRequest,
        _user_id: str = Depends(require_rate_limit),
    ):
        return save_instance_connector_binding_response(name, connector_id, request)

    @app.post("/instances/{name}/activate")
    async def activate_instance(
        name: str,
        _user_id: str = Depends(require_rate_limit),
    ):
        return activate_instance_response(name)

    @app.delete("/instances/{name}")
    async def delete_instance(
        name: str,
        _user_id: str = Depends(require_rate_limit),
    ):
        return delete_instance_response(name)

    @app.get("/instances/{name}/logs")
    async def get_instance_logs(
        name: str,
        limit: int = 50,
        _user_id: str = Depends(require_rate_limit),
    ):
        return build_instance_logs_response(name, limit=limit)

    @app.post("/instances/{name}/query")
    async def query_instance(
        name: str,
        request: InstanceQueryRequest,
        _user_id: str = Depends(require_rate_limit),
    ):
        return await query_instance_response(name, request)

    return SimpleNamespace(
        list_instances=list_instances,
        create_or_update_instance=create_or_update_instance,
        save_instance_governance=save_instance_governance,
        list_connectors=list_connectors,
        verify_connector=verify_connector,
        connect_connector=connect_connector,
        reconnect_connector=reconnect_connector,
        disconnect_connector=disconnect_connector,
        list_instance_connectors=list_instance_connectors,
        save_instance_connector_binding=save_instance_connector_binding,
        activate_instance=activate_instance,
        delete_instance=delete_instance,
        get_instance_logs=get_instance_logs,
        query_instance=query_instance,
    )
