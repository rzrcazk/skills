#!/usr/bin/env python3
"""
Segment Pipeline Runner - 分段流水线主控脚本

功能：
协调整个分段视频生成流程：
1. 初始化流水线（将分镜拆分为段）
2. 循环处理每个段：生成 → 播放 → 确认 → 合并
3. 支持断点续传
4. 后台预生成下一段

使用：
    # 启动分段流水线
    python run_segment_pipeline.py --project .

    # 指定目标段时长（默认20秒）
    python run_segment_pipeline.py --project . --target-duration 15

    # 从指定段开始（断点续传）
    python run_segment_pipeline.py --project . --start-from 2

    # 跳过确认（自动模式，用于测试）
    python run_segment_pipeline.py --project . --auto-confirm
"""

import json
import subprocess
import sys
import time
import argparse
from pathlib import Path
from typing import Optional, List

sys.path.insert(0, str(Path(__file__).parent))
from segment_pipeline import SegmentPipeline, Segment
from segment_generator import SegmentGenerator
from segment_merger import SegmentMerger
from segment_player import SegmentPlayer, ConfirmResult
from config import CONFIG
from logger import get_logger

logger = get_logger(__name__)


class SegmentPipelineRunner:
    """分段流水线运行器"""

    def __init__(self, project_dir: Path,
                 target_duration: int = CONFIG.segment.default_duration,
                 auto_confirm: bool = False, preload: bool = True,
                 headless: bool = False):
        self.project_dir = Path(project_dir)
        self.target_duration = target_duration
        self.auto_confirm = auto_confirm
        self.preload = preload
        self.headless = headless  # 无头模式：只生成脚本，不渲染不播放

        self.pipeline = SegmentPipeline(project_dir)
        self.generator = SegmentGenerator(project_dir, skip_render=headless)
        self.merger = SegmentMerger(project_dir)
        self.player = SegmentPlayer(project_dir)

        self.preload_process = None

    def run(self, start_from: Optional[int] = None):
        """
        运行完整流水线

        Args:
            start_from: 从指定段开始（用于断点续传）
        """
        print("\n" + "="*70)
        print("🎬 Explainer 分段视频生成流水线")
        print("="*70)

        # 1. 检查/初始化流水线
        if not self._ensure_pipeline():
            return False

        # 2. 显示进度
        progress = self.pipeline.get_progress()
        print(f"\n📊 当前进度:")
        print(f"   总段数: {progress['total_segments']}")
        print(f"   已确认: {progress['confirmed_segments']}")
        print(f"   进度: {progress['progress_percent']:.1f}%")
        print()

        # 3. 处理每个段
        current_index = start_from if start_from is not None else self._get_start_index()
        total = len(self.pipeline.data["segments"])

        while current_index < total:
            success = self._process_segment(current_index)
            if not success:
                print(f"\n⛔ 段 {current_index} 处理失败，流水线暂停")
                print("   修复问题后重新运行脚本即可继续")
                return False

            current_index += 1

        # 4. 生成最终视频
        print("\n" + "="*70)
        print("🎉 所有段已确认！生成最终视频...")
        print("="*70)

        final_video = self.merger.merge_final()
        if final_video:
            print(f"\n✅ 视频制作完成!")
            print(f"   最终视频: {final_video}")
            return True
        else:
            print("\n❌ 最终视频生成失败")
            return False

    def _ensure_pipeline(self) -> bool:
        """确保流水线已初始化"""
        pipeline_file = self.project_dir / "segment_pipeline.json"

        if pipeline_file.exists():
            print("✓ 流水线已初始化")
            return True

        print("⚙️  初始化流水线...")

        # 检查必要文件
        storyboard = self._find_storyboard()
        if not storyboard:
            print("Error: 分镜脚本不存在")
            print("   请确保存在: 分镜脚本.md 或 storyboard.md")
            return False

        audio_info = self.project_dir / "audio" / "audio_info.json"
        if not audio_info.exists():
            print("Error: 音频信息不存在")
            print("   请先运行 TTS 生成: python scripts/generate_tts.py")
            return False

        # 初始化
        try:
            self.pipeline.init_from_storyboard(
                storyboard_path=storyboard,
                audio_info_path=audio_info,
                target_duration=self.target_duration
            )
            return True
        except Exception as e:
            print(f"Error: 初始化失败: {e}")
            return False

    def _find_storyboard(self) -> Optional[Path]:
        """查找分镜脚本"""
        candidates = [
            self.project_dir / "分镜脚本.md",
            self.project_dir / "storyboard.md",
            self.project_dir / "分镜.md",
        ]
        for c in candidates:
            if c.exists():
                return c
        return None

    def _get_start_index(self) -> int:
        """获取开始索引（断点续传）"""
        # 找到第一个非 confirmed 的段
        for i, seg_data in enumerate(self.pipeline.data["segments"]):
            if seg_data["status"] != "confirmed":
                return i
        return 0

    def _process_segment(self, index: int) -> bool:
        """处理单个段"""
        segment = self.pipeline.get_segment(index)
        if not segment:
            print(f"Error: Segment {index} not found")
            return False

        print("\n" + "="*70)
        print(f"🎬 处理第 {index + 1} 段 / 共 {len(self.pipeline.data['segments'])} 段")
        print(f"   ID: {segment.id} | 时间: {segment.time_range}")
        print(f"   Scenes: {segment.scenes}")
        print("="*70)

        # 1. 生成段（如果需要）
        if segment.status in ["pending", "rejected", "fixing"]:
            print("\n📦 步骤 1/4: 生成分段视频")
            success = self.generator.generate(index)
            if not success:
                return False
        else:
            print(f"\n✓ 分段视频已存在 (状态: {segment.status})")

        # 无头模式：跳过播放和确认，提示用户去终端渲染
        if self.headless:
            print("\n🤖 无头模式：脚本已生成，跳过渲染和播放")
            print("="*70)
            print("📋 请用户在终端执行以下命令：")
            print("="*70)
            seg_dir = self.project_dir / "segments" / f"{segment.id}_{segment.time_range.replace(':', '_')}"
            print(f"\n   cd {seg_dir}")
            print(f"   manim -qh script.py ExplainerScene")
            print(f"\n   # 播放预览：")
            print(f"   ffplay -autoexit media/videos/script/1080p60/ExplainerScene.mp4")
            print(f"   # 或 macOS: open media/videos/script/1080p60/ExplainerScene.mp4")
            print("\n   观看后告知 Claude Code 结果，继续下一段。")
            print("="*70)
            return True

        # 2. 播放并确认
        print("\n👤 步骤 2/4: 播放并确认")
        result = self.player.play_and_confirm(index, self.auto_confirm)

        # 3. 保存确认结果
        print("\n💾 步骤 3/4: 保存确认结果")
        self.player.save_confirmation(index, result)

        if not result.confirmed:
            print("\n📝 段被拒绝，需要修复")
            print("   问题列表:")
            for issue in result.issues:
                severity_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
                print(f"   {severity_emoji.get(issue['severity'], '⚪')} "
                      f"[{issue['type']}] {issue['description']}")

            # 修复流程
            if self._fix_segment(index, result.issues):
                # 修复成功，重新处理
                return self._process_segment(index)
            else:
                return False

        # 4. 合并到当前段
        print("\n🔀 步骤 4/4: 合并已确认段")
        merged = self.merger.merge_up_to(index)
        if merged:
            print(f"   累积视频: {merged}")

        # 5. 后台预生成下一段
        if self.preload and index + 1 < len(self.pipeline.data["segments"]):
            self._preload_next(index + 1)

        return True

    def _fix_segment(self, index: int, issues: List[dict]) -> bool:
        """
        修复段

        Args:
            index: 段索引
            issues: 问题列表

        Returns:
            bool: 是否修复成功
        """
        print("\n🔧 修复段...")

        # 分类问题
        video_issues = [i for i in issues if i["type"] == "video"]
        audio_issues = [i for i in issues if i["type"] == "audio"]
        subtitle_issues = [i for i in issues if i["type"] == "subtitle"]
        timing_issues = [i for i in issues if i["type"] == "timing"]

        # 修复视频问题（需要修改 Manim 代码）
        if video_issues or timing_issues:
            print("\n⚠️  发现视频/时间相关问题，需要修改 Manim 脚本")
            print("   请根据以下反馈修改 script.py:")
            for issue in video_issues + timing_issues:
                print(f"   - {issue['description']}")
            print()

            # 等待用户修改
            input("修改完成后按 Enter 继续...")

        # 修复音频问题（重新生成 TTS）
        if audio_issues:
            print("\n🔊 修复音频问题...")
            # 重新生成本段的 TTS
            # 这里简化处理，实际可能需要重新生成特定 scene 的音频
            print("   请手动重新生成音频: python scripts/generate_tts.py")

        # 修复字幕问题
        if subtitle_issues:
            print("\n📝 修复字幕问题...")
            segment = self.pipeline.get_segment(index)
            subtitle_path = self.project_dir / segment.subtitle_path

            print(f"   字幕文件: {subtitle_path}")
            print("   请直接编辑 SRT 文件修复字幕")
            input("修改完成后按 Enter 继续...")

        # 更新状态为 fixing，然后重新生成
        self.pipeline.update_segment(index, "fixing")
        return True

    def _preload_next(self, next_index: int):
        """后台预生成下一段"""
        if next_index >= len(self.pipeline.data["segments"]):
            return

        next_segment = self.pipeline.get_segment(next_index)
        if next_segment.status != "pending":
            return

        print(f"\n⏳ 后台预生成段 {next_index}...")

        # 启动后台进程
        try:
            cmd = [
                sys.executable,
                str(Path(__file__).parent / "segment_generator.py"),
                "--project", str(self.project_dir),
                "--segment", str(next_index),
                "--background"
            ]
            # 无头模式下跳过渲染
            if self.headless:
                cmd.append("--skip-render")

            self.preload_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            print(f"   预生成进程 PID: {self.preload_process.pid}")

        except Exception as e:
            print(f"   预生成启动失败: {e}")

    def resume(self):
        """恢复流水线（断点续传）"""
        pipeline_file = self.project_dir / "segment_pipeline.json"

        if not pipeline_file.exists():
            print("Error: 流水线未初始化")
            return False

        # 读取当前进度
        with open(pipeline_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 找到第一个非 confirmed 的段
        resume_index = None
        for i, seg in enumerate(data["segments"]):
            if seg["status"] != "confirmed":
                resume_index = i
                break

        if resume_index is None:
            print("✓ 所有段已确认，无需恢复")
            return True

        print(f"\n🔄 从段 {resume_index} 恢复...")
        return self.run(start_from=resume_index)

    def status(self):
        """显示状态"""
        pipeline_file = self.project_dir / "segment_pipeline.json"

        if not pipeline_file.exists():
            print("流水线未初始化")
            return

        progress = self.pipeline.get_progress()

        print("\n" + "="*60)
        print("📊 分段流水线状态")
        print("="*60)
        print(f"总段数: {progress['total_segments']}")
        print(f"脚本就绪: {progress.get('scripts_ready', 0)}")
        print(f"已生成: {progress['generated_segments']}")
        print(f"已确认: {progress['confirmed_segments']}")
        print(f"进度: {progress['progress_percent']:.1f}%")
        print(f"当前段: {progress['current_segment_index']}")
        print(f"完成: {'是' if progress['is_complete'] else '否'}")
        print("="*60)

        print("\n段详情:")
        for seg in self.pipeline.list_segments():
            status_emoji = {
                "pending": "⏳",
                "generating": "🔄",
                "scripts_ready": "📝",
                "generated": "✅",
                "confirmed": "✓",
                "rejected": "❌",
                "fixing": "🔧"
            }
            emoji = status_emoji.get(seg.status, "?")
            print(f"  {emoji} {seg.id}: {seg.time_range} ({seg.status})")


def main():
    parser = argparse.ArgumentParser(
        description="Segment Pipeline Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    # 启动流水线（完整模式，需要图形界面）
    python run_segment_pipeline.py --project .

    # 无头模式（跳过渲染，生成脚本后等待用户手动渲染）
    python run_segment_pipeline.py --project . --headless

    # 指定段时长
    python run_segment_pipeline.py --project . --target-duration 15

    # 断点续传
    python run_segment_pipeline.py --project . --resume

    # 查看状态
    python run_segment_pipeline.py --project . --status

    # 自动确认模式（测试用）
    python run_segment_pipeline.py --project . --auto-confirm
        """
    )

    parser.add_argument("--project", "-p", default=".", help="Project directory")
    parser.add_argument("--target-duration", "-t", type=int,
                       default=CONFIG.segment.default_duration,
                       help=f"Target segment duration in seconds (default: {CONFIG.segment.default_duration})")
    parser.add_argument("--start-from", "-s", type=int, help="Start from specific segment")
    parser.add_argument("--resume", "-r", action="store_true", help="Resume from last position")
    parser.add_argument("--status", action="store_true", help="Show pipeline status")
    parser.add_argument("--auto-confirm", "-a", action="store_true",
                       help="Auto confirm segments (for testing)")
    parser.add_argument("--no-preload", action="store_true",
                       help="Disable background preloading")
    parser.add_argument("--headless", action="store_true",
                       help="Headless mode: generate scripts only, skip render and play (for Claude Code)")

    args = parser.parse_args()

    project_dir = Path(args.project)
    if not project_dir.exists():
        print(f"Error: Project directory does not exist: {project_dir}")
        return 1

    runner = SegmentPipelineRunner(
        project_dir=project_dir,
        target_duration=args.target_duration,
        auto_confirm=args.auto_confirm,
        preload=not args.no_preload,
        headless=args.headless
    )

    if args.status:
        runner.status()
        return 0

    if args.resume:
        success = runner.resume()
        return 0 if success else 1

    success = runner.run(start_from=args.start_from)
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
