"""Lightweight task dispatcher for the API process.

The API only needs to enqueue tasks by name — it must not import the worker
task modules themselves, since those pull in heavy/optional deps (torch,
demucs, RVC) that don't belong in the API image.
"""

from functools import lru_cache

from celery import Celery

from .config import get_settings


@lru_cache
def get_celery_client() -> Celery:
    settings = get_settings()
    return Celery("ai-voice-cover-client", broker=settings.redis_url, backend=settings.redis_url)


def send_task(name: str, args: list, queue: str):
    return get_celery_client().send_task(name, args=args, queue=queue)
