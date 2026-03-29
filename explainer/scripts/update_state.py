#!/usr/bin/env python3
"""
工作流状态更新脚本
用于AI自动调用，记录进度和更新状态

用法:
    python3 update_state.py <内容目录路径> [选项]

示例:
    # 更新当前步骤
    python3 update_state.py 数学/几何/勾股定理/ --step 3.5 --status pending_confirmation

    # 标记检查点已确认
    python3 update_state.py 数学/几何/勾股定理/ --checkpoint 2 --confirmed \
        --feedback "用户满意，继续生成"

    # 标记内容已压缩
    python3 update_state.py 数学/几何/勾股定理/ --compressed \
        --original "12分钟" --current "7分钟"
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from state_manager import StateManager

STEP_NAMES = {
    0: "select_category",
    1: "knowledge_level",
    2: "topic_analysis",
    2.5: "outline_confirmation",
    3: "html_preview",
    3.5: "preview_confirmation",
    4: "storyboard",
    4.5: "storyboard_confirmation",
    5: "generate_tts",
    6: "validate_audio",
    7: "scaffold",
    8: "implement",
    9: "check_and_render",
    10: "update_index",
}


def get_manager(content_dir: Path) -> StateManager:
    """获取 StateManager，自动迁移旧状态文件"""
    manager = StateManager(content_dir)
    workflow_file = content_dir / "workflow_state.json"
    if not manager.state_file.exists() and workflow_file.exists():
        manager.migrate_from_workflow_state(workflow_file)
    return manager


def update_step(manager: StateManager, step: float, status: str = None):
    """更新当前步骤"""
    step_name = STEP_NAMES.get(step, f"step_{step}")
    manager.set_workflow_step(step, status)
    manager._state["current_step_name"] = step_name
    manager.save()
    print(f"已更新步骤: {step} - {step_name}")
    if status:
        print(f"已更新状态: {status}")


def confirm_checkpoint(manager: StateManager, checkpoint_num: int, feedback: str = None):
    """标记检查点为已确认"""
    manager.set_checkpoint(checkpoint_num, "confirmed", feedback)
    print(f"检查点 {checkpoint_num} 已确认")
    if feedback:
        print(f"用户反馈: {feedback}")


def mark_checkpoint_pending(manager: StateManager, checkpoint_num: int, file: str = None):
    """标记检查点为等待确认"""
    manager.set_checkpoint(checkpoint_num, "pending")
    if file:
        key = f"checkpoint{checkpoint_num}"
        manager._state.setdefault("checkpoints", {}).setdefault(key, {})["file"] = file
        manager.save()
    print(f"检查点 {checkpoint_num} 标记为等待确认")


def mark_content_compressed(manager: StateManager, original: str = None, current: str = None,
                            original_scenes: int = None, current_scenes: int = None):
    """标记内容已压缩"""
    manager._state["content_compressed"] = True

    if original:
        manager._state.setdefault("original_plan", {})["estimated_duration"] = original
    if current:
        manager._state.setdefault("current_plan", {})["estimated_duration"] = current
    if original_scenes:
        manager._state.setdefault("original_plan", {})["scenes_count"] = original_scenes
    if current_scenes:
        manager._state.setdefault("current_plan", {})["scenes_count"] = current_scenes

    manager.save()
    print("内容已标记为压缩")
    if original and current:
        print(f"   原始: {original} -> 当前: {current}")


def main():
    parser = argparse.ArgumentParser(
        description='更新工作流状态',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 更新当前步骤
  python3 update_state.py 数学/几何/勾股定理/ --step 3.5 --status pending_confirmation

  # 标记检查点已确认
  python3 update_state.py 数学/几何/勾股定理/ --checkpoint 2 --confirmed

  # 标记检查点等待确认
  python3 update_state.py 数学/几何/勾股定理/ --checkpoint 2 --pending --file preview.html

  # 标记内容已压缩
  python3 update_state.py 数学/几何/勾股定理/ --compressed --original "12分钟" --current "7分钟"
        """
    )

    parser.add_argument('content_dir', help='内容目录路径')
    parser.add_argument('--step', type=float, help='当前步骤编号 (如: 3.5)')
    parser.add_argument('--status', help='状态 (如: pending_confirmation, in_progress, completed)')
    parser.add_argument('--checkpoint', type=int, choices=[1, 2, 3], help='检查点编号')
    parser.add_argument('--confirmed', action='store_true', help='标记检查点为已确认')
    parser.add_argument('--pending', action='store_true', help='标记检查点为等待确认')
    parser.add_argument('--feedback', help='用户反馈信息')
    parser.add_argument('--file', help='关联文件')
    parser.add_argument('--compressed', action='store_true', help='标记内容已压缩')
    parser.add_argument('--original', help='原始预估时长')
    parser.add_argument('--current', help='当前预估时长')
    parser.add_argument('--original-scenes', type=int, help='原始幕数')
    parser.add_argument('--current-scenes', type=int, help='当前幕数')

    args = parser.parse_args()

    content_dir = Path(args.content_dir)

    if not content_dir.exists():
        print(f"错误: 目录不存在: {content_dir}")
        sys.exit(1)

    manager = get_manager(content_dir)

    if args.step is not None:
        update_step(manager, args.step, args.status)

    if args.checkpoint:
        if args.confirmed:
            confirm_checkpoint(manager, args.checkpoint, args.feedback)
        elif args.pending:
            mark_checkpoint_pending(manager, args.checkpoint, args.file)

    if args.compressed:
        mark_content_compressed(
            manager,
            args.original,
            args.current,
            args.original_scenes,
            args.current_scenes,
        )

    print(f"状态已保存到: {content_dir}/production_state.json")


if __name__ == "__main__":
    main()
