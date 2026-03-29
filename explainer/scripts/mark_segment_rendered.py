#!/usr/bin/env python3
"""
Mark Segment Rendered - 标记段已渲染

功能：
在视频渲染完成后，更新流水线状态为 "generated"
可用于 Claude Code 渲染后或用户终端渲染后更新状态

使用：
    python mark_segment_rendered.py --project . --segment 0
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from segment_pipeline import SegmentPipeline


def main():
    parser = argparse.ArgumentParser(description="Mark Segment as Rendered")
    parser.add_argument("--project", "-p", default=".", help="Project directory")
    parser.add_argument("--segment", "-s", type=int, required=True, help="Segment index")

    args = parser.parse_args()

    project_dir = Path(args.project)
    if not project_dir.exists():
        print(f"Error: Project directory does not exist: {project_dir}")
        return 1

    pipeline_file = project_dir / "segment_pipeline.json"
    if not pipeline_file.exists():
        print(f"Error: Pipeline not initialized.")
        return 1

    pipeline = SegmentPipeline(project_dir)
    segment = pipeline.get_segment(args.segment)

    if not segment:
        print(f"Error: Segment {args.segment} not found")
        return 1

    if segment.status == "generated":
        print(f"✓ 段 {args.segment} 已经是 generated 状态")
        return 0

    if segment.status != "scripts_ready":
        print(f"Error: Segment {args.segment} status is {segment.status}, expected scripts_ready")
        return 1

    # 更新状态为 generated
    pipeline.update_segment(args.segment, "generated")
    print(f"✅ 段 {args.segment} 已标记为 generated")
    print(f"   现在可以在 Claude Code 中继续处理下一段")

    return 0


if __name__ == "__main__":
    exit(main())
