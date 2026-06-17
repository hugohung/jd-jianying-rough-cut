#!/usr/bin/env python3
"""
media_prep.py — 视频素材分析 + 音频提取拼接

用法:
  python media_prep.py <output_dir> <video1> <video2> ...

输出:
  <output_dir>/meta.json     — 素材元数据（时长、分辨率、累积偏移）
  <output_dir>/full.wav      — 拼接后的 16kHz mono 音频
"""

import json
import subprocess
import sys
import os
import re


def find_ffmpeg():
    """Locate ffmpeg binary from imageio_ffmpeg."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return None


def ffprobe(video_path, ffmpeg_bin):
    """Extract duration (seconds) and resolution from a video file."""
    result = subprocess.run(
        [ffmpeg_bin, "-i", video_path],
        capture_output=True, text=True, errors="replace"
    )
    stderr = result.stderr

    duration = None
    width = None
    height = None
    fps = None

    dur_match = re.search(r"Duration: (\d+):(\d+):(\d+)\.(\d+)", stderr)
    if dur_match:
        h, m, s, cs = map(int, dur_match.groups())
        duration = h * 3600 + m * 60 + s + cs / 100.0

    vid_match = re.search(r"Stream #0:0.*Video:.* (\d+)x(\d+)", stderr)
    if vid_match:
        width = int(vid_match.group(1))
        height = int(vid_match.group(2))

    fps_match = re.search(r"(\d+\.?\d*) fps", stderr)
    if fps_match:
        fps = float(fps_match.group(1))

    return {
        "path": os.path.abspath(video_path),
        "name": os.path.basename(video_path),
        "duration_s": duration,
        "width": width,
        "height": height,
        "fps": fps,
    }


def extract_audio(video_path, output_wav, ffmpeg_bin, sample_rate=16000):
    """Extract audio as 16kHz mono WAV."""
    subprocess.run(
        [
            ffmpeg_bin, "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", str(sample_rate), "-ac", "1",
            output_wav,
        ],
        capture_output=True, text=True, errors="replace",
    )
    return os.path.exists(output_wav) and os.path.getsize(output_wav) > 0


def concat_wavs(wav_paths, output_wav, ffmpeg_bin):
    """Concatenate multiple WAV files into one."""
    concat_file = output_wav + ".concat.txt"
    with open(concat_file, "w") as f:
        for p in wav_paths:
            f.write(f"file '{p}'\n")

    subprocess.run(
        [ffmpeg_bin, "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
         "-c", "copy", output_wav],
        capture_output=True, text=True, errors="replace",
    )
    return os.path.exists(output_wav) and os.path.getsize(output_wav) > 0


def main():
    if len(sys.argv) < 3:
        print("Usage: python media_prep.py <output_dir> <video1> <video2> ...")
        sys.exit(1)

    out_dir = os.path.abspath(sys.argv[1])
    video_paths = sys.argv[2:]

    ffmpeg = find_ffmpeg()
    if not ffmpeg or not os.path.exists(ffmpeg):
        print(json.dumps({"error": "FFmpeg not found"}, ensure_ascii=False))
        sys.exit(1)

    os.makedirs(out_dir, exist_ok=True)

    # Step 1: FFprobe all videos
    meta_list = []
    for vp in video_paths:
        if not os.path.exists(vp):
            print(json.dumps({"error": f"Video not found: {vp}"}, ensure_ascii=False))
            sys.exit(1)
        info = ffprobe(vp, ffmpeg)
        if info["duration_s"] is None:
            print(json.dumps({"error": f"Could not read duration: {vp}"}, ensure_ascii=False))
            sys.exit(1)
        meta_list.append(info)

    # Step 2: Calculate cumulative offsets (in microseconds)
    cumulative_us = 0
    for i, m in enumerate(meta_list):
        m["start_us"] = cumulative_us
        m["end_us"] = cumulative_us + int(m["duration_s"] * 1_000_000)
        m["duration_us"] = int(m["duration_s"] * 1_000_000)
        # Transition: 200ms (not applied to last clip)
        if i < len(meta_list) - 1:
            cumulative_us += int((m["duration_s"] - 0.1) * 1_000_000)  # overlap 0.1s for dissolve
        else:
            cumulative_us += m["duration_us"]

    total_duration_us = sum(m["duration_us"] for m in meta_list)
    # Actual timeline accounts for overlap
    if len(meta_list) > 1:
        total_timeline_us = meta_list[-1]["end_us"]
    else:
        total_timeline_us = total_duration_us

    # Step 3: Extract audio from each video
    wav_paths = []
    for i, m in enumerate(meta_list):
        wav_path = os.path.join(out_dir, f"seg_{i}.wav")
        if extract_audio(m["path"], wav_path, ffmpeg):
            wav_paths.append(wav_path)

    # Step 4: Concatenate WAVs
    full_wav = os.path.join(out_dir, "full.wav")
    concat_success = False
    if wav_paths:
        concat_success = concat_wavs(wav_paths, full_wav, ffmpeg)

    # Step 5: Write metadata
    meta = {
        "output_dir": out_dir,
        "full_audio": full_wav if concat_success else None,
        "total_duration_s": total_timeline_us / 1_000_000,
        "clip_count": len(meta_list),
        "clips": meta_list,
    }

    meta_path = os.path.join(out_dir, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(json.dumps({"status": "ok", "meta": meta_path}, ensure_ascii=False))


if __name__ == "__main__":
    main()
