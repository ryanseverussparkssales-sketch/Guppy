from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from apscheduler.schedulers.background import BackgroundScheduler
from dateutil import parser as dateutil_parser

from src.guppy.daemon.notifier import GuppyNotifier
from src.guppy.daemon.support import RUNTIME_DIR, _write_json_atomic, logger


class TaskScheduler:
    """Manage scheduled reminders and tasks (APScheduler wrapper)."""

    def __init__(self, notifier: Optional[GuppyNotifier] = None):
        self.scheduler = BackgroundScheduler()
        self.notifier = notifier
        self.jobs = {}
        self.reminders = {}
        self.runtime_dir = RUNTIME_DIR
        self.reminder_events_path = self.runtime_dir / "reminder_events.jsonl"

    def _emit_ipc(self, agent: str, cmd: str, payload: Optional[dict] = None):
        """Write a lightweight IPC command file for a UI agent."""
        try:
            self.runtime_dir.mkdir(parents=True, exist_ok=True)
            cmd_path = self.runtime_dir / f"{agent}.cmd"
            _write_json_atomic(
                cmd_path,
                {
                    "cmd": cmd,
                    "payload": payload or {},
                    "ts": datetime.now().isoformat(),
                },
            )
        except Exception as e:
            logger.debug(f"IPC emit failed ({agent}:{cmd}): {e}")

    def _record_reminder_event(
        self,
        event: str,
        job_id: str,
        message: str,
        trigger_time: Optional[datetime] = None,
    ):
        """Append reminder workflow events for schedule/action/confirmation traceability."""
        try:
            self.runtime_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "ts": datetime.now().isoformat(),
                "event": event,
                "job_id": job_id,
                "short_id": job_id[-8:] if job_id else "",
                "message": message,
            }
            if trigger_time is not None:
                payload["trigger_time"] = trigger_time.isoformat()
            with self.reminder_events_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=True) + "\n")
        except Exception as e:
            logger.debug(f"Reminder event logging failed: {e}")

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Task scheduler started")

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Task scheduler stopped")

    def schedule_reminder(self, text: str, run_time: str) -> str:
        try:
            trigger_time = self._parse_time(run_time)
            job_id = f"reminder_{uuid4().hex}"

            def notify():
                if self.notifier:
                    self.notifier.reminder(text)
                logger.info(f"Reminder: {text}")
                self._record_reminder_event("fired", job_id, text, trigger_time)
                payload = {
                    "message": text,
                    "job_id": job_id,
                    "short_id": job_id[-8:],
                    "trigger_time": trigger_time.isoformat(),
                }
                self._emit_ipc("guppy", "reminder_fired", payload)
                self._emit_ipc("council", "reminder_fired", payload)
                self.jobs.pop(job_id, None)
                self.reminders.pop(job_id, None)

            job = self.scheduler.add_job(
                notify,
                "date",
                run_date=trigger_time,
                id=job_id,
                replace_existing=False,
            )
            self.jobs[job_id] = job
            self.reminders[job_id] = text
            logger.info(f"Reminder scheduled: {text} at {trigger_time}")
            self._record_reminder_event("scheduled", job_id, text, trigger_time)
            return (
                f"Reminder scheduled: '{text}' at "
                f"{trigger_time.strftime('%Y-%m-%d %H:%M:%S')} (ID: {job_id[-8:]})"
            )
        except Exception as e:
            logger.error(f"Schedule reminder failed: {e}")
            return f"Error scheduling reminder: {e}"

    def cancel_reminder(self, job_id: str) -> str:
        if job_id in self.jobs:
            try:
                self.scheduler.remove_job(job_id)
                del self.jobs[job_id]
                self.reminders.pop(job_id, None)
                logger.info(f"Reminder cancelled: {job_id}")
                self._record_reminder_event("cancelled", job_id, "cancelled by user")
                return f"Reminder {job_id[-8:]} cancelled."
            except Exception as e:
                logger.error(f"Cancel failed: {e}")
                return f"Error cancelling reminder: {e}"
        return f"Reminder {job_id} not found."

    def get_scheduled_reminders(self) -> dict[str, dict[str, str]]:
        reminders_dict = {}
        for job_id, job in self.jobs.items():
            try:
                if self.scheduler.get_job(job_id) is not None:
                    reminder_text = self.reminders.get(job_id, "Reminder")
                    next_run = getattr(job, "next_run_time", None)
                    if next_run:
                        reminders_dict[job_id] = {
                            "message": reminder_text,
                            "trigger": str(job.trigger),
                            "next_run": str(next_run),
                        }
            except Exception as e:
                logger.debug(f"Error checking job {job_id}: {e}")
        return reminders_dict

    def list_reminders(self) -> list[dict[str, str]]:
        jobs = []
        for job_id, job in self.jobs.items():
            if job.next_run_time:
                jobs.append({"id": job_id, "next_run": str(job.next_run_time)})
        return jobs

    def _parse_time(self, time_str: str) -> datetime:
        time_str = time_str.strip().lower()
        now = datetime.now()

        if time_str.startswith("in "):
            parts = time_str[3:].split()
            if len(parts) >= 2:
                try:
                    amount = int(parts[0])
                    unit = parts[1].rstrip("s")
                    if unit == "minute":
                        return now + timedelta(minutes=amount)
                    if unit == "hour":
                        return now + timedelta(hours=amount)
                    if unit == "second":
                        return now + timedelta(seconds=amount)
                except (ValueError, IndexError):
                    pass

        if time_str.startswith("tomorrow"):
            tomorrow = now + timedelta(days=1)
            remainder = time_str.replace("tomorrow", "").strip()
            if remainder:
                if remainder.startswith("at "):
                    remainder = remainder[3:]
                try:
                    parsed_time = dateutil_parser.parse(remainder, default=tomorrow)
                    return parsed_time.replace(
                        year=tomorrow.year,
                        month=tomorrow.month,
                        day=tomorrow.day,
                    )
                except Exception:
                    return tomorrow.replace(hour=12, minute=0, second=0, microsecond=0)
            return tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)

        try:
            parsed = dateutil_parser.parse(time_str, default=now)
            if parsed < now:
                if any(day in time_str for day in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]):
                    days_ahead = 0
                    while (
                        now + timedelta(days=days_ahead)
                    ).strftime("%a").lower() != parsed.strftime("%a").lower():
                        days_ahead += 1
                    parsed = now + timedelta(days=days_ahead)
                    parsed = parsed.replace(
                        hour=parsed.hour,
                        minute=parsed.minute,
                        second=parsed.second,
                    )
                else:
                    parsed = parsed.replace(year=now.year, month=now.month, day=now.day)
                    if parsed < now:
                        parsed = parsed + timedelta(days=1)
            return parsed
        except Exception as e:
            logger.error(f"Time parse failed: {e}")
            raise ValueError(f"Could not parse time: {time_str}")
