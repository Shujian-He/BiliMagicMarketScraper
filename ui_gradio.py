"""Gradio interface for the Bilibili Magic Market scraper."""

import queue
import threading
from dataclasses import dataclass, field

import gradio as gr

from db import initialize_database
from main import ScrapeConfig, crawl
from tools import load_checkpoint


@dataclass
class TaskController:
    lock: threading.Lock = field(default_factory=threading.Lock)
    stop_event: threading.Event = field(default_factory=threading.Event)
    running: bool = False

    def start(self):
        with self.lock:
            if self.running:
                return False
            self.running = True
            self.stop_event.clear()
            return True

    def request_stop(self):
        with self.lock:
            if not self.running:
                return False
            self.stop_event.set()
            return True

    def finish(self):
        with self.lock:
            self.running = False


controller = TaskController()


def run_scrape_job(
    *,
    connection_factory,
    crawl_function,
    controller,
    config,
    next_id,
    emit,
):
    connection = None
    try:
        connection = connection_factory()
        status = crawl_function(
            connection,
            config,
            start_next_id=next_id,
            stop_event=controller.stop_event,
            log=emit,
        )
        emit(f"Scraper {status.value}.")
    except Exception as exc:
        emit(f"Scraper failed: {exc}")
    finally:
        try:
            if connection is not None:
                connection.close()
        finally:
            controller.finish()


def scrape(want_text, price_filters, discount_filters, category_filter, continue_from_id):
    if not controller.start():
        yield "A scraper task is already running."
        return

    want_list = tuple(value.strip() for value in want_text.split(",") if value.strip())
    config = ScrapeConfig(
        want_list=want_list or ("初音未来",),
        price_filters=tuple(price_filters or ("10000-20000", "20000-0")),
        discount_filters=tuple(
            discount_filters or ("0-30", "30-50", "50-70", "70-100")
        ),
        category_filter=category_filter or "",
    )
    next_id = load_checkpoint() if continue_from_id else None
    messages = queue.Queue()
    worker = threading.Thread(
        target=run_scrape_job,
        kwargs={
            "connection_factory": initialize_database,
            "crawl_function": crawl,
            "controller": controller,
            "config": config,
            "next_id": next_id,
            "emit": messages.put,
        },
        daemon=True,
    )

    try:
        worker.start()
    except Exception as exc:
        controller.finish()
        yield f"Unable to start scraper: {exc}"
        return

    log_lines = []
    while worker.is_alive() or not messages.empty():
        try:
            log_lines.append(messages.get(timeout=0.2))
        except queue.Empty:
            continue
        yield "\n".join(log_lines)

    worker.join()


def stop_scraping():
    if controller.request_stop():
        return "Stopping after the current request or page completes."
    return "No scraper task is running."


with gr.Blocks(title="Bili Market Scraper") as demo:
    gr.Markdown("## Bili Market Scraper")
    want = gr.Textbox(label="Wanted item names (comma-separated)", value="初音未来")
    price = gr.CheckboxGroup(
        ["0-2000", "2000-3000", "3000-5000", "5000-10000", "10000-20000", "20000-0"],
        label="Price filters",
        value=["10000-20000", "20000-0"],
    )
    discount = gr.CheckboxGroup(
        ["0-30", "30-50", "50-70", "70-100"],
        label="Discount filters",
        value=["0-30", "30-50", "50-70", "70-100"],
    )
    category = gr.Dropdown(
        ["", "2312", "2066", "2331", "2273", "fudai_cate_id"],
        label="Category",
        value="",
    )
    continue_from_id = gr.Checkbox(label="Continue from nextId.txt", value=False)
    with gr.Row():
        run_button = gr.Button("Start scraping", variant="primary")
        stop_button = gr.Button("Stop scraping", variant="stop")
    log_output = gr.Textbox(label="Logs", lines=25, interactive=False)

    run_button.click(
        fn=scrape,
        inputs=[want, price, discount, category, continue_from_id],
        outputs=log_output,
    )
    stop_button.click(
        fn=stop_scraping,
        inputs=None,
        outputs=log_output,
        queue=False,
    )


if __name__ == "__main__":
    demo.queue().launch(inbrowser=True)
