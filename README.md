# 剪映自动粗剪 (Jianying Rough Cut)

> Agent Skill — 将视频素材按剧本顺序自动拼入剪映草稿，添加叠化转场和 AI 语音识别字幕

## 功能特性

- 视频素材自动排列并创建剪映草稿（1080p）
- 素材间自动添加 200ms 叠化转场
- Whisper 语音识别生成精准字幕（中文优化，自动长句分段）
- 字幕统一底部白字黑描边 + 渐显渐隐动画
- 前序 AI 短剧 Skill 剧本检测，自动匹配素材顺序并校正字幕同音错字
- 环境检测优先，已有工具零下载复用

## 安装方式

### Agent 用户

1. 下载 [Release zip](../../releases/latest)
2. 在 Agent 客户端的 Skill 管理 → 上传技能，选择 zip 文件

### 从源码安装

```bash
git clone https://github.com/hugohung/workbuddy-skill-jianying-rough-cut.git ~/.workbuddy/skills/jianying-rough-cut
```

## 使用方式

在支持 Skill 的 Agent 对话中直接说：

> "帮我把这段视频粗剪一下，加上字幕和转场"

> "对这段素材做剪映粗剪"

## 依赖说明

| 工具 | 大小 | 说明 |
|------|------|------|
| cutcli | ~88 MB | 剪映草稿 CLI，PATH 中找不到时自动下载 |
| whisper.cpp | ~4.4 MB | 语音识别引擎 |
| whisper base 模型 | ~148 MB | 中文语音识别模型 |
| FFmpeg | ~88 MB | 音频提取，系统已有时复用 |

全部已有则零下载，全缺时最坏情况约 328MB。

## License

MIT License
