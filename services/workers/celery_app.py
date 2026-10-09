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
    # Voice-model training — consumed by worker-separate-convert alongside
    # separate/convert, since all three need the host's single GPU.
    Queue("train", routing_key="train.#"),
)

app.conf.task_routes = {
    "tasks.cover_ingest_youtube": {"queue": "download"},
    "tasks.cover_separate": {"queue": "separate"},
    "tasks.cover_separate_mdx": {"queue": "mdx"},
    "tasks.cover_convert": {"queue": "convert"},
    "tasks.cover_mix": {"queue": "dsp"},
    "tasks.train_voice_model": {"queue": "train"},
    "tasks.canary_healthcheck": {"queue": "dsp"},
    "tasks.purge_expired_media": {"queue": "dsp"},
}

app.conf.task_track_started = True
app.conf.task_acks_late = True
app.conf.worker_prefetch_multiplier = 1
app.conf.timezone = "UTC"
app.conf.broker_connection_retry_on_startup = True
# Redis re-delivers an unacked message once this window passes. With
# task_acks_late, a cover task prefetched by worker-separate-convert while it
# is busy with a multi-hour training run would otherwise be handed out a
# second time after the 1h default — so the window must outlast a training run.
app.conf.broker_transport_options = {"visibility_timeout": 60 * 60 * 24}

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
