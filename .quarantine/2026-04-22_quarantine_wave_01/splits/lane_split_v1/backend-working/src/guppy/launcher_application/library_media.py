from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


_AUDIO_EXTENSIONS = {
    ".aac",
    ".flac",
    ".m4a",
    ".mp3",
    ".ogg",
    ".wav",
    ".wma",
}

_VIDEO_EXTENSIONS = {
    ".avi",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".webm",
    ".wmv",
}


@dataclass(frozen=True)
class LibraryMediaDescriptor:
    path: str
    extension: str
    exists: bool
    is_local_file: bool
    is_media: bool
    media_kind: str
    source_label: str


def describe_library_media_path(path: str | Path | None) -> LibraryMediaDescriptor:
    cleaned = str(path or "").strip()
    if not cleaned:
        return LibraryMediaDescriptor(
            path="",
            extension="",
            exists=False,
            is_local_file=False,
            is_media=False,
            media_kind="",
            source_label="",
        )
    if "://" in cleaned and not cleaned.lower().startswith("file://"):
        return LibraryMediaDescriptor(
            path=cleaned,
            extension="",
            exists=False,
            is_local_file=False,
            is_media=False,
            media_kind="",
            source_label="",
        )
    try:
        normalized_path = str(Path(cleaned).expanduser().resolve())
    except OSError:
        normalized_path = str(Path(cleaned).expanduser())
    extension = Path(cleaned).suffix.strip().lower()
    media_kind = "audio" if extension in _AUDIO_EXTENSIONS else "video" if extension in _VIDEO_EXTENSIONS else ""
    return LibraryMediaDescriptor(
        path=normalized_path,
        extension=extension,
        exists=Path(normalized_path).exists(),
        is_local_file=True,
        is_media=bool(media_kind),
        media_kind=media_kind,
        source_label=(f"Local {media_kind}" if media_kind else ""),
    )


def is_library_media_path(path: str | Path | None) -> bool:
    return describe_library_media_path(path).is_media
