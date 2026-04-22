from PySide6.QtWidgets import QApplication, QLabel, QWidget

from ui.launcher.views.models_hub_view import ModelsHubView


def _qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_models_hub_keeps_runtime_and_voice_ownership_inside_models() -> None:
    _qapp()
    hub = ModelsHubView(QWidget(), QWidget(), QWidget())

    labels = [label.text() for label in hub.findChildren(QLabel)]

    assert any("backend choice" in text.lower() for text in labels)
    assert any("settings > device & accounts" in text.lower() for text in labels)


def test_model_sourcing_tab_surfaces_readiness_but_defers_credentials_to_settings() -> None:
    _qapp()
    hub = ModelsHubView(QWidget(), QWidget(), QWidget())

    hub._set_active_tab("sourcing")

    assert "backend readiness" in hub._sourcing_page._summary_lbl.text().lower()
    assert "settings > device & accounts" in hub._sourcing_page._status_lbl.text().lower()
