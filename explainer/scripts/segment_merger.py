#!/usr/bin/env python3
"""
Segment Merger - 分段视频合并器

功能：
1. 合并已确认的段视频
2. 生成累积视频（1段、1+2段、1+2+3段...）
3. 合并字幕
4. 生成最终视频

使用：
    # 合并到指定段（包含段 0 到 N）
    python segment_merger.py --project . --upto 2

    # 合并全部（生成最终视频）
    python segment_merger.py --project . --final

    # 指定输出文件名
    python segment_merger.py --project . --final --output final_video.mp4
"""

import json
import subprocess
import argparse
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent))
from segment_pipeline import SegmentPipeline, Segment


class SegmentMerger:
    """分段视频合并器"""

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.pipeline = SegmentPipeline(project_dir)

        self.segments_dir = self.project_dir / "segments"
        self.merged_dir = self.project_dir / "merged"
        self.merged_dir.mkdir(exist_ok=True)

    def merge_up_to(self, up_to_index: int, output_name: Optional[str] = None) -> Optional[Path]:
        """
        合并从 0 到指定索引的所有段

        Args:
            up_to_index: 合并到的段索引（包含）
            output_name: 输出文件名（可选）

        Returns:
            Path: 输出视频路径
        """
        # 获取需要合并的段
        segments = []
        for i in range(up_to_index + 1):
            segment = self.pipeline.get_segment(i)
            if not segment:
                print(f"Error: Segment {i} not found")
                return None
            if segment.status != "confirmed":
                print(f"Error: Segment {i} is not confirmed (status: {segment.status})")
                return None
            segments.append(segment)

        if not segments:
            print("Error: No segments to merge")
            return None

        print(f"\n{'='*60}")
        print(f"🎬 合并视频: 段 0 到 {up_to_index}")
        print(f"   共 {len(segments)} 个段")
        print(f"{'='*60}\n")

        # 生成输出文件名
        if output_name:
            output_file = self.merged_dir / output_name
        else:
            last_seg = segments[-1]
            output_file = self.merged_dir / f"merged_{last_seg.id}_{last_seg.time_range.replace(':', '_')}.mp4"

        # 合并视频
        video_result = self._merge_videos(segments, output_file)
        if not video_result:
            return None

        # 合并字幕
        subtitle_file = output_file.with_suffix('.srt')
        self._merge_subtitles(segments, subtitle_file)

        # 更新流水线状态
        self.pipeline.data["merged_up_to_index"] = up_to_index
        self.pipeline.save()

        print(f"\n✅ 合并完成!")
        print(f"   视频: {output_file}")
        print(f"   字幕: {subtitle_file}")

        return output_file

    def merge_final(self, output_name: Optional[str] = None) -> Optional[Path]:
        """
        合并所有段生成最终视频

        Args:
            output_name: 输出文件名（可选）

        Returns:
            Path: 最终视频路径
        """
        total_segments = len(self.pipeline.data["segments"])

        # 检查是否全部 confirmed
        for i in range(total_segments):
            segment = self.pipeline.get_segment(i)
            if segment.status != "confirmed":
                print(f"Error: Segment {i} is not confirmed (status: {segment.status})")
                print("Please confirm all segments before generating final video.")
                return None

        # 合并全部
        final_name = output_name or f"{self.project_dir.name}_final.mp4"
        output_file = self.merge_up_to(total_segments - 1, final_name)

        if output_file:
            # 更新最终视频路径
            self.pipeline.set_final_video(str(output_file))

            # 同时拷贝到 output 目录
            output_dir = self.project_dir / "output"
            output_dir.mkdir(exist_ok=True)

            final_output = output_dir / final_name
            import shutil
            shutil.copy2(output_file, final_output)
            print(f"   最终视频已拷贝到: {final_output}")

        return output_file

    def _merge_videos(self, segments: List[Segment], output_file: Path) -> bool:
        """使用 ffmpeg 合并视频"""
        print("📼 合并视频...")

        # 创建 concat 列表文件
        concat_list = self.merged_dir / "video_concat_list.txt"
        with open(concat_list, 'w', encoding='utf-8') as f:
            for seg in segments:
                video_path = self.project_dir / seg.video_path
                if video_path.exists():
                    # ffmpeg concat 需要特定格式
                    f.write(f"file '{video_path.absolute()}'\n")
                else:
                    print(f"⚠️  Video not found: {video_path}")
                    return False

        # 构建 ffmpeg 命令
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",  # 直接复制，不重新编码
            str(output_file)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"FFmpeg error: {result.stderr}")
                return False

            print(f"✓ 视频合并完成: {output_file}")
            return True

        except FileNotFoundError:
            print("Error: ffmpeg not found. Please install ffmpeg.")
            return False

        finally:
            # 清理临时文件
            concat_list.unlink(missing_ok=True)

    def _merge_subtitles(self, segments: List[Segment], output_file: Path):
        """合并字幕文件"""
        print("📜 合并字幕...")

        all_subtitles = []
        time_offset = 0

        for seg in segments:
            subtitle_path = self.project_dir / seg.subtitle_path
            if not subtitle_path.exists():
                continue

            # 解析 SRT
            subtitles = self._parse_srt(subtitle_path)

            # 调整时间戳
            for sub in subtitles:
                sub["start"] += time_offset
                sub["end"] += time_offset
                sub["index"] = len(all_subtitles) + 1
                all_subtitles.append(sub)

            # 更新时间偏移
            time_offset += (seg.end_time - seg.start_time)

        # 生成合并后的 SRT
        srt_content = self._generate_srt(all_subtitles)
        output_file.write_text(srt_content, encoding='utf-8')

        print(f"✓ 字幕合并完成: {len(all_subtitles)} 条字幕")

    def _parse_srt(self, srt_path: Path) -> List[dict]:
        """解析 SRT 文件"""
        content = srt_path.read_text(encoding='utf-8')
        subtitles = []

        blocks = content.strip().split('\n\n')
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) >= 3:
                index = lines[0].strip()
                time_line = lines[1].strip()
                text = '\n'.join(lines[2:])

                # 解析时间
                start_str, end_str = time_line.split(' --> ')
                start = self._parse_srt_time(start_str)
                end = self._parse_srt_time(end_str)

                subtitles.append({
                    "index": int(index),
                    "start": start,
                    "end": end,
                    "text": text
                })

        return subtitles

    def _parse_srt_time(self, time_str: str) -> float:
        """解析 SRT 时间格式"""
        # 格式: 00:00:05,000
        time_str = time_str.replace(',', '.')
        parts = time_str.split(':')

        hours = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2])

        return hours * 3600 + minutes * 60 + seconds

    def _generate_srt(self, subtitles: List[dict]) -> str:
        """生成 SRT 格式"""
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

    def get_merge_info(self) -> dict:
        """获取合并信息"""
        total = len(self.pipeline.data["segments"])
        merged_up_to = self.pipeline.data["merged_up_to_index"]

        confirmed = []
        pending = []

        for i in range(total):
            segment = self.pipeline.get_segment(i)
            if segment.status == "confirmed":
                confirmed.append(i)
            else:
                pending.append(i)

        return {
            "total_segments": total,
            "confirmed_segments": confirmed,
            "pending_segments": pending,
            "merged_up_to_index": merged_up_to,
            "can_merge_up_to": len(confirmed) - 1 if confirmed else -1,
            "merged_files": [str(f) for f in self.merged_dir.glob("merged_*.mp4")]
        }


def main():
    parser = argparse.ArgumentParser(description="Segment Video Merger")
    parser.add_argument("--project", "-p", default=".", help="Project directory")
    parser.add_argument("--upto", "-u", type=int, help="Merge up to segment index")
    parser.add_argument("--final", "-f", action="store_true", help="Merge all segments to final video")
    parser.add_argument("--output", "-o", help="Output filename")
    parser.add_argument("--info", "-i", action="store_true", help="Show merge info")

    args = parser.parse_args()

    project_dir = Path(args.project)
    if not project_dir.exists():
        print(f"Error: Project directory does not exist: {project_dir}")
        return 1

    pipeline_file = project_dir / "segment_pipeline.json"
    if not pipeline_file.exists():
        print(f"Error: Pipeline not initialized.")
        return 1

    merger = SegmentMerger(project_dir)

    if args.info:
        info = merger.get_merge_info()
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0

    if args.final:
        output = merger.merge_final(args.output)
        return 0 if output else 1

    if args.upto is not None:
        output = merger.merge_up_to(args.upto, args.output)
        return 0 if output else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    exit(main())
