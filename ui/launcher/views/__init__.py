"""ui/launcher/views — one module per tab in the OBSIDIAN launcher."""
from .assistant_view import AssistantView
from .instance_manager_view import InstanceManagerView
from .library_view import LibraryView
from .tools_view import ToolsView
from .settings_view import SettingsView
from .advanced_view import AdvancedView
from .my_pc_view import MyPCView
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
    "AdvancedView",
    "MyPCView",
    "LocalLLMView",
    "ModelsView",
    "RuntimeRoutingView",
    "VoicesView",
]
