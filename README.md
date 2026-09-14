# AI Voice Cover

노래 음원(파일 업로드 또는 유튜브 URL)을 업로드하고, 보이스 모델과 몇 가지 설정값만 고르면 **보컬/반주 분리 → 보이스 변환(RVC) → 믹스**까지 전 과정을 서버에서 자동으로 처리해서 완성된 커버 음원을 다운로드까지 할 수 있는 셀프 호스팅 웹 앱입니다.

- 백엔드/인프라 구조는 [Music-Tools](../Music-Tools) (FastAPI + Celery + Postgres + Redis + MinIO, 쿠키 세션 인증 + 관리자 승인제)를 그대로 따릅니다.
- 보이스 변환 엔진은 [RVC-Learning](../RVC-Learning)의 RVC WebUI 포크에서 추론 코드만 라이브러리 형태로 이식했습니다 (`services/workers/rvc_engine/`) — 별도 서비스를 띄우거나 API를 호출하는 게 아니라, 이 프로젝트의 워커 프로세스 안에서 직접 실행됩니다.

## 파이프라인

```
업로드/유튜브 URL
      │
      ▼  (ingest, queue: download)
  원본 오디오 확보
      │
      ▼  (separate, queue: separate — Demucs)
  보컬 / 반주(MR) 분리
      │
      ▼  (convert, queue: convert — RVC)
  보컬을 선택한 보이스 모델로 변환
      │
      ▼  (mix, queue: dsp)
  반주와 다시 믹스 (샘플레이트 정합 · 러프니스 매칭 · 반주 피치 조절)
      │
      ▼
  완성된 커버 (재생 / 다운로드)
```

네 단계 모두 각자의 Celery 큐에서 도는 별도 태스크이고, 하나의 `Job` row(`stage` 컬럼)가 파이프라인 전체 상태를 추적합니다. 진행률은 `GET /api/v1/jobs/{id}/events` SSE로 프론트엔드에 실시간 전달됩니다. 한 단계가 끝나면 다음 태스크를 직접 큐에 넣는 방식(`job_lifecycle.advance_stage`)으로 이어지며, Celery chain/chord를 쓰지 않고 DB의 `Job` row 하나를 always 단일 진실 공급원으로 유지합니다.

## 아키텍처

| 서비스 | 역할 |
|---|---|
| `api` | FastAPI. 인증/관리자/업로드/유튜브 정보 조회/커버 요청/Job 상태(SSE)/미디어 스트리밍·다운로드 프록시 |
| `worker-download` | 유튜브 다운로드 (yt-dlp, CPU) |
| `worker-separate-convert` | Demucs 분리 + RVC 변환 (GPU 하나를 `-c 1 -P solo`로 순차 처리 — 4GB VRAM에서 두 GPU 작업이 동시에 뜨는 걸 방지) |
| `worker-dsp` | 믹스, 반주 피치 조절, 주기 작업(canary 헬스체크·만료 미디어 정리) |
| `worker-mdx` | UVR-MDX-NET 분리 (CPU 전용, 독립된 이미지 — RVC 엔진과 torch/numpy 버전이 서로 맞지 않아 별도 컨테이너로 분리) |
| `beat` | Celery beat 스케줄러 |
| `postgres` / `redis` / `minio` | DB / 큐·캐시·진행률 pub-sub / 오브젝트 스토리지 |
| `web` | Next.js 프론트엔드 |

음원·스템·결과물은 MinIO에 저장되지만, **재생/다운로드는 MinIO를 직접 노출하지 않고 API가 프록시**합니다 (Range 요청 지원 — seek 가능). 보이스 모델(`.pth`+`.index`)은 MinIO가 아니라 `data/voice-models/`에 파일로 직접 보관합니다 (RVC 엔진이 로컬 경로로 읽는 구조라 더 단순하고, `ls`로 바로 보여서 관리하기 편합니다).

## 처음 실행하기

```bash
cp .env.example .env
# .env에서 ADMIN_EMAIL / ADMIN_PASSWORD를 채워두면 첫 기동 시 관리자 계정이 자동 생성됩니다.
```

RVC 엔진에 필요한 사전학습 모델 2개(HuBERT/ContentVec, RMVPE — 각각 189MB/181MB)는 GitHub 100MB 제한 때문에 저장소에 포함되어 있지 않습니다. 빌드 전에 채워 넣어야 합니다:

