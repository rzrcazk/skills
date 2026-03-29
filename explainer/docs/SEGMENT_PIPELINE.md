# 分段流水线架构说明

## 概述

分段流水线（Segment Pipeline）是一种增量视频生成架构，将长视频拆分为约15-20秒的小段，每段生成后让用户确认，通过后再继续下一段。

## 核心优势

1. **早发现问题**：不用等到最后才知道有问题
2. **精确定位**：用户可以说"第3段画面有问题"
3. **降低返工**：只需修复有问题的小段
4. **断点续传**：关闭 Claude Code 后能从断点继续

## 文件结构

```
{内容目录}/
├── segments/                    # 分段工作目录
│   ├── seg_001_0_00-0_18/      # 第1段：0:00-0:18
│   │   ├── video.mp4           # 渲染输出
│   │   ├── audio.wav           # 合并后的音频
│   │   ├── subtitle.srt        # 字幕文件
│   │   ├── scenes.json         # 本分镜包含的scenes
│   │   └── metadata.json       # 时长、状态等元数据
│   ├── seg_002_0_18-0_35/
│   └── ...
├── merged/                      # 累积合并结果
│   ├── merged_001_0_00-0_18.mp4
│   ├── merged_002_0_00-0_35.mp4
│   └── merged_003_0_00-0_52.mp4
├── segment_pipeline.json        # 流水线状态（断点续传关键）
└── workflow_state.json          # 原有状态
```

## segment_pipeline.json 结构

```json
{
  "content_id": "勾股定理",
  "content_path": "数学/几何/勾股定理",
  "total_scenes": 10,
  "total_duration": 180,
  "target_segment_duration": 20,
  "segments": [
    {
      "id": "seg_001",
      "index": 0,
      "time_range": "0:00-0:18",
      "start_time": 0,
      "end_time": 18,
      "scenes": [0, 1, 2],
      "status": "confirmed",
      "video_path": "segments/seg_001_0_00-0_18/video.mp4",
      "audio_path": "segments/seg_001_0_00-0_18/audio.wav",
      "subtitle_path": "segments/seg_001_0_00-0_18/subtitle.srt",
      "metadata_path": "segments/seg_001_0_00-0_18/metadata.json",
      "confirmed_at": "2026-03-08T10:30:00",
      "issues": []
    }
  ],
  "current_segment_index": 2,
  "merged_up_to_index": 1,
  "final_video_path": null,
  "created_at": "2026-03-08T10:00:00",
  "updated_at": "2026-03-08T10:35:00"
}
```

### 状态说明

| 状态 | 说明 |
|------|------|
| `pending` | 等待生成 |
| `generating` | 正在生成（TTS/渲染中） |
| `generated` | 已生成，等待用户确认 |
| `confirmed` | 用户已确认 |
| `rejected` | 用户拒绝，需要修复 |
| `fixing` | 正在修复 |

## 工作流程

### 1. 初始化流水线

```bash
python segment_generator.py --project . --init
```

读取 `分镜脚本.md` 和 `audio_info.json`，将scenes分组到各段。

### 2. 生成分段

```bash
# 生成指定段
python segment_generator.py --project . --segment 0

# 或生成下一段
python segment_generator.py --project . --next
```

### 3. 播放并确认

```bash
python segment_player.py --project . --segment 0
```

播放视频，询问用户确认。

### 4. 合并已确认段

```bash
python segment_merger.py --project . --upto 1
```

将 seg_001 和 seg_002 合并为 merged_002_0_00-0_35.mp4

### 5. 断点续传

重新启动时自动读取 `segment_pipeline.json`，找到第一个非 confirmed 的段继续。

## 分段策略

### 分组算法

1. 读取所有scenes的时长
2. 累积scene时长，当超过 `target_segment_duration` (默认20秒) 时，开启新段
3. 单个scene如果超过20秒，单独成段

### 示例

