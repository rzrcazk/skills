#!/usr/bin/env python3
"""
Segment Generator - 分段视频生成器

功能：
1. 生成指定段的 TTS 音频（合并本段所有 scenes）
2. 创建分段专用的 Manim 脚本（只包含本段的 scenes）
3. 渲染视频
4. 生成字幕文件

使用：
    # 生成指定段
    python segment_generator.py --project . --segment 0

    # 生成下一段
    python segment_generator.py --project . --next

    # 强制重新生成
    python segment_generator.py --project . --segment 0 --force

    # 后台运行（用于预加载）
    python segment_generator.py --project . --segment 1 --background
"""

import json
import shutil
import subprocess
import sys
import argparse
import asyncio
from pathlib import Path
from typing import List, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent))
from segment_pipeline import SegmentPipeline, Segment
from config import CONFIG
from logger import get_logger

logger = get_logger(__name__)


class SegmentGenerator:
    """分段视频生成器"""

    def __init__(self, project_dir: Path, skip_render: bool = False):
        self.project_dir = Path(project_dir)
        self.pipeline = SegmentPipeline(project_dir)
        self.skill_dir = Path(__file__).parent.parent
        self.skip_render = skip_render  # 跳过渲染，只生成脚本

        # 目录
        self.segments_dir = self.project_dir / "segments"
        self.audio_dir = self.project_dir / "audio"
        self.script_file = self.project_dir / "script.py"

    def generate(self, segment_index: int, force: bool = False) -> bool:
        """
        生成指定段

        Args:
            segment_index: 段索引
            force: 强制重新生成

        Returns:
            bool: 是否成功
        """
        segment = self.pipeline.get_segment(segment_index)
        if not segment:
            print(f"Error: Segment {segment_index} not found")
            return False

        # 检查是否需要生成
        if not force and segment.status in ["generated", "confirmed"]:
            print(f"Segment {segment_index} already generated (status: {segment.status})")
            print("Use --force to regenerate")
            return True

        print(f"\n{'='*60}")
        print(f"🎬 生成第 {segment_index + 1} 段: {segment.time_range}")
        print(f"   Scenes: {segment.scenes}")
        print(f"   时长: {segment.end_time - segment.start_time:.1f} 秒")
        print(f"{'='*60}\n")

        # 更新状态为 generating
        self.pipeline.update_segment(segment_index, "generating")

        try:
            # 1. 创建段目录
            seg_dir = self._create_segment_dir(segment)

            # 2. 生成分段音频（合并本段所有 scenes）
            self._generate_segment_audio(segment, seg_dir)

            # 3. 创建分段 Manim 脚本
            self._create_segment_script(segment, seg_dir)

            # 4. 渲染视频（如果 skip_render 为 False）
            if self.skip_render:
                print("\n" + "="*60)
                print("⏭️  跳过渲染（--skip-render 模式）")
                print("="*60)
                print("\n✅ 分段脚本已生成，如需手动渲染，请执行：")
                print(f"\n   cd {seg_dir}")
                print(f"   manim -qh script.py ExplainerScene")
                print(f"\n   # 渲染完成后播放预览：")
                print(f"   ffplay -autoexit media/videos/script/1080p60/ExplainerScene.mp4")
                print(f"   # 或 macOS: open media/videos/script/1080p60/ExplainerScene.mp4")
                print("\n观看后告知 Claude Code 结果，继续下一段。")
                print("="*60)
            else:
                self._render_segment_video(segment, seg_dir)

            # 5. 生成字幕
            self._generate_subtitle(segment, seg_dir)

            # 6. 保存元数据
            self._save_metadata(segment, seg_dir)

            # 7. 更新状态
            if self.skip_render:
                self.pipeline.update_segment(segment_index, "scripts_ready")
                print(f"\n✅ 第 {segment_index + 1} 段脚本生成完成!")
                print(f"   状态: scripts_ready (等待用户渲染)")
            else:
                self.pipeline.update_segment(segment_index, "generated")
                print(f"\n✅ 第 {segment_index + 1} 段生成完成!")
                print(f"   视频: {segment.video_path}")
            return True

        except Exception as e:
            print(f"\n❌ 生成失败: {e}")
            self.pipeline.update_segment(segment_index, "pending")
            raise

    def _create_segment_dir(self, segment: Segment) -> Path:
        """创建段目录"""
        dir_name = f"{segment.id}_{segment.time_range.replace(':', '_')}"
        seg_dir = self.segments_dir / dir_name
        seg_dir.mkdir(parents=True, exist_ok=True)
        print(f"✓ 创建目录: {seg_dir}")
        return seg_dir

    def _generate_segment_audio(self, segment: Segment, seg_dir: Path):
        """生成分段音频（合并本段所有 scene 的音频）"""
        print("\n🔊 步骤 1/5: 生成分段音频")
        print("-" * 40)

        # 读取 audio_info.json
        audio_info_file = self.audio_dir / "audio_info.json"
        if not audio_info_file.exists():
            raise FileNotFoundError(f"Audio info not found: {audio_info_file}")

        with open(audio_info_file, 'r', encoding='utf-8') as f:
            audio_info = json.load(f)

        # 找到本段需要的音频文件
        audio_files = []
        for item in audio_info.get("files", []):
            scene_num = item.get("scene", 0)
            if scene_num in segment.scenes:
                audio_path = self.audio_dir / item["file"]
                if audio_path.exists():
                    audio_files.append({
                        "file": str(audio_path),
                        "scene": scene_num,
                        "text": item.get("text", "")
                    })

        if not audio_files:
            raise RuntimeError(f"No audio files found for scenes: {segment.scenes}")

        # 按 scene 顺序排序
        audio_files.sort(key=lambda x: x["scene"])

        # 生成合并音频的输入列表
        concat_list = seg_dir / "concat_list.txt"
        with open(concat_list, 'w', encoding='utf-8') as f:
            for af in audio_files:
                f.write(f"file '{af['file']}'\n")

        # 使用 ffmpeg 合并音频
        output_audio = seg_dir / "audio.wav"

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            "-ac", "2",
            str(output_audio)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg failed: {result.stderr}")

            print(f"✓ 合并音频: {len(audio_files)} 个文件")
            print(f"✓ 输出: {output_audio}")

        except FileNotFoundError:
            print("⚠️  ffmpeg not found, trying alternative method...")
            # 备用：直接复制第一个音频文件
            if audio_files:
                shutil.copy2(audio_files[0]["file"], output_audio)
                print(f"✓ 复制音频（备用方法）: {output_audio}")

        # 清理
        concat_list.unlink(missing_ok=True)

    def _create_segment_script(self, segment: Segment, seg_dir: Path):
        """创建分段 Manim 脚本"""
        print("\n📝 步骤 2/5: 创建分段脚本")
        print("-" * 40)

        if not self.script_file.exists():
            raise FileNotFoundError(f"Script file not found: {self.script_file}")

        # 读取原脚本
        with open(self.script_file, 'r', encoding='utf-8') as f:
            original_script = f.read()

        # 创建分段脚本
        seg_script = self._modify_script_for_segment(original_script, segment)

        # 保存
        seg_script_file = seg_dir / "script.py"
        with open(seg_script_file, 'w', encoding='utf-8') as f:
            f.write(seg_script)

        print(f"✓ 分段脚本: {seg_script_file}")

    def _modify_script_for_segment(self, script: str, segment: Segment) -> str:
        """修改脚本，只渲染指定 scenes"""
        # 提取 scene 范围
        scene_range = f"SCENE_RANGE = {segment.scenes}"

        # 在脚本开头添加 scene range
        modified = f'''# Auto-generated segment script
# Scenes: {segment.scenes}
# Time range: {segment.time_range}

{scene_range}

# Original script below (modified for segment rendering):

{script}
'''

        # 修改 construct 方法，只渲染指定 scenes
        # 在原有脚本中插入过滤逻辑
        modified = modified.replace(
            "def construct(self):",
            f'''def construct(self):
        # Segment rendering: only scenes {segment.scenes}
        self._segment_scenes = {segment.scenes}
'''
        )

        # 修改音频目录指向
        modified = modified.replace(
            'self.audio_dir = "audio"',
            f'self.audio_dir = "."'
        )

        return modified

    def _render_segment_video(self, segment: Segment, seg_dir: Path,
                              max_retries: int = CONFIG.segment.max_retries):
        """
        渲染分段视频（带重试机制）

        Args:
            segment: 段信息
            seg_dir: 段目录
            max_retries: 最大重试次数（默认3次）
        """
        print("\n🎬 步骤 3/5: 渲染视频")
        print("-" * 40)

        seg_script = seg_dir / "script.py"

        # 构建 manim 命令
        cmd = [
            "manim",
            "-qh",  # high quality
            "--fps", "60",
            str(seg_script),
            "ExplainerScene"
        ]

        print(f"执行: {' '.join(cmd)}")
        print(f"工作目录: {seg_dir}")

        # 重试循环
        last_error = None
        for attempt in range(max_retries):
            if attempt > 0:
                print(f"\n🔄 第 {attempt + 1}/{max_retries} 次重试...")

            try:
                result = subprocess.run(cmd, cwd=seg_dir, capture_output=True, text=True)

                if result.returncode == 0:
                    # 成功，跳出重试循环
                    break

                # 失败，记录错误
                last_error = f"Manim render failed: {result.returncode}"
                print(f"  渲染失败 (attempt {attempt + 1}): {last_error}")

                if attempt < max_retries - 1:
                    import time
                    time.sleep(CONFIG.segment.retry_delay)

            except FileNotFoundError:
                raise RuntimeError("manim command not found. Please install manim.")
            except Exception as e:
                last_error = str(e)
                print(f"  异常 (attempt {attempt + 1}): {e}")

                if attempt < max_retries - 1:
                    import time
                    time.sleep(CONFIG.segment.retry_delay)

        else:
            # 所有重试都失败
            print(f"\n❌ 渲染失败，已重试 {max_retries} 次")
            print(f"STDOUT: {result.stdout if 'result' in dir() else 'N/A'}")
            print(f"STDERR: {result.stderr if 'result' in dir() else 'N/A'}")
            raise RuntimeError(f"Manim render failed after {max_retries} retries: {last_error}")

        # 查找生成的视频
        media_dir = seg_dir / "media" / "videos" / "script"
        possible_paths = [
            media_dir / "1080p60" / "ExplainerScene.mp4",
            media_dir / "720p30" / "ExplainerScene.mp4",
        ]

        video_src = None
        for path in possible_paths:
            if path.exists():
                video_src = path
                break

        if video_src:
            video_dst = seg_dir / "video.mp4"
            shutil.copy2(video_src, video_dst)
            print(f"✓ 视频已生成: {video_dst}")
        else:
            raise RuntimeError("Video file not found after render")

    def _generate_subtitle(self, segment: Segment, seg_dir: Path):
        """生成字幕文件"""
        print("\n📜 步骤 4/5: 生成字幕")
        print("-" * 40)

        # 读取 audio_info
        audio_info_file = self.audio_dir / "audio_info.json"
        if not audio_info_file.exists():
            print("⚠️  audio_info.json not found, skipping subtitle")
            return

        with open(audio_info_file, 'r', encoding='utf-8') as f:
            audio_info = json.load(f)

        # 收集本段的字幕
        subtitles = []
        current_time = segment.start_time

        for item in audio_info.get("files", []):
            scene_num = item.get("scene", 0)
            if scene_num in segment.scenes:
                duration = item.get("duration", 5.0)
                text = item.get("text", "")

                subtitles.append({
                    "index": len(subtitles) + 1,
                    "start": current_time - segment.start_time,  # 相对于段开始
                    "end": current_time - segment.start_time + duration,
                    "text": text
                })

                current_time += duration

        # 生成 SRT 格式
        srt_content = self._generate_srt(subtitles)
        srt_file = seg_dir / "subtitle.srt"
        srt_file.write_text(srt_content, encoding='utf-8')

        print(f"✓ 字幕生成: {srt_file} ({len(subtitles)} 条)")

    def _generate_srt(self, subtitles: List[Dict]) -> str:
        """生成 SRT 格式字幕"""
        lines = []
        for sub in subtitles:
            lines.append(str(sub["index"]))
            lines.append(f"{self._format_srt_time(sub['start'])} --> {self._format_srt_time(sub['end'])}")
            lines.append(sub["text"])
            lines.append("")
        return "\n".join(lines)

    def _format_srt_time(self, seconds: float) -> str:
        """格式化为 SRT 时间格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _save_metadata(self, segment: Segment, seg_dir: Path):
        """保存段元数据"""
        print("\n💾 步骤 5/5: 保存元数据")
        print("-" * 40)

        metadata = {
            "segment": segment.to_dict(),
            "generated_at": subprocess.check_output(["date", "+%Y-%m-%dT%H:%M:%S"]).decode().strip(),
            "files": {
                "video": str(seg_dir / "video.mp4"),
                "audio": str(seg_dir / "audio.wav"),
                "subtitle": str(seg_dir / "subtitle.srt"),
                "script": str(seg_dir / "script.py")
            }
        }

        metadata_file = seg_dir / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        print(f"✓ 元数据: {metadata_file}")

    def generate_next(self, force: bool = False) -> bool:
        """生成下一段"""
        current = self.pipeline.get_current_segment()
        if not current:
            print("All segments are already generated and confirmed!")
            return True

        return self.generate(current.index, force)

    def get_segment_info(self, segment_index: int) -> Optional[Dict]:
        """获取段信息"""
        segment = self.pipeline.get_segment(segment_index)
        if not segment:
            return None

        seg_dir = self.segments_dir / f"{segment.id}_{segment.time_range.replace(':', '_')}"

        return {
            "segment": segment.to_dict(),
            "directory": str(seg_dir),
            "files_exist": {
                "video": (seg_dir / "video.mp4").exists(),
                "audio": (seg_dir / "audio.wav").exists(),
                "subtitle": (seg_dir / "subtitle.srt").exists(),
                "script": (seg_dir / "script.py").exists(),
            }
        }


def main():
    parser = argparse.ArgumentParser(description="Segment Video Generator")
    parser.add_argument("--project", "-p", default=".", help="Project directory")
    parser.add_argument("--segment", "-s", type=int, help="Segment index to generate")
    parser.add_argument("--next", "-n", action="store_true", help="Generate next segment")
    parser.add_argument("--force", "-f", action="store_true", help="Force regeneration")
    parser.add_argument("--background", "-b", action="store_true", help="Run in background mode")
    parser.add_argument("--info", "-i", type=int, help="Show segment info")
    parser.add_argument("--skip-render", action="store_true",
                       help="Skip video rendering, only generate scripts (for Claude Code)")

    args = parser.parse_args()

    project_dir = Path(args.project)
    if not project_dir.exists():
        print(f"Error: Project directory does not exist: {project_dir}")
        return 1

    # 检查流水线是否存在
    pipeline_file = project_dir / "segment_pipeline.json"
    if not pipeline_file.exists():
        print(f"Error: Pipeline not initialized. Run segment_pipeline.py --init first.")
        return 1

    generator = SegmentGenerator(project_dir, skip_render=args.skip_render)

    if args.info is not None:
        info = generator.get_segment_info(args.info)
        if info:
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            print(f"Segment {args.info} not found")
        return 0

    if args.next:
        success = generator.generate_next(args.force)
        return 0 if success else 1

    if args.segment is not None:
        success = generator.generate(args.segment, args.force)
        return 0 if success else 1

    # 默认：显示帮助
    parser.print_help()
    return 0


if __name__ == "__main__":
    exit(main())
