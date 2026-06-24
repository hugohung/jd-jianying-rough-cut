---
name: jd-jianying-rough-cut
version: "1.0.0"
description: >-
  剪映自动粗剪助手。将视频素材按剧本顺序拼入剪映草稿，自动添加叠化转场、
  底部白字黑描边字幕（渐显渐隐动画），长句自动分段。
  触发词：粗剪、rough cut、剪映粗剪、自动剪辑、加字幕、拼视频。
agent_created: true
author: honghaoxiang
---

# 剪映粗剪 (Jianying Rough Cut)

自动将视频素材按剧本顺序创建剪映草稿，含叠化转场和 AI 语音识别字幕。

## 环境准备（检测优先，按需安装）

执行 skill 时先排查本地环境，已有则复用，缺失才下载。所有操作幂等。

### 0. 检测总入口（一条命令判断缺什么）

```bash
# 先跑这个，看输出就知道缺哪些
echo "=== cutcli ===" && (command -v cutcli 2>/dev/null && cutcli --version || echo "MISSING")
echo "=== ffmpeg ===" && (command -v ffmpeg 2>/dev/null && ffmpeg -version 2>&1 | head -1 || echo "MISSING")
echo "=== python ===" && (python3 --version 2>/dev/null || python --version 2>/dev/null || echo "MISSING")
echo "=== whisper.cpp ===" && (command -v whisper-cli 2>/dev/null && whisper-cli --version 2>/dev/null | head -1 || echo "MISSING")
```

### 1. Python + FFmpeg

**检测逻辑**：
- 先查 `python3` / `python`，再查 WorkBuddy 托管路径
- 先查 `ffmpeg` 命令，不存在则用 `pip install imageio-ffmpeg`

```bash
# 找 Python（优先级：系统 PATH → WorkBuddy 托管 → 报错退出）
if command -v python3 &>/dev/null; then
  PYTHON=$(command -v python3)
elif command -v python &>/dev/null; then
  PYTHON=$(command -v python)
elif [ -f "C:/Users/$USER/.workbuddy/binaries/python/versions/3.13.12/python.exe" ]; then
  PYTHON="C:/Users/$USER/.workbuddy/binaries/python/versions/3.13.12/python.exe"
else
  echo "ERROR: 未找到 Python，请安装 Python 3.10+"
  exit 1
fi

# 验证 FFmpeg（系统已有直接复用，没有则装 imageio_ffmpeg）
if ! command -v ffmpeg &>/dev/null; then
  "$PYTHON" -m pip install imageio-ffmpeg -q
  FFMPEG=$("$PYTHON" -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())")
else
  FFMPEG=$(command -v ffmpeg)
fi
echo "Python: $PYTHON | FFmpeg: $FFMPEG"
```

### 2. cutcli

**检测逻辑**：PATH 搜 `cutcli` → 搜 WorkBuddy 路径 → 搜 workspace → 下载

```bash
# 找 cutcli
CUTCLI=""
for candidate in "cutcli" "$HOME/.workbuddy/bin/cutcli.exe" "./cutcli.exe"; do
  if command -v "$candidate" &>/dev/null || [ -f "$candidate" ]; then
    CUTCLI="$candidate"
    break
  fi
done

# 没有就下载
if [ -z "$CUTCLI" ]; then
  mkdir -p "$HOME/.workbuddy/bin"
  curl -fsSL "https://cutcli.com/releases/bin/latest/cut_cli_windows_amd64.exe" \
    -o "$HOME/.workbuddy/bin/cutcli.exe"
  CUTCLI="$HOME/.workbuddy/bin/cutcli.exe"
fi

"$CUTCLI" --version
```

**重要**：每次调用 cutcli 必须设置草稿目录环境变量：
```bash
# Windows 剪映草稿目录（注意是 lveditor 不是 liveditor）
export CUT_DRAFTS_DIR="$LOCALAPPDATA/JianyingPro/User Data/Projects/com.lveditor.draft"

# Mac 剪映草稿目录
# export CUT_DRAFTS_DIR="$HOME/Movies/CapCut/User Data/Projects/com.lveditor.draft"
```

### 3. whisper.cpp

**检测逻辑**：PATH 搜 `whisper-cli` → TEMP 缓存 → 下载

