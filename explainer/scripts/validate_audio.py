#!/usr/bin/env python3
"""
音频验证脚本

功能：
1. 读取分镜脚本的音频清单部分
2. 验证音频文件存在且时长正常
3. 生成/更新时长信息到JSON
4. 更新分镜脚本的时长列
5. 如果缺少长度或长度异常，报错提醒

使用：
    python validate_audio.py 分镜.md ./audio

输出：
    - 更新后的分镜.md（填充时长列）
    - audio/audio_info.json
"""

import sys
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# 添加脚本目录到路径
sys.path.insert(0, str(Path(__file__).parent))
from utils import get_audio_duration_cached, atomic_write_text, atomic_write_json
from config import CONFIG
from logger import get_logger

logger = get_logger(__name__)


def parse_storyboard(
    storyboard_path: Union[str, Path],
) -> Tuple[List[Dict[str, Any]], str]:
    """
    解析分镜脚本，提取音频清单部分

    Args:
        storyboard_path: 分镜脚本路径

    Returns:
        (audio_list, original_content)
    """
    with open(str(storyboard_path), 'r', encoding='utf-8') as f:
        content = f.read()

    # 查找音频生成清单表格
    # 支持格式：| 幕号 | 文件名 | 读白文本 | 时长 | 说话人 | 情感 |
    pattern = r'##\s*音频生成清单.*?(?=##|$)'
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        logger.warning("未找到音频生成清单部分")
        return [], content

    section = match.group(0)
    lines = section.split('\n')

    audio_list = []
    for line in lines:
        line = line.strip()
        # 匹配表格行
        if line.startswith('|') and not line.startswith('|---'):
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2 and parts[0].isdigit():
                # 解析表格行
                scene_num = int(parts[0])
                filename = parts[1] if len(parts) > 1 else ""
                text = parts[2] if len(parts) > 2 else ""
                duration_str = parts[3] if len(parts) > 3 else ""
                speaker = parts[4] if len(parts) > 4 else "xiaoxiao"
                emotion = parts[5] if len(parts) > 5 else "平和"

                # 解析时长（可能是空字符串或数字）
                duration = None
                if duration_str:
                    try:
                        # 支持格式：8, 8s, 8.5, 8.5s, 8秒
                        duration = float(duration_str.replace('s', '').replace('秒', ''))
                    except ValueError:
                        duration = None

                audio_list.append({
                    'scene': scene_num,
                    'file': filename,
                    'text': text,
                    'duration': duration,
                    'speaker': speaker,
                    'emotion': emotion
                })

    return audio_list, content


def validate_audio_files(
    audio_list: List[Dict[str, Any]],
    audio_dir: Union[str, Path],
) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
    """
    验证音频文件，使用缓存获取时长

    Args:
        audio_list: 音频条目列表
        audio_dir: 音频文件目录

    Returns:
        (valid, errors, updated_list)
    """
    errors: List[str] = []
    updated_list: List[Dict[str, Any]] = []
    valid = True

    for item in audio_list:
        scene_num = item['scene']
        filename = item['file']
        audio_path = os.path.join(str(audio_dir), filename)

        if not os.path.exists(audio_path):
            errors.append(f"错误：第{scene_num}幕音频文件不存在: {filename}")
            valid = False
            updated_list.append(item)
            continue

        actual_duration = get_audio_duration_cached(audio_path)

        if actual_duration is None:
            errors.append(f"错误：第{scene_num}幕音频时长获取失败: {filename}")
            valid = False
            updated_list.append(item)
            continue

        if actual_duration <= 0:
            errors.append(f"错误：第{scene_num}幕音频时长异常({actual_duration:.2f}s): {filename}")
            valid = False
            updated_list.append(item)
            continue

        if actual_duration < CONFIG.audio.min_duration:
            errors.append(f"警告：第{scene_num}幕音频时长过短({actual_duration:.2f}s): {filename}")

        updated_item = {**item, 'duration': round(actual_duration, 2)}
        updated_list.append(updated_item)
        logger.info("第%s幕: %s - %.2fs", scene_num, filename, actual_duration)

    return valid, errors, updated_list


