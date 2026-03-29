#!/usr/bin/env python3
"""
Explainer Utilities - 公共工具函数

包含：
1. 音频工具：获取音频时长（带缓存）、从 audio_info.json 读取总时长
2. 路径工具：查找项目根目录、解析场景编号、查找分镜脚本
3. 时间工具：格式化时间、解析 SRT 时间
4. 文件工具：原子写入文本/JSON

使用：
    from utils import get_audio_duration, format_time, atomic_write_json
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# 模块级音频时长缓存：cache_key = "绝对路径:mtime" -> duration(秒)
_audio_duration_cache: Dict[str, float] = {}


def get_audio_duration(audio_path: Union[str, Path]) -> Optional[float]:
    """
    获取音频文件时长（秒）

    尝试使用以下方法（按优先级）：
    1. mutagen（支持多种格式）
    2. wave（仅支持wav）
    3. ffprobe（需要ffmpeg）

    Args:
        audio_path: 音频文件路径

    Returns:
        float: 时长（秒），失败返回 None
    """
    audio_path = Path(audio_path)

    if not audio_path.exists():
        return None

    # 尝试 mutagen
    try:
        from mutagen.mp3 import MP3
        audio = MP3(audio_path)
        return audio.info.length
    except Exception:
        pass

    try:
        from mutagen.wave import WAVE
        audio = WAVE(audio_path)
        return audio.info.length
    except Exception:
        pass

    try:
        from mutagen.wavpack import WavPack
        audio = WavPack(audio_path)
        return audio.info.length
    except Exception:
        pass

    # 尝试 wave 模块（仅wav）
    try:
        import wave
        with wave.open(str(audio_path), 'rb') as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / float(rate)
    except Exception:
        pass

    # 尝试 ffprobe
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', str(audio_path)],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception:
        pass

    return None


def get_audio_duration_cached(audio_path: Union[str, Path]) -> Optional[float]:
    """
    带缓存的音频时长获取

    缓存键为 (绝对路径:mtime)，文件修改后自动失效。

    Args:
        audio_path: 音频文件路径

    Returns:
        float: 时长（秒），失败返回 None
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        return None

    mtime = audio_path.stat().st_mtime
    cache_key = f"{audio_path.resolve()}:{mtime}"

    if cache_key in _audio_duration_cache:
        return _audio_duration_cache[cache_key]

    duration = get_audio_duration(audio_path)
    if duration is not None:
        _audio_duration_cache[cache_key] = duration

    return duration


def get_total_audio_duration_from_info(audio_dir: Union[str, Path]) -> Optional[float]:
    """
    从 audio_info.json 获取总时长

    Args:
        audio_dir: 音频目录路径（包含 audio_info.json）

    Returns:
        float: 总时长（秒），文件不存在返回 None
    """
    info_file = Path(audio_dir) / "audio_info.json"
    if not info_file.exists():
        return None
    data = json.loads(info_file.read_text(encoding="utf-8"))
    total = data.get("total_duration")
    if total is not None:
        return float(total)
    return float(sum(f.get("duration", 0) for f in data.get("files", [])))


def extract_scene_number(filename: str) -> int:
    """
    从文件名提取幕号

    支持格式:
    - audio_001_xxx.wav
    - scene_01_xxx.wav
    - 001_xxx.wav

    Args:
        filename: 文件名

    Returns:
        int: 幕号，未找到返回 0
    """
    # 匹配数字序列
    match = re.search(r'\d+', filename)
    if match:
        return int(match.group())
    return 0


def format_time(seconds: float, format_type: str = "srt") -> str:
    """
    格式化时间为字符串

    Args:
        seconds: 秒数
        format_type: 格式类型
            "srt"        → 00:00:05,000
            "human"      → 1:23
            "minutes"    → 1.4m
            "underscore" → 1_23（用于文件名）

    Returns:
        str: 格式化后的时间字符串
    """
    if format_type == "srt":
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    elif format_type == "human":
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"

    elif format_type == "minutes":
        return f"{seconds / 60:.1f}m"

    elif format_type == "underscore":
        # 用于文件名：1_23
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}_{secs:02d}"

    else:
        return str(seconds)


