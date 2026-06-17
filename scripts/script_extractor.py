#!/usr/bin/env python3
"""
script_extractor.py — 从 Skill 1/2 产出中提取剧本结构信息

支持两种输入：
  1. Skill 1（jd-ai-short-drama-helper）产出的 Markdown 剧本文档
  2. Skill 2（jd-ai-short-drama-libtv）产出的 LibTV 分镜信息

输出 JSON：
{
  "source": "skill1_markdown" | "skill2_libtv" | null,
  "scenes": [{"name": "镜头1", "order": 1, "dialog": ["台词..."]}, ...],
  "voiceover": ["所有旁白/对白文本的列表"],
  "script_path": "原始文件路径"
}

用法：
  python script_extractor.py <file_or_dir> [--skill2-project-id UUID]

检测策略：
  - 先检查命令行参数是否指定了剧本路径
  - 再检查当前目录及子目录是否有 .md 剧本文件
  - 最后检查是否有 LibTV 项目目录
"""

import json
import os
import re
import sys


def detect_skill1_script(base_dir="."):
    """Detect Skill 1 Markdown script files in directory.
    
    Skill 1 output format contains sections like:
      【剧名】：xxx
      【视频开场】
      【序幕 - XXX】
      【第一幕 - XXX】
      旁白：...
      台词（角色）：...
    
    Returns list of matching file paths.
    """
    candidates = []
    patterns = [
        "*.md",           # 剧本通常为 Markdown
        "剧本*.md",
        "*剧本*.md",
        "*脚本*.md",
    ]

    for pattern in patterns:
        import glob
        for f in glob.glob(os.path.join(base_dir, pattern), recursive=False):
            if os.path.isfile(f):
                candidates.append(f)

    # Also search one level deep
    try:
        for item in os.listdir(base_dir):
            item_path = os.path.join(base_dir, item)
            if os.path.isdir(item_path):
                for pattern in patterns:
                    import glob as g2
                    for f in g2.glob(os.path.join(item_path, pattern), recursive=False):
                        if os.path.isfile(f):
                            candidates.append(f)
    except PermissionError:
        pass

    # Filter: file must contain Skill 1 markers
    validated = []
    for f in candidates:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                content = fh.read()
            # Check for key Skill 1 markers
            markers = ["【剧名】", "【视频开场】", "节奏地图", "【序幕"]
            score = sum(1 for m in markers if m in content)
            if score >= 2:
                validated.append(f)
        except Exception:
            pass

    return validated


def parse_skill1_markdown(file_path):
    """Parse Skill 1 Markdown to extract scenes and dialog.
    
    Returns dict with scenes and voiceover lists.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    scenes = []
    all_dialog = []

    # Split by act markers: 【视频开场】, 【序幕】, 【第X幕】
    act_pattern = re.compile(
        r"(?:【(视频开场|序幕[^】]*|第[一二三四五六七八九十\d]+幕[^】]*)】)",
        re.MULTILINE,
    )

    parts = act_pattern.split(content)
    # parts alternates: [marker1, content1, marker2, content2, ...]
    # First element (before first marker) is preamble

    scene_order = 0
    for i in range(1, len(parts), 2):
        marker = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""

        # Extract dialog/voiceover lines from this scene
        dialogs = []
        # Patterns:
        #   旁白（声音描述）："文本"
        #   旁白："文本"
        #   台词（角色）："文本"
        #   [角色名]："文本"
        dialog_patterns = [
            r'旁白[（(][^)）]*[)）]?[：:]\s*["""]([^"""]+)["""]',
            r'台词[（(][^)）]*[)）]?[：:]\s*["""]([^"""]+)["""]',
            r'[（(][^)）]*声音[)）]?[：:]\s*["""]([^"""]+)["""]',
            r'[：:]\s*["""]([^"""]{2,50})["""]',  # generic quoted text
        ]

        for pattern in dialog_patterns:
            matches = re.findall(pattern, body)
            for m in matches:
                m = m.strip()
                if m and len(m) >= 2:
                    dialogs.append(m)
                    all_dialog.append(m)

        # Deduplicate while preserving order
        seen = set()
        dialogs_unique = []
        for d in dialogs:
            if d not in seen:
                seen.add(d)
                dialogs_unique.append(d)

        scenes.append({
            "name": marker,
            "order": scene_order,
            "dialog": dialogs_unique,
        })
        all_dialog.extend(dialogs_unique)
        scene_order += 1

    # Deduplicate voiceover list
    seen_all = set()
    voiceover_unique = []
    for v in all_dialog:
        if v not in seen_all:
            seen_all.add(v)
            voiceover_unique.append(v)

    return {
        "source": "skill1_markdown",
        "scenes": scenes,
        "voiceover": voiceover_unique,
        "script_path": file_path,
    }


