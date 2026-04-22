from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from src.guppy.daemon.notifier import GuppyNotifier
from src.guppy.daemon.scheduler import TaskScheduler
from src.guppy.daemon.support import (
    PSUTIL_AVAILABLE,
    RUNTIME_DIR,
    get_operator,
    get_runtime_envelope_config,
    is_quiet_hours_now,
    log_operational_event,
    logger,
    psutil,
)


class ProactiveLoop:
    """
    Phase 8 - Proactive / Daemon Mode.

    Background thread that polls for agent health every POLL_INTERVAL seconds.
    - Nudges stale agents; repairs dead ones via HubOperator.
    - Fires upcoming-reminder toasts (<=15 min ahead).
    - Runs daily Haiku "anything important?" summary at GUPPY_DAILY_SUMMARY_HOUR.
    - Refreshes HubOperator pattern analysis (throttled 1/hr).
    """

    POLL_INTERVAL = 60

    def __init__(self, notifier: GuppyNotifier, scheduler: TaskScheduler):
        self.notifier = notifier
        self.scheduler = scheduler
        self._operator = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._reminder_notice_cache: set[str] = set()
        self._last_pattern_scan: float = 0.0
        self._last_nudge_at: dict[str, float] = {}
        self._last_repair_at: dict[str, float] = {}
        self._report_slots_fired: set[str] = set()
        self._nudge_cooldown_s = int(os.environ.get("GUPPY_NUDGE_COOLDOWN_S", "300"))
        self._repair_cooldown_s = int(os.environ.get("GUPPY_REPAIR_COOLDOWN_S", "900"))
        self._quiet_hours = os.environ.get("GUPPY_QUIET_HOURS", "22-7")
        self._quiet_hours_enabled = os.environ.get("GUPPY_QUIET_HOURS_ENABLED", "1").strip() in {"1", "true", "yes", "on"}
        self._daily_summary_hour = int(os.environ.get("GUPPY_DAILY_SUMMARY_HOUR", "8"))
        try:
            poll_s = int(os.environ.get("GUPPY_PROACTIVE_POLL_S", str(self.POLL_INTERVAL)))
        except Exception:
            poll_s = self.POLL_INTERVAL
        self.POLL_INTERVAL = max(30, min(poll_s, 300))
        news_hours_env = os.environ.get("GUPPY_NEWS_REPORT_HOURS", "12,18,22")
        parsed_hours: list[int] = []
        for raw in news_hours_env.split(","):
            raw = raw.strip()
            if not raw:
                continue
            try:
                hour = int(raw)
                if 0 <= hour <= 23:
                    parsed_hours.append(hour)
            except Exception:
                continue
        self._news_report_hours = sorted(set(parsed_hours)) if parsed_hours else [12, 18, 22]
        self._reports_dir = RUNTIME_DIR / "daily_reports"
        self._resource_status_path = RUNTIME_DIR / "resource_envelope.status.json"
        envelope_cfg = get_runtime_envelope_config()
        self._envelope_cfg = envelope_cfg
        self._resource_check_every_s = int(envelope_cfg.get("check_interval_s", 60))
        self._last_resource_check = 0.0
        self._last_resource_state = "unknown"
        self._last_resource_alert = 0.0
        self._resource_alert_cooldown_s = int(os.environ.get("GUPPY_ENVELOPE_ALERT_COOLDOWN_S", "600"))

    @staticmethod
    def _tail_lines(path: Path, limit: int = 20) -> list[str]:
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            return [line for line in lines[-limit:] if line.strip()]
        except Exception:
            return []

    def _collect_runtime_log_context(self) -> str:
        sources = {
            "agent_performance.jsonl": RUNTIME_DIR / "agent_performance.jsonl",
            "session_events.jsonl": RUNTIME_DIR / "session_events.jsonl",
            "integration_events.jsonl": RUNTIME_DIR / "integration_events.jsonl",
            "hub_patterns.jsonl": RUNTIME_DIR / "hub_patterns.jsonl",
        }
        lines: list[str] = []
        max_each = int(os.environ.get("GUPPY_DAILY_LOG_LINES", "8"))
        for label, path in sources.items():
            raw = self._tail_lines(path, limit=max_each)
            if not raw:
                continue
            lines.append(f"{label} (latest {len(raw)}):")
            for line in raw:
                snippet = line[:240] + ("..." if len(line) > 240 else "")
                lines.append(f"- {snippet}")
        return "\n".join(lines) if lines else "No recent runtime logs found."

    def _collect_manual_events(self) -> str:
        candidates = [
            RUNTIME_DIR / "manual_events.jsonl",
            RUNTIME_DIR / "manual_events.txt",
            RUNTIME_DIR / "daily_manual_events.md",
            RUNTIME_DIR / ("to" "do.txt"),
            RUNTIME_DIR / ("to" "do.md"),
        ]
        out: list[str] = []
        max_lines = int(os.environ.get("GUPPY_DAILY_MANUAL_LINES", "20"))
        for path in candidates:
            if not path.exists():
                continue
            out.append(f"{path.name}:")
            raw = self._tail_lines(path, limit=max_lines)
            for line in raw:
                if path.suffix.lower() == ".jsonl":
                    try:
                        obj = json.loads(line)
                        text = obj.get("text") or obj.get("event") or obj.get("message") or str(obj)
                        ts = obj.get("ts") or obj.get("timestamp") or ""
                        out.append(f"- {ts} {text}".strip())
                        continue
                    except Exception:
                        pass
                out.append(f"- {line[:220]}")
        return "\n".join(out) if out else "No manual events or carry-forward files found in runtime/."

    def _fetch_rss_feed(self, url: str, limit: int) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Guppy/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = resp.read()
            root = ET.fromstring(data)

            for item in root.findall(".//channel/item")[:limit]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                if title:
                    items.append({"title": title, "link": link})

            if not items:
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall(".//atom:entry", ns)[:limit]:
                    title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
                    link_el = entry.find("atom:link", ns)
                    link = (link_el.get("href") if link_el is not None else "") or ""
                    if title:
                        items.append({"title": title, "link": link})
        except Exception as e:
            logger.debug(f"RSS fetch failed for {url}: {e}")
        return items[:limit]

    def _collect_world_news(self) -> str:
        default_feeds = [
            "https://feeds.bbci.co.uk/news/world/rss.xml",
            "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
            "https://www.aljazeera.com/xml/rss/all.xml",
            "https://www.reuters.com/world/rss",
            "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
        ]
        feed_env = os.environ.get("GUPPY_DAILY_RSS_FEEDS", "").strip()
        feeds = [feed.strip() for feed in feed_env.split(",") if feed.strip()] if feed_env else default_feeds
        per_feed = int(os.environ.get("GUPPY_DAILY_RSS_ITEMS", "4"))

        lines: list[str] = []
        for url in feeds:
            items = self._fetch_rss_feed(url, per_feed)
            if not items:
                continue
            lines.append(f"Feed: {url}")
            for item in items:
                title = item.get("title", "")
                link = item.get("link", "")
                lines.append(f"- {title}" + (f" ({link})" if link else ""))
        return "\n".join(lines) if lines else "No world news headlines available from configured RSS feeds."

    def _load_yesterday_report(self) -> str:
        yday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        path = self._reports_dir / f"{yday}.md"
        if not path.exists():
            return "No previous daily report found (first run or file missing)."
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            lines = [line for line in text.splitlines() if line.strip()]
            snippet = "\n".join(lines[:40])
            return f"Yesterday report: {path.name}\n{snippet}"
        except Exception as e:
            return f"Yesterday report exists but could not be read: {e}"

    def _collect_memory_context(self) -> tuple[str, str]:
        memory_context = []
        tasks_block = "No pending tasks."
        try:
            from src.guppy.memory import memory as guppy_memory

            tasks_block = guppy_memory.get_tasks("pending")
            facts = guppy_memory.recall(limit=10)
            if tasks_block:
                memory_context.append("Pending tasks:\n" + tasks_block)
            if facts:
                memory_context.append("Recent facts:\n" + facts)
        except Exception as e:
            logger.debug(f"ProactiveLoop daily summary: memory load failed: {e}")
        if memory_context:
            return "\n\n".join(memory_context), tasks_block
        return "No pending tasks or notable facts.", tasks_block

    def _write_daily_report(self, report_text: str, report_kind: str, slot_hour: int) -> Path:
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        out_name = f"{today}.md" if report_kind == "daily" else f"{today}-{report_kind}-{slot_hour:02d}00.md"
        out_path = self._reports_dir / out_name
        out_path.write_text(report_text, encoding="utf-8")
        return out_path

    @staticmethod
    def _slot_key(report_kind: str, day: str, hour: int) -> str:
        return f"{day}:{report_kind}:{hour:02d}"

    def _was_slot_fired(self, report_kind: str, hour: int) -> bool:
        day = datetime.now().strftime("%Y-%m-%d")
        return self._slot_key(report_kind, day, hour) in self._report_slots_fired

    def _mark_slot_fired(self, report_kind: str, hour: int) -> None:
        day = datetime.now().strftime("%Y-%m-%d")
        self._report_slots_fired.add(self._slot_key(report_kind, day, hour))
        keep_days = {day, (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")}
        self._report_slots_fired = {
            key for key in self._report_slots_fired if any(key.startswith(f"{day_key}:") for day_key in keep_days)
        }

    def _run_scheduled_report(self, report_kind: str, slot_hour: int) -> None:
        memory_context, tasks_block = self._collect_memory_context()
        world_news = self._collect_world_news()
        runtime_logs = self._collect_runtime_log_context()
        manual_events = self._collect_manual_events()
        yesterday_report = self._load_yesterday_report()

        context = (
            "MEMORY CONTEXT:\n"
            f"{memory_context}\n\n"
            "WORLD NEWS (RSS):\n"
            f"{world_news}\n\n"
            "RUNTIME LOGS:\n"
            f"{runtime_logs}\n\n"
            "MANUAL EVENTS / CARRY-FORWARD INPUTS:\n"
            f"{manual_events}\n\n"
            "YESTERDAY REPORT REFERENCE:\n"
            f"{yesterday_report}\n"
        )

        summary = ""
        report_md = ""
        heading = "Daily Report" if report_kind == "daily" else "News Report"

        try:
            import anthropic

            client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
            intent = (
                "Prioritize top personal actions for today."
                if report_kind == "daily"
                else "Prioritize world-news updates, likely impacts, and what to monitor next."
            )
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=900,
                system=(
                    "You are Guppy's scheduled briefing assistant. "
                    "Produce two outputs in this exact format:\n"
                    "SUMMARY:\n"
                    "<under 80 words, bullets, actionable, can be 'nothing urgent'>\n"
                    "REPORT_MD:\n"
                    "<markdown report with sections: Key Actions, World News, Logs Signals, Manual Events & Carry-Forward Notes, Delta vs Yesterday, Carry-Forward Items>"
                ),
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Report type: {report_kind}\n"
                            f"Scheduled hour: {slot_hour:02d}:00\n"
                            f"Instruction: {intent}\n\n"
                            f"Compile report from context:\n\n{context}"
                        ),
                    }
                ],
            )
            raw = resp.content[0].text.strip() if resp.content else ""
            if "REPORT_MD:" in raw:
                left, right = raw.split("REPORT_MD:", 1)
                summary = left.replace("SUMMARY:", "").strip()
                report_md = right.strip()
            else:
                summary = raw
        except Exception as e:
            logger.warning(f"ProactiveLoop {report_kind} report: Haiku call failed: {e}")
            summary = f"{heading} generated without Haiku (fallback mode)."

        if not report_md:
            report_md = (
                f"# {heading} — {datetime.now().strftime('%Y-%m-%d')} {slot_hour:02d}:00\n\n"
                "## Key Actions\n"
                f"{summary or 'No urgent items detected.'}\n\n"
                "## World News\n"
                f"{world_news}\n\n"
                "## Logs Signals\n"
                f"{runtime_logs}\n\n"
                "## Manual Events & Carry-Forward Notes\n"
                f"{manual_events}\n\n"
                "## Delta vs Yesterday\n"
                f"{yesterday_report}\n\n"
                "## Carry-Forward Items\n"
                f"{tasks_block}\n"
            )

        report_path = None
        try:
            report_path = self._write_daily_report(report_md, report_kind=report_kind, slot_hour=slot_hour)
        except Exception as e:
            logger.warning(f"ProactiveLoop {report_kind} report: failed writing report: {e}")

        actionable = bool(summary and summary.lower() != "nothing urgent")
        if actionable:
            msg = summary[:200]
            if report_path is not None:
                msg = f"{msg} | report: {report_path.name}"
            toast_title = "Guppy Daily Briefing" if report_kind == "daily" else "Guppy News Briefing"
            self.notifier.info(toast_title, msg)
            op = self.operator
            if op:
                try:
                    op.send_command(
                        "guppy",
                        "nudge",
                        {
                            "reason": f"{report_kind}_summary",
                            "summary": summary[:500],
                            "report_path": str(report_path) if report_path is not None else "",
                        },
                    )
                    op.record_event("guppy", f"{report_kind}_summary", "proactive_loop", "sent")
                except Exception as e:
                    logger.debug(f"ProactiveLoop {report_kind} report: IPC nudge failed: {e}")

        logger.info(
            f"ProactiveLoop {report_kind} report fired (actionable={actionable}, "
            f"hour={slot_hour}, report={report_path.name if report_path else 'none'})"
        )
        self._mark_slot_fired(report_kind, slot_hour)

    @property
    def operator(self):
        if self._operator is None:
            self._operator = get_operator()
        return self._operator

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="ProactiveLoop")
        self._thread.start()
        logger.info("ProactiveLoop started")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("ProactiveLoop stopped")

    def _loop(self) -> None:
        while self._running:
            try:
                self._tick()
            except Exception as e:
                logger.error(f"ProactiveLoop tick error: {e}")
            time.sleep(self.POLL_INTERVAL)

    def _tick(self) -> None:
        op = self.operator
        if op is None:
            return
        now_ts = time.time()
        for hb_file in RUNTIME_DIR.glob("*.heartbeat"):
            agent_id = hb_file.stem
            try:
                last_seen = time.time() - hb_file.stat().st_mtime
                rec = op.smart_recommend(agent_id, is_stalled=(last_seen > 30), last_seen_seconds=last_seen)
                if rec == "nudge":
                    if now_ts - self._last_nudge_at.get(agent_id, 0.0) < self._nudge_cooldown_s:
                        continue
                    logger.info(f"ProactiveLoop: nudging stale agent '{agent_id}'")
                    op.nudge_agent(agent_id)
                    op.record_event(agent_id, "auto_nudge", "proactive_loop", "sent")
                    self._last_nudge_at[agent_id] = now_ts
                elif rec == "repair":
                    if now_ts - self._last_repair_at.get(agent_id, 0.0) < self._repair_cooldown_s:
                        continue
                    logger.info(f"ProactiveLoop: repairing dead agent '{agent_id}'")
                    removed = op.repair_agent(agent_id)
                    if removed and not self._is_quiet_hours_now():
                        self.notifier.info(
                            "Guppy Hub",
                            f"Agent '{agent_id}' repaired — cleared {len(removed)} stale files.",
                        )
                    self._last_repair_at[agent_id] = now_ts
            except Exception as e:
                logger.debug(f"ProactiveLoop: check failed for '{agent_id}': {e}")

        self._check_upcoming_reminders()
        self._check_pattern_learning()
        self._check_daily_summary()
        self._check_news_reports()
        self._check_resource_envelope()

    def _check_resource_envelope(self) -> None:
        now = time.time()
        if now - self._last_resource_check < self._resource_check_every_s:
            return
        self._last_resource_check = now

        profile = str(
            os.environ.get("GUPPY_RUNTIME_PROFILE", self._envelope_cfg.get("profile", "standard"))
        ).strip().lower() or "standard"
        self._envelope_cfg = get_runtime_envelope_config(profile)
        cpu_limit = float(self._envelope_cfg.get("cpu_max_pct", 80.0))
        ram_limit = float(self._envelope_cfg.get("ram_max_pct", 88.0))

        payload: dict[str, Any] = {
            "ts": datetime.now().isoformat(),
            "profile": profile,
            "limits": {"cpu_max_pct": cpu_limit, "ram_max_pct": ram_limit},
            "metrics": {},
            "state": "unknown",
            "violations": [],
            "message": "resource envelope check unavailable",
        }

        if not PSUTIL_AVAILABLE or psutil is None:
            payload["message"] = "psutil not available"
            self._write_resource_status(payload)
            return

        try:
            cpu_pct = float(psutil.cpu_percent(interval=0.2))
            vm = psutil.virtual_memory()
            ram_pct = float(vm.percent)
            available_gb = round(float(vm.available) / (1024 ** 3), 2)
            total_gb = round(float(vm.total) / (1024 ** 3), 2)
        except Exception as e:
            payload["message"] = f"psutil read failed: {e}"
            self._write_resource_status(payload)
            return

        violations: list[str] = []
        if cpu_pct > cpu_limit:
            violations.append("cpu")
        if ram_pct > ram_limit:
            violations.append("ram")

        state = "violation" if violations else "ok"
        payload.update(
            {
                "state": state,
                "metrics": {
                    "cpu_pct": round(cpu_pct, 2),
                    "ram_pct": round(ram_pct, 2),
                    "available_ram_gb": available_gb,
                    "total_ram_gb": total_gb,
                },
                "violations": violations,
                "message": "resource envelope within limits" if not violations else "resource envelope exceeded",
            }
        )

        state_changed = state != self._last_resource_state
        if state_changed or (state == "violation" and now - self._last_resource_alert >= self._resource_alert_cooldown_s):
            evt_level = "warning" if state == "violation" else "info"
            log_operational_event(
                stream="resource_envelope",
                event="resource_violation" if state == "violation" else "resource_ok",
                level=evt_level,
                payload=payload,
            )
            if state == "violation":
                if not self._is_quiet_hours_now():
                    self.notifier.info(
                        "Guppy Resource Envelope",
                        f"Profile {profile}: CPU {cpu_pct:.0f}% / RAM {ram_pct:.0f}% exceeds limits",
                    )
                self._last_resource_alert = now

        self._last_resource_state = state
        self._write_resource_status(payload)

    def _write_resource_status(self, payload: dict[str, Any]) -> None:
        try:
            self._resource_status_path.parent.mkdir(parents=True, exist_ok=True)
            self._resource_status_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug(f"Resource envelope status write failed: {e}")

    def _check_daily_summary(self) -> None:
        if self._is_quiet_hours_now():
            return
        now_hour = datetime.now().hour
        if now_hour != self._daily_summary_hour:
            return
        if self._was_slot_fired("daily", now_hour):
            return
        self._run_scheduled_report("daily", now_hour)

    def _check_news_reports(self) -> None:
        if self._is_quiet_hours_now():
            return
        now_hour = datetime.now().hour
        if now_hour not in self._news_report_hours:
            return
        if self._was_slot_fired("news", now_hour):
            return
        self._run_scheduled_report("news", now_hour)

    def _check_pattern_learning(self) -> None:
        now = time.time()
        if now - self._last_pattern_scan < 3600:
            return
        op = self.operator
        if op is None:
            return
        try:
            insight = op.analyze_patterns(force=False)
            if insight:
                logger.info("ProactiveLoop pattern insight refreshed")
            self._last_pattern_scan = now
        except Exception as e:
            logger.debug(f"ProactiveLoop pattern scan failed: {e}")

    def _check_upcoming_reminders(self) -> None:
        if self._is_quiet_hours_now():
            return
        now = datetime.now()
        if not self.scheduler or not getattr(self.scheduler, "jobs", None):
            return
        for job_id, job in list(self.scheduler.jobs.items()):
            try:
                run_at = getattr(job, "next_run_time", None)
                if run_at is None:
                    continue
                run_local = run_at.replace(tzinfo=None)
                mins = (run_local - now).total_seconds() / 60.0
                if 0 <= mins <= 15 and job_id not in self._reminder_notice_cache:
                    msg = self.scheduler.reminders.get(job_id, "Reminder")
                    self.notifier.info("Guppy Heads Up", f"Reminder in {max(1, int(mins))}m: {msg}")
                    op = self.operator
                    if op:
                        op.send_command("guppy", "nudge", {"reason": "upcoming_reminder", "job_id": job_id})
                        op.record_event("guppy", "proactive_reminder", job_id, "nudged")
                    self._reminder_notice_cache.add(job_id)
            except Exception as e:
                logger.debug(f"ProactiveLoop reminder check failed for '{job_id}': {e}")

    def _is_quiet_hours_now(self) -> bool:
        return is_quiet_hours_now(self._quiet_hours, self._quiet_hours_enabled)