def generate_audio_info_json(
    updated_list: List[Dict[str, Any]],
    audio_dir: Union[str, Path],
) -> str:
    """
    原子写入 audio_info.json

    Args:
        updated_list: 已验证的音频条目列表
        audio_dir: 音频目录

    Returns:
        str: 输出文件路径
    """
    output = {
        'files': updated_list,
        'total_duration': sum(item.get('duration', 0) or 0 for item in updated_list),
        'count': len(updated_list),
    }
    output_path = os.path.join(str(audio_dir), 'audio_info.json')
    atomic_write_json(output_path, output)
    logger.info("已生成: %s", output_path)
    return output_path


def update_storyboard(
    storyboard_path: Union[str, Path],
    original_content: str,
    updated_list: List[Dict[str, Any]],
) -> None:
    """
    原子更新分镜脚本的时长列

    Args:
        storyboard_path: 分镜脚本路径
        original_content: 原始文件内容
        updated_list: 已验证的音频条目列表
    """
    lines = original_content.split('\n')
    new_lines: List[str] = []
    audio_idx = 0
    in_audio_section = False

    for line in lines:
        if '音频生成清单' in line:
            in_audio_section = True

        if in_audio_section and line.startswith('|') and not line.startswith('|---'):
            parts = [p for p in (p.strip() for p in line.split('|')) if p]

            if len(parts) >= 2 and parts[0].isdigit() and audio_idx < len(updated_list):
                scene_num = int(parts[0])
                if scene_num == updated_list[audio_idx]['scene']:
                    duration = updated_list[audio_idx].get('duration')
                    if duration is not None:
                        new_parts = parts[:3]
                        new_parts.append(f"{duration:.1f}")
                        if len(parts) > 4:
                            new_parts.append(parts[4])
                        if len(parts) > 5:
                            new_parts.append(parts[5])
                        line = '| ' + ' | '.join(new_parts) + ' |'
                    audio_idx += 1

        new_lines.append(line)

    atomic_write_text(storyboard_path, '\n'.join(new_lines))
    logger.info("已更新: %s", storyboard_path)


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_audio.py <分镜.md> [audio_dir]")
        print("Example: python validate_audio.py 分镜.md ./audio")
        sys.exit(1)

    storyboard_path = sys.argv[1]
    audio_dir = sys.argv[2] if len(sys.argv) > 2 else "./audio"

    # 检查文件
    if not os.path.exists(storyboard_path):
        print(f"Error: 分镜文件不存在: {storyboard_path}")
        sys.exit(1)

    if not os.path.exists(audio_dir):
        print(f"Error: 音频目录不存在: {audio_dir}")
        sys.exit(1)

    logger.info("解析分镜: %s", storyboard_path)
    logger.info("音频目录: %s", audio_dir)

    audio_list, original_content = parse_storyboard(storyboard_path)

    if not audio_list:
        logger.error("未找到音频清单，请检查分镜脚本格式")
        sys.exit(1)

    logger.info("找到 %d 个音频条目", len(audio_list))

    valid, errors, updated_list = validate_audio_files(audio_list, audio_dir)

    if errors:
        print("\n" + "="*50)
        print("验证问题：")
        for error in errors:
            print(error)
        print("="*50)

    if updated_list:
        generate_audio_info_json(updated_list, audio_dir)

    if any(item.get('duration') is not None for item in updated_list):
        update_storyboard(storyboard_path, original_content, updated_list)

    print("\n" + "="*50)
    if valid:
        total_duration = sum(item.get('duration', 0) or 0 for item in updated_list)
        print(f"验证通过！所有音频文件正常。")
        print(f"总时长: {total_duration:.1f}秒 ({total_duration/60:.1f}分钟)")
        sys.exit(0)
    else:
        print("验证失败！请检查上述错误。")
        sys.exit(1)


if __name__ == '__main__':
    main()