```
Scenes: [0:05, 0:08, 0:06, 0:12, 0:15, 0:10]

Segments:
- seg_001: scenes [0, 1, 2] = 0:05 + 0:08 + 0:06 = 0:19
- seg_002: scenes [3] = 0:12 (单独成段，接近20秒)
- seg_003: scenes [4, 5] = 0:15 + 0:10 = 0:25 (超过20秒，但scene 4,5 关联性强)
```

## 错误处理

### 用户反馈问题类型

| 类型 | 处理方式 |
|------|----------|
| `video` | 修改Manim代码，重新渲染本段 |
| `audio` | 重新生成TTS，替换音频 |
| `subtitle` | 修改字幕文件 |
| `timing` | 调整动画时长与音频匹配 |

### 修复流程

```python
# 1. 用户指出问题
issues = [
  {"type": "video", "description": "三角形颜色太淡"},
  {"type": "subtitle", "description": "第二行字幕有错字"}
]

# 2. 更新状态
segment["status"] = "fixing"
segment["issues"] = issues

# 3. 针对性修复
if "video" in issue_types:
    fix_manim_code(segment)
    re_render(segment)

if "audio" in issue_types:
    regenerate_tts(segment)

if "subtitle" in issue_types:
    fix_subtitle(segment)

# 4. 重新确认
segment["status"] = "generated"
play_and_confirm(segment)
```

## 预生成策略

使用 subagent 后台预生成下一段：

```python
import subprocess

# 当前正在确认段 N
# 后台启动 subagent 生成段 N+1
subprocess.Popen([
    "python", "segment_generator.py",
    "--project", project_dir,
    "--segment", str(current_index + 1),
    "--background"
])
```

## 集成到主工作流

### 修改后的 workflow_state.json

```json
{
  "current_step": "segment_pipeline",
  "segment_pipeline": {
    "enabled": true,
    "pipeline_file": "segment_pipeline.json",
    "current_segment": 2,
    "total_segments": 5
  }
}
```

### 主流程调用

```python
# 在生成完 TTS 后，进入分段流水线
def run_segment_pipeline(project_dir):
    # 1. 初始化或恢复流水线
    pipeline = load_or_init_pipeline(project_dir)

    # 2. 找到当前段
    current = pipeline.get_current_segment()

    # 3. 如果不是 generated，先生成
    if current["status"] == "pending":
        generate_segment(current)

    # 4. 播放并确认
    result = play_and_confirm(current)

    # 5. 根据用户反馈处理
    if result["confirmed"]:
        merge_up_to(current["index"])
        # 后台预生成下一段
        preload_next_segment(current["index"] + 1)
    else:
        fix_segment(current, result["issues"])

    # 6. 保存状态
    pipeline.save()
```

## 命令行工具

### segment_generator.py

```bash
# 初始化流水线
python segment_generator.py --project <dir> --init

# 生成指定段
python segment_generator.py --project <dir> --segment <index>

# 生成下一段
python segment_generator.py --project <dir> --next

# 后台生成（用于预加载）
python segment_generator.py --project <dir> --segment <index> --background

# 强制重新生成
python segment_generator.py --project <dir> --segment <index> --force

# 指定分镜脚本
python segment_generator.py --project <dir> --storyboard <path>
```

### segment_merger.py

```bash
# 合并到指定段
python segment_merger.py --project <dir> --upto <index>

# 合并全部（生成最终视频）
python segment_merger.py --project <dir> --final

# 指定输出文件名
python segment_merger.py --project <dir> --final --output final.mp4
```

### segment_player.py

```bash
# 播放并交互确认
python segment_player.py --project <dir> --segment <index>

# 仅播放
python segment_player.py --project <dir> --segment <index> --play-only

# 自动模式（用于测试）
python segment_player.py --project <dir> --segment <index> --auto-confirm
```

## 注意事项

1. **Manim 分段渲染**：需要修改脚手架，支持只渲染指定范围的scenes
2. **音频合并**：使用 ffmpeg concat 合并各段音频
3. **字幕时间戳**：合并时需要调整各段字幕的时间偏移
4. **视频播放器**：macOS 用 `open`，Linux 用 `xdg-open` 或 `ffplay`
5. **并发安全**：后台预生成时要注意文件锁，避免冲突