```bash
# RVC-Learning을 로컬에 이미 클론해뒀다면 그대로 복사
cp /path/to/RVC-Learning/Retrieval-based-Voice-Conversion-WebUI-main/assets/hubert_base/pytorch_model.bin \
   services/workers/rvc_engine/assets/hubert_base/
cp /path/to/RVC-Learning/Retrieval-based-Voice-Conversion-WebUI-main/assets/rmvpe/rmvpe.pt \
   services/workers/rvc_engine/assets/rmvpe/
```

```bash
docker compose up -d --build
docker compose logs -f api   # alembic upgrade head 가 끝나는지 확인
```

- API: http://localhost:8010 (`/health`)
- 웹: http://localhost:3010
- MinIO 콘솔: http://localhost:9011

Music-Tools의 postgres/redis/minio와 포트가 겹치지 않도록 완전히 분리되어 있습니다 (기본 5433/6380/9010/9011/8010/3010, `.env`에서 조정 가능).

## 보이스 모델 준비

관리자 페이지(`/admin/models`)에서 `.pth`(+선택적으로 `.index`)를 직접 업로드하거나, RVC-Learning에 이미 학습해 둔 모델들을 일괄로 가져올 수 있습니다:

```bash
docker compose exec -T api python tools/import_voice_models.py \
  --source /path/to/RVC-Learning/.../assets \
  --index-dir /path/to/RVC-Learning/.../logs \
  --weight-root data/voice-models/weights \
  --index-root data/voice-models/indices
```

`.pth`와 `.index`는 파일명 기준으로 최대한 자동 매칭되고, 매칭 결과는 확신도(`auto_high` / `auto_low` / `unpaired`)로 콘솔에 요약 출력됩니다. `auto_low`/`unpaired`로 표시된 모델은 `/admin/models`에서 인덱스를 수동으로 재매칭하거나 그대로(인덱스 없이) 사용할 수 있습니다.

## 주요 기능

- 파일 업로드 또는 유튜브 URL로 소스 음원 지정
- 보이스 모델 선택 (관리자가 업로드/가져오기한 모델 목록에서)
- 변환 설정: 보컬 피치, 피치 추출 방식(pm/rmvpe/fcpe), 인덱스 반영 비율, 보호 강도, 라우드니스 믹스 비율, 보컬 볼륨 보정, 출력 형식(mp3/wav)
- 분리 엔진/품질 선택 — Demucs(빠름/고품질) 또는 UVR-MDX-NET(Kim_Vocal_2, CPU 전용 — 보컬 분리 정확도가 더 높은 편)
- **반주(MR) 피치 조절** — 보컬 피치와 독립적으로 반주 자체의 키를 템포 유지한 채 변경
- 계정별 작업 이력(`/library`) — 지금까지 만든 커버를 재생/다운로드/삭제
- 관리자: 회원 승인, 보이스 모델 등록/재매칭/활성화 관리

## 알려진 제약 · 다음에 할 만한 것

- **RVC 모델의 목표 샘플레이트가 반주(Demucs, 44100Hz)와 다를 수 있어** 믹스 단계에서 항상 반주 기준으로 리샘플링합니다 — 이미 처리되어 있지만, 추가하는 보이스 모델이 늘어날수록 계속 정확히 맞는지 확인이 필요합니다.
- 보컬/반주 길이 정렬은 패딩/트림 수준입니다 (DTW 등 정교한 재정렬은 하지 않음).
- Demucs 분리 + RVC 변환이 한 컨테이너에서 순차 처리됩니다 (`worker-separate-convert`, GPU VRAM 제약 때문). 처리량이 부족해지면 컨테이너를 분리하고 Redis 기반 GPU 락 도입을 고려하세요.
- 보이스 모델 삭제 시 DB row만 지워지고 `data/voice-models/`의 실제 파일은 남습니다 (다른 모델이나 재매칭이 같은 파일을 참조할 수 있어서 — 필요하면 수동으로 정리).

## 라이선스 관련

- `services/workers/rvc_engine/`은 RVC-Learning(MIT)에서 이식한 코드입니다 — 해당 디렉터리의 `LICENSE` 참고.
- Demucs(MIT), 나머지 의존성은 각 패키지 라이선스를 따릅니다.