```bash
# 找 whisper-cli
WHISPER_EXE=""
if command -v whisper-cli &>/dev/null; then
  WHISPER_EXE=$(command -v whisper-cli)
elif [ -f "$TEMP/whisper-cpp/Release/whisper-cli.exe" ]; then
  WHISPER_EXE="$TEMP/whisper-cpp/Release/whisper-cli.exe"
fi

# 没有就下载（~4.4MB）
if [ -z "$WHISPER_EXE" ]; then
  WHISPER_TEMP="$TEMP/whisper-cpp"
  curl -fsSL "https://github.com/ggerganov/whisper.cpp/releases/download/v1.8.7/whisper-bin-x64.zip" \
    -o "$WHISPER_TEMP.zip"
  unzip -o "$WHISPER_TEMP.zip" -d "$WHISPER_TEMP"
  WHISPER_EXE="$WHISPER_TEMP/Release/whisper-cli.exe"
fi

# 模型（~148MB）：优先查 whisper.cpp 默认路径，再查 TEMP
WHISPER_MODEL=""
for candidate in \
  "$WHISPER_EXE/../models/ggml-base.bin" \
  "$TEMP/whisper-cpp/Release/ggml-base.bin" \
  "./ggml-base.bin"; do
  # normalize path
  candidate_dir=$(dirname "$WHISPER_EXE")
  candidate_path="$candidate_dir/../models/ggml-base.bin"
  if [ -f "$candidate_path" ]; then
    WHISPER_MODEL="$candidate_path"
    break
  fi
done

# 兜底：搜 TEMP
if [ -z "$WHISPER_MODEL" ] && [ -f "$TEMP/whisper-cpp/Release/ggml-base.bin" ]; then
  WHISPER_MODEL="$TEMP/whisper-cpp/Release/ggml-base.bin"
fi

# 实在没有才下载（~148MB）
if [ -z "$WHISPER_MODEL" ]; then
  MODEL_DIR=$(dirname "$WHISPER_EXE")
  curl -fsSL "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin" \
    -o "$MODEL_DIR/ggml-base.bin"
  WHISPER_MODEL="$MODEL_DIR/ggml-base.bin"
fi

echo "whisper: $WHISPER_EXE | model: $WHISPER_MODEL"
```

### 4. 环境变量汇总（检测完成后导出）

```bash
# 以下变量由上述检测步骤填充，后续流程直接引用
export PYTHON           # Python 路径
export FFMPEG           # FFmpeg 路径
export CUTCLI           # cutcli 路径
export CUT_DRAFTS_DIR   # 剪映草稿目录
export WHISPER_EXE      # whisper-cli 路径
export WHISPER_MODEL    # 模型路径
```

### 5. 快速自检

```bash
echo "--- 环境自检 ---"
"$PYTHON" --version && echo "Python OK" || echo "Python FAIL"
"$FFMPEG" -version 2>&1 | head -1 && echo "FFmpeg OK" || echo "FFmpeg FAIL"
"$CUTCLI" --version && echo "cutcli OK" || echo "cutcli FAIL"
"$WHISPER_EXE" --version && echo "whisper OK" || echo "whisper FAIL"
[ -f "$WHISPER_MODEL" ] && echo "whisper model OK ($(ls -lh "$WHISPER_MODEL" | awk '{print $5}'))" || echo "whisper model MISSING"
```

### 下载量预估

| 工具 | 大小 | 何时触发 |
|------|------|----------|
| cutcli | ~88 MB | PATH 中找不到时 |
| whisper.cpp 程序 | ~4.4 MB | PATH 中找不到时 |
| whisper base 模型 | ~148 MB | 本地无模型文件时 |
| imageio_ffmpeg | ~88 MB | 系统无 ffmpeg 时 |
| **最坏情况合计** | **~328 MB** | 全缺 |
| **最佳情况** | **0 MB** | 全部已有 |

---

## 能力范围

1. 读取视频素材目录，FFprobe 获取每段时长和分辨率
2. **前序剧本检测**：自动扫描目录，判断前序沟通是否使用了 `jd-ai-short-drama-helper`（Skill 1）或 `jd-ai-short-drama-libtv`（Skill 2）；检测到则提取剧本场景顺序和台词文本，用于素材排序参考和字幕校正
3. 按用户指定的剧本顺序排列素材（有剧本则参考场景顺序），计算累积时间偏移
4. 素材间自动添加 0.2s 叠化转场
5. 提取音频 → whisper.cpp 语音识别 → 生成精准字幕时间戳
6. 有剧本参考时，自动用剧本台词校正 Whisper 识别结果
7. 长字幕（超过 12 个中文字符）自动拆分为两段，按时长比例分配时间
8. 所有字幕统一：底部位置（`--transform-y -0.85`）、白字黑描边（`--border-color "#000000" --border-width 2`）、渐显渐隐动画

**不包含**：BGM、音效、滤镜、特效。后续由用户在剪映中手动添加。

## 工作流程

### 输入

用户提供：
- 视频素材目录路径
- 视频素材的排列顺序（可选；未指定时按文件名排序；有剧本则按场景顺序自动匹配）
- 剧本/字幕文本（可选，有则用于校正 Whisper 识别结果；也可通过前序检测自动获取）

### 步骤

#### Step 0: 前序剧本检测

在执行粗剪前，先检测前序沟通是否使用了 AI 短剧 Skill。

**检测逻辑**：

```bash
# 运行检测脚本，返回 JSON
# {source: "skill1_markdown"|"skill2_libtv"|null, scenes: [...], voiceover: [...]}
python scripts/script_extractor.py <视频素材所在目录> [--skill2-project-id UUID]
```

