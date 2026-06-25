import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_gradio import TaskController, run_scrape_job


class FakeConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_task_controller_prevents_duplicate_runs():
    controller = TaskController()

    assert controller.start() is True
    assert controller.start() is False
    assert controller.request_stop() is True
    assert controller.stop_event.is_set()
    controller.finish()
    assert controller.running is False
    assert controller.start() is True


def test_task_controller_reports_no_task_to_stop():
    controller = TaskController()

    assert controller.request_stop() is False


def test_worker_always_closes_connection_and_resets_controller():
    controller = TaskController()
    controller.start()
    connection = FakeConnection()
    messages = []

    def failing_crawl(*_args, **_kwargs):
        raise RuntimeError("boom")

    run_scrape_job(
        connection_factory=lambda: connection,
        crawl_function=failing_crawl,
        controller=controller,
        config=None,
        next_id=None,
        emit=messages.append,
    )

    assert connection.closed is True
    assert controller.running is False
    assert any("boom" in message for message in messages)


def test_worker_reports_completion_and_closes_connection():
    controller = TaskController()
    controller.start()
    connection = FakeConnection()
    messages = []

    class Finished:
        value = "finished"

    run_scrape_job(
        connection_factory=lambda: connection,
        crawl_function=lambda *_args, **_kwargs: Finished(),
        controller=controller,
        config=None,
        next_id="cursor",
        emit=messages.append,
    )

    assert messages[-1] == "Scraper finished."
    assert connection.closed is True
    assert controller.running is False


def test_worker_resets_controller_even_if_connection_close_fails():
    controller = TaskController()
    controller.start()
    messages = []

    class BrokenConnection:
        def close(self):
            raise RuntimeError("close failed")

    class Finished:
        value = "finished"

    with pytest.raises(RuntimeError, match="close failed"):
        run_scrape_job(
            connection_factory=BrokenConnection,
            crawl_function=lambda *_args, **_kwargs: Finished(),
            controller=controller,
            config=None,
            next_id=None,
            emit=messages.append,
        )

    assert controller.running is False
