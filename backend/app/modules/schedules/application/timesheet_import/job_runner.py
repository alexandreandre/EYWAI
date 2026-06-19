"""Abstraction exécution jobs import (BackgroundTasks aujourd'hui, worker externe demain)."""

from __future__ import annotations

from typing import Any, Callable, Protocol


class BackgroundTasksLike(Protocol):
    def add_task(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None: ...


class ImportJobRunner(Protocol):
    def enqueue(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None: ...


class BackgroundTasksRunner:
    def __init__(self, background_tasks: BackgroundTasksLike) -> None:
        self._tasks = background_tasks

    def enqueue(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        self._tasks.add_task(fn, *args, **kwargs)


class InlineRunner:
    """Exécution synchrone (tests)."""

    def enqueue(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        fn(*args, **kwargs)


__all__ = ["BackgroundTasksRunner", "ImportJobRunner", "InlineRunner"]
