"""Tests job runner abstraction."""

from app.modules.schedules.application.timesheet_import.job_runner import InlineRunner


def test_inline_runner_executes():
    ran = []

    def fn(x):
        ran.append(x)

    InlineRunner().enqueue(fn, 42)
    assert ran == [42]
