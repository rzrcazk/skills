# 分段流水线快速开始指南

## 概述

分段流水线（Segment Pipeline）将长视频拆分为约15-20秒的小段，逐段生成、确认、合并，支持断点续传。

## 安装

确保已安装依赖：

```bash
# 检查依赖
python3 explainer/scripts/segment_pipeline.py --help
```

## 快速开始

### 1. 初始化项目

假设你已有：
- `分镜脚本.md` - 分镜脚本
- `audio/` - TTS 音频文件
- `audio/audio_info.json` - 音频信息

```bash
cd your-project/

# 初始化流水线（自动拆分分镜为段）
python3 ../explainer/scripts/segment_pipeline.py --project . --init

# 查看分段结果
python3 ../explainer/scripts/segment_pipeline.py --project . --list
```

### 2. 运行分段流水线

```bash
# 启动完整流水线
python3 ../explainer/scripts/run_segment_pipeline.py --project .
```

流程：
1. 生成分段视频
2. 播放给用户确认
3. 用户选择：✅确认 / 📝提出问题
4. 确认后合并到累积视频
5. 后台预生成下一段
6. 继续下一段...

### 3. 断点续传

如果中途关闭 Claude Code：

```bash
# 恢复进度继续
python3 ../explainer/scripts/run_segment_pipeline.py --project . --resume
```

### 4. 查看状态

```bash
# 查看当前进度
python3 ../explainer/scripts/run_segment_pipeline.py --project . --status
```

## 详细命令

### 分段流水线管理

```bash
# 初始化（默认20秒/段）
python3 explainer/scripts/segment_pipeline.py -p . --init

# 初始化（15秒/段）
python3 explainer/scripts/segment_pipeline.py -p . --init -t 15

# 列出所有段
python3 explainer/scripts/segment_pipeline.py -p . --list

# 查看进度
python3 explainer/scripts/segment_pipeline.py -p . --progress
```

### 分段生成

```bash
# 生成指定段
python3 explainer/scripts/segment_generator.py -p . -s 0

# 生成下一段
python3 explainer/scripts/segment_generator.py -p . --next

# 强制重新生成
python3 explainer/scripts/segment_generator.py -p . -s 0 -f

# 查看段信息
python3 explainer/scripts/segment_generator.py -p . --info 0
```

### 分段播放与确认

```bash
# 播放并交互确认
python3 explainer/scripts/segment_player.py -p . -s 0 --update-status

# 仅播放
python3 explainer/scripts/segment_player.py -p . -s 0 --play-only

# 自动确认（测试用）
python3 explainer/scripts/segment_player.py -p . -s 0 --auto-confirm --update-status
```

### 分段合并

```bash
# 合并到指定段（0到N）
python3 explainer/scripts/segment_merger.py -p . -u 2

# 合并全部（生成最终视频）
python3 explainer/scripts/segment_merger.py -p . --final

# 指定输出文件名
python3 explainer/scripts/segment_merger.py -p . --final -o my_video.mp4

# 查看合并信息
python3 explainer/scripts/segment_merger.py -p . --info
```

### 主控脚本

```bash
# 完整流程（推荐）
python3 explainer/scripts/run_segment_pipeline.py -p .

# 指定段时长
python3 explainer/scripts/run_segment_pipeline.py -p . -t 15

# 从指定段开始
python3 explainer/scripts/run_segment_pipeline.py -p . -s 2

# 断点续传
python3 explainer/scripts/run_segment_pipeline.py -p . --resume

# 自动确认模式（测试）
python3 explainer/scripts/run_segment_pipeline.py -p . --auto-confirm

# 禁用预加载
python3 explainer/scripts/run_segment_pipeline.py -p . --no-preload
```

## 工作流程示例

