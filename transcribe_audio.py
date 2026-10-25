import os
import ctypes

os.environ.pop("KMP_DUPLICATE_LIB_OK", None)

omp_handle = ctypes.WinDLL(
    r"D:\Programs\Library\bin\libiomp5md.dll"
)

from pathlib import Path
from faster_whisper import WhisperModel

# Load the working OpenMP runtime before initializing Whisper
os.environ.pop("KMP_DUPLICATE_LIB_OK", None)

omp_handle = ctypes.WinDLL(
    r"D:\Programs\Library\bin\libiomp5md.dll"
)

BASE = Path.home() / "UdemyNoteTaker"
RECORDINGS = BASE / "recordings"
TRANSCRIPTS = BASE / "transcripts"

TRANSCRIPTS.mkdir(parents=True, exist_ok=True)


def transcribe_lecture(audio_path):
    audio_path = Path(audio_path)

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    print(f"Audio: {audio_path}", flush=True)
    print("Loading Whisper model...", flush=True)

    model = WhisperModel(
        "base",
        device="cpu",
        compute_type="int8"
    )

    output_file = TRANSCRIPTS / f"{audio_path.stem}.txt"

    print("Transcribing...", flush=True)

    segments, info = model.transcribe(
        str(audio_path),
        beam_size=1,
        vad_filter=False
    )

    with output_file.open("w", encoding="utf-8") as f:
        f.write(f"Language: {info.language}\n\n")

        for segment in segments:
            line = (
                f"[{segment.start:.1f}s - "
                f"{segment.end:.1f}s] {segment.text}"
            )
            print(line, flush=True)
            f.write(line + "\n")

    print(f"\nTranscription saved to: {output_file}", flush=True)
    return output_file


if __name__ == "__main__":
    recordings = sorted(
        RECORDINGS.glob("*.wav"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not recordings:
        print(f"No WAV recordings found in: {RECORDINGS}")
    else:
        transcribe_lecture(recordings[0])
