# AI Voice Cover

> 🔗 **배포 주소:** https://ai-voice-cover.hotgarlic.dedyn.io

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
| `worker-separate-convert` | Demucs 분리 + RVC 변환 + **보이스 모델 학습** (GPU 하나를 `-c 1 -P solo`로 순차 처리 — 4GB VRAM에서 GPU 작업이 동시에 뜨는 걸 방지) |
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

## 보이스 모델 학습

관리자는 `/train`(헤더의 "보이스 학습")에서 새 목소리를 직접 학습시킬 수 있습니다. RVC-Learning의 WebUI는 데이터 경로 입력 → 전처리 → 특징 추출 → 학습 → 인덱스 → 모델 파일 정리를 단계마다 버튼으로 눌러야 했지만, 여기서는 **음원을 올리고 이름만 정하면 끝까지 자동**으로 진행되고 완성된 모델이 바로 보이스 모델 목록에 등록됩니다.

- **음원 그대로 업로드** — 여러 파일 드래그 앤 드롭. "보컬 자동 추출"을 켜면 반주가 섞인 노래 원곡도 Demucs로 목소리만 뽑아서 학습에 씁니다.
- **데이터 분량 안내** — 올린 총 분량을 보고 너무 짧음/권장 분량 등을 바로 알려줍니다 (최소 1분, 권장 10~30분).
- **학습 강도 프리셋** — 빠른 테스트(50) / 표준(200) / 고품질(400) epoch. 고급 설정에서 epoch·batch size·샘플레이트(40k/48k) 직접 지정 가능.
- **진행 상황 실시간 표시** — 5단계 진행 표시, 현재 epoch와 남은 시간(ETA), 상세 로그. 페이지를 닫아도 서버에서 계속 진행됩니다.
- **GPU 메모리 자동 대응** — 학습 전에 커버 워커가 들고 있던 모델 캐시를 비우고, 그래도 메모리가 부족(OOM)하면 batch size를 절반씩 줄여 마지막 체크포인트부터 자동으로 이어서 학습합니다.
- **이어서 학습** — 끝난 학습에 epoch를 더 얹거나(+50/+100/+200 또는 직접 입력), 중지·실패한 학습을 마지막 체크포인트부터 이어갑니다. 데이터 준비·전처리·특징 추출은 건너뛰고 바로 학습 단계부터 시작하며, 끝나면 등록된 모델이 새 버전으로 교체됩니다. 체크포인트가 생기기 전에 실패한 학습은 "다시 시도"로 같은 설정 그대로 처음부터 재실행.
- **모델 파일 다운로드** — 학습된 `.pth`와 `.index`를 각각, 또는 한 번에 `.zip`으로 받을 수 있습니다 (RVC WebUI 등 다른 RVC 프로그램에서 그대로 사용 가능).
- **중지 / 기록 삭제**, 완료 후 **"이 목소리로 커버 만들기"** 바로가기. 중지해도 마지막 체크포인트는 남고, 기록을 삭제하면 체크포인트도 함께 지워져 더 이상 이어서 학습할 수 없습니다.

내부적으로는 RVC-Learning의 학습 스크립트(`train/preprocess.py`, `extract_f0.py`, `extract_hubert_feature.py`, `train.py`, `train_index.py`)를 `services/workers/rvc_engine/train/`에 그대로 이식해서 WebUI와 같은 방식(서브프로세스)으로 실행합니다 — 오케스트레이션은 `services/workers/training/pipeline.py`, Celery 태스크는 `tasks.train_voice_model`(큐 `train`).

