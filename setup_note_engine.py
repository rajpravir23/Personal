# -*- coding: utf-8 -*-
"""
Created on Sun Oct 25 21:00:55 2026

@author: rajpr
"""


from pathlib import Path
import sqlite3

# Keep the existing transcription files untouched
BASE_DIR = Path.home() / "UdemyNoteTaker"
ENGINE_DIR = BASE_DIR / "note_engine"

COURSES_DIR = ENGINE_DIR / "courses"
OUTPUT_DIR = ENGINE_DIR / "outputs"
LOGS_DIR = ENGINE_DIR / "logs"

DB_PATH = ENGINE_DIR / "course_ledger.sqlite3"

# Create the working folders
for folder in (COURSES_DIR, OUTPUT_DIR, LOGS_DIR):
    folder.mkdir(parents=True, exist_ok=True)

# Create a persistent database
with sqlite3.connect(DB_PATH) as conn:
    conn.execute("PRAGMA journal_mode=WAL")

    conn.executescript("""
    CREATE TABLE IF NOT EXISTS courses (
        course_id TEXT PRIMARY KEY,
        course_name TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'registered'
    );

    CREATE TABLE IF NOT EXISTS chunks (
        chunk_id TEXT PRIMARY KEY,
        course_id TEXT NOT NULL,
        lecture_name TEXT NOT NULL,
        source_file TEXT NOT NULL,
        chunk_index INTEGER NOT NULL,
        start_seconds REAL NOT NULL,
        end_seconds REAL NOT NULL,
        transcript_text TEXT NOT NULL,
        text_hash TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0,
        error_message TEXT,
        notes_path TEXT,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (course_id) REFERENCES courses(course_id),
        UNIQUE (course_id, source_file, chunk_index)
    );

    CREATE INDEX IF NOT EXISTS idx_chunks_course_status
    ON chunks(course_id, status);

    CREATE INDEX IF NOT EXISTS idx_chunks_course_order
    ON chunks(course_id, source_file, chunk_index);
    """)

print("Course note engine initialized.")
print(f"Database: {DB_PATH}")
print(f"Course folders: {COURSES_DIR}")
print(f"Output folders: {OUTPUT_DIR}")
print("Chunk ledger is ready.")