def detect_skill2_libtv(base_dir=".", project_id=None):
    """Detect Skill 2 LibTV storyboard output.
    
    Looks for LibTV project directories or storyboard JSON files.
    """
    # If project_id provided, construct expected path
    if project_id:
        libtv_home = os.path.join(os.path.expanduser("~"), ".libtv")
        project_dir = os.path.join(libtv_home, "projects", project_id)
        if os.path.isdir(project_dir):
            return project_dir

    # Search for .libtv directories
    candidates = []
    try:
        for item in os.listdir(base_dir):
            item_path = os.path.join(base_dir, item)
            if os.path.isdir(item_path) and item.startswith(".libtv"):
                candidates.append(item_path)
    except PermissionError:
        pass

    return candidates[0] if candidates else None


def find_closest_script(text, candidates):
    """Find the closest matching script text from candidates.
    
    Uses simple substring matching with tolerance for whisper errors.
    """
    if not text or not candidates:
        return text

    # Exact match
    for c in candidates:
        if c in text:
            return text
        if text in c:
            return c  # return the longer, cleaner version

    # Fuzzy: remove punctuation and compare
    import string as _string
    clean_text = "".join(ch for ch in text if ch not in _string.punctuation + " ")
    best_match = text
    best_score = 0

    for c in candidates:
        clean_c = "".join(ch for ch in c if ch not in _string.punctuation + " ")
        # Count common characters
        common = sum(1 for a, b in zip(clean_text, clean_c) if a == b)
        score = common / max(len(clean_text), 1) if clean_text else 0
        if score > best_score and score > 0.5:
            best_score = score
            best_match = c

    return best_match


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract script structure from Skill 1/2 outputs"
    )
    parser.add_argument("path", nargs="?", default=".",
                        help="File path (Skill 1 .md) or directory to search")
    parser.add_argument("--skill2-project-id", default=None,
                        help="LibTV project UUID (for Skill 2 detection)")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON only (no extra text)")
    args = parser.parse_args()

    result = None
    target = args.path

    # If path is a file, try parsing directly
    if os.path.isfile(target) and target.endswith(".md"):
        result = parse_skill1_markdown(target)

    # If path is a directory, search for Skill 1 scripts
    elif os.path.isdir(target):
        scripts = detect_skill1_script(target)
        if scripts:
            # Use the first matching script
            result = parse_skill1_markdown(scripts[0])
        else:
            # Try Skill 2 detection
            libtv_dir = detect_skill2_libtv(target, args.skill2_project_id)
            if libtv_dir:
                result = {
                    "source": "skill2_libtv",
                    "libtv_dir": libtv_dir,
                    "scenes": [],
                    "voiceover": [],
                    "script_path": libtv_dir,
                    "note": "LibTV project detected. Full storyboard parsing requires libtv CLI.",
                }

    if result is None:
        result = {
            "source": None,
            "scenes": [],
            "voiceover": [],
            "script_path": None,
            "note": "No Skill 1/2 output detected. Will use filename order + Whisper only.",
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