def parse_srt_time(time_str: str) -> float:
    """
    解析 SRT 时间格式

    Args:
        time_str: SRT 时间字符串 (如 "00:01:23,456")

    Returns:
        float: 秒数
    """
    time_str = time_str.replace(',', '.')
    parts = time_str.split(':')

    hours = float(parts[0])
    minutes = float(parts[1])
    seconds = float(parts[2])

    return hours * 3600 + minutes * 60 + seconds


def find_project_root(start_path: Union[str, Path] = ".") -> Optional[Path]:
    """
    从指定路径向上查找项目根目录

    项目根目录标识：
    - 包含 CLAUDE.md 或 _content_info.json
    - 或包含 audio/ 目录

    Args:
        start_path: 起始路径

    Returns:
        Path: 项目根目录，未找到返回 None
    """
    current = Path(start_path).resolve()

    # 向上查找最多5层
    for _ in range(5):
        if (current / "CLAUDE.md").exists():
            return current
        if (current / "_content_info.json").exists():
            return current
        if (current / "audio").is_dir():
            return current
        if (current / "segment_pipeline.json").exists():
            return current

        parent = current.parent
        if parent == current:  # 到达根目录
            break
        current = parent

    return None


def sanitize_filename(name: str) -> str:
    """
    清理文件名，移除非法字符

    Args:
        name: 原始文件名

    Returns:
        str: 清理后的文件名
    """
    # 移除或替换非法字符
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = name.strip('. ')
    return name


def truncate_text(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """
    截断文本到指定长度

    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 截断后缀

    Returns:
        str: 截断后的文本
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


# 颜色工具
def hex_to_rgb(hex_color: str) -> tuple:
    """
    将 HEX 颜色转换为 RGB 元组

    Args:
        hex_color: 如 "#1a1a2e"

    Returns:
        tuple: (r, g, b)
    """
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))


def rgb_to_hex(rgb: tuple) -> str:
    """
    将 RGB 元组转换为 HEX 颜色

    Args:
        rgb: (r, g, b) 每个值 0-1

    Returns:
        str: HEX 颜色代码
    """
    return '#{:02x}{:02x}{:02x}'.format(
        int(rgb[0] * 255),
        int(rgb[1] * 255),
        int(rgb[2] * 255)
    )


def find_storyboard(project_dir: Union[str, Path]) -> Optional[Path]:
    """
    查找分镜脚本文件

    按优先级搜索：分镜脚本.md > storyboard.md > 分镜.md

    Args:
        project_dir: 项目目录路径

    Returns:
        Path: 分镜脚本路径，未找到返回 None
    """
    project_dir = Path(project_dir)
    for candidate in [
        project_dir / "分镜脚本.md",
        project_dir / "storyboard.md",
        project_dir / "分镜.md",
    ]:
        if candidate.exists():
            return candidate
    return None


def atomic_write_text(
    file_path: Union[str, Path],
    content: str,
    encoding: str = "utf-8",
) -> None:
    """
    原子写入文本文件（先写 .tmp 再 rename，防止写入中途崩溃导致文件损坏）

    Args:
        file_path: 目标文件路径
        content: 文件内容
        encoding: 编码（默认 utf-8）
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        dir=file_path.parent,
        suffix=".tmp",
        prefix=f".{file_path.name}.",
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
        os.replace(tmp_path, str(file_path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise


def atomic_write_json(
    file_path: Union[str, Path],
    data: Any,
    encoding: str = "utf-8",
) -> None:
    """
    原子写入 JSON 文件

    Args:
        file_path: 目标文件路径
        data: 可 JSON 序列化的对象
        encoding: 编码（默认 utf-8）
    """
    content = json.dumps(data, ensure_ascii=False, indent=2)
    atomic_write_text(file_path, content, encoding)


if __name__ == "__main__":
    # 简单测试
    print("Testing utils...")

    # 测试时间格式化
    print(f"format_time(65.5, 'human') = {format_time(65.5, 'human')}")
    print(f"format_time(65.5, 'srt') = {format_time(65.5, 'srt')}")

    # 测试解析 SRT 时间
    print(f"parse_srt_time('00:01:05,500') = {parse_srt_time('00:01:05,500')}")

    # 测试提取场景号
    print(f"extract_scene_number('audio_001_开场.wav') = {extract_scene_number('audio_001_开场.wav')}")

    # 测试清理文件名
    print(f"sanitize_filename('hello/world: test') = {sanitize_filename('hello/world: test')}")

    print("All tests passed!")
