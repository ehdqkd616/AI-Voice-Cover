"""Celery queue routing for the AI Voice Cover pipeline.

Four stages, four queues: download -> separate -> convert -> mix (dsp queue).
Separation and conversion share one GPU-bound container on this host's single
4GB GPU (see docker-compose.yml's worker-separate-convert, `-P solo -c 1`), so
there's no benefit to more concurrency there — the GPU itself is the
bottleneck resource.
"""

from celery import Celery
from kombu import Queue

from common.config import get_settings

settings = get_settings()

app = Celery("ai-voice-cover", broker=settings.redis_url, backend=settings.redis_url)

app.conf.task_queues = (
    Queue("download", routing_key="download.#"),
    Queue("separate", routing_key="separate.#"),
    Queue("convert", routing_key="convert.#"),
    Queue("dsp", routing_key="dsp.#"),
    # UVR-MDX-NET separation — isolated CPU-only worker (see
    # services/workers/Dockerfile.mdx), an alternative to the Demucs path
    # above rather than a stage of its own; either lands on "convert" next.
    Queue("mdx", routing_key="mdx.#"),
)

app.conf.task_routes = {
    "tasks.cover_ingest_youtube": {"queue": "download"},
    "tasks.cover_separate": {"queue": "separate"},
    "tasks.cover_separate_mdx": {"queue": "mdx"},
    "tasks.cover_convert": {"queue": "convert"},
    "tasks.cover_mix": {"queue": "dsp"},
    "tasks.canary_healthcheck": {"queue": "dsp"},
    "tasks.purge_expired_media": {"queue": "dsp"},
}

app.conf.task_track_started = True
app.conf.task_acks_late = True
app.conf.worker_prefetch_multiplier = 1
app.conf.timezone = "UTC"
app.conf.broker_connection_retry_on_startup = True

app.conf.beat_schedule = {
    "canary-healthcheck": {
        "task": "tasks.canary_healthcheck",
        "schedule": 300.0,  # 5 min
    },
    "purge-expired-media": {
        "task": "tasks.purge_expired_media",
        "schedule": 900.0,  # 15 min, TTL cleanup
    },
}

app.autodiscover_tasks(["workers"], related_name="tasks")
