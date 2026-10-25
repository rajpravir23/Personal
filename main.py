# -*- coding: utf-8 -*-
"""
Udemy Note Taker - Main Orchestrator

Workflow:
1. Record lecture audio until Ctrl+C.
2. Transcribe the newest recording.
3. Initialize the note engine.
4. Import transcript into timestamped chunks and SQLite.
5. Generate Markdown notes using local Ollama.

Save this file as:
C:\\Users\\rajpr\\UdemyNoteTaker\\main.py
"""

import runpy
import traceback
import time
import sys
from pathlib import Path


BASE_DIR = Path.home() / "UdemyNoteTaker"
# Ensure the sibling scripts can be imported even if Spyder uses another working directory.
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
RECORDINGS_DIR = BASE_DIR / "recordings"
TRANSCRIPTS_DIR = BASE_DIR / "transcripts"

# Update these two values for each course.
COURSE_ID = "prompt_engineering"
COURSE_NAME = "Prompt Engineering"


def latest_file(folder, pattern, newer_than=None):
    """Return the newest matching file, optionally created after a timestamp."""
    files = [
        path for path in folder.glob(pattern)
        if path.is_file()
        and (newer_than is None or path.stat().st_mtime >= newer_than)
    ]
    return max(files, key=lambda path: path.stat().st_mtime) if files else None


def main():
    print("=" * 68)
    print("UDEMY NOTE TAKER - FULL WORKFLOW")
    print("=" * 68)
    print(f"Project folder: {BASE_DIR}")
    print(f"Course: {COURSE_NAME} ({COURSE_ID})")
    print()
    print("Workflow: Record -> Transcribe -> Import -> Generate notes")
    print("When recording, press Ctrl+C in this Spyder console to stop.")
    print()

    BASE_DIR.mkdir(parents=True, exist_ok=True)
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    recording_started_at = time.time()

    # 1. Record. test_audio.py catches Ctrl+C, saves the WAV, and returns.
    # print("\n[1/5] Starting audio recording...")
    # try:
    #     import test_audio
    #     test_audio.main()
    # except KeyboardInterrupt:
    #     print("\nRecording interrupted. Continuing to the next step...")
    # except Exception:
    #     print("\nRecording failed. Workflow stopped.")
    #     traceback.print_exc()
    #     return

    # recording = latest_file(
    #     RECORDINGS_DIR, "*.wav", newer_than=recording_started_at - 2
    # )
    # if recording is None:
    #     print(f"\nNo new WAV recording found in: {RECORDINGS_DIR}")
    #     print("Workflow stopped; no transcription was attempted.")
    #     return

    # print(f"\nRecording selected: {recording}")

    # 2. Transcribe the new WAV. This module loads the known-good OpenMP DLL
    # before importing faster-whisper.
    print("\n[2/5] Transcribing audio...")
    try:
        import transcribe_audio
        transcript_path = transcribe_audio.transcribe_lecture(recording)
    except Exception:
        print("\nTranscription failed. Workflow stopped.")
        traceback.print_exc()
        return

    if not transcript_path or not Path(transcript_path).is_file():
        print("\nTranscription did not produce a transcript file.")
        print("Workflow stopped.")
        return

    transcript_path = Path(transcript_path)
    print(f"Transcript ready: {transcript_path}")

    # 3. Initialize folders and SQLite ledger.
    print("\n[3/5] Initializing note engine...")
    try:
        setup_script = BASE_DIR / "setup_note_engine.py"
        if not setup_script.is_file():
            raise FileNotFoundError(f"Setup script not found: {setup_script}")
        runpy.run_path(str(setup_script), run_name="note_engine_setup")
    except Exception:
        print("\nNote engine setup failed. Workflow stopped.")
        traceback.print_exc()
        return

    # 4. Import transcript into timestamped chunks and SQLite.
    print("\n[4/5] Importing transcript into the course ledger...")
    try:
        import import_transcripts
        chunk_count = import_transcripts.import_transcript(
            transcript_path,
            COURSE_ID,
            COURSE_NAME,
        )
        if not chunk_count:
            print("No chunks were created. Workflow stopped.")
            return
    except Exception:
        print("\nTranscript import failed. Workflow stopped.")
        traceback.print_exc()
        return

    # 5. Generate notes with local Ollama.
    print("\n[5/5] Generating notes with local Ollama...")
    try:
        import process_chunks
        process_chunks.COURSE_ID = COURSE_ID
        process_chunks.main()
    except Exception:
        print("\nNote generation failed.")
        traceback.print_exc()
        return

    print("\n" + "=" * 68)
    print("WORKFLOW FINISHED")
    print(f"Recording:   {recording}")
    print(f"Transcript:  {transcript_path}")
    print(f"Notes folder: {BASE_DIR / 'note_engine' / 'outputs' / COURSE_ID}")
    print("=" * 68)


if __name__ == "__main__":
    main()
