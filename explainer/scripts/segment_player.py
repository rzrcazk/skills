#!/usr/bin/env python3
"""
Segment Player - 分段视频播放器与确认工具

功能：
1. 播放分段视频
2. 显示字幕
3. 交互式用户确认
4. 收集问题反馈

使用：
    # 播放并交互确认
    python segment_player.py --project . --segment 0

    # 仅播放（不确认）
    python segment_player.py --project . --segment 0 --play-only

    # 自动确认（用于测试）
    python segment_player.py --project . --segment 0 --auto-confirm
"""

import json
import subprocess
import sys
import argparse
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent))
from segment_pipeline import SegmentPipeline, Segment


@dataclass
class ConfirmResult:
    """确认结果"""
    confirmed: bool
    issues: List[Dict]
    notes: str = ""


class SegmentPlayer:
    """分段播放器"""

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.pipeline = SegmentPipeline(project_dir)

    def play_and_confirm(self, segment_index: int, auto_confirm: bool = False) -> ConfirmResult:
        """
        播放视频并获取用户确认

        Args:
            segment_index: 段索引
            auto_confirm: 自动确认（用于测试）

        Returns:
            ConfirmResult: 确认结果
        """
        segment = self.pipeline.get_segment(segment_index)
        if not segment:
            print(f"Error: Segment {segment_index} not found")
            return ConfirmResult(confirmed=False, issues=[])

        # 检查状态
        if segment.status == "scripts_ready":
            # 检查视频文件是否已经存在（用户已渲染）
            video_path = self.project_dir / segment.video_path
            if video_path.exists():
                print(f"\n✓ 检测到视频文件已存在，自动更新状态")
                self.pipeline.update_segment(segment_index, "generated")
                segment.status = "generated"
            else:
                print(f"\n⚠️  段 {segment_index} 的脚本已生成，但视频尚未渲染")
                print("   请先执行以下命令渲染视频：")
                seg_dir = self.project_dir / "segments" / f"{segment.id}_{segment.time_range.replace(':', '_')}"
                print(f"\n   cd {seg_dir}")
                print(f"   manim -qh script.py ExplainerScene")
                print(f"\n   渲染完成后再运行此脚本播放。")
                return ConfirmResult(confirmed=False, issues=[],
                                   notes="Video not rendered yet")

        if segment.status not in ["generated", "confirmed", "rejected", "fixing"]:
            print(f"Error: Segment {segment_index} is not ready (status: {segment.status})")
            return ConfirmResult(confirmed=False, issues=[])

        # 显示段信息
        self._show_segment_info(segment)

        # 播放视频
        self._play_video(segment)

        if auto_confirm:
            print("\n🤖 自动确认模式")
            return ConfirmResult(confirmed=True, issues=[])

        # 获取用户确认
        return self._interactive_confirm(segment)

    def _show_segment_info(self, segment: Segment):
        """显示段信息"""
        print(f"\n{'='*60}")
        print(f"🎬 第 {segment.index + 1} 段 / 共 {len(self.pipeline.data['segments'])} 段")
        print(f"   ID: {segment.id}")
        print(f"   时间: {segment.time_range}")
        print(f"   Scenes: {segment.scenes}")
        print(f"   时长: {segment.end_time - segment.start_time:.1f} 秒")
        print(f"{'='*60}\n")

        # 显示字幕预览
        subtitle_path = self.project_dir / segment.subtitle_path
        if subtitle_path.exists():
            print("📜 字幕预览:")
            subtitles = self._load_subtitles(subtitle_path)
            for sub in subtitles[:3]:  # 只显示前3条
                print(f"   [{self._format_time(sub['start'])}] {sub['text'][:40]}...")
            if len(subtitles) > 3:
                print(f"   ... 共 {len(subtitles)} 条字幕")
            print()

    def _load_subtitles(self, subtitle_path: Path) -> List[Dict]:
        """加载字幕"""
        content = subtitle_path.read_text(encoding='utf-8')
        subtitles = []

        blocks = content.strip().split('\n\n')
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) >= 3:
                time_line = lines[1].strip()
                text = '\n'.join(lines[2:])

                # 解析时间
                start_str = time_line.split(' --> ')[0]
                start = self._parse_srt_time(start_str)

                subtitles.append({"start": start, "text": text})

        return subtitles

    def _parse_srt_time(self, time_str: str) -> float:
        """解析 SRT 时间"""
        time_str = time_str.replace(',', '.')
        parts = time_str.split(':')
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])

    def _format_time(self, seconds: float) -> str:
        """格式化时间"""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}:{secs:02d}"

    def _play_video(self, segment: Segment) -> bool:
        """
        播放视频（多播放器支持）

        播放优先级：
        1. ffplay（如果有，支持更多格式）
        2. 系统默认播放器（open/xdg-open/start）

        Args:
            segment: 段信息

        Returns:
            bool: 是否成功启动播放
        """
        video_path = self.project_dir / segment.video_path

        if not video_path.exists():
            print(f"Error: Video not found: {video_path}")
            return False

        print(f"▶️  正在播放: {video_path.name}")
        print(f"   路径: {video_path}")
        print("   (请观看视频后，在终端输入反馈)\n")

        # 尝试不同的播放器
        players_tried = []

        # 1. 尝试 ffplay（ffmpeg 自带，功能最强）
        try:
            result = subprocess.run(
                ["which", "ffplay"],
                capture_output=True
            )
            if result.returncode == 0:
                subprocess.Popen(
                    ["ffplay", "-autoexit", "-loglevel", "quiet", str(video_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                print("   使用播放器: ffplay")
                return True
        except Exception:
            pass
        players_tried.append("ffplay")

        # 2. 尝试系统默认播放器
        try:
            if sys.platform == "darwin":
                # macOS: open
                subprocess.Popen(["open", str(video_path)])
                print("   使用播放器: open (系统默认)")
                return True
            elif sys.platform == "linux":
                # Linux: xdg-open
                subprocess.Popen(["xdg-open", str(video_path)])
                print("   使用播放器: xdg-open (系统默认)")
                return True
            else:
                # Windows: startfile
                import os
                os.startfile(str(video_path))
                print("   使用播放器: start (系统默认)")
                return True
        except Exception as e:
            players_tried.append(f"system ({e})")


        # 所有播放器都失败了
        print(f"\n⚠️  无法自动播放视频")
        print(f"   已尝试: {', '.join(players_tried)}")
        print(f"   请手动打开: {video_path}")
        print(f"   观看完成后在此输入 'done' 继续\n")

        # 等待用户确认
        while True:
            user_input = input("输入 'done' 表示已观看: ").strip().lower()
            if user_input in ['done', 'd', 'yes', 'y', '']:
                return True
            if user_input in ['skip', 's']:
                return False
            print("输入无效，请输入 'done' 或按 Enter 继续")

        return True

    def _interactive_confirm(self, segment: Segment) -> ConfirmResult:
        """交互式确认"""
        print("\n" + "="*60)
        print("👤 请确认这段视频")
        print("="*60)
        print()
        print("选项:")
        print("  1. ✅ 没问题，继续下一段")
        print("  2. 📝 画面有问题（请描述）")
        print("  3. 🔊 声音/音频有问题")
        print("  4. 📝 字幕有问题")
        print("  5. ⏱️  时间/节奏有问题")
        print("  6. 🔄 重新播放")
        print("  7. 📷 显示关键帧（用于截图说明）")
        print("  0. 🚪 退出")
        print()

        issues = []

        while True:
            try:
                choice = input("请选择 [1-7, 0]: ").strip()

                if choice == "1":
                    return ConfirmResult(confirmed=True, issues=issues)

                elif choice == "2":
                    issue = self._collect_issue("video")
                    if issue:
                        issues.append(issue)
                    print(f"\n已记录 {len(issues)} 个问题")

                elif choice == "3":
                    issue = self._collect_issue("audio")
                    if issue:
                        issues.append(issue)
                    print(f"\n已记录 {len(issues)} 个问题")

                elif choice == "4":
                    issue = self._collect_issue("subtitle")
                    if issue:
                        issues.append(issue)
                    print(f"\n已记录 {len(issues)} 个问题")

                elif choice == "5":
                    issue = self._collect_issue("timing")
                    if issue:
                        issues.append(issue)
                    print(f"\n已记录 {len(issues)} 个问题")

                elif choice == "6":
                    self._play_video(segment)

                elif choice == "7":
                    self._show_keyframes(segment)

                elif choice == "0":
                    return ConfirmResult(confirmed=False, issues=issues, notes="User quit")

                else:
                    print("无效选择，请重试")

            except KeyboardInterrupt:
                print("\n\n用户中断")
                return ConfirmResult(confirmed=False, issues=issues, notes="Interrupted")

    def _collect_issue(self, issue_type: str) -> Optional[Dict]:
        """收集问题详情"""
        type_names = {
            "video": "画面",
            "audio": "声音",
            "subtitle": "字幕",
            "timing": "时间/节奏"
        }

        print(f"\n📝 请描述{type_names.get(issue_type, issue_type)}问题:")
        print("   (例如: 三角形颜色太淡 / 第2句字幕有错字 / 动画太快)")
        print("   可以截图并描述截图中的问题")
        print()

        description = input("问题描述: ").strip()
        if not description:
            print("未输入描述，取消")
            return None

        # 询问严重程度
        print("\n严重程度:")
        print("  1. 🔴 严重 - 必须修复")
        print("  2. 🟡 中等 - 最好修复")
        print("  3. 🟢 轻微 - 可接受")
        severity_map = {"1": "high", "2": "medium", "3": "low"}

        severity = "medium"
        sev_choice = input("请选择 [1-3, 默认2]: ").strip() or "2"
        severity = severity_map.get(sev_choice, "medium")

        return {
            "type": issue_type,
            "description": description,
            "severity": severity,
            "timestamp": subprocess.check_output(["date", "+%Y-%m-%dT%H:%M:%S"]).decode().strip()
        }

    def _show_keyframes(self, segment: Segment):
        """显示关键帧（使用 ffmpeg 提取）"""
        print("\n📷 提取关键帧...")

        video_path = self.project_dir / segment.video_path
        if not video_path.exists():
            print("视频不存在")
            return

        # 创建关键帧目录
        keyframe_dir = self.project_dir / "segments" / f"{segment.id}_{segment.time_range.replace(':', '_')}" / "keyframes"
        keyframe_dir.mkdir(exist_ok=True)

        # 获取视频时长
        duration = segment.end_time - segment.start_time

        # 提取关键帧（开始、中间、结束）
        timestamps = [0, duration / 2, duration - 0.1]
        labels = ["start", "middle", "end"]

        for ts, label in zip(timestamps, labels):
            output = keyframe_dir / f"{label}.png"
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(ts),
                "-i", str(video_path),
                "-vframes", "1",
                "-q:v", "2",
                str(output)
            ]
            try:
                subprocess.run(cmd, capture_output=True)
                print(f"   {label}: {output}")
            except Exception as e:
                print(f"   {label}: 失败 ({e})")

        print(f"\n关键帧已保存到: {keyframe_dir}")
        print("请在文件管理器中查看，并描述截图中的问题\n")

        # 打开目录
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", str(keyframe_dir)])
            elif sys.platform == "linux":
                subprocess.Popen(["xdg-open", str(keyframe_dir)])
        except:
            pass

    def play_only(self, segment_index: int):
        """仅播放视频"""
        segment = self.pipeline.get_segment(segment_index)
        if not segment:
            print(f"Segment {segment_index} not found")
            return

        self._show_segment_info(segment)
        self._play_video(segment)

        print("\n视频已在外部播放器打开")

    def save_confirmation(self, segment_index: int, result: ConfirmResult):
        """保存确认结果到流水线"""
        if result.confirmed:
            self.pipeline.update_segment(segment_index, "confirmed")
            print(f"\n✅ 段 {segment_index} 已确认")
        else:
            self.pipeline.update_segment(
                segment_index,
                "rejected" if result.issues else "pending",
                issues=result.issues
            )
            if result.issues:
                print(f"\n📝 段 {segment_index} 标记为需要修复")
                print("   问题列表:")
                for issue in result.issues:
                    print(f"   - [{issue['type']}] {issue['description']}")


def main():
    parser = argparse.ArgumentParser(description="Segment Video Player & Confirm")
    parser.add_argument("--project", "-p", default=".", help="Project directory")
    parser.add_argument("--segment", "-s", type=int, required=True, help="Segment index")
    parser.add_argument("--play-only", action="store_true", help="Play only, no confirmation")
    parser.add_argument("--auto-confirm", action="store_true", help="Auto confirm (for testing)")
    parser.add_argument("--update-status", action="store_true", help="Update pipeline status")

    args = parser.parse_args()

    project_dir = Path(args.project)
    if not project_dir.exists():
        print(f"Error: Project directory does not exist: {project_dir}")
        return 1

    pipeline_file = project_dir / "segment_pipeline.json"
    if not pipeline_file.exists():
        print(f"Error: Pipeline not initialized.")
        return 1

    player = SegmentPlayer(project_dir)

    if args.play_only:
        player.play_only(args.segment)
        return 0

    # 播放并确认
    result = player.play_and_confirm(args.segment, args.auto_confirm)

    if args.update_status:
        player.save_confirmation(args.segment, result)

    # 输出结果（JSON格式，供其他脚本使用）
    output = {
        "confirmed": result.confirmed,
        "issues": result.issues,
        "notes": result.notes
    }
    print("\n" + json.dumps(output, ensure_ascii=False))

    return 0 if result.confirmed else 1


if __name__ == "__main__":
    exit(main())
