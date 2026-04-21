"""Embedded terminal session runtime for App Mgmt views."""

from __future__ import annotations

import queue
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .terminal_recipes import apply_terminal_recipe_marker, build_tracked_terminal_recipe


@dataclass(frozen=True, slots=True)
class TerminalSessionUpdate:
    ok: bool = True
    log_lines: tuple[str, ...] = ()
    status_text: str = ""
    focus_output: bool = False
    clear_input: bool = False
    completed_payloads: tuple[dict[str, Any], ...] = ()


class EmbeddedTerminalSession:
    """Owns the embedded PowerShell process, output queue, and tracked recipes."""

    def __init__(self, *, root: Path) -> None:
        self._root = Path(root)
        self._output_queue: queue.SimpleQueue[tuple[str, str]] = queue.SimpleQueue()
        self._process: subprocess.Popen[str] | None = None
        self._focus_pending = False
        self._recipes: dict[str, dict[str, object]] = {}

    @property
    def recipes(self) -> dict[str, dict[str, object]]:
        return self._recipes

    @property
    def process(self) -> subprocess.Popen[str] | None:
        return self._process

    def queue_commands(
        self,
        commands: list[str],
        *,
        label: str,
        recipe_context: dict[str, object] | None = None,
    ) -> TerminalSessionUpdate:
        cleaned = [str(item).strip() for item in commands if str(item).strip()]
        if not cleaned:
            return TerminalSessionUpdate(
                ok=False,
                log_lines=(f"[launcher] {label} has no commands to run",),
            )

        ensure = self._ensure_process()
        if not ensure.ok:
            return ensure

        proc = self._process
        if proc is None or proc.stdin is None:
            return TerminalSessionUpdate(
                ok=False,
                log_lines=ensure.log_lines + ("[launcher] terminal stdin unavailable",),
                status_text=f"{label} could not access terminal stdin",
            )

        rendered_commands = cleaned
        if isinstance(recipe_context, dict):
            plan = build_tracked_terminal_recipe(cleaned, label=label, recipe_context=recipe_context)
            self._recipes[plan.recipe_id] = plan.context
            rendered_commands = list(plan.rendered_commands)

        lines = list(ensure.log_lines)
        lines.append(f"[workflow] running {label} ({len(cleaned)} commands)")
        lines.extend(f"> [{idx}/{len(cleaned)}] {command}" for idx, command in enumerate(cleaned, start=1))
        try:
            for command in rendered_commands:
                proc.stdin.write(command + "\n")
            proc.stdin.flush()
        except Exception as exc:
            return TerminalSessionUpdate(
                ok=False,
                log_lines=tuple(lines) + (f"[launcher] workflow run failed: {exc}",),
                status_text=f"{label} failed: {exc}",
            )
        self._focus_pending = True
        return TerminalSessionUpdate(
            ok=True,
            log_lines=tuple(lines),
            status_text=f"Shell running {label.lower()}",
        )

    def submit_command(self, command: str) -> TerminalSessionUpdate:
        text = str(command or "").strip()
        if not text:
            return TerminalSessionUpdate(ok=False)

        ensure = self._ensure_process()
        if not ensure.ok:
            return ensure

        proc = self._process
        if proc is None or proc.stdin is None:
            return TerminalSessionUpdate(
                ok=False,
                log_lines=ensure.log_lines + ("[launcher] terminal stdin unavailable",),
                status_text="Shell input unavailable",
            )
        try:
            proc.stdin.write(text + "\n")
            proc.stdin.flush()
        except Exception as exc:
            return TerminalSessionUpdate(
                ok=False,
                log_lines=ensure.log_lines + (f"[launcher] terminal write failed: {exc}",),
                status_text=f"Shell write failed: {exc}",
            )
        return TerminalSessionUpdate(
            ok=True,
            log_lines=ensure.log_lines + (f"> {text}",),
            status_text="Shell running command",
            clear_input=True,
        )

    def handle_recipe_marker(self, line: str) -> TerminalSessionUpdate:
        result = apply_terminal_recipe_marker(
            line,
            self._recipes,
            shell_pid=self._process.pid if self._process is not None else None,
            shell_alive=self._process is not None and self._process.poll() is None,
        )
        if not result.consumed:
            return TerminalSessionUpdate(ok=False)
        self._recipes.clear()
        self._recipes.update(result.recipes)
        payloads: tuple[dict[str, Any], ...] = ()
        if result.completed_payload is not None:
            payloads = (result.completed_payload,)
        return TerminalSessionUpdate(
            ok=True,
            status_text=result.status_text or "",
            completed_payloads=payloads,
        )

    def drain_output(self, *, max_items: int = 80) -> TerminalSessionUpdate:
        lines: list[str] = []
        completed_payloads: list[dict[str, Any]] = []
        status_text = ""
        focus_output = False
        drained = 0
        while drained < max_items:
            try:
                stream_name, line = self._output_queue.get_nowait()
            except queue.Empty:
                break
            if line:
                marker = self.handle_recipe_marker(line)
                if marker.ok:
                    if marker.status_text:
                        status_text = marker.status_text
                    if marker.completed_payloads:
                        completed_payloads.extend(marker.completed_payloads)
                    drained += 1
                    continue
                prefix = "[stderr] " if stream_name == "stderr" else ""
                lines.append(prefix + line)
                if self._focus_pending:
                    focus_output = True
                    self._focus_pending = False
            drained += 1

        if self._process is not None and self._process.poll() is not None:
            status_text = f"Shell exited [{self._process.returncode}]"
            self._process = None

        return TerminalSessionUpdate(
            ok=True,
            log_lines=tuple(lines),
            status_text=status_text,
            focus_output=focus_output,
            completed_payloads=tuple(completed_payloads),
        )

    def stop(self) -> TerminalSessionUpdate:
        proc = self._process
        if proc is None or proc.poll() is not None:
            self._process = None
            return TerminalSessionUpdate(ok=True, status_text="Shell idle")
        try:
            proc.terminate()
            return TerminalSessionUpdate(
                ok=True,
                log_lines=("[launcher] stop requested",),
                status_text="Shell stopping",
            )
        except Exception as exc:
            return TerminalSessionUpdate(
                ok=False,
                log_lines=(f"[launcher] stop failed: {exc}",),
                status_text=f"Shell stop failed: {exc}",
            )

    def _ensure_process(self) -> TerminalSessionUpdate:
        if self._process is not None and self._process.poll() is None:
            return TerminalSessionUpdate(ok=True)
        try:
            self._process = subprocess.Popen(
                ["powershell", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit", "-Command", "-"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(self._root),
                bufsize=1,
            )
        except Exception as exc:
            return TerminalSessionUpdate(
                ok=False,
                log_lines=(f"[launcher] terminal start failed: {exc}",),
                status_text=f"Shell failed: {exc}",
            )

        self._start_reader(self._process.stdout, "stdout")
        self._start_reader(self._process.stderr, "stderr")
        return TerminalSessionUpdate(
            ok=True,
            log_lines=(f"[launcher] embedded PowerShell ready in {self._root}",),
            status_text=f"Shell ready [pid={self._process.pid}]",
        )

    def _start_reader(self, stream, stream_name: str) -> None:
        if stream is None:
            return

        def _reader() -> None:
            while True:
                try:
                    line = stream.readline()
                except Exception as exc:
                    self._output_queue.put(("stderr", f"[launcher] terminal reader failed: {exc}"))
                    return
                if line == "":
                    return
                self._output_queue.put((stream_name, line.rstrip("\r\n")))

        threading.Thread(target=_reader, daemon=True).start()
