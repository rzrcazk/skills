#!/usr/bin/env python3
"""
Parallel Scene Generator
并行场景生成器 - 场景级并行生成

功能：
1. 解析分镜脚本，提取所有场景
2. 为每个场景创建独立目录结构
3. 并行调用子 agent 生成每个场景
4. 管理场景状态和进度
5. 支持场景级增量修复

输出结构：
    scenes/
    ├── scene_000_opening/
    │   ├── audio_main.wav              # 主旁白音频
    │   ├── audio_narration.wav         # 角色独白音频
    │   ├── audio_bg.wav                # 背景音乐
    │   ├── video_preview.mp4           # 预览视频
    │   ├── timeline.md                 # 时间轴文档（审核用）
    │   ├── narration_script.md         # 独白脚本
    │   ├── README.md                   # 场景说明
    │   └── status.json                 # 生成状态
    ├── scene_001_intro/
    └── ...

使用方式：
    # 并行生成所有场景
    python3 scripts/parallel_generator.py --project . --storyboard 分镜脚本.md

    # 指定最大并行数
    python3 scripts/parallel_generator.py --project . --storyboard 分镜脚本.md --max-workers 5

    # 仅生成指定场景
    python3 scripts/parallel_generator.py --project . --storyboard 分镜脚本.md --scene 1

    # 重新生成失败场景
    python3 scripts/parallel_generator.py --project . --storyboard 分镜脚本.md --retry-failed

    # 重新生成指定场景（增量修复）
    python3 scripts/parallel_generator.py --project . --scene 3 --force

    # 确认/拒绝场景
    python3 scripts/parallel_generator.py --project . --confirm 1
    python3 scripts/parallel_generator.py --project . --reject 1 --reason "动画有问题"
"""

import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
from state_manager import StateManager
from config import CONFIG
from logger import get_logger

logger = get_logger(__name__)


@dataclass
class Scene:
    """场景信息"""
    scene_id: int
    name: str
    description: str
    duration: float = 0.0
    audio_files: List[str] = field(default_factory=list)
    narration_entries: List[Dict] = field(default_factory=list)
    template_type: str = "content"  # opening, content, ending
    status: str = "pending"  # pending, generating, generated, confirmed, rejected, fixing


