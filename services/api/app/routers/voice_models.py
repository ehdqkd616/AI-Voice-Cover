"""Voice model registry: a public read-only listing (for the cover-request
form) plus admin CRUD for managing the RVC weight/index files on the
`voice-models` named volume (see docker-compose.yml, RVC_WEIGHT_ROOT/
RVC_INDEX_ROOT in common.config)."""

import os

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select

from common.config import get_settings
from common.db.models import User, VoiceModel
from common.db.session import SessionLocal
from common.ids import new_id

from ..deps import require_admin, require_user
from ..errors import ApiError
from ..schemas.voice_models import VoiceModelAdminResponse, VoiceModelResponse, VoiceModelUpdateRequest

router = APIRouter()
admin_router = APIRouter()


def _to_response(vm: VoiceModel) -> VoiceModelResponse:
    return VoiceModelResponse(
        id=vm.id,
        name=vm.name,
        description=vm.description,
        thumbnail_url=vm.thumbnail_url,
        version=vm.version,
        sample_rate=vm.sample_rate,
        has_f0=vm.has_f0,
        pairing_confidence=vm.pairing_confidence,
    )


def _to_admin_response(vm: VoiceModel) -> VoiceModelAdminResponse:
    return VoiceModelAdminResponse(
        id=vm.id,
        name=vm.name,
        description=vm.description,
        thumbnail_url=vm.thumbnail_url,
        weight_filename=vm.weight_filename,
        index_filename=vm.index_filename,
        version=vm.version,
        sample_rate=vm.sample_rate,
        has_f0=vm.has_f0,
        speaker_id=vm.speaker_id,
        pairing_confidence=vm.pairing_confidence,
        is_active=vm.is_active,
        created_at=vm.created_at,
    )


def _get_voice_model_or_404(db, voice_model_id: str) -> VoiceModel:
    vm = db.get(VoiceModel, voice_model_id)
    if not vm:
        raise ApiError("NOT_FOUND", "음성 모델을 찾을 수 없습니다.", {"voice_model_id": voice_model_id})
    return vm


@router.get("", response_model=list[VoiceModelResponse], dependencies=[Depends(require_user)])
def list_voice_models() -> list[VoiceModelResponse]:
    db = SessionLocal()
    try:
        rows = (
            db.execute(select(VoiceModel).where(VoiceModel.is_active.is_(True)).order_by(VoiceModel.name))
            .scalars()
            .all()
        )
        return [_to_response(vm) for vm in rows]
    finally:
        db.close()


@admin_router.get("", response_model=list[VoiceModelAdminResponse], dependencies=[Depends(require_admin)])
def admin_list_voice_models() -> list[VoiceModelAdminResponse]:
    db = SessionLocal()
    try:
        rows = db.execute(select(VoiceModel).order_by(VoiceModel.created_at.desc())).scalars().all()
        return [_to_admin_response(vm) for vm in rows]
    finally:
        db.close()


@admin_router.get("/unmatched-indices", dependencies=[Depends(require_admin)])
def unmatched_indices() -> list[str]:
    """Lists .index files sitting on the volume that no VoiceModel row
    currently references — fuel for the admin UI's manual re-pair dropdown."""
    settings = get_settings()
    try:
        on_disk = {f for f in os.listdir(settings.rvc_index_root) if f.lower().endswith(".index")}
    except FileNotFoundError:
        on_disk = set()

    db = SessionLocal()
    try:
        referenced = {
            row[0]
            for row in db.execute(
                select(VoiceModel.index_filename).where(VoiceModel.index_filename.is_not(None))
            ).all()
        }
    finally:
        db.close()

    return sorted(on_disk - referenced)


@admin_router.post("", response_model=VoiceModelAdminResponse, dependencies=[Depends(require_admin)])
async def upload_voice_model(
    name: str = Form(...),
    description: str | None = Form(default=None),
    weight_file: UploadFile = File(...),
    index_file: UploadFile | None = File(default=None),
    current_user: User = Depends(require_admin),
) -> VoiceModelAdminResponse:
    import torch  # heavy, admin-only dependency — see requirements.txt comment

    settings = get_settings()

    if not (weight_file.filename or "").lower().endswith(".pth"):
        raise ApiError(
            "UNSUPPORTED_FORMAT", "가중치 파일은 .pth 형식이어야 합니다.", {"filename": weight_file.filename}
        )
    if index_file is not None and not (index_file.filename or "").lower().endswith(".index"):
        raise ApiError(
            "UNSUPPORTED_FORMAT", "인덱스 파일은 .index 형식이어야 합니다.", {"filename": index_file.filename}
        )

    os.makedirs(settings.rvc_weight_root, exist_ok=True)
    weight_path = os.path.join(settings.rvc_weight_root, weight_file.filename)
    with open(weight_path, "wb") as f:
        f.write(await weight_file.read())

    index_filename: str | None = None
    if index_file is not None:
        os.makedirs(settings.rvc_index_root, exist_ok=True)
        index_path = os.path.join(settings.rvc_index_root, index_file.filename)
        with open(index_path, "wb") as f:
            f.write(await index_file.read())
        index_filename = index_file.filename

    checkpoint = torch.load(weight_path, map_location="cpu")
    version = checkpoint.get("version", "v2")
    sample_rate = checkpoint["config"][-1]
    has_f0 = bool(checkpoint.get("f0", 1))

    pairing_confidence = "manual" if index_filename else "unpaired"

    db = SessionLocal()
    try:
        vm = VoiceModel(
            id=new_id("vm"),
            name=name,
            weight_filename=weight_file.filename,
            index_filename=index_filename,
            version=version,
            sample_rate=sample_rate,
            has_f0=has_f0,
            description=description,
            pairing_confidence=pairing_confidence,
            uploaded_by=current_user.id,
        )
        db.add(vm)
        db.commit()
        db.refresh(vm)
        return _to_admin_response(vm)
    finally:
        db.close()


@admin_router.patch("/{voice_model_id}", response_model=VoiceModelAdminResponse, dependencies=[Depends(require_admin)])
def update_voice_model(voice_model_id: str, body: VoiceModelUpdateRequest) -> VoiceModelAdminResponse:
    db = SessionLocal()
    try:
        vm = _get_voice_model_or_404(db, voice_model_id)
        updates = body.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(vm, key, value)
        db.commit()
        db.refresh(vm)
        return _to_admin_response(vm)
    finally:
        db.close()


@admin_router.delete("/{voice_model_id}", dependencies=[Depends(require_admin)])
def delete_voice_model(voice_model_id: str) -> dict:
    """Deletes the DB row only. The underlying .pth/.index files on the
    voice-models volume are left in place — they're cheap to keep, and a
    future re-pair or re-import might still want them."""
    db = SessionLocal()
    try:
        vm = _get_voice_model_or_404(db, voice_model_id)
        db.delete(vm)
        db.commit()
        return {"deleted": voice_model_id}
    finally:
        db.close()
