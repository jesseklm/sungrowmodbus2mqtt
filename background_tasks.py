import asyncio
import logging

background_tasks = set()


def run_in_background(coro):
    task = asyncio.create_task(coro)
    background_tasks.add(task)

    def task_done(t):
        background_tasks.discard(t)
        try:
            t.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.exception("unhandled exception in background task: %s", e)

    task.add_done_callback(task_done)
