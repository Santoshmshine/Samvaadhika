import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.pipeline import (
    _atempo_filter,
    mux_translated_video,
    probe_media_duration,
    synthesize_timed_speech,
)


def test_atempo_filter_keeps_each_factor_in_supported_range():
    factors = [float(item.split("=")[1]) for item in _atempo_filter(8.5).split(",")]

    assert all(0.5 <= factor <= 2.0 for factor in factors)
    assert np.prod(factors) == pytest.approx(8.5, rel=1e-5)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg is required")
def test_synthesize_timed_speech_places_and_fits_segments(tmp_path):
    sample_rate = 8000

    def fake_synthesizer(text, language, output_path):
        duration = 0.8 if text == "first" else 0.2
        time = np.arange(round(duration * sample_rate)) / sample_rate
        sf.write(output_path, 0.2 * np.sin(2 * np.pi * 440 * time), sample_rate)
        return True

    output_path = tmp_path / "timed.wav"
    synthesize_timed_speech(
        [
            {"start": 0.5, "end": 1.0, "text": "first"},
            {"start": 1.5, "end": 2.0, "text": "second"},
        ],
        "en",
        output_path,
        total_duration=2.5,
        synthesizer=fake_synthesizer,
        sample_rate=sample_rate,
    )

    audio, actual_rate = sf.read(output_path)
    assert actual_rate == sample_rate
    assert len(audio) == round(2.5 * sample_rate)
    assert np.max(np.abs(audio[:round(0.5 * sample_rate)])) == 0
    assert np.max(np.abs(audio[round(0.55 * sample_rate):round(0.95 * sample_rate)])) > 0.05
    assert np.max(np.abs(audio[round(1.05 * sample_rate):round(1.5 * sample_rate)])) == 0
    assert np.max(np.abs(audio[round(1.55 * sample_rate):round(1.95 * sample_rate)])) > 0.05
    assert np.max(np.abs(audio[round(2.0 * sample_rate):])) == 0


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="ffmpeg and ffprobe are required",
)
def test_mux_translated_video_contains_video_audio_and_subtitles(tmp_path):
    video_path = tmp_path / "input.mp4"
    audio_path = tmp_path / "dub.wav"
    subtitle_path = tmp_path / "translated.srt"
    output_path = tmp_path / "translated.mp4"

    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=3:r=25",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video_path),
        ],
        check=True,
        capture_output=True,
    )
    sample_rate = 44100
    time = np.arange(3 * sample_rate) / sample_rate
    sf.write(audio_path, 0.15 * np.sin(2 * np.pi * 440 * time), sample_rate)
    subtitle_path.write_text(
        "1\n00:00:00,500 --> 00:00:01,500\nनमस्ते दुनिया\n",
        encoding="utf-8",
    )

    mux_translated_video(video_path, audio_path, subtitle_path, output_path, "hi")
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(output_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    codecs = {
        (stream["codec_type"], stream["codec_name"])
        for stream in json.loads(result.stdout)["streams"]
    }

    assert ("video", "h264") in codecs
    assert ("audio", "aac") in codecs
    assert ("subtitle", "mov_text") in codecs
    assert probe_media_duration(output_path) == pytest.approx(3.0, abs=0.1)