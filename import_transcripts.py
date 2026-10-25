# -*- coding: utf-8 -*-
"""
Created on Sun Oct 25 21:02:21 2026

@author: rajpr
"""


from pathlib import Path
import sqlite3
import hashlib
import re
import json
import math

BASE_DIR = Path.home() / "UdemyNoteTaker"
ENGINE_DIR = BASE_DIR / "note_engine"
COURSES_DIR = ENGINE_DIR / "courses"
DB_PATH = ENGINE_DIR / "course_ledger.sqlite3"

# Aim for about 8 minutes of speech per chunk.
# Overlap retains context at boundaries.
CHUNK_SECONDS = 8 * 60
OVERLAP_SECONDS = 30

TIMESTAMP_RE = re.compile(
    r"^\[(\d+(?:\.\d+)?)s\s*-\s*(\d+(?:\.\d+)?)s\]\s*(.*)$"
)


def parse_transcript(path):
    """Read timestamped Whisper transcript lines."""
    segments = []

    with path.open("r", encoding="utf-8-sig") as f:
        for line_number, line in enumerate(f, 1):
            line = line.strip()

            if not line or line.lower().startswith("language:"):
                continue

            match = TIMESTAMP_RE.match(line)
            if not match:
                # Don't silently discard unrecognized lines.
                print(f"Skipped unrecognized line {line_number}: {line[:100]}")
                continue

            start, end, text = match.groups()
            start, end = float(start), float(end)

            if end < start:
                print(f"Invalid timestamp on line {line_number}")
                continue

            if text.strip():
                segments.append({
                    "start": start,
                    "end": end,
                    "text": text.strip()
                })

    return segments


def make_chunks(segments):
    """Group segments by time, preserving source timestamps."""
    if not segments:
        return []

    chunks = []
    current = []
    chunk_start = segments[0]["start"]
    chunk_end = chunk_start

    for seg in segments:
        # Start a new chunk only at a segment boundary.
        if current and seg["end"] - chunk_start > CHUNK_SECONDS:
            chunks.append({
                "start": current[0]["start"],
                "end": current[-1]["end"],
                "text": " ".join(s["text"] for s in current)
            })

            # Keep segments overlapping the previous boundary.
            boundary = current[-1]["end"] - OVERLAP_SECONDS
            current = [s for s in current if s["end"] > boundary]
            chunk_start = current[0]["start"] if current else seg["start"]

        current.append(seg)
        chunk_end = seg["end"]

    if current:
        chunks.append({
            "start": current[0]["start"],
            "end": current[-1]["end"],
            "text": " ".join(s["text"] for s in current)
        })

    return chunks


def stable_id(*parts):
    value = "|".join(str(p) for p in parts)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def import_transcript(transcript_path, course_id, course_name):
    transcript_path = Path(transcript_path).resolve()

    if not transcript_path.is_file():
        raise FileNotFoundError(transcript_path)

    segments = parse_transcript(transcript_path)
    chunks = make_chunks(segments)

    if not chunks:
        raise ValueError(
            "No timestamped transcript segments found. "
            "Expected lines like [0.0s - 4.5s] spoken words."
        )

    lecture_name = transcript_path.stem
    source_file = str(transcript_path)
    digest = hashlib.sha256(transcript_path.read_bytes()).hexdigest()

    course_dir = COURSES_DIR / course_id
    course_dir.mkdir(parents=True, exist_ok=True)

    # Save the source manifest so each import is auditable.
    manifest = {
        "course_id": course_id,
        "course_name": course_name,
        "lecture_name": lecture_name,
        "source_file": source_file,
        "source_sha256": digest,
        "segment_count": len(segments),
        "chunk_count": len(chunks),
        "chunk_seconds_target": CHUNK_SECONDS,
        "overlap_seconds": OVERLAP_SECONDS
    }

    manifest_path = course_dir / f"{lecture_name}_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8"
    )

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO courses (course_id, course_name)
            VALUES (?, ?)
            ON CONFLICT(course_id) DO UPDATE SET
                course_name=excluded.course_name
            """,
            (course_id, course_name)
        )

        for index, chunk in enumerate(chunks):
            text_hash = hashlib.sha256(
                chunk["text"].encode("utf-8")
            ).hexdigest()

            chunk_id = stable_id(
                course_id, source_file, digest, index, text_hash
            )

            # Persist a separate source chunk for auditing and recovery.
            chunk_path = course_dir / f"{lecture_name}_chunk_{index + 1:04d}.json"
            chunk_path.write_text(
                json.dumps({
                    **chunk,
                    "chunk_index": index,
                    "source_file": source_file,
                    "source_sha256": digest
                }, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

            conn.execute(
                """
                INSERT INTO chunks (
                    chunk_id, course_id, lecture_name, source_file,
                    chunk_index, start_seconds, end_seconds,
                    transcript_text, text_hash, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                ON CONFLICT(course_id, source_file, chunk_index)
                DO UPDATE SET
                    chunk_id=excluded.chunk_id,
                    start_seconds=excluded.start_seconds,
                    end_seconds=excluded.end_seconds,
                    transcript_text=excluded.transcript_text,
                    text_hash=excluded.text_hash,
                    status=CASE
                        WHEN chunks.text_hash=excluded.text_hash
                        THEN chunks.status
                        ELSE 'pending'
                    END,
                    attempts=CASE
                        WHEN chunks.text_hash=excluded.text_hash
                        THEN chunks.attempts
                        ELSE 0
                    END,
                    error_message=CASE
                        WHEN chunks.text_hash=excluded.text_hash
                        THEN chunks.error_message
                        ELSE NULL
                    END,
                    notes_path=CASE
                        WHEN chunks.text_hash=excluded.text_hash
                        THEN chunks.notes_path
                        ELSE NULL
                    END,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    chunk_id, course_id, lecture_name, source_file,
                    index, chunk["start"], chunk["end"],
                    chunk["text"], text_hash
                )
            )

    print(f"Imported: {transcript_path.name}")
    print(f"Segments: {len(segments)}")
    print(f"Chunks: {len(chunks)}")
    print(f"Manifest: {manifest_path}")
    return len(chunks)


if __name__ == "__main__":
    # Example: update these two values for your course.
    COURSE_ID = "prompt_engineering"
    COURSE_NAME = "Prompt Engineering"

    transcript = (
        Path.home()
        / "UdemyNoteTaker"
        / "transcripts"
        / "lecture_20261025_195253.txt"
    )

    import_transcript(transcript, COURSE_ID, COURSE_NAME)
