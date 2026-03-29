#!/usr/bin/env python3
"""
SRT 字幕生成脚本

从 audio_info.json 读取场景文本和时长，生成 SRT 字幕文件。
生成的 SRT 文件可导入剪映进行字幕编辑和样式调整。

使用方法:
    python3 scripts/generate_srt.py [audio_dir] [--output path.srt] [--gap 0.5]

参数:
    audio_dir:      音频目录（含 audio_info.json），默认 ./audio
    --output:       输出文件路径，默认 ./subtitles.srt
    --gap:          每幕开始前的过渡间隔（秒），默认 0.5
    --end-buffer:   每幕字幕提前消失的时间（秒），默认 0.2
    --max-chars:    每行最大字符数，默认 25

时间戳计算说明:
    字幕时间戳基于累积音频时长，而非视频实际帧时间。
    由于 Manim 场景可能包含额外的动画等待时间，字幕在视频中
    可能略有偏差，但与语音内容精确对齐。可在剪映中手动微调。
"""

import json
import sys
import argparse
from pathlib import Path


def load_audio_info(audio_dir: Path) -> list:
    """从 audio_info.json 读取场景信息，按 scene 编号排序。"""
    info_file = audio_dir / 'audio_info.json'
    if not info_file.exists():
        raise FileNotFoundError(f'audio_info.json 不存在: {info_file}')

    with open(info_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    files = data.get('files', [])
    if not files:
        raise ValueError('audio_info.json 中 files 列表为空')

    valid = []
    skipped = 0
    for entry in files:
        scene = entry.get('scene')
        text = entry.get('text', '').strip().strip('"').strip()
        duration = entry.get('duration')

        if scene is None:
            skipped += 1
            continue
        if duration is None:
            print(f'警告: 幕 {scene} 缺少 duration，已跳过', file=sys.stderr)
            skipped += 1
            continue
        if not text:
            print(f'警告: 幕 {scene} 文本为空，已跳过', file=sys.stderr)
            skipped += 1
            continue

        valid.append({**entry, 'scene': scene, 'text': text, 'duration': float(duration)})

    if skipped:
        print(f'共跳过 {skipped} 条无效记录', file=sys.stderr)

    return sorted(valid, key=lambda e: e['scene'])


def calculate_timestamps(entries: list, gap: float = 0.5, end_buffer: float = 0.2) -> list:
    """计算每条字幕的开始/结束时间戳（纯函数，返回新列表）。"""
    result = []
    t = 0.0

    for entry in entries:
        duration = entry['duration']
        srt_start = t + gap
        srt_end = t + gap + duration - end_buffer

        if srt_end <= srt_start:
            srt_end = srt_start + max(duration, 0.5)

        result.append({**entry, 'srt_start': srt_start, 'srt_end': srt_end})
        t += gap + duration

    return result


def format_srt_time(seconds: float) -> str:
    """将秒数转换为 SRT 时间格式 HH:MM:SS,mmm。"""
    total_ms = round(seconds * 1000)
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


def wrap_text(text: str, max_chars: int = 25) -> list:
    """将中文文本按标点或字数分割为最多 2 行。"""
    if len(text) <= max_chars:
        return [text]

    split_chars = '。！？；，、：'
    best_pos = -1
    for i, ch in enumerate(text):
        if ch in split_chars and i < max_chars:
            best_pos = i + 1

    if best_pos > 0:
        return [text[:best_pos], text[best_pos:].strip()]

    return [text[:max_chars], text[max_chars:].strip()]


def build_srt_content(entries_with_timestamps: list, max_chars: int = 25) -> str:
    """将带时间戳的条目组装成完整 SRT 字符串。"""
    blocks = []
    for idx, entry in enumerate(entries_with_timestamps, start=1):
        start = format_srt_time(entry['srt_start'])
        end = format_srt_time(entry['srt_end'])
        lines = wrap_text(entry['text'], max_chars)
        text_content = '\n'.join(line for line in lines if line)
        blocks.append(f'{idx}\n{start} --> {end}\n{text_content}')

    return '\n\n'.join(blocks) + '\n'


def generate_srt(audio_dir: Path, output_path: Path,
                 gap: float = 0.5, end_buffer: float = 0.2,
                 max_chars: int = 25) -> Path:
    """主编排函数：读取 audio_info.json -> 计算时间戳 -> 写入 SRT 文件。"""
    entries = load_audio_info(audio_dir)
    entries_with_ts = calculate_timestamps(entries, gap, end_buffer)
    content = build_srt_content(entries_with_ts, max_chars)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return output_path


def main():
    parser = argparse.ArgumentParser(description='从 audio_info.json 生成 SRT 字幕文件')
    parser.add_argument('audio_dir', nargs='?', default='audio',
                        help='音频目录路径（含 audio_info.json），默认 ./audio')
    parser.add_argument('--output', '-o', default=None,
                        help='输出 SRT 文件路径，默认 ./subtitles.srt')
    parser.add_argument('--gap', type=float, default=0.5,
                        help='每幕开始前的过渡间隔（秒），默认 0.5')
    parser.add_argument('--end-buffer', type=float, default=0.2,
                        help='每幕字幕提前消失的时间（秒），默认 0.2')
    parser.add_argument('--max-chars', type=int, default=25,
                        help='每行最大字符数，默认 25')
    args = parser.parse_args()

    audio_dir = Path(args.audio_dir).resolve()
    output_path = Path(args.output).resolve() if args.output else Path('subtitles.srt').resolve()

    try:
        result = generate_srt(audio_dir, output_path, args.gap, args.end_buffer, args.max_chars)
        print(f'SRT 文件已生成: {result}')
    except FileNotFoundError as e:
        print(f'错误: {e}', file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f'错误: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
