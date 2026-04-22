import unittest

from src.guppy.daemon.daemon import TaskScheduler


class ReminderWorkflowTest(unittest.TestCase):
    def test_schedule_list_cancel_roundtrip(self):
        scheduler = TaskScheduler(notifier=None)
        scheduler.start()
        try:
            msg = scheduler.schedule_reminder("workflow check", "in 10 minutes")
            self.assertIn("Reminder scheduled", msg)

            self.assertTrue(scheduler.jobs)
            job_id = next(iter(scheduler.jobs.keys()))

            reminders = scheduler.get_scheduled_reminders()
            self.assertIn(job_id, reminders)
            self.assertIn("workflow check", reminders[job_id]["message"])

            cancel_msg = scheduler.cancel_reminder(job_id)
            self.assertIn("cancelled", cancel_msg.lower())
            self.assertNotIn(job_id, scheduler.get_scheduled_reminders())
        finally:
            scheduler.stop()


if __name__ == "__main__":
    unittest.main()
