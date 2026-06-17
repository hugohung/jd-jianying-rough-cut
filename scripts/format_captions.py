#!/usr/bin/env python3
"""
format_captions.py — SRT 解析 + 长句拆分 + cutcli JSON 格式化

用法:
  python format_captions.py <srt_file> [--max-chars 12] [--script script.txt]

输入:
  SRT 文件（whisper.cpp 输出），可选剧本文件用于文本校正

输出:
  标准输出的 captions JSON 数组，可直接用于 cutcli captions add --captions '...'
"""

import json
import re
import sys
import os


def parse_srt(srt_path):
    """Parse an SRT file into a list of {text, start_us, end_us} dicts."""
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()

    segments = []
    # Pattern: index, timestamp, text
    pattern = re.compile(
        r"(\d+)\s*\n"
        r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*"
        r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*\n"
        r"([\s\S]*?)(?=\n\d+\n|\Z)",
        re.MULTILINE,
    )

    for match in pattern.finditer(content):
        idx = match.group(1)
        sh, sm, ss, sms = map(int, match.group(2, 3, 4, 5))
        eh, em, es, ems = map(int, match.group(6, 7, 8, 9))
        text = match.group(10).strip().replace("\n", "")

        start_us = (sh * 3600 + sm * 60 + ss) * 1_000_000 + sms * 1000
        end_us = (eh * 3600 + em * 60 + es) * 1_000_000 + ems * 1000

        if text:
            segments.append({"text": text, "start_us": start_us, "end_us": end_us})

    return segments


def count_chinese_chars(text):
    """Count Chinese characters (and Chinese punctuation) in text."""
    count = 0
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff" or "\u3000" <= ch <= "\u303f" or "\uff00" <= ch <= "\uffef":
            count += 1
        elif "\u3400" <= ch <= "\u4dbf":  # CJK Extension A
            count += 1
    return count


def split_long_caption(segment, max_chars=12):
    """Split a caption segment into two if it exceeds max_chars Chinese characters.

    Returns list of 1 or 2 segment dicts.
    """
    text = segment["text"]
    char_count = count_chinese_chars(text)
    total_chars = len(text)

    if char_count <= max_chars or total_chars <= 3:
        return [segment]

    # Find best split point
    # Priority: Chinese punctuation (。！？；，、), then space, then midpoint
    split_punct = "。！？；，、"
    mid = total_chars // 2
    best_split = mid

    # Look for punctuation near the middle (±40% of text length)
    search_start = max(1, total_chars // 3)
    search_end = min(total_chars - 1, total_chars * 2 // 3)
    for punct in split_punct:
        # Search from middle outward
        for offset in range(max(search_start - mid, -mid),
                           min(search_end - mid, total_chars - mid) + 1):
            pos = mid + offset
            if 0 < pos < total_chars and text[pos - 1] == punct:
                best_split = pos
                break
        if best_split != mid:
            break

    part1 = text[:best_split].strip()
    part2 = text[best_split:].strip()

    if not part1 or not part2:
        return [segment]

    duration_us = segment["end_us"] - segment["start_us"]
    overlap_us = 200_000  # 200ms overlap

    seg1 = {
        "text": part1,
        "start_us": segment["start_us"],
        "end_us": segment["start_us"] + duration_us // 2 + overlap_us // 2,
    }
    seg2 = {
        "text": part2,
        "start_us": segment["start_us"] + duration_us // 2 - overlap_us // 2,
        "end_us": segment["end_us"],
    }

    return [seg1, seg2]


def get_font_size_for_text(text):
    """Determine font size based on text length. Shorter text = bigger.

    Used for cutcli captions font-size (6-14 range in Jianying).
    """
    cn_chars = count_chinese_chars(text)
    total = len(text)

    if cn_chars <= 3:
        return 10
    elif cn_chars <= 6:
        return 9
    else:
        return 8


def get_anim_durations(text):
    """Return (in_dur, out_dur) in microseconds based on text length."""
    cn_chars = count_chinese_chars(text)
    if cn_chars <= 4:
        return 300_000, 200_000  # short
    else:
        return 500_000, 300_000  # long


def format_for_cutcli(segments, max_chars=12):
    """Convert segments to cutcli captions JSON array format."""
    captions = []
    for seg in segments:
        text = seg["text"]
        in_dur, out_dur = get_anim_durations(text)
        font_size = get_font_size_for_text(text)

        caption = {
            "text": text,
            "start": seg["start_us"],
            "end": seg["end_us"],
            "fontSize": font_size,
            "inAnimation": "渐显",
            "outAnimation": "渐隐",
            "inAnimationDuration": in_dur,
            "outAnimationDuration": out_dur,
        }
        captions.append(caption)
    return captions


def load_reference_texts(ref_path):
    """Load reference texts from a JSON file (script_extractor.py output).
    
    Returns list of reference dialog/voiceover strings for fuzzy matching.
    """
    with open(ref_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    refs = []
    for voice in data.get("voiceover", []):
        if voice:
            refs.append(voice)
    return refs


def correct_with_reference(segments, ref_texts):
    """Correct whisper transcription using script reference texts.
    
    For each segment, find the closest matching reference text.
    """
    import string as _string

    for seg in segments:
        text = seg["text"]
        # Normalize for comparison
        clean = "".join(ch for ch in text if ch not in _string.punctuation + " ")

        best = text
        best_score = 0
        for ref in ref_texts:
            clean_ref = "".join(ch for ch in ref if ch not in _string.punctuation + " ")
            common = sum(1 for a, b in zip(clean, clean_ref) if a == b)
            score = common / max(len(clean), 1)
            if score > best_score and score > 0.4:
                best_score = score
                best = ref

        if best != text:
            seg["text"] = best
            seg["_corrected"] = True

    return segments


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Parse SRT and format captions for cutcli"
    )
    parser.add_argument("srt_file", help="Whisper output SRT file")
    parser.add_argument("--max-chars", type=int, default=12,
                        help="Max Chinese chars before splitting (default: 12)")
    parser.add_argument("--script-ref", default=None,
                        help="script_extractor.py JSON output for text correction")
    parser.add_argument("--no-split", action="store_true",
                        help="Disable long caption splitting")
    args = parser.parse_args()

    srt_path = args.srt_file
    max_chars = args.max_chars

    if not os.path.exists(srt_path):
        print(json.dumps({"error": f"SRT not found: {srt_path}"}, ensure_ascii=False))
        sys.exit(1)

    # Load reference texts if provided
    ref_texts = None
    if args.script_ref:
        if os.path.exists(args.script_ref):
            ref_texts = load_reference_texts(args.script_ref)
        else:
            print(f"# Warning: --script-ref file not found: {args.script_ref}", file=sys.stderr)

    # Parse SRT
    raw_segments = parse_srt(srt_path)

    # Correct with script reference if available
    if ref_texts:
        raw_segments = correct_with_reference(raw_segments, ref_texts)

    # Split long captions (unless disabled)
    all_segments = []
    if args.no_split:
        all_segments = raw_segments
    else:
        for seg in raw_segments:
            split = split_long_caption(seg, max_chars=max_chars)
            all_segments.extend(split)
    all_segments = []
    for seg in raw_segments:
        split = split_long_caption(seg, max_chars=max_chars)
        all_segments.extend(split)

    # Format for cutcli
    captions = format_for_cutcli(all_segments, max_chars=max_chars)

    # Output JSON array
    print(json.dumps(captions, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
