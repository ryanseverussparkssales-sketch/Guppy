from __future__ import annotations

from .models_view import ModelsView


class RuntimeRoutingView(ModelsView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._title_lbl.setText("RUNTIME")
        self._set_page_mode("runtime")
