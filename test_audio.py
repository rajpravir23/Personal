
import wave
import threading
from datetime import datetime
from pathlib import Path

import pyaudiowpatch as pyaudio

OUTPUT_DIR = Path(__file__).resolve().parent / "recordings"
OUTPUT_DIR.mkdir(exist_ok=True)

CHUNK_SIZE = 4096
stop_event = threading.Event()


def main():
    p = pyaudio.PyAudio()
    stream = None

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f"lecture_{stamp}.wav"

    try:
        wasapi = p.get_host_api_info_by_type(
            pyaudio.paWASAPI
        )
        output = p.get_device_info_by_index(
            wasapi["defaultOutputDevice"]
        )

        device = next(
            (
                d for d in p.get_loopback_device_info_generator()
                if output["name"] in d["name"]
            ),
            None,
        )

        if device is None:
            raise RuntimeError("Loopback device not found.")

        rate = int(device["defaultSampleRate"])
        channels = min(2, int(device["maxInputChannels"]))

        print("Recording:", device["name"])
        print("Press Ctrl+C in THIS terminal to stop.")
        print("Recording will be saved when stopped.")

        with wave.open(str(output_file), "wb") as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(2)
            wav.setframerate(rate)

            stream = p.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=device["index"],
                frames_per_buffer=CHUNK_SIZE,
            )

            try:
                while not stop_event.is_set():
                    data = stream.read(
                        CHUNK_SIZE,
                        exception_on_overflow=False,
                    )
                    wav.writeframes(data)

            except KeyboardInterrupt:
                print("\nStop requested. Saving recording...")

    except KeyboardInterrupt:
        print("\nStop requested.")

    finally:
        if stream is not None:
            try:
                stream.stop_stream()
            except Exception:
                pass
            stream.close()

        p.terminate()

    print("Recording saved:", output_file)


if __name__ == "__main__":
    main()