학습 중에는 GPU를 학습이 쓰기 때문에, 그 사이 요청한 커버 만들기는 학습이 끝날 때까지 대기열에서 기다립니다. 이 호스트의 GTX 1050 Ti(4GB, Pascal)는 fp32로 학습하며, 학습에는 **여유 VRAM이 약 2.5GB 이상** 필요합니다 (batch size 2 기준, 모델 가중치+옵티마이저만 ~1.65GB). 같은 GPU를 쓰는 다른 프로젝트 워커(Music-Tools 분리 워커 ~0.8GB, image-tools upscale ~0.8GB)가 VRAM을 잡고 있으면 batch 1에서도 OOM이 나므로, 학습 전에 잠시 멈췄다가 끝나면 다시 켜주세요:

```bash
docker stop music-tools-worker-separate-1 image-tools-worker-1   # 학습 전
docker start music-tools-worker-separate-1 image-tools-worker-1  # 학습 후
```

**준비물** — 학습에 쓰는 사전학습 모델(G/D)은 용량(D 파일 137MB) 때문에 저장소에 없습니다. `data/rvc-pretrained/`에 넣어두세요:

```bash
mkdir -p data/rvc-pretrained
cp /path/to/RVC-Learning/Retrieval-based-Voice-Conversion-WebUI-main/assets/pretrained_v2/f0{G,D}{40k,48k}.pth data/rvc-pretrained/
```

학습 중간 파일(데이터셋, 슬라이스, 특징, 체크포인트)은 `data/training/<실험명>/`에 쌓이고, 완성된 모델은 `data/voice-models/weights/`·`indices/`에 바로 저장됩니다. 학습 기록을 삭제하면 중간 파일만 지워지고 등록된 모델은 남습니다.

## 주요 기능

- 파일 업로드 또는 유튜브 URL로 소스 음원 지정
- 보이스 모델 선택 (관리자가 업로드/가져오기한 모델 목록에서)
- 변환 설정: 보컬 피치, 피치 추출 방식(pm/rmvpe/fcpe), 인덱스 반영 비율, 보호 강도, 라우드니스 믹스 비율, 보컬 볼륨 보정, 출력 형식(mp3/wav)
- 분리 엔진/품질 선택 — Demucs(빠름/고품질) 또는 UVR-MDX-NET(Kim_Vocal_2, CPU 전용 — 보컬 분리 정확도가 더 높은 편)
- **반주(MR) 피치 조절** — 보컬 피치와 독립적으로 반주 자체의 키를 템포 유지한 채 변경
- 계정별 작업 이력(`/library`) — 지금까지 만든 커버를 재생/다운로드/삭제
- **보이스 모델 학습**(`/train`) — 음원만 올리면 보컬 추출부터 모델 등록까지 자동 (위 섹션 참고)
- 관리자: 회원 승인, 보이스 모델 등록/재매칭/활성화 관리

## 알려진 제약 · 다음에 할 만한 것

- **RVC 모델의 목표 샘플레이트가 반주(Demucs, 44100Hz)와 다를 수 있어** 믹스 단계에서 항상 반주 기준으로 리샘플링합니다 — 이미 처리되어 있지만, 추가하는 보이스 모델이 늘어날수록 계속 정확히 맞는지 확인이 필요합니다.
- 보컬/반주 길이 정렬은 패딩/트림 수준입니다 (DTW 등 정교한 재정렬은 하지 않음).
- Demucs 분리 + RVC 변환이 한 컨테이너에서 순차 처리됩니다 (`worker-separate-convert`, GPU VRAM 제약 때문). 처리량이 부족해지면 컨테이너를 분리하고 Redis 기반 GPU 락 도입을 고려하세요.
- 보이스 모델 삭제 시 DB row만 지워지고 `data/voice-models/`의 실제 파일은 남습니다 (다른 모델이나 재매칭이 같은 파일을 참조할 수 있어서 — 필요하면 수동으로 정리).

## 라이선스 관련

- `services/workers/rvc_engine/`은 RVC-Learning(MIT)에서 이식한 코드입니다 — 해당 디렉터리의 `LICENSE` 참고.
- Demucs(MIT), 나머지 의존성은 각 패키지 라이선스를 따릅니다.
