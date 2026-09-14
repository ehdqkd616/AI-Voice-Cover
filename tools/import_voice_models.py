#!/usr/bin/env python3
"""One-time / occasional import of RVC voice models into the app's registry.

Not part of the API or worker containers' startup — run this manually,
whenever you have a new batch of trained RVC checkpoints (.pth + .index) to
register.

Requirements to run this script:
  - `torch` must be importable in whatever environment runs it (this script
    does NOT install it for you — use the same venv/container the workers
    image uses, or a local venv with `pip install torch`).
  - PYTHONPATH must include this repo's `services/` directory so that
    `common.*` imports resolve, e.g.:

      PYTHONPATH=/home/rudy/git-repository/AI-Voice-Cover/services \\
        python tools/import_voice_models.py \\
        --source /path/to/Retrieval-based-Voice-Conversion-WebUI-main/assets \\
        --index-dir /path/to/Retrieval-based-Voice-Conversion-WebUI-main/logs \\
        --weight-root /path/to/voice-models-volume/weights \\
        --index-root /path/to/voice-models-volume/indices

  - When targeting the dockerized `voice-models` named volume, point
    --weight-root/--index-root at wherever that volume is mounted on the
    host (or run this inside a one-off container with the volume mounted,
    e.g. `docker compose run --rm -v voice-models:/mnt ...`).

Real RVC-Learning layout note: index files are typically split across
`Retrieval-based-Voice-Conversion-WebUI-main/logs/*.index` (where training
actually writes them) and an often-empty `assets/indices/`. --index-dir
should normally point at the `logs` directory — `assets/indices` alone is
rarely sufficient, so both are searched.
"""

import argparse
import os
import re
import shutil
import sys

EXPERIMENT_SUFFIX_RE = re.compile(r"_e\d+_s\d+$", re.IGNORECASE)


def derive_experiment_name(pth_stem: str) -> str:
    """Strips a trailing `_e<digits>_s<digits>` checkpoint-step suffix, e.g.
    "my_singer_e250_s10000" -> "my_singer"."""
    return EXPERIMENT_SUFFIX_RE.sub("", pth_stem)


def prettify_name(experiment_name: str) -> str:
    return experiment_name.replace("_", " ").replace("-", " ").strip()


def find_pth_files(source: str) -> list[str]:
    weights_dir = os.path.join(source, "weights")
    if not os.path.isdir(weights_dir):
        return []
    return sorted(
        os.path.join(weights_dir, f) for f in os.listdir(weights_dir) if f.lower().endswith(".pth")
    )


def find_index_files(source: str, index_dir: str) -> list[str]:
    """Searches --index-dir (normally .../logs, where RVC training actually
    writes .index files) plus the assets/indices fallback location."""
    search_dirs = []
    for d in (index_dir, os.path.join(source, "indices")):
        if d and os.path.isdir(d) and d not in search_dirs:
            search_dirs.append(d)

    found: list[str] = []
    for d in search_dirs:
        for f in os.listdir(d):
            if f.lower().endswith(".index"):
                found.append(os.path.join(d, f))
    return sorted(found)


def match_index(experiment_name: str, index_paths: list[str]) -> tuple[str | None, str]:
    """Returns (matched_index_path, confidence)."""
    exp_lower = experiment_name.lower()

    for path in index_paths:
        basename_lower = os.path.basename(path).lower()
        if f"_{exp_lower}_v1" in basename_lower or f"_{exp_lower}_v2" in basename_lower:
            return path, "auto_high"

    for path in index_paths:
        basename_lower = os.path.basename(path).lower()
        if exp_lower and exp_lower in basename_lower:
            return path, "auto_low"

    return None, "unpaired"


def inspect_checkpoint(pth_path: str) -> dict:
    import torch

    checkpoint = torch.load(pth_path, map_location="cpu")
    version = checkpoint.get("version", "v2")
    sample_rate = checkpoint["config"][-1]
    has_f0 = bool(checkpoint.get("f0", 1))
    return {"version": version, "sample_rate": sample_rate, "has_f0": has_f0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--source", required=True, help="Path to the RVC-WebUI 'assets' directory (contains weights/)."
    )
    parser.add_argument(
        "--index-dir",
        required=True,
        help="Path to the directory holding trained .index files (normally '.../logs').",
    )
    parser.add_argument("--weight-root", required=True, help="Destination directory for .pth files.")
    parser.add_argument("--index-root", required=True, help="Destination directory for .index files.")
    args = parser.parse_args()

    from common.db.models import VoiceModel
    from common.db.session import session_scope
    from common.ids import new_id
    from sqlalchemy import select

    pth_files = find_pth_files(args.source)
    if not pth_files:
        print(f"No .pth files found under {os.path.join(args.source, 'weights')}", file=sys.stderr)
        sys.exit(1)
    index_files = find_index_files(args.source, args.index_dir)

    os.makedirs(args.weight_root, exist_ok=True)
    os.makedirs(args.index_root, exist_ok=True)

    summary_rows = []

    for pth_path in pth_files:
        pth_filename = os.path.basename(pth_path)
        pth_stem = os.path.splitext(pth_filename)[0]
        experiment_name = derive_experiment_name(pth_stem)
        display_name = prettify_name(experiment_name) or experiment_name

        matched_index_path, confidence = match_index(experiment_name, index_files)

        try:
            meta = inspect_checkpoint(pth_path)
        except Exception as exc:  # corrupt/unexpected checkpoint shape
            print(f"  SKIP {pth_filename}: failed to load checkpoint ({exc})", file=sys.stderr)
            continue

        # Copy (never move) — the source assets directory is left untouched.
        dest_weight_path = os.path.join(args.weight_root, pth_filename)
        shutil.copy2(pth_path, dest_weight_path)

        index_filename = None
        if matched_index_path:
            index_filename = os.path.basename(matched_index_path)
            dest_index_path = os.path.join(args.index_root, index_filename)
            shutil.copy2(matched_index_path, dest_index_path)

        with session_scope() as db:
            existing = db.execute(select(VoiceModel).where(VoiceModel.name == display_name)).scalar_one_or_none()
            if existing:
                existing.weight_filename = pth_filename
                existing.index_filename = index_filename
                existing.version = meta["version"]
                existing.sample_rate = meta["sample_rate"]
                existing.has_f0 = meta["has_f0"]
                existing.pairing_confidence = confidence
            else:
                db.add(
                    VoiceModel(
                        id=new_id("vm"),
                        name=display_name,
                        weight_filename=pth_filename,
                        index_filename=index_filename,
                        version=meta["version"],
                        sample_rate=meta["sample_rate"],
                        has_f0=meta["has_f0"],
                        pairing_confidence=confidence,
                    )
                )

        summary_rows.append(
            {
                "name": display_name,
                "weight_filename": pth_filename,
                "index_filename": index_filename or "none",
                "confidence": confidence,
            }
        )

    print()
    print(f"{'Name':<30} {'Weight file':<40} {'Index file':<45} Confidence")
    print("-" * 130)
    for row in summary_rows:
        print(f"{row['name']:<30} {row['weight_filename']:<40} {row['index_filename']:<45} {row['confidence']}")
    print()
    print(f"Imported {len(summary_rows)} of {len(pth_files)} .pth files found.")
    needs_review = [r for r in summary_rows if r["confidence"] in ("unpaired", "auto_low")]
    if needs_review:
        print(f"{len(needs_review)} model(s) need manual review/re-pair in the admin UI:")
        for r in needs_review:
            print(f"  - {r['name']} ({r['confidence']})")


if __name__ == "__main__":
    main()
