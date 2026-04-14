"""ui/launcher/views — one module per tab in the OBSIDIAN launcher."""
from .assistant_view import AssistantView
from .instance_manager_view import InstanceManagerView
from .tools_view import ToolsView
from .settings_view import SettingsView
from .advanced_view import AdvancedView
from .models_view import ModelsView
from .voices_view import VoicesView

__all__ = [
    "AssistantView",
    "InstanceManagerView",
    "ToolsView",
    "SettingsView",
    "AdvancedView",
    "ModelsView",
    "VoicesView",
]