class ParallelGenerator:
    """并行场景生成器"""

    def __init__(self, project_dir: Path, max_workers: int = CONFIG.concurrency.max_scene_workers):
        self.project_dir = Path(project_dir)
        self.max_workers = max_workers
        self.skill_dir = Path(__file__).parent.parent

        # 目录结构
        self.scenes_dir = self.project_dir / "scenes"
        self.audio_dir = self.project_dir / "audio"

        # 统一状态管理器
        self.state_manager = StateManager(project_dir)

        # 场景列表
        self.scenes: List[Scene] = []

    def parse_storyboard(self, storyboard_path: Path) -> List[Scene]:
        """解析分镜脚本，提取场景信息"""
        print(f"\n📖 解析分镜脚本：{storyboard_path}")
        print("-" * 50)

        content = storyboard_path.read_text(encoding='utf-8')
        scenes = []

        # 匹配场景标题（如：### 场景 1：引入）
        scene_pattern = r'### 场景 (\d+)[:：](.+?)(?=\n|$)'
        matches = re.findall(scene_pattern, content)

        if not matches:
            # 尝试其他格式
            scene_pattern = r'##?\s*幕\s*(\d+)[:：]?\s*(.+?)(?=\n|$)'
            matches = re.findall(scene_pattern, content)

        if not matches:
            # 更宽松的匹配
            scene_pattern = r'(?:场景|Scene)\s*(\d+)[:：]?\s*(.+?)(?=\n|$)'
            matches = re.findall(scene_pattern, content, re.IGNORECASE)

        for scene_id_str, name in matches:
            scene_id = int(scene_id_str)
            name = name.strip()

            # 提取场景描述
            pattern = rf'### 场景{scene_id}[:：].+?\n(.+?)(?=### 场景|\Z)'
            desc_match = re.search(pattern, content, re.DOTALL)
            description = desc_match.group(1).strip() if desc_match else ""

            # 确定模板类型
            if scene_id == 0 or "开场" in name or "intro" in name.lower():
                template_type = "opening"
            elif scene_id >= 98 or "结尾" in name or "结束" in name or "outro" in name.lower():
                template_type = "ending"
            else:
                template_type = "content"

            scene = Scene(
                scene_id=scene_id,
                name=name,
                description=description[:200],
                template_type=template_type
            )
            scenes.append(scene)
            print(f"  ✓ 场景 {scene_id}: {name} ({template_type})")

        # 如果没有找到场景，创建默认场景
        if not scenes:
            print("  ⚠️ 未找到场景定义，创建默认场景...")
            scenes = self._create_default_scenes()

        print(f"\n共找到 {len(scenes)} 个场景")
        return scenes

    def _create_default_scenes(self) -> List[Scene]:
        """创建默认场景（当分镜解析失败时）"""
        return [
            Scene(scene_id=0, name="开场", description="系列开场", template_type="opening"),
            Scene(scene_id=1, name="引入", description="概念引入", template_type="content"),
            Scene(scene_id=2, name="讲解", description="核心讲解", template_type="content"),
            Scene(scene_id=99, name="结尾", description="系列结尾", template_type="ending"),
        ]

    def init_scene_directories(self, scenes: List[Scene]):
        """初始化场景目录结构"""
        print(f"\n📁 初始化场景目录")
        print("-" * 50)

        self.scenes_dir.mkdir(parents=True, exist_ok=True)

        for scene in scenes:
            scene_dir = self._get_scene_dir(scene)
            scene_dir.mkdir(parents=True, exist_ok=True)

            # 创建初始状态文件
            status = {
                "scene_id": scene.scene_id,
                "name": scene.name,
                "template_type": scene.template_type,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            status_file = scene_dir / "status.json"
            status_file.write_text(json.dumps(status, ensure_ascii=False, indent=2))

            print(f"  ✓ {scene_dir.name}/")

        # 同步到统一状态管理器
        self._sync_to_state_manager(scenes)
        print(f"\n已创建 {len(scenes)} 个场景目录")

    def _sync_to_state_manager(self, scenes: List[Scene]):
        """同步场景信息到统一状态管理器"""
        items = []
        for scene in scenes:
            items.append({
                "id": scene.scene_id,
                "type": "scene",
                "status": "pending",
                "name": scene.name,
                "template_type": scene.template_type
            })

        # 只添加不存在的项
        existing_ids = {item["id"] for item in self.state_manager.get_render_items()}
        new_items = [item for item in items if item["id"] not in existing_ids]
        if new_items:
            self.state_manager.add_render_items(new_items)

    def _get_scene_dir(self, scene: Scene) -> Path:
        """获取场景目录路径"""
        # 清理场景名称作为目录名
        safe_name = re.sub(r'[^\w\u4e00-\u9fff-]', '_', scene.name)
        return self.scenes_dir / f"scene_{scene.scene_id:03d}_{safe_name}"

    def generate_scene(self, scene: Scene, force: bool = False) -> Dict:
        """生成单个场景（调用子 agent）"""
        scene_dir = self._get_scene_dir(scene)

        # 检查是否已生成（除非强制重新生成）
        status_file = scene_dir / "status.json"
        if status_file.exists() and not force:
            data = json.loads(status_file.read_text())
            if data.get("status") == "completed":
                print(f"\n⏭️  场景 {scene.scene_id} 已生成，跳过")
                return {"scene_id": scene.scene_id, "status": "skipped"}
            elif data.get("status") == "confirmed":
                print(f"\n⏭️  场景 {scene.scene_id} 已确认，跳过")
                return {"scene_id": scene.scene_id, "status": "skipped"}

        # 更新状态为 generating
        self._update_scene_status(scene, "generating")
        self.state_manager.update_render_item(scene.scene_id, "generating", "scene")

        try:
            # 构建场景配置
            scene_config = {
                "scene_id": scene.scene_id,
                "name": scene.name,
                "description": scene.description,
                "template_type": scene.template_type,
                "duration": scene.duration,
            }

            # 调用 scene_agent.py 生成场景
            cmd = [
                sys.executable,
                str(self.skill_dir / "scripts" / "scene_agent.py"),
                "--project", str(self.project_dir),
                "--scene-dir", str(scene_dir),
                "--config", json.dumps(scene_config),
            ]

            print(f"\n🎬 生成场景 {scene.scene_id}: {scene.name}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=CONFIG.concurrency.scene_timeout,
            )

            if result.returncode == 0:
                self._update_scene_status(scene, "generated")
                self.state_manager.update_render_item(scene.scene_id, "generated", "scene")
                print(f"   ✅ 场景 {scene.scene_id} 生成成功")
                return {"scene_id": scene.scene_id, "status": "success", "output": result.stdout}
            else:
                self._update_scene_status(scene, "failed")
                self.state_manager.update_render_item(scene.scene_id, "rejected", "scene",
                                                     {"error": result.stderr[:500]})
                print(f"   ❌ 场景 {scene.scene_id} 生成失败")
                print(f"   错误：{result.stderr[:200]}")
                return {"scene_id": scene.scene_id, "status": "failed", "error": result.stderr}

        except subprocess.TimeoutExpired:
            self._update_scene_status(scene, "timeout")
            self.state_manager.update_render_item(scene.scene_id, "rejected", "scene",
                                                 {"error": "Timeout"})
            print(f"   ⏱️ 场景 {scene.scene_id} 生成超时")
            return {"scene_id": scene.scene_id, "status": "timeout"}

        except Exception as e:
            self._update_scene_status(scene, "error")
            self.state_manager.update_render_item(scene.scene_id, "rejected", "scene",
                                                 {"error": str(e)})
            print(f"   ❌ 场景 {scene.scene_id} 异常：{e}")
            return {"scene_id": scene.scene_id, "status": "error", "error": str(e)}

    def _update_scene_status(self, scene: Scene, status: str):
        """更新场景状态"""
        scene.status = status
        scene_dir = self._get_scene_dir(scene)
        status_file = scene_dir / "status.json"

        if status_file.exists():
            data = json.loads(status_file.read_text())
            data["status"] = status
            data["updated_at"] = datetime.now().isoformat()
            status_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def run_parallel(self, scenes: List[Scene], specific_scene: Optional[int] = None,
                     force: bool = False) -> List[Dict]:
        """并行生成场景"""
        if specific_scene is not None:
            # 仅生成指定场景
            scenes = [s for s in scenes if s.scene_id == specific_scene]
            if not scenes:
                print(f"错误：找不到场景 {specific_scene}")
                return []

        print(f"\n🚀 启动并行生成")
        print(f"   场景数：{len(scenes)}")
        print(f"   并行数：{self.max_workers}")
        print("-" * 50)

        results = []
        completed = 0
        failed = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_scene = {
                executor.submit(self.generate_scene, scene, force): scene
                for scene in scenes
            }

            # 收集结果
            for future in as_completed(future_to_scene):
                scene = future_to_scene[future]
                try:
                    result = future.result()
                    results.append(result)

                    if result["status"] in ["success", "skipped"]:
                        completed += 1
                    else:
                        failed += 1

                    # 显示进度
                    print(f"\n📊 进度：{completed + failed}/{len(scenes)} "
                          f"(成功：{completed}, 失败：{failed})")

                except Exception as e:
                    print(f"   ❌ 场景 {scene.scene_id} 处理异常：{e}")
                    failed += 1

        return results

    def retry_failed(self, scenes: List[Scene]) -> List[Dict]:
        """重新生成失败的场景"""
        failed_scenes = []
        for scene in scenes:
            scene_dir = self._get_scene_dir(scene)
            status_file = scene_dir / "status.json"
            if status_file.exists():
                data = json.loads(status_file.read_text())
                if data.get("status") in ["failed", "timeout", "error"]:
                    failed_scenes.append(scene)

        if not failed_scenes:
            # 检查状态管理器
            rejected_items = self.state_manager.get_rejected_items()
            for item in rejected_items:
                if item.get("type") == "scene":
                    scene = self._find_scene_by_id(scenes, item["id"])
                    if scene:
                        failed_scenes.append(scene)

        if not failed_scenes:
            print("没有失败的场景需要重试")
            return []

        print(f"\n🔄 重试 {len(failed_scenes)} 个失败场景")
        return self.run_parallel(failed_scenes, force=True)

    def _find_scene_by_id(self, scenes: List[Scene], scene_id: int) -> Optional[Scene]:
        """根据 ID 查找场景"""
        for scene in scenes:
            if scene.scene_id == scene_id:
                return scene
        return None

    def regenerate_scenes(self, scenes: List[Scene], scene_ids: List[int]) -> List[Dict]:
        """重新生成指定场景（用于增量修复）"""
        scenes_to_regenerate = [s for s in scenes if s.scene_id in scene_ids]

        if not scenes_to_regenerate:
            print(f"错误：找不到指定的场景 {scene_ids}")
            return []

        print(f"\n🔧 重新生成 {len(scenes_to_regenerate)} 个场景:")
        for scene in scenes_to_regenerate:
            print(f"   - 场景 {scene.scene_id}: {scene.name}")

        return self.run_parallel(scenes_to_regenerate, force=True)

    def print_summary(self, results: List[Dict]):
        """打印生成摘要"""
        print(f"\n{'='*60}")
        print("📋 生成摘要")
        print(f"{'='*60}")

        success = [r for r in results if r["status"] in ["success", "skipped"]]
        failed = [r for r in results if r["status"] not in ["success", "skipped"]]

        print(f"\n总场景数：{len(results)}")
        print(f"  ✅ 成功：{len(success)}")
        print(f"  ❌ 失败：{len(failed)}")

        if failed:
            print(f"\n失败场景:")
            for r in failed:
                print(f"  - 场景 {r['scene_id']}: {r['status']}")
                if "error" in r:
                    print(f"    错误：{r['error'][:100]}...")

        # 显示状态管理器摘要
        print(f"\n📊 状态摘要:")
        print(self.state_manager.get_summary())

        print(f"\n输出目录：{self.scenes_dir}")
        print(f"{'='*60}\n")

    def confirm_scene(self, scene_id: int):
        """标记场景为已确认"""
        # 尝试从场景目录查找
        scene_dir = self.scenes_dir / f"scene_{scene_id:03d}"
        if scene_dir.exists():
            status_file = scene_dir / "status.json"
            if status_file.exists():
                data = json.loads(status_file.read_text())
                data["status"] = "confirmed"
                data["updated_at"] = datetime.now().isoformat()
                status_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))

        self.state_manager.update_render_item(scene_id, "confirmed", "scene")
        print(f"✅ 场景 {scene_id} 已确认")

    def reject_scene(self, scene_id: int, reason: str = ""):
        """标记场景为被拒绝"""
        # 尝试从场景目录查找
        scene_dir = self.scenes_dir / f"scene_{scene_id:03d}"
        if scene_dir.exists():
            status_file = scene_dir / "status.json"
            if status_file.exists():
                data = json.loads(status_file.read_text())
                data["status"] = "rejected"
                data["updated_at"] = datetime.now().isoformat()
                data["reject_reason"] = reason
                status_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))

        self.state_manager.update_render_item(scene_id, "rejected", "scene",
                                             {"reason": reason})
        print(f"📝 场景 {scene_id} 被拒绝：{reason}")

    def check_all_scenes_status(self) -> Tuple[List, List, List]:
        """检查所有场景的状态"""
        if not self.scenes_dir.exists():
            return [], [], []

        confirmed = []
        pending = []
        failed = []

        for scene_dir in self.scenes_dir.iterdir():
            if not scene_dir.is_dir() or not scene_dir.name.startswith("scene_"):
                continue

            status_file = scene_dir / "status.json"
            if status_file.exists():
                data = json.loads(status_file.read_text())
                status = data.get("status", "pending")

                # 提取场景 ID
                try:
                    scene_id = int(scene_dir.name.split("_")[1])
                except (ValueError, IndexError):
                    continue

                if status in ["confirmed", "generated"]:
                    confirmed.append((scene_id, scene_dir))
                elif status in ["failed", "timeout", "error", "rejected"]:
                    failed.append((scene_id, scene_dir, status))
                else:
                    pending.append((scene_id, scene_dir, status))

        return confirmed, pending, failed

    def resume(self, scenes: List[Scene], force: bool = False) -> List[Dict]:
        """
        断点续传：跳过已完成场景，只生成剩余场景

        Args:
            scenes: 全部场景列表
            force: 是否强制重新生成（包括已完成场景）

        Returns:
            生成结果列表
        """
        pending_scenes: List[Scene] = []
        skipped: List[Scene] = []

        for scene in scenes:
            scene_dir = self._get_scene_dir(scene)
            status_file = scene_dir / "status.json"
            if status_file.exists() and not force:
                try:
                    data = json.loads(status_file.read_text())
                    if data.get("status") in ("completed", "confirmed", "generated"):
                        skipped.append(scene)
                        continue
                except Exception:
                    pass
            pending_scenes.append(scene)

        if skipped:
            logger.info("断点续传：跳过 %d 个已完成场景", len(skipped))

        if not pending_scenes:
            logger.info("所有场景均已完成，无需生成")
            return []

        logger.info("续传：将生成 %d 个未完成场景", len(pending_scenes))
        return self.run_parallel(pending_scenes, force=force)