**检测范围**：
- 扫描当前目录及子目录，寻找 Skill 1 产出的 Markdown 剧本文件（含 `【剧名】`、`【视频开场】`、`【序幕` 等标记）
- 如果用户提供了 LibTV 项目 UUID，检测 Skill 2 产出的分镜信息

**检测到剧本时的行为**：
| 信息 | 用途 |
|------|------|
| `scenes[].name` + `scenes[].order` | 参考场景顺序，用于视频素材排序（尝试匹配素材文件名与场景名） |
| `voiceover[]` | 传入 `format_captions.py --script-ref`，校正 Whisper 识别结果 |

**未检测到时**：正常按文件名排序，仅用 Whisper 结果生成字幕。

#### Step 1: 分析视频素材

对每个视频文件运行 FFprobe 获取时长和分辨率：

```bash
ffmpeg -i <video> 2>&1  # 解析 Duration, Stream 行
```

计算累积偏移，确定每个素材在时间轴上的起止位置（单位：微秒 μs）。

输出素材清单：文件名、时长(s)、累积起始时间(μs)、分辨率。

#### Step 2: 提取音频并语音识别

见 `scripts/media_prep.py` — 提取各视频音轨为 16kHz mono WAV，拼接为完整音频。

下载/确认 whisper.cpp 可用：

```bash
# 若不存在则下载
curl -fsSL "https://github.com/ggerganov/whisper.cpp/releases/download/v1.8.7/whisper-bin-x64.zip" \
  -o "%TEMP%/whisper-cpp.zip"
unzip -o whisper-cpp.zip -d %TEMP%/whisper-cpp

# 若不存在则下载 base 模型（支持中文）
curl -fsSL "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin" \
  -o "%TEMP%/whisper-cpp/Release/ggml-base.bin"
```

运行识别：

```bash
whisper-cli.exe -m ggml-base.bin -f full.wav -l zh -osrt -of output
```

#### Step 3: 格式化字幕

见 `scripts/format_captions.py` — 解析 SRT 文件，处理逻辑：

1. **文本校正**（有剧本时）：加载 Step 0 检测到的剧本台词，对 Whisper 识别结果做模糊匹配校正，替换同音错字
2. **长句分段**：中文字符数 > 12 时，优先在标点符号处拆分（。！？；，、），无合适断点则在中间位置分段。两段按原时长的 50/50 比例分配，重叠 200ms
3. **输出格式**：cutcli `captions add` 所需的 JSON 数组

```bash
# 基本用法（无剧本）
python scripts/format_captions.py output.srt --max-chars 12

# 带剧本参考（Step 0 检测到时）
python scripts/format_captions.py output.srt --max-chars 12 \
  --script-ref <script_extractor_output.json>
```

#### Step 4: 创建剪映草稿

**关键约束：必须先加字幕，后加视频。** 加视频后 cutcli 可能将 `draft_content.json` 编码为二进制，导致后续字幕操作失败。

```bash
# 1. 创建草稿（1080p）
CUT_DRAFTS_DIR="..." cutcli.exe draft create --width 1920 --height 1080 --name "草稿名"

# 2. 添加字幕（批量，全部渐显渐隐 + 底部白字黑描边）
CUT_DRAFTS_DIR="..." cutcli.exe captions add "草稿名" \
  --captions '<JSON_ARRAY>' \
  --font-size 8 --text-color "#FFFFFF" \
  --border-color "#000000" --border-width 2 \
  --bold --transform-y -0.85

# 3. 添加视频素材（叠化 200ms）
CUT_DRAFTS_DIR="..." cutcli.exe videos add "草稿名" \
  --video-infos '<JSON_ARRAY>'
```

#### Step 5: 验证

确认草稿目录存在且 `draft_content.json` 为有效 JSON（非二进制）。

### 输出

草稿名格式：`{剧本简称}_粗剪`，位于剪映标准草稿目录。

告知用户：
- 可忽略的旧草稿（如有）
- 字幕时间轴概览表
- 需要用户在剪映中手动补充的内容（BGM/音效）

## 字幕动画规格（固定）

所有字幕使用统一的渐显渐隐动画：

| 参数 | 值 |
|------|------|
| inAnimation | `"渐显"` |
| outAnimation | `"渐隐"` |
| inAnimationDuration | 300000 (短句) / 500000 (长句) |
| outAnimationDuration | 200000 (短句) / 300000 (长句) |

短句标准：≤ 4 个中文字符；长句标准：> 4 个中文字符。

## 注意事项

- **cutcli 操作顺序**：必须先字幕后视频，否则 `draft_content.json` 会变成二进制编码
- **环境变量**：每次调用 cutcli 需设置 `CUT_DRAFTS_DIR`
- **时间单位**：cutcli 使用微秒(μs)，1秒 = 1,000,000
- **路径**：所有文件路径使用正斜杠 `/`
- **Whisper 模型**：base 模型中文识别准确率已足够，无需下载 larger 模型