```
用户: 我想做一个勾股定理的科普视频

AI: 好的，我们先确认分镜...
[生成分镜脚本和 TTS]

AI: 现在启动分段流水线，逐段制作视频。

# 初始化
python3 scripts/segment_pipeline.py -p . --init

# 运行流水线
python3 scripts/run_segment_pipeline.py -p .

[生成第1段 0:00-0:18]
[播放视频给用户]

用户: 这个三角形颜色太淡了

AI: 收到，我调整颜色后重新生成第1段。

[修复问题]
[重新生成第1段]
[播放视频]

用户: 没问题了

AI: 好的，确认第1段，现在生成第2段。

[确认第1段]
[后台预生成第2段]
[生成第2段 0:18-0:35]
[播放视频]

用户: ✅ 没问题

AI: 确认第2段，已合并 0:00-0:35。

...继续直到完成...

AI: 所有段已确认，生成最终视频！
[生成 final_video.mp4]
```

## 目录结构

```
your-project/
├── 分镜脚本.md
├── script.py                    # Manim 脚本
├── audio/                       # TTS 音频
│   ├── audio_000_开场.wav
│   └── audio_info.json
├── segments/                    # 分段输出
│   ├── seg_001_0_00-0_18/
│   │   ├── video.mp4
│   │   ├── audio.wav
│   │   ├── subtitle.srt
│   │   └── metadata.json
│   ├── seg_002_0_18-0_35/
│   └── ...
├── merged/                      # 累积合并
│   ├── merged_001_0_00-0_18.mp4
│   ├── merged_002_0_00-0_35.mp4
│   └── ...
├── output/                      # 最终输出
│   └── 勾股定理_final.mp4
├── segment_pipeline.json        # 流水线状态
└── workflow_state.json          # 工作流状态
```

## 状态说明

| 状态 | 说明 |
|------|------|
| `pending` | 等待生成 |
| `generating` | 正在生成 |
| `generated` | 已生成，等待确认 |
| `confirmed` | 用户已确认 |
| `rejected` | 用户拒绝，需要修复 |
| `fixing` | 正在修复 |

## 故障排除

### 问题：段生成失败

```bash
# 检查音频是否存在
ls audio/

# 强制重新生成
python3 scripts/segment_generator.py -p . -s 0 -f
```

### 问题：无法播放视频

```bash
# 手动播放
open segments/seg_001_0_00-0_18/video.mp4

# 然后手动更新状态
python3 scripts/segment_pipeline.py -p . -u 0 --status confirmed
```

### 问题：合并失败

```bash
# 检查 ffmpeg 是否安装
ffmpeg -version

# 手动合并
python3 scripts/segment_merger.py -p . -u 2
```

### 问题：流水线状态损坏

```bash
# 删除状态文件重新初始化
rm segment_pipeline.json
python3 scripts/segment_pipeline.py -p . --init
```

## 高级用法

### 自定义分段策略

修改 `segment_pipeline.py` 中的 `DEFAULT_SEGMENT_DURATION`：

```python
DEFAULT_SEGMENT_DURATION = 15  # 15秒/段
```

### 批量自动确认（测试）

```bash
# 自动确认所有段（不播放视频）
for i in {0..5}; do
  python3 scripts/segment_player.py -p . -s $i --auto-confirm --update-status
done
```

### 手动控制流程

```bash
# 1. 生成段0
python3 scripts/segment_generator.py -p . -s 0

# 2. 播放确认
python3 scripts/segment_player.py -p . -s 0 --update-status

# 3. 合并
python3 scripts/segment_merger.py -p . -u 0

# 4. 生成段1
python3 scripts/segment_generator.py -p . --next

# ...重复
```

## 注意事项

1. **Manim 脚本**：使用 `templates/script_scaffold_segment.py` 作为模板，支持分段渲染
2. **音频**：确保 `audio/audio_info.json` 存在且正确
3. **分镜**：分镜脚本使用 `## 幕X` 格式标记各幕
4. **ffmpeg**：合并视频需要 ffmpeg 已安装
5. **断点续传**：定期保存 `segment_pipeline.json` 状态
