#!/usr/bin/env python3
"""
Scene Merger - 场景合并脚本

功能：
- 收集所有场景的视频和音频
- 按场景 ID 顺序合并
- 生成最终视频
- 支持增量合并（只合并新确认的场景）
- 使用统一状态管理器追踪进度

使用方式：
    # 合并所有已确认的场景
    python3 scripts/merge_scenes.py --project . --output output/final.mp4

    # 仅合并音频
    python3 scripts/merge_scenes.py --project . --audio-only

    # 合并到指定场景
    python3 scripts/merge_scenes.py --project . --upto 5

    # 显示场景摘要
    python3 scripts/merge_scenes.py --project . --summary

    # 增量合并（只合并新确认的）
    python3 scripts/merge_scenes.py --project . --incremental
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 导入统一状态管理器
sys.path.insert(0, str(Path(__file__).parent))
from state_manager import StateManager


class SceneMerger:
    """场景合并器"""

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.scenes_dir = self.project_dir / "scenes"
        self.output_dir = self.project_dir / "output"
        self.state_manager = StateManager(project_dir)

        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def collect_scenes(self, status_filter: str = "confirmed") -> List[Tuple[int, Path]]:
        """收集所有场景目录"""
        if not self.scenes_dir.exists():
            print(f"错误：场景目录不存在：{self.scenes_dir}")
            return []

        scenes = []
        for scene_dir in self.scenes_dir.iterdir():
            if not scene_dir.is_dir():
                continue

            name = scene_dir.name
            if not name.startswith("scene_"):
                continue

            try:
                # 提取场景 ID
                parts = name.split("_")
                if len(parts) >= 2:
                    scene_id = int(parts[1])
                else:
                    continue

                # 检查状态文件
                status_file = scene_dir / "status.json"
                if status_file.exists():
                    data = json.loads(status_file.read_text(encoding='utf-8'))
                    status = data.get("status", "pending")

                    if status_filter is None or status == status_filter:
                        scenes.append((scene_id, scene_dir))

            except (ValueError, IndexError):
                continue

        # 按 ID 排序
        scenes.sort(key=lambda x: x[0])
        return scenes

    def check_scene_status(self) -> Tuple[List, List, List]:
        """检查所有场景的状态"""
        scenes = self.collect_scenes(status_filter=None)

        confirmed = []
        pending = []
        failed = []

        for scene_id, scene_dir in scenes:
            status_file = scene_dir / "status.json"
            if status_file.exists():
                data = json.loads(status_file.read_text(encoding='utf-8'))
                status = data.get("status", "pending")

                if status in ["confirmed", "generated"]:
                    confirmed.append((scene_id, scene_dir))
                elif status in ["failed", "timeout", "error", "rejected"]:
                    failed.append((scene_id, scene_dir, status))
                else:
                    pending.append((scene_id, scene_dir, status))

        return confirmed, pending, failed

    def get_scene_video(self, scene_dir: Path) -> Optional[Path]:
        """获取场景视频文件路径"""
        possible_paths = [
            scene_dir / "video_preview.mp4",
            scene_dir / "video.mp4",
            scene_dir / "output.mp4",
        ]

        for path in possible_paths:
            if path.exists():
                return path
        return None

    def get_scene_audio(self, scene_dir: Path) -> Optional[Path]:
        """获取场景音频文件路径"""
        possible_paths = [
            scene_dir / "audio_main.wav",
            scene_dir / "audio.wav",
        ]

        for path in possible_paths:
            if path.exists():
                return path
        return None

    def merge_videos(self, scenes: List[Tuple[int, Path]],
                     output_path: Path) -> bool:
        """合并视频文件"""
        if not scenes:
            print("错误：没有场景可以合并")
            return False

        print(f"\n🎬 合并 {len(scenes)} 个场景的视频...")

        # 创建 ffmpeg concat 列表
        concat_list = self.output_dir / "video_concat_list.txt"
        video_files = []

        for scene_id, scene_dir in scenes:
            video_path = self.get_scene_video(scene_dir)
            if video_path:
                video_files.append(video_path)
            else:
                print(f"  ⚠️  场景 {scene_id} 缺少视频文件")

        if not video_files:
            print("错误：没有找到任何视频文件")
            return False

        # 写入 concat 列表
        with open(concat_list, 'w', encoding='utf-8') as f:
            for video_file in video_files:
                f.write(f"file '{video_file.absolute()}'\n")

        # 执行 ffmpeg 合并
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(output_path)
        ]

        print(f"  输出：{output_path}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  ✅ 视频合并成功")
                return True
            else:
                print(f"  ❌ 视频合并失败：{result.stderr}")
                return False
        except FileNotFoundError:
            print("  ❌ ffmpeg 未找到，请安装 ffmpeg")
            return False
        finally:
            # 清理临时文件
            concat_list.unlink(missing_ok=True)

    def merge_audio(self, scenes: List[Tuple[int, Path]],
                    output_path: Path) -> bool:
        """合并音频文件（主旁白）"""
        if not scenes:
            print("错误：没有场景可以合并")
            return False

        print(f"\n🔊 合并 {len(scenes)} 个场景的音频...")

        # 创建 ffmpeg concat 列表
        concat_list = self.output_dir / "audio_concat_list.txt"
        audio_files = []

        for scene_id, scene_dir in scenes:
            audio_path = self.get_scene_audio(scene_dir)
            if audio_path:
                audio_files.append(audio_path)
            else:
                print(f"  ⚠️  场景 {scene_id} 缺少音频文件")

        if not audio_files:
            print("错误：没有找到任何音频文件")
            return False

        # 写入 concat 列表
        with open(concat_list, 'w', encoding='utf-8') as f:
            for audio_file in audio_files:
                f.write(f"file '{audio_file.absolute()}'\n")

        # 执行 ffmpeg 合并
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            "-ac", "2",
            str(output_path)
        ]

        print(f"  输出：{output_path}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  ✅ 音频合并成功")
                return True
            else:
                print(f"  ❌ 音频合并失败：{result.stderr}")
                return False
        except FileNotFoundError:
            print("  ❌ ffmpeg 未找到，请安装 ffmpeg")
            return False
        finally:
            # 清理临时文件
            concat_list.unlink(missing_ok=True)

    def merge_with_audio(self, scenes: List[Tuple[int, Path]],
                         video_output: Path, audio_output: Path) -> bool:
        """合并视频并合成音频"""
        # 先合并视频（无音频）
        temp_video = self.output_dir / "temp_video_no_audio.mp4"

        if not self.merge_videos(scenes, temp_video):
            return False

        # 再合并音频
        if not self.merge_audio(scenes, audio_output):
            return False

        # 将音频合成到视频
        cmd = [
            "ffmpeg", "-y",
            "-i", str(temp_video),
            "-i", str(audio_output),
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(video_output)
        ]

        print(f"\n🎬 合成音视频...")
        print(f"  输出：{video_output}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  ✅ 音视频合成成功")
                # 清理临时文件
                temp_video.unlink(missing_ok=True)
                return True
            else:
                print(f"  ❌ 音视频合成失败：{result.stderr}")
                return False
        except FileNotFoundError:
            print("  ❌ ffmpeg 未找到")
            return False

    def merge_all(self, output_path: Path = None,
                  audio_only: bool = False,
                  upto_scene: int = None,
                  incremental: bool = False) -> bool:
        """合并所有已确认的场景"""
        # 确定输出路径
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.output_dir / f"merged_{timestamp}.mp4"

        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 收集已确认的场景
        confirmed, pending, failed = self.check_scene_status()

        print(f"\n📊 场景状态摘要:")
        print(f"  ✅ 已确认/生成：{len(confirmed)}")
        print(f"  ⏳ 待处理：{len(pending)}")
        print(f"  ❌ 失败：{len(failed)}")

        if not confirmed:
            print("\n❌ 错误：没有已确认的场景")
            return False

        # 如果指定了 upto_scene，只合并到该场景
        if upto_scene is not None:
            confirmed = [(sid, sdir) for sid, sdir in confirmed if sid <= upto_scene]
            print(f"\n📋 只合并到场景 {upto_scene}, 共 {len(confirmed)} 个场景")

        # 增量合并：检查是否已有部分合并
        if incremental:
            existing_merged = self.output_dir / "merged_incremental.mp4"
            if existing_merged.exists():
                print(f"\n⚠️  增量合并模式：将追加到新场景")
                # TODO: 实现增量合并逻辑
                print("  (当前简化为完整合并)")

        # 执行合并
        if audio_only:
            audio_output = output_path.with_suffix('.wav')
            return self.merge_audio(confirmed, audio_output)
        else:
            # 合并视频 + 音频
            return self.merge_with_audio(
                confirmed,
                output_path,
                output_path.with_suffix('.wav')
            )

    def print_summary(self):
        """打印场景摘要"""
        confirmed, pending, failed = self.check_scene_status()

        print("\n" + "="*60)
        print("📋 场景状态摘要")
        print("="*60)

        print(f"\n✅ 已确认/生成的场景 ({len(confirmed)}):")
        for scene_id, scene_dir in confirmed:
            video = self.get_scene_video(scene_dir)
            audio = self.get_scene_audio(scene_dir)
            video_icon = "🎬" if video else "❌"
            audio_icon = "🔊" if audio else "❌"
            print(f"  {video_icon}{audio_icon} 场景 {scene_id}: {scene_dir.name}")

        if pending:
            print(f"\n⏳ 待处理的场景 ({len(pending)}):")
            for scene_id, scene_dir, status in pending:
                print(f"  ⏹ 场景 {scene_id}: {scene_dir.name} ({status})")

        if failed:
            print(f"\n❌ 失败的场景 ({len(failed)}):")
            for scene_id, scene_dir, status in failed:
                print(f"  ❌ 场景 {scene_id}: {scene_dir.name} ({status})")

        # 显示统一状态管理器的进度
        print(f"\n📊 统一状态:")
        print(self.state_manager.get_summary())

        print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description="Scene Merger - 场景合并器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    # 合并所有已确认的场景
    python3 scripts/merge_scenes.py --project . --output output/final.mp4

    # 仅音频合并
    python3 scripts/merge_scenes.py --project . --audio-only

    # 合并到指定场景
    python3 scripts/merge_scenes.py --project . --upto 5

    # 显示场景摘要
    python3 scripts/merge_scenes.py --project . --summary

    # 增量合并（只合并新确认的）
    python3 scripts/merge_scenes.py --project . --incremental
        """
    )

    parser.add_argument("--project", "-p", required=True,
                       help="项目目录路径")
    parser.add_argument("--output", "-o", type=str,
                       help="输出视频文件路径")
    parser.add_argument("--audio-only", "-a", action="store_true",
                       help="仅合并音频")
    parser.add_argument("--upto", "-u", type=int,
                       help="合并到指定场景 ID")
    parser.add_argument("--incremental", "-i", action="store_true",
                       help="增量合并")
    parser.add_argument("--summary", "-s", action="store_true",
                       help="显示场景摘要")

    args = parser.parse_args()

    project_dir = Path(args.project)
    if not project_dir.exists():
        print(f"错误：项目目录不存在：{project_dir}")
        return 1

    merger = SceneMerger(project_dir)

    if args.summary:
        merger.print_summary()
        return 0

    if args.audio_only:
        output_path = Path(args.output) if args.output else None
        success = merger.merge_all(output_path, audio_only=True)
    elif args.upto is not None:
        output_path = Path(args.output) if args.output else None
        success = merger.merge_all(output_path, upto_scene=args.upto,
                                   incremental=args.incremental)
    else:
        output_path = Path(args.output) if args.output else None
        success = merger.merge_all(output_path, incremental=args.incremental)

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
