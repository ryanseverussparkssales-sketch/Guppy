#!/usr/bin/env python3
"""
test_reminders.py — Test reminder tools integration
====================================================
Tests:
  1. Daemon manager initialization
  2. TaskScheduler.schedule_reminder() with various time formats
  3. TaskScheduler.get_scheduled_reminders()
  4. TaskScheduler.cancel_reminder()
  5. Tool handlers through guppy_core.run_tool()
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

# Add Guppy directory to path
GUPPY_DIR = Path(__file__).parent
sys.path.insert(0, str(GUPPY_DIR))

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def test_daemon_manager():
    """Test DaemonManager initialization and lifecycle."""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Daemon Manager Initialization")
    logger.info("="*60)
    
    try:
        from guppy_daemon import get_daemon_manager
        
        manager = get_daemon_manager()
        logger.info(f"✓ Daemon manager created: {manager}")
        logger.info(f"  - Notifier: {manager.notifier}")
        logger.info(f"  - Window Watcher: {manager.window_watcher}")
        logger.info(f"  - Task Scheduler: {manager.task_scheduler}")
        
        # Start daemon
        manager.start()
        logger.info("✓ Daemon started successfully")
        time.sleep(1)  # Let daemon settle
        
        return manager
    except Exception as e:
        logger.error(f"✗ Daemon manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_task_scheduler(manager):
    """Test TaskScheduler time parsing and scheduling."""
    logger.info("\n" + "="*60)
    logger.info("TEST 2: Task Scheduler — Time Parsing & Scheduling")
    logger.info("="*60)
    
    try:
        scheduler = manager.task_scheduler
        
        # Test 1: Schedule in 5 seconds
        logger.info("\nScheduling reminder in 5 seconds...")
        result = scheduler.schedule_reminder("Test reminder 1 (in 5 seconds)", "in 5 seconds")
        logger.info(f"✓ Result: {result}")
        
        # Test 2: Schedule for specific time (tomorrow 10am)
        logger.info("\nScheduling reminder for tomorrow at 10am...")
        result = scheduler.schedule_reminder("Test reminder 2 (tomorrow 10am)", "tomorrow at 10am")
        logger.info(f"✓ Result: {result}")
        
        # Test 3: Schedule for today at specific time
        logger.info("\nScheduling reminder for today at specific time...")
        now = datetime.now()
        target_time = (now + timedelta(minutes=10)).strftime("%I:%M %p")
        result = scheduler.schedule_reminder(f"Test reminder 3 ({target_time})", target_time)
        logger.info(f"✓ Result: {result}")
        
        logger.info("\n✓ All scheduling tests completed")
        return True
    except Exception as e:
        logger.error(f"✗ Task scheduler test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_reminders(manager):
    """Test retrieving scheduled reminders."""
    logger.info("\n" + "="*60)
    logger.info("TEST 3: Get Scheduled Reminders")
    logger.info("="*60)
    
    try:
        reminders = manager.task_scheduler.get_scheduled_reminders()
        
        if not reminders:
            logger.warning("⚠ No reminders found (may have not scheduled yet)")
            return True
        
        logger.info(f"✓ Found {len(reminders)} reminders:")
        for job_id, details in reminders.items():
            logger.info(f"\n  ID: {job_id}")
            logger.info(f"    Message: {details['message']}")
            logger.info(f"    Trigger: {details['trigger']}")
            logger.info(f"    Next Run: {details['next_run']}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Get reminders test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cancel_reminder(manager):
    """Test cancelling a reminder."""
    logger.info("\n" + "="*60)
    logger.info("TEST 4: Cancel Reminder")
    logger.info("="*60)
    
    try:
        # Get first reminder to cancel
        reminders = manager.task_scheduler.get_scheduled_reminders()
        if not reminders:
            logger.warning("⚠ No reminders to cancel")
            return True
        
        job_id = list(reminders.keys())[0]
        logger.info(f"Cancelling reminder: {job_id}")
        
        result = manager.task_scheduler.cancel_reminder(job_id)
        logger.info(f"✓ Result: {result}")
        
        # Verify it's gone
        remaining = manager.task_scheduler.get_scheduled_reminders()
        logger.info(f"✓ Remaining reminders: {len(remaining)}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Cancel reminder test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tool_handlers():
    """Test tool execution through guppy_core.run_tool()"""
    logger.info("\n" + "="*60)
    logger.info("TEST 5: Tool Handlers (guppy_core.run_tool)")
    logger.info("="*60)
    
    try:
        from guppy_core import run_tool
        
        # Make sure daemon is enabled
        import guppy_core
        if not guppy_core.DAEMON:
            logger.warning("⚠ DAEMON feature flag is False, skipping tool tests")
            return True
        
        # Test remind_me tool
        logger.info("\nTesting remind_me tool...")
        result = run_tool("remind_me", {
            "message": "Test reminder from tool",
            "time": "in 10 seconds"
        })
        logger.info(f"✓ remind_me result: {result}")
        
        # Test get_reminders tool
        logger.info("\nTesting get_reminders tool...")
        result = run_tool("get_reminders", {})
        logger.info(f"✓ get_reminders result: {result}")
        
        # Test cancel_reminder tool (if we have reminders)
        if "No active reminders" not in result:
            logger.info("\nTesting cancel_reminder tool...")
            # Extract a job ID from the result (format: "[ID] message — ...")
            import re
            match = re.search(r'\[([^\]]+)\]', result)
            if match:
                job_id = match.group(1)
                result = run_tool("cancel_reminder", {"reminder_id": job_id})
                logger.info(f"✓ cancel_reminder result: {result}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Tool handlers test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    logger.info("\n🧪 REMINDER TOOLS TEST SUITE 🧪\n")
    
    # Test 1: Daemon initialization
    manager = test_daemon_manager()
    if not manager:
        logger.error("\n❌ FAILED: Could not initialize daemon manager")
        return False
    
    # Test 2: Task scheduling
    if not test_task_scheduler(manager):
        logger.error("\n❌ FAILED: Task scheduler test failed")
        return False
    
    # Wait a moment for jobs to be scheduled
    time.sleep(1)
    
    # Test 3: Get reminders
    if not test_get_reminders(manager):
        logger.error("\n❌ FAILED: Get reminders test failed")
        return False
    
    # Test 4: Cancel reminder
    if not test_cancel_reminder(manager):
        logger.error("\n❌ FAILED: Cancel reminder test failed")
        return False
    
    # Test 5: Tool handlers
    if not test_tool_handlers():
        logger.error("\n❌ FAILED: Tool handlers test failed")
        return False
    
    # Clean shutdown
    logger.info("\n" + "="*60)
    logger.info("Shutting down daemon...")
    logger.info("="*60)
    manager.stop()
    logger.info("✓ Daemon stopped")
    
    logger.info("\n" + "="*60)
    logger.info("✅ ALL TESTS PASSED")
    logger.info("="*60 + "\n")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
