"""ui/launcher/views — one module per tab in the OBSIDIAN launcher."""
from .assistant_view import AssistantView
from .instance_manager_view import InstanceManagerView
from .library_view import LibraryView
from .tools_view import ToolsView
from .settings_view import SettingsView
from .settings_hub_view import SettingsHubView
from .settings_device_accounts_panel import SettingsDeviceAccountsPanel
from .settings_operations_panel import SettingsOperationsPanel
from .models_hub_view import ModelsHubView
from .local_llm_view import LocalLLMView
from .models_view import ModelsView
from .runtime_routing_view import RuntimeRoutingView
from .voices_view import VoicesView

__all__ = [
    "AssistantView",
    "InstanceManagerView",
    "LibraryView",
    "ToolsView",
    "SettingsView",
    "SettingsHubView",
    "SettingsDeviceAccountsPanel",
    "SettingsOperationsPanel",
    "ModelsHubView",
    "LocalLLMView",
    "ModelsView",
    "RuntimeRoutingView",
    "VoicesView",
]
