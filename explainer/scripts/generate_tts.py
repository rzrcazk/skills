#!/usr/bin/env python3
"""
TTS 生成脚本

功能：
- 从 CSV 文件读取对白列表
- 使用 Edge TTS (xiaoxiao 语音) 生成音频
- 输出到指定目录
- 生成 audio_info.json 供验证脚本使用

CSV 格式：
    filename,text
    audio_001_开场.wav,"大家好，今天我们来学习..."
    audio_002_介绍.wav,"首先，让我们来看这个图形..."

使用：
    python generate_tts.py audio_list.csv ./audio --voice xiaoxiao

支持的声音：
    xiaoxiao (晓晓，女声，默认)
    xiaoyi (晓伊，女声)
    yunyang (云扬，男声)
    yunjian (云健，男声)
"""

import sys
import os
import csv
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# 添加脚本目录到路径
sys.path.insert(0, str(Path(__file__).parent))
from utils import get_audio_duration, extract_scene_number, atomic_write_json
from config import CONFIG
from logger import get_logger

logger = get_logger(__name__)

# 检查 edge-tts
try:
    import edge_tts
except ImportError:
    logger.error("edge-tts 未安装，请运行: uv pip install edge-tts")
    sys.exit(1)


# 声音映射表（从配置读取）
VOICE_MAP = CONFIG.tts.voice_map


async def generate_audio(
    text: str,
    output_path: Union[str, Path],
    voice: str = "xiaoxiao",
) -> Tuple[bool, Optional[float]]:
    """
    生成单条音频

    Args:
        text: 文本内容
        output_path: 输出文件路径
        voice: 声音名称

    Returns:
        (success, duration): 是否成功，音频时长（秒）
    """
    voice_id = VOICE_MAP.get(voice, VOICE_MAP[CONFIG.tts.default_voice])

    try:
        communicate = edge_tts.Communicate(text, voice_id)
        await communicate.save(str(output_path))
        duration = get_audio_duration(output_path)
        return True, duration
    except Exception as e:
        logger.error("生成音频失败 %s: %s", output_path, e)
        return False, None


def parse_csv(csv_path: Union[str, Path]) -> List[Dict[str, str]]:
    """
    解析 CSV 文件

    支持格式：
    - 标准 CSV: filename,text
    - 带 BOM 的 UTF-8
    - 不同分隔符（优先逗号，支持分号）

    Args:
        csv_path: CSV 文件路径

    Returns:
        list of {filename, text}
    """
    entries: List[Dict[str, str]] = []

    for encoding in ['utf-8-sig', 'utf-8', 'gbk', 'gb2312']:
        try:
            with open(csv_path, 'r', encoding=encoding) as f:
                sample = f.read(2048)
                f.seek(0)
                delimiter = ';' if sample.count(';') > sample.count(',') else ','
                reader = csv.DictReader(f, delimiter=delimiter)
                for row in reader:
                    filename = row.get('filename') or row.get('文件名') or row.get('file')
                    text = row.get('text') or row.get('对白') or row.get('content') or row.get('读白')
                    if filename and text:
                        entries.append({'filename': filename, 'text': text.strip()})
            logger.info("解析 CSV 成功 (%s), 共 %d 条", encoding, len(entries))
            return entries
        except Exception:
            continue

    # 简单解析兜底
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            for line in f.readlines()[1:]:
                parts = line.strip().split(',', 1)
                if len(parts) == 2:
                    entries.append({
                        'filename': parts[0].strip(),
                        'text': parts[1].strip().strip('"'),
                    })
        if entries:
            logger.info("简单解析 CSV 成功, 共 %d 条", len(entries))
            return entries
    except Exception:
        pass

    logger.error("无法解析 CSV 文件: %s", csv_path)
    return []


