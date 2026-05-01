"""ui/launcher — OBSIDIAN unified launcher package."""

__all__ = ["LauncherWindow"]


def __getattr__(name: str):
	if name == "LauncherWindow":
		from .launcher_window import LauncherWindow

		return LauncherWindow
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
