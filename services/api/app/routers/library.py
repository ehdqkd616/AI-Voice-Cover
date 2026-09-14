"""A user's own cover history — the Job row (not just the final Media) is the
natural unit here since it carries the conversion params (voice model,
pitch, etc.) that make a library entry meaningful, unlike a bare media list.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select

from common.db.models import Job, Media, User
from common.db.session import SessionLocal
from common.storage import delete_object

from ..deps import require_user
from ..errors import ApiError
from ..schemas.library import LibraryItem

router = APIRouter()


def _collect_descendants(db, media_id: str) -> list[Media]:
    """Same recursive walk as media.py's delete route — duplicated locally
    rather than imported across routers to keep each router self-contained."""
    found: list[Media] = []
    frontier = [media_id]
    while frontier:
        children = db.execute(select(Media).where(Media.parent_id.in_(frontier))).scalars().all()
        if not children:
            break
        found.extend(children)
        frontier = [c.id for c in children]
    return found


@router.get("", response_model=list[LibraryItem])
def list_library(current_user: User = Depends(require_user)) -> list[LibraryItem]:
    db = SessionLocal()
    try:
        jobs = (
            db.execute(
                select(Job)
                .where(Job.user_id == current_user.id, Job.type == "cover", Job.status == "succeeded")
                .order_by(Job.finished_at.desc().nullslast(), Job.queued_at.desc())
            )
            .scalars()
            .all()
        )
        items: list[LibraryItem] = []
        for job in jobs:
            if not job.output_media:
                continue
            media = db.get(Media, job.output_media[0])
            if not media:
                continue
            params = job.params or {}
            items.append(
                LibraryItem(
                    job_id=job.id,
                    media_id=media.id,
                    title=media.title,
                    artist=media.artist,
                    voice_model_name=params.get("voice_model_name"),
                    source_type=params.get("source_type"),
                    duration_sec=float(media.duration_sec) if media.duration_sec is not None else None,
                    output_format=params.get("output_format"),
                    created_at=job.finished_at or job.queued_at,
                )
            )
        return items
    finally:
        db.close()


@router.delete("/{job_id}")
def delete_library_item(job_id: str, current_user: User = Depends(require_user)) -> dict:
    """Deletes the whole cover — job row + the source media and everything
    derived from it (stems, converted vocal, final mix), matching media.py's
    single-source-media cascade. `job.params["media_id"]` is the root source
    media for both the upload and youtube paths by the time a job reaches
    "separate" or later (see tasks/cover.py's advance_stage calls)."""
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job or job.user_id != current_user.id:
            raise ApiError("NOT_FOUND", "작업을 찾을 수 없습니다.", {"job_id": job_id})

        root_media_id = (job.params or {}).get("media_id")
        cascaded = 0
        if root_media_id:
            root_media = db.get(Media, root_media_id)
            if root_media:
                descendants = _collect_descendants(db, root_media_id)
                for child in descendants:
                    delete_object(child.storage_key)
                delete_object(root_media.storage_key)
                # Row deletion for descendants is left to the DB's ON DELETE
                # CASCADE on media.parent_id (see media.py's delete_media,
                # same pattern) — S3 objects had to be enumerated up front
                # since their storage_key wouldn't be reachable afterward.
                db.delete(root_media)
                cascaded = len(descendants)

        db.delete(job)
        db.commit()
        return {"deleted": job_id, "cascaded": cascaded}
    finally:
        db.close()