async def generate_all(
    csv_path: Union[str, Path],
    output_dir: Union[str, Path],
    voice: str = "xiaoxiao",
    max_concurrent: int = CONFIG.tts.max_concurrent,
    incremental: bool = False,
) -> bool:
    """
    批量生成音频（支持并行和增量）

    Args:
        csv_path: CSV 文件路径
        output_dir: 输出目录
        voice: 声音名称
        max_concurrent: 最大并发数
        incremental: 增量模式——跳过文本未变更的已有音频

    Returns:
        bool: 所有条目均成功时返回 True
    """
    entries = parse_csv(csv_path)
    if not entries:
        return False

    os.makedirs(str(output_dir), exist_ok=True)

    # 增量模式：加载已有 audio_info.json，对比文本
    existing_texts: Dict[str, str] = {}
    if incremental:
        info_path = os.path.join(str(output_dir), 'audio_info.json')
        if os.path.exists(info_path):
            try:
                old_info = json.loads(open(info_path, encoding='utf-8').read())
                existing_texts = {
                    item['file']: item.get('text', '')
                    for item in old_info.get('files', [])
                }
            except Exception:
                pass

    # 准备任务：区分需要生成和可跳过的条目
    to_generate: List[Dict] = []
    skipped: List[Dict] = []

    for entry in entries:
        filename = entry['filename']
        if not filename.endswith(('.wav', '.mp3')):
            filename += '.wav'
        entry['filename'] = filename
        entry['output_path'] = os.path.join(str(output_dir), filename)

        if (incremental
                and os.path.exists(entry['output_path'])
                and existing_texts.get(filename) == entry['text']):
            skipped.append(entry)
        else:
            to_generate.append(entry)

    if skipped:
        logger.info("增量模式：跳过 %d 个未变更的音频", len(skipped))

    total = len(entries)
    gen_count = len(to_generate)

    if gen_count == 0:
        logger.info("所有音频均为最新，无需生成")
    else:
        logger.info("开始生成音频 (声音: %s, 并发: %d, 共 %d 条)...",
                    voice, max_concurrent, gen_count)

    semaphore = asyncio.Semaphore(max_concurrent)

    async def generate_with_semaphore(entry: Dict, index: int) -> Optional[Dict]:
        async with semaphore:
            filename = entry['filename']
            text = entry['text']
            output_path = entry['output_path']
            logger.info("[%d/%d] 开始: %s", index + 1, gen_count, filename)
            success, duration = await generate_audio(text, output_path, voice)
            if success:
                scene_num = extract_scene_number(filename)
                logger.info("  完成: %s (%.2fs)", filename, duration or 0)
                return {
                    'scene': scene_num,
                    'file': filename,
                    'text': text,
                    'duration': round(duration, 2) if duration else 0,
                }
            logger.warning("  失败: %s", filename)
            return None

    tasks = [generate_with_semaphore(e, i) for i, e in enumerate(to_generate)]
    results = await asyncio.gather(*tasks)
    new_results = [r for r in results if r is not None]

    # 合并已跳过的条目（从旧 info 中读取）
    skip_results: List[Dict] = []
    if skipped and existing_texts:
        old_info_map = {}
        info_path = os.path.join(str(output_dir), 'audio_info.json')
        if os.path.exists(info_path):
            old_info = json.loads(open(info_path, encoding='utf-8').read())
            old_info_map = {item['file']: item for item in old_info.get('files', [])}
        for entry in skipped:
            if entry['filename'] in old_info_map:
                skip_results.append(old_info_map[entry['filename']])

    all_results = new_results + skip_results

    if all_results:
        info = {
            'files': all_results,
            'total_duration': sum(r.get('duration', 0) for r in all_results),
            'count': len(all_results),
            'voice': voice,
        }
        info_path = os.path.join(str(output_dir), 'audio_info.json')
        atomic_write_json(info_path, info)
        logger.info("已生成: %s", info_path)

    logger.info("生成完成: %d/%d 成功", len(new_results), gen_count)
    return len(new_results) == gen_count


def main():
    import argparse

    voice_list = "\n".join(f"  {k:<25} {v}" for k, v in VOICE_MAP.items())
    parser = argparse.ArgumentParser(
        description="从 CSV 批量生成 TTS 音频",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"可用声音:\n{voice_list}\n\n示例:\n"
               "  python generate_tts.py audio_list.csv ./audio\n"
               "  python generate_tts.py audio_list.csv ./audio --voice yunyang\n"
               "  python generate_tts.py audio_list.csv ./audio --incremental",
    )
    parser.add_argument("csv_file", help="CSV 文件路径")
    parser.add_argument("output_dir", nargs="?", default="./audio", help="输出目录 (默认: ./audio)")
    parser.add_argument("--voice", default=CONFIG.tts.default_voice, help="声音名称")
    parser.add_argument("--incremental", "-i", action="store_true",
                        help="增量模式：跳过文本未变的已有音频")
    parser.add_argument("--concurrent", type=int, default=CONFIG.tts.max_concurrent,
                        help=f"最大并发数 (默认: {CONFIG.tts.max_concurrent})")
    args = parser.parse_args()

    if not os.path.exists(args.csv_file):
        logger.error("CSV 文件不存在: %s", args.csv_file)
        sys.exit(1)

    logger.info("CSV 文件: %s", args.csv_file)
    logger.info("输出目录: %s", args.output_dir)
    logger.info("使用声音: %s", args.voice)
    if args.incremental:
        logger.info("增量模式: 已启用")

    success = asyncio.run(
        generate_all(args.csv_file, args.output_dir, args.voice,
                     args.concurrent, args.incremental)
    )
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
