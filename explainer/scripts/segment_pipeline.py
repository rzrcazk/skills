#!/usr/bin/env python3
"""
Segment Pipeline - 分段流水线管理器

功能：
1. 初始化流水线（将分镜拆分为段）
2. 管理分段状态（持久化到 segment_pipeline.json）
3. 提供分段查询和状态更新接口

使用：
    # 初始化流水线
    python segment_pipeline.py --project . --init

    # 获取当前段信息
    python segment_pipeline.py --project . --current

    # 更新段状态
    python segment_pipeline.py --project . --update-segment 0 --status confirmed

    # 列出所有段
    python segment_pipeline.py --project . --list
"""

import json
import re
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict

sys.path.insert(0, str(Path(__file__).parent))
from config import CONFIG
from utils import atomic_write_json, find_storyboard
from logger import get_logger

logger = get_logger(__name__)


@dataclass
class Segment:
    """分段信息"""
    id: str
    index: int
    time_range: str
    start_time: float
    end_time: float
    scenes: List[int]
    status: str = "pending"  # pending, generating, scripts_ready, rendering, generated, confirmed, rejected, fixing
    video_path: Optional[str] = None
    audio_path: Optional[str] = None
    subtitle_path: Optional[str] = None
    metadata_path: Optional[str] = None
    confirmed_at: Optional[str] = None
    issues: List[Dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Segment":
        return cls(**data)

    def update_status(self, status: str, issues: List[Dict] = None):
        """更新状态"""
        self.status = status
        self.updated_at = datetime.now().isoformat()
        if issues:
            self.issues = issues
        if status == "confirmed":
            self.confirmed_at = datetime.now().isoformat()


class SegmentPipeline:
    """分段流水线管理器"""

    DEFAULT_SEGMENT_DURATION = CONFIG.segment.default_duration

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.pipeline_file = self.project_dir / CONFIG.state.segment_pipeline_file
        self.data = self._load_or_init()

    def _load_or_init(self) -> dict:
        """加载或初始化流水线"""
        if self.pipeline_file.exists():
            with open(self.pipeline_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return self._create_empty_pipeline()

    def _create_empty_pipeline(self) -> dict:
        """创建空流水线结构"""
        return {
            "content_id": "",
            "content_path": str(self.project_dir),
            "total_scenes": 0,
            "total_duration": 0,
            "target_segment_duration": self.DEFAULT_SEGMENT_DURATION,
            "segments": [],
            "current_segment_index": 0,
            "merged_up_to_index": -1,
            "final_video_path": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

    def save(self):
        """保存流水线状态（原子写入）"""
        self.data["updated_at"] = datetime.now().isoformat()
        atomic_write_json(self.pipeline_file, self.data)
        logger.debug("流水线状态已保存: %s", self.pipeline_file)

    def init_from_storyboard(self, storyboard_path: Optional[Path] = None,
                            audio_info_path: Optional[Path] = None,
                            target_duration: int = DEFAULT_SEGMENT_DURATION):
        """
        从分镜脚本初始化流水线

        Args:
            storyboard_path: 分镜脚本路径（默认: 分镜脚本.md）
            audio_info_path: 音频信息路径（默认: audio/audio_info.json）
            target_duration: 目标段时长（秒）
        """
        # 查找分镜脚本
        if storyboard_path is None:
            storyboard_path = self._find_storyboard()
        if not storyboard_path or not storyboard_path.exists():
            raise FileNotFoundError(f"分镜脚本不存在: {storyboard_path}")

        # 查找音频信息
        if audio_info_path is None:
            audio_info_path = self.project_dir / "audio" / "audio_info.json"

        audio_info = {}
        if audio_info_path.exists():
            with open(audio_info_path, 'r', encoding='utf-8') as f:
                audio_info = json.load(f)

        # 解析分镜
        scenes = self._parse_storyboard(storyboard_path, audio_info)

        # 分组到段
        segments = self._group_scenes_to_segments(scenes, target_duration)

        # 更新流水线
        self.data["content_id"] = self.project_dir.name
        self.data["total_scenes"] = len(scenes)
        self.data["total_duration"] = sum(s["duration"] for s in scenes)
        self.data["target_segment_duration"] = target_duration
        self.data["segments"] = [s.to_dict() for s in segments]
        self.data["current_segment_index"] = 0
        self.data["merged_up_to_index"] = -1

        self.save()
        logger.info("流水线初始化完成: %d 个分段", len(segments))
        return segments

    def _find_storyboard(self) -> Optional[Path]:
        """查找分镜脚本文件（委托给 utils.find_storyboard）"""
        return find_storyboard(self.project_dir)

    def _parse_storyboard(self, storyboard_path: Path, audio_info: dict) -> List[Dict]:
        """解析分镜脚本，提取scene信息"""
        scenes = []

        # 从audio_info获取时长信息
        audio_files = {item.get("scene", 0): item for item in audio_info.get("files", [])}

        with open(storyboard_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 匹配分镜格式：## 幕X 或 ## Scene X 或 ### X.
        pattern = r'(?:##|###)\s*(?:幕|Scene|场景)?\s*(\d+)[\.:\s]*([^\n]*)'
        matches = list(re.finditer(pattern, content, re.IGNORECASE))

        for i, match in enumerate(matches):
            scene_num = int(match.group(1))
            scene_name = match.group(2).strip() if match.group(2) else f"Scene {scene_num}"

            # 获取时长
            duration = audio_files.get(scene_num, {}).get("duration", 5.0)
            audio_file = audio_files.get(scene_num, {}).get("file", f"audio_{scene_num:03d}.wav")

            scenes.append({
                "num": scene_num,
                "name": scene_name,
                "duration": duration,
                "audio_file": audio_file,
                "start_time": 0,  # 稍后计算
                "end_time": 0
            })

        # 计算每个scene的绝对时间
        current_time = 0
        for scene in scenes:
            scene["start_time"] = current_time
            scene["end_time"] = current_time + scene["duration"]
            current_time = scene["end_time"]

        logger.info("解析分镜: %d 个scene，总时长 %.1f 秒", len(scenes), current_time)
        return scenes

    def _group_scenes_to_segments(self, scenes: List[Dict],
                                   target_duration: int) -> List[Segment]:
        """将scenes分组到segments"""
        segments = []
        current_scenes = []
        current_duration = 0
        segment_index = 0

        for scene in scenes:
            scene_duration = scene["duration"]

            # 如果单个scene就超过目标时长，单独成段
            if scene_duration >= target_duration and not current_scenes:
                current_scenes = [scene["num"]]
                current_duration = scene_duration
                # 立即创建段
                segment = self._create_segment(segment_index, current_scenes, scenes)
                segments.append(segment)
                segment_index += 1
                current_scenes = []
                current_duration = 0
            # 如果加入当前scene会超过目标时长，先结束当前段
            elif current_duration + scene_duration > target_duration and current_scenes:
                # 创建段
                segment = self._create_segment(segment_index, current_scenes, scenes)
                segments.append(segment)
                segment_index += 1
                # 开始新段
                current_scenes = [scene["num"]]
                current_duration = scene_duration
            else:
                current_scenes.append(scene["num"])
                current_duration += scene_duration

        # 处理剩余的scenes
        if current_scenes:
            segment = self._create_segment(segment_index, current_scenes, scenes)
            segments.append(segment)

        return segments

    def _create_segment(self, index: int, scene_nums: List[int],
                        all_scenes: List[Dict]) -> Segment:
        """创建段对象"""
        # 找到这些scenes的时间范围
        scene_data = [s for s in all_scenes if s["num"] in scene_nums]
        if not scene_data:
            raise ValueError(f"Invalid scene numbers: {scene_nums}")

        start_time = min(s["start_time"] for s in scene_data)
        end_time = max(s["end_time"] for s in scene_data)
        duration = end_time - start_time

        # 格式化时间范围
        time_range = f"{self._format_time(start_time)}-{self._format_time(end_time)}"

        # 段ID
        seg_id = f"seg_{index+1:03d}"

        # 目录名
        dir_name = f"{seg_id}_{time_range.replace(':', '_')}"

        # 路径
        base_path = f"segments/{dir_name}"

        return Segment(
            id=seg_id,
            index=index,
            time_range=time_range,
            start_time=start_time,
            end_time=end_time,
            scenes=scene_nums,
            video_path=f"{base_path}/video.mp4",
            audio_path=f"{base_path}/audio.wav",
            subtitle_path=f"{base_path}/subtitle.srt",
            metadata_path=f"{base_path}/metadata.json"
        )

    def _format_time(self, seconds: float) -> str:
        """格式化时间为 M_SS（用于文件名）"""
        from utils import format_time
        return format_time(seconds, "underscore")

    def get_segment(self, index: int) -> Optional[Segment]:
        """获取指定段"""
        if 0 <= index < len(self.data["segments"]):
            return Segment.from_dict(self.data["segments"][index])
        return None

    def get_current_segment(self) -> Optional[Segment]:
        """获取当前段（第一个非 confirmed 的段）"""
        for seg_data in self.data["segments"]:
            if seg_data["status"] != "confirmed":
                return Segment.from_dict(seg_data)
        return None

    def get_next_segment(self) -> Optional[Segment]:
        """获取下一段"""
        current = self.data["current_segment_index"]
        return self.get_segment(current + 1)

    def update_segment(self, index: int, status: str, issues: List[Dict] = None,
                       **kwargs):
        """更新段状态"""
        if 0 <= index < len(self.data["segments"]):
            seg_data = self.data["segments"][index]
            seg_data["status"] = status
            seg_data["updated_at"] = datetime.now().isoformat()

            if issues:
                seg_data["issues"] = issues
            if status == "confirmed":
                seg_data["confirmed_at"] = datetime.now().isoformat()
                self.data["current_segment_index"] = max(
                    self.data["current_segment_index"], index + 1
                )

            # 更新其他字段
            for key, value in kwargs.items():
                seg_data[key] = value

            self.save()
            logger.info("段 %d 状态更新为: %s", index, status)
            return True
        return False

    def get_progress(self) -> Dict:
        """获取进度信息"""
        total = len(self.data["segments"])
        confirmed = sum(1 for s in self.data["segments"] if s["status"] == "confirmed")
        generated = sum(1 for s in self.data["segments"] if s["status"] in ["generated", "confirmed"])
        scripts_ready = sum(1 for s in self.data["segments"] if s["status"] == "scripts_ready")

        current = self.get_current_segment()

        return {
            "total_segments": total,
            "confirmed_segments": confirmed,
            "generated_segments": generated,
            "scripts_ready": scripts_ready,
            "progress_percent": (confirmed / total * 100) if total > 0 else 0,
            "current_segment_index": current.index if current else None,
            "current_segment_id": current.id if current else None,
            "is_complete": confirmed == total
        }

    def list_segments(self) -> List[Segment]:
        """列出所有段"""
        return [Segment.from_dict(s) for s in self.data["segments"]]

    def get_merged_path(self, up_to_index: int) -> str:
        """获取合并视频路径"""
        seg = self.get_segment(up_to_index)
        if not seg:
            return ""
        return f"merged/merged_{seg.id}_{seg.time_range.replace(':', '_')}.mp4"

    def set_final_video(self, path: str):
        """设置最终视频路径"""
        self.data["final_video_path"] = path
        self.save()


def main():
    parser = argparse.ArgumentParser(description="Segment Pipeline Manager")
    parser.add_argument("--project", "-p", default=".", help="Project directory")
    parser.add_argument("--init", action="store_true", help="Initialize pipeline")
    parser.add_argument("--storyboard", "-s", help="Storyboard file path")
    parser.add_argument("--audio-info", "-a", help="Audio info file path")
    parser.add_argument("--target-duration", "-t", type=int, default=20,
                       help="Target segment duration in seconds")
    parser.add_argument("--current", action="store_true", help="Get current segment")
    parser.add_argument("--list", "-l", action="store_true", help="List all segments")
    parser.add_argument("--update-segment", "-u", type=int, help="Update segment status")
    parser.add_argument("--status", help="New status (for --update-segment)")
    parser.add_argument("--progress", action="store_true", help="Show progress")

    args = parser.parse_args()

    project_dir = Path(args.project)
    if not project_dir.exists():
        print(f"Error: Project directory does not exist: {project_dir}")
        return 1

    pipeline = SegmentPipeline(project_dir)

    if args.init:
        storyboard = Path(args.storyboard) if args.storyboard else None
        audio_info = Path(args.audio_info) if args.audio_info else None
        pipeline.init_from_storyboard(storyboard, audio_info, args.target_duration)
        return 0

    if args.current:
        seg = pipeline.get_current_segment()
        if seg:
            print(json.dumps(seg.to_dict(), ensure_ascii=False, indent=2))
        else:
            print("All segments confirmed!")
        return 0

    if args.list:
        segments = pipeline.list_segments()
        print(f"\n{'Index':<6}{'ID':<12}{'Time':<15}{'Scenes':<20}{'Status':<12}")
        print("-" * 65)
        for seg in segments:
            scenes_str = ",".join(map(str, seg.scenes[:5]))
            if len(seg.scenes) > 5:
                scenes_str += "..."
            print(f"{seg.index:<6}{seg.id:<12}{seg.time_range:<15}{scenes_str:<20}{seg.status:<12}")
        print()
        return 0

    if args.progress:
        progress = pipeline.get_progress()
        print(json.dumps(progress, ensure_ascii=False, indent=2))
        return 0

    if args.update_segment is not None:
        if not args.status:
            print("Error: --status required with --update-segment")
            return 1
        success = pipeline.update_segment(args.update_segment, args.status)
        return 0 if success else 1

    # 默认：显示帮助
    parser.print_help()
    return 0


if __name__ == "__main__":
    exit(main())
