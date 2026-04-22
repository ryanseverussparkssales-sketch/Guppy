from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.local_llm_harness import build_record_id


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def ensure_record_ids(artifact: dict[str, Any]) -> None:
    for record in artifact.get("records") or []:
        if not record.get("record_id"):
            record["record_id"] = build_record_id(record)


def packet_path_for_artifact(artifact_path: str | Path) -> Path:
    artifact = Path(artifact_path)
    return artifact.with_name(f"{artifact.stem}.human_review_packet.json")


def build_review_packet(artifact: dict[str, Any], artifact_path: str | Path) -> dict[str, Any]:
    ensure_record_ids(artifact)
    records = []
    for record in artifact.get("records") or []:
        records.append(
            {
                "record_id": record["record_id"],
                "track": record.get("track"),
                "prompt_index": record.get("prompt_index"),
                "prompt": record.get("prompt"),
                "requested_tag": record.get("requested_tag"),
                "resolved_tag": record.get("resolved_tag"),
                "prompt_style": record.get("prompt_style"),
                "memory_backend": record.get("memory_backend"),
                "route": record.get("route"),
                "response_preview": record.get("response_preview"),
                "memory_context_preview": record.get("memory_context_preview", ""),
                "review_score": record.get("review_score"),
                "notes": record.get("notes", ""),
                "reviewer": record.get("reviewer", ""),
            }
        )
    return {
        "artifact_file": str(Path(artifact_path)),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "instructions": {
            "score_scale": "1-5 human usefulness score",
            "fields": ["review_score", "notes", "reviewer"],
            "guidance": [
                "Score usefulness, groundedness, tone fit, and whether recall helped rather than adding noise.",
                "Use notes to call out hallucination risk, over-reasoning, missed memory, or especially strong retrieval.",
                "Leave review_score null if the record has not been reviewed yet."
            ],
        },
        "records": records,
    }


def apply_review_packet(artifact: dict[str, Any], packet: dict[str, Any]) -> dict[str, Any]:
    ensure_record_ids(artifact)
    review_by_id = {
        str(item.get("record_id") or "").strip(): item
        for item in (packet.get("records") or [])
        if str(item.get("record_id") or "").strip()
    }
    reviewed = 0
    scores: list[float] = []
    for record in artifact.get("records") or []:
        review = review_by_id.get(record["record_id"])
        if not review:
            continue
        score = review.get("review_score")
        notes = str(review.get("notes") or "")
        reviewer = str(review.get("reviewer") or "")
        record["review_score"] = score
        record["notes"] = notes
        if reviewer:
            record["reviewer"] = reviewer
        if isinstance(score, (int, float)):
            reviewed += 1
            scores.append(float(score))
    total = len(artifact.get("records") or [])
    artifact["human_review_summary"] = {
        "reviewed_records": reviewed,
        "pending_records": max(0, total - reviewed),
        "average_review_score": round(sum(scores) / len(scores), 2) if scores else None,
        "last_applied_at_utc": datetime.now(timezone.utc).isoformat(),
        "review_packet_file": str(packet.get("artifact_file") or ""),
    }
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit or apply a human review packet for local LLM benchmark artifacts.")
    parser.add_argument("artifact_file", help="Benchmark artifact JSON file.")
    parser.add_argument("--emit-packet", default="", help="Write a human review packet JSON to this path.")
    parser.add_argument("--apply-packet", default="", help="Apply a filled human review packet JSON back into the artifact.")
    args = parser.parse_args()

    artifact_path = Path(args.artifact_file)
    artifact = load_json(artifact_path)

    if args.apply_packet:
        packet = load_json(args.apply_packet)
        updated = apply_review_packet(artifact, packet)
        write_json(artifact_path, updated)
        print(f"Applied review packet to {artifact_path}")
        return 0

    output_path = Path(args.emit_packet) if args.emit_packet else packet_path_for_artifact(artifact_path)
    packet = build_review_packet(artifact, artifact_path)
    write_json(output_path, packet)
    print(f"Human review packet written: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