def main():
    parser = argparse.ArgumentParser(
        description="Parallel Scene Generator - 并行场景生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    # 并行生成所有场景
    python3 scripts/parallel_generator.py --project . --storyboard 分镜脚本.md

    # 指定最大并行数
    python3 scripts/parallel_generator.py --project . --storyboard 分镜脚本.md --max-workers 3

    # 仅生成指定场景
    python3 scripts/parallel_generator.py --project . --storyboard 分镜脚本.md --scene 1

    # 重试失败场景
    python3 scripts/parallel_generator.py --project . --storyboard 分镜脚本.md --retry-failed

    # 重新生成指定场景（增量修复）
    python3 scripts/parallel_generator.py --project . --scene 3 --force

    # 确认/拒绝场景
    python3 scripts/parallel_generator.py --project . --confirm 1
    python3 scripts/parallel_generator.py --project . --reject 1 --reason "动画有问题"
        """
    )

    parser.add_argument("--project", "-p", required=True,
                       help="项目目录路径")
    parser.add_argument("--storyboard", "-s", required=False,
                       help="分镜脚本文件路径 (.md)")
    parser.add_argument("--max-workers", "-w", type=int,
                       default=CONFIG.concurrency.max_scene_workers,
                       help=f"最大并行工作线程数 (默认：{CONFIG.concurrency.max_scene_workers})")
    parser.add_argument("--scene", "-n", type=int,
                       help="仅生成指定场景 ID")
    parser.add_argument("--force", "-f", action="store_true",
                       help="强制重新生成")
    parser.add_argument("--retry-failed", "-r", action="store_true",
                       help="重试失败的场景")
    parser.add_argument("--resume", action="store_true",
                       help="断点续传：跳过已完成场景，继续生成未完成场景")
    parser.add_argument("--confirm", type=int,
                       help="确认指定场景")
    parser.add_argument("--reject", type=int,
                       help="拒绝指定场景")
    parser.add_argument("--reason", type=str, default="",
                       help="拒绝原因")
    parser.add_argument("--summary", action="store_true",
                       help="显示场景摘要")

    args = parser.parse_args()

    project_dir = Path(args.project)

    if not project_dir.exists():
        print(f"错误：项目目录不存在：{project_dir}")
        return 1

    generator = ParallelGenerator(project_dir)

    # 确认/拒绝场景模式
    if args.confirm is not None:
        generator.confirm_scene(args.confirm)
        return 0

    if args.reject is not None:
        generator.reject_scene(args.reject, args.reason)
        return 0

    # 显示摘要
    if args.summary:
        confirmed, pending, failed = generator.check_all_scenes_status()
        print(f"\n📊 场景状态摘要:")
        print(f"  ✅ 已确认/生成：{len(confirmed)}")
        print(f"  ⏳ 待处理：{len(pending)}")
        print(f"  ❌ 失败：{len(failed)}")
        print(f"\n📊 统一状态:")
        print(generator.state_manager.get_summary())
        return 0

    # 生成分镜需要 storyboard 文件
    storyboard_path = Path(args.storyboard) if args.storyboard else None
    if not storyboard_path:
        # 尝试默认路径
        storyboard_path = project_dir / "分镜脚本.md"

    if not storyboard_path.exists():
        print(f"错误：分镜脚本不存在：{storyboard_path}")
        return 1

    # 解析分镜
    scenes = generator.parse_storyboard(storyboard_path)
    if not scenes:
        print("错误：未能从分镜脚本中解析出任何场景")
        return 1

    # 初始化目录
    generator.init_scene_directories(scenes)

    # 执行生成
    if args.retry_failed:
        results = generator.retry_failed(scenes)
    elif args.resume:
        results = generator.resume(scenes, force=args.force)
    elif args.scene is not None:
        results = generator.run_parallel(scenes, specific_scene=args.scene, force=args.force)
    else:
        results = generator.run_parallel(scenes, force=args.force)

    # 打印摘要
    generator.print_summary(results)

    # 返回退出码
    failed_count = len([r for r in results if r["status"] not in ["success", "skipped"]])
    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    exit(main())
