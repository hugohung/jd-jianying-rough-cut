# cutcli 命令速查

## 环境变量

```bash
export CUT_DRAFTS_DIR="C:/Users/honghaoxiang/AppData/Local/JianyingPro/User Data/Projects/com.lveditor.draft"
```

## 常用命令

### 创建草稿

```bash
cutcli.exe draft create --width 1920 --height 1080 --name "草稿名"
```

### 添加字幕

```bash
cutcli.exe captions add "草稿名" \
  --captions '[{"text":"字幕1","start":0,"end":3000000,...}]' \
  --font-size 8 \
  --text-color "#FFFFFF" \
  --border-color "#000000" \
  --border-width 2 \
  --bold \
  --transform-y -0.85
```

### 添加视频

```bash
cutcli.exe videos add "草稿名" \
  --video-infos '[
    {"videoUrl":"D:/path/video.mp4","width":1920,"height":1080,"duration":3000000,
     "start":0,"end":3000000,"transition":"叠化","transitionDuration":200000}
  ]'
```

### 添加音频

```bash
cutcli.exe audios add "草稿名" \
  --audio-infos '[{"audioUrl":"D:/path/bgm.wav","duration":189330000,"start":4040000,"end":16110000,"volume":0.3}]'
```

## 时间单位

所有 `start`/`end`/`duration` 字段使用**微秒(μs)**：
- 1 秒 = 1,000,000 μs
- 100ms = 100,000 μs

## 动画类型

| 名称 | 值 |
|------|-----|
| 渐显 | `"渐显"` |
| 渐隐 | `"渐隐"` |
| 波浪弹入 | `"波浪弹入"` |
| 轻微放大 | `"轻微放大"` |
| 冲刺急停 | `"冲刺急停"` |

## 转场类型

| 名称 | 值 |
|------|-----|
| 叠化 | `"叠化"` |
| 闪白 | `"闪白"` |
| 模糊 | `"模糊"` |

## 重要约束

1. **操作顺序**：必须先 `captions add` 再 `videos add`，否则 `draft_content.json` 会被编码为二进制
2. **字幕样式**：统一使用 `--border-color "#000000" --border-width 2 --bold --transform-y -0.85`
3. **字体大小**：6-14 范围，短字幕(≤3字)用 10，中等(≤6字)用 9，长字幕用 8
