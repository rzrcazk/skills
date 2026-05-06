#!/usr/bin/env python3
"""
Unified State Manager - 统一状态管理器

功能：
1. 统一管理 workflow_state.json 和 segment_pipeline.json
2. 提供一致的状态查询和更新接口
3. 支持中断恢复和模式切换

状态文件结构：
{
  "version": "1.0",
  "content": {
    "title": "勾股定理",
    "category": "数学",
    "subcategory": "几何",
    "knowledge_level": "初中"
  },
  "current_phase": "planning",  // planning | audio | render | completed
  "render_mode": "auto",        // auto | segment | standard

  "phases": {
    "planning": {
      "status": "completed",
      "files": ["outline.md", "分镜脚本.md"],
      "completed_at": "ISO 时间戳"
    },
    "audio": {
      "status": "completed",
      "files": ["audio/*.wav", "audio_info.json"],
      "completed_at": "ISO 时间戳"
    },
    "render": {
      "status": "in_progress",
      "mode": "segment",  // segment | standard
      "progress": {
        "total": 10,
        "completed": 5,
        "confirmed": 3
      },
      "items": [  // 场景或段的状态列表
        {"id": 1, "status": "confirmed", "type": "scene"},
        {"id": 2, "status": "confirmed", "type": "scene"},
        {"id": 3, "status": "pending", "type": "scene"}
      ]
    }
  },

  "created_at": "ISO 时间戳",
  "updated_at": "ISO 时间戳"
}
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from constants import STEP_NAMES, DECISION_LABELS, CHECKPOINT_LABELS

# 延迟导入，避免循环依赖
def _atomic_write_json(file_path, data):
    from utils import atomic_write_json
    atomic_write_json(file_path, data)


class StateManager:
    """统一状态管理器"""

    STATE_FILE = "production_state.json"

    # 阶段定义
    PHASES = ["planning", "audio", "render", "completed"]
    PHASE_STATUS = ["pending", "in_progress", "completed"]

    # 渲染模式
    RENDER_MODES = ["auto", "segment", "standard"]

    # 场景/段状态
    ITEM_STATUS = ["pending", "generating", "generated", "confirmed", "rejected", "fixing"]

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.state_file = self.project_dir / self.STATE_FILE
        self._state: Dict[str, Any] = self._load_or_create()

    def _load_or_create(self) -> Dict:
        """加载现有状态或创建新状态，首次访问时自动迁移旧文件"""
        if self.state_file.exists():
            return json.loads(self.state_file.read_text(encoding='utf-8'))

        state = self._create_default_state()

        # 自动迁移旧状态文件
        migrated = False
        workflow_file = self.project_dir / "workflow_state.json"
        pipeline_file = self.project_dir / "segment_pipeline.json"

        if workflow_file.exists():
            self._state = state
            self.migrate_from_workflow_state(workflow_file)
            state = self._state
            migrated = True

        if pipeline_file.exists():
            self._state = state
            self.migrate_from_segment_pipeline(pipeline_file)
            state = self._state
            migrated = True

        if migrated:
            state["migrated_at"] = datetime.now().isoformat()

        return state

    def _create_default_state(self) -> Dict:
        """创建默认状态结构"""
        return {
            "version": "1.0",
            "content": {
                "title": "",
                "category": "",
                "subcategory": "",
                "knowledge_level": ""
            },
            "decisions": {},
            "current_phase": "planning",
            "render_mode": "auto",
            "phases": {
                "planning": {
                    "status": "pending",
                    "files": [],
                    "completed_at": None
                },
                "audio": {
                    "status": "pending",
                    "files": [],
                    "completed_at": None
                },
                "render": {
                    "status": "pending",
                    "mode": "auto",
                    "progress": {
                        "total": 0,
                        "completed": 0,
                        "confirmed": 0
                    },
                    "items": []
                }
            },
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

    def save(self):
        """保存状态到文件（原子写入，防止写入中途崩溃导致文件损坏）"""
        self._state["updated_at"] = datetime.now().isoformat()
        _atomic_write_json(self.state_file, self._state)

    # ========== 内容信息 ==========

    def set_content_info(self, title: str, category: str = "",
                         subcategory: str = "", knowledge_level: str = ""):
        """设置内容信息"""
        self._state["content"].update({
            "title": title,
            "category": category,
            "subcategory": subcategory,
            "knowledge_level": knowledge_level
        })
        self.save()

    def get_content_info(self) -> Dict:
        """获取内容信息"""
        return self._state["content"]

    # ========== 阶段管理 ==========

    def get_phase(self) -> str:
        """获取当前阶段"""
        return self._state["current_phase"]

    def get_phase_status(self, phase: str) -> str:
        """获取指定阶段的状态"""
        if phase not in self._state["phases"]:
            return "pending"
        return self._state["phases"][phase].get("status", "pending")

    def set_phase_status(self, phase: str, status: str, files: List[str] = None):
        """设置阶段状态"""
        if phase not in self._state["phases"]:
            self._state["phases"][phase] = {
                "status": "pending",
                "files": [],
                "completed_at": None
            }

        self._state["phases"][phase]["status"] = status
        if files:
            self._state["phases"][phase]["files"] = files
        if status == "completed":
            self._state["phases"][phase]["completed_at"] = datetime.now().isoformat()

        # 如果阶段完成，更新 current_phase 到下一个阶段
        if status == "completed":
            phase_index = self.PHASES.index(phase) if phase in self.PHASES else -1
            if phase_index >= 0 and phase_index < len(self.PHASES) - 1:
                self._state["current_phase"] = self.PHASES[phase_index + 1]

        self.save()

    def advance_phase(self):
        """推进到下一个阶段"""
        current = self._state["current_phase"]
        if current in self.PHASES:
            current_index = self.PHASES.index(current)
            if current_index < len(self.PHASES) - 1:
                self._state["current_phase"] = self.PHASES[current_index + 1]
                self.save()

    # ========== 渲染模式 ==========

    def get_render_mode(self) -> str:
        """获取渲染模式"""
        return self._state.get("render_mode", "auto")

    def set_render_mode(self, mode: str):
        """设置渲染模式"""
        if mode not in self.RENDER_MODES:
            raise ValueError(f"Invalid render mode: {mode}")
        self._state["render_mode"] = mode
        self._state["phases"]["render"]["mode"] = mode
        self.save()

    def auto_select_render_mode(self, audio_duration: float, scenes_count: int) -> str:
        """根据视频时长和场景数自动选择渲染模式"""
        from config import CONFIG

        if (audio_duration < CONFIG.render.short_video_threshold
                and scenes_count <= CONFIG.render.max_scenes_for_standard):
            mode = "standard"
        else:
            mode = "segment"

        self.set_render_mode(mode)
        return mode

    # ========== 渲染项管理（场景/段） ==========

    def add_render_items(self, items: List[Dict]):
        """添加渲染项（场景或段）"""
        for item in items:
            if "id" not in item or "type" not in item:
                raise ValueError("Each item must have 'id' and 'type'")
            item["status"] = item.get("status", "pending")

        self._state["phases"]["render"]["items"].extend(items)
        self._update_progress()
        self.save()

    def get_render_items(self, status_filter: str = None) -> List[Dict]:
        """获取渲染项列表"""
        items = self._state["phases"]["render"]["items"]
        if status_filter:
            return [item for item in items if item.get("status") == status_filter]
        return items

    def update_render_item(self, item_id: int, status: str,
                           item_type: str = None, data: Dict = None):
        """更新渲染项状态"""
        for item in self._state["phases"]["render"]["items"]:
            if item["id"] == item_id:
                item["status"] = status
                if item_type:
                    item["type"] = item_type
                if data:
                    item.update(data)
                break

        self._update_progress()
        self.save()

    def get_pending_items(self) -> List[Dict]:
        """获取待处理的渲染项"""
        return self.get_render_items("pending")

    def get_confirmed_items(self) -> List[Dict]:
        """获取已确认的渲染项"""
        return self.get_render_items("confirmed")

    def get_rejected_items(self) -> List[Dict]:
        """获取被拒绝的渲染项"""
        return self.get_render_items("rejected")

    def _update_progress(self):
        items = self._state["phases"]["render"]["items"]
        completed = confirmed = 0
        for i in items:
            s = i["status"]
            if s == "generated":
                completed += 1
            elif s == "confirmed":
                confirmed += 1
        self._state["phases"]["render"]["progress"] = {
            "total": len(items),
            "completed": completed,
            "confirmed": confirmed,
        }

    def get_progress(self) -> Dict:
        """获取进度统计"""
        return self._state["phases"]["render"]["progress"]

    def is_render_complete(self) -> bool:
        """检查渲染是否完成"""
        progress = self.get_progress()
        return progress["total"] > 0 and progress["confirmed"] == progress["total"]

    # ========== 工作流步骤管理（替代 workflow_state.json 直接读写） ==========

    def get_workflow_step(self) -> float:
        """获取当前工作流步骤号"""
        return float(self._state.get("workflow_step", 0))

    def set_workflow_step(self, step: float, status: str = None):
        """设置工作流步骤"""
        self._state["workflow_step"] = step
        if status:
            self._state["workflow_status"] = status
        self.save()

    def get_checkpoint(self, checkpoint_num: int) -> Dict:
        """获取检查点信息"""
        return self._state.get("checkpoints", {}).get(f"checkpoint{checkpoint_num}", {})

    def set_checkpoint(self, checkpoint_num: int, status: str, feedback: str = None):
        """设置检查点状态"""
        if "checkpoints" not in self._state:
            self._state["checkpoints"] = {}
        key = f"checkpoint{checkpoint_num}"
        checkpoint = self._state["checkpoints"].setdefault(key, {})
        checkpoint["status"] = status
        checkpoint["updated_at"] = datetime.now().isoformat()
        if feedback:
            checkpoint["user_feedback"] = feedback
            # 累积反馈历史
            history = checkpoint.setdefault("feedback_history", [])
            history.append({"feedback": feedback, "at": datetime.now().isoformat()})
        if status == "confirmed":
            checkpoint["confirmed_at"] = datetime.now().isoformat()
            checkpoint["attempts"] = checkpoint.get("attempts", 0) + 1
        self.save()

    # ========== 失败记录 ==========

    def record_failure(self, step: float, reason: str, method_tried: str = None):
        """记录步骤失败（供会话简报使用）"""
        if "failures" not in self._state:
            self._state["failures"] = []
        self._state["failures"].append({
            "step": step,
            "reason": reason,
            "method_tried": method_tried,
            "at": datetime.now().isoformat()
        })
        self.save()

    def get_failures(self) -> list:
        """获取失败记录"""
        return self._state.get("failures", [])

    # ========== 向后兼容：从旧状态文件迁移 ==========

    def migrate_from_workflow_state(self, workflow_state_file: Path):
        """从旧的 workflow_state.json 迁移数据"""
        if not workflow_state_file.exists():
            return False

        old_state = json.loads(workflow_state_file.read_text(encoding='utf-8'))

        # 迁移内容信息
        content_path = old_state.get("content_path", "")
        if content_path:
            parts = content_path.strip("/").split("/")
            self._state["content"]["title"] = parts[-1] if parts else ""
            if len(parts) >= 2:
                self._state["content"]["subcategory"] = parts[-2]
            if len(parts) >= 3:
                self._state["content"]["category"] = parts[-3]

        # 迁移阶段状态
        current_step = old_state.get("current_step", 0)

        # step 0-4: planning
        if current_step >= 4:
            self.set_phase_status("planning", "completed",
                                 ["outline.md", "分镜脚本.md"])

        # step 5-6: audio
        if current_step >= 6:
            self.set_phase_status("audio", "completed",
                                 ["audio/*.wav", "audio_info.json"])

        # step 7-10: render
        if current_step >= 7:
            self.set_phase_status("render", "in_progress")

        if current_step >= 10:
            self.set_phase_status("completed", "completed")
            self._state["current_phase"] = "completed"

        self.save()
        return True

    def migrate_from_segment_pipeline(self, pipeline_file: Path):
        """从旧的 segment_pipeline.json 迁移数据"""
        if not pipeline_file.exists():
            return False

        old_state = json.loads(pipeline_file.read_text(encoding='utf-8'))

        # 设置为分段模式
        self.set_render_mode("segment")

        # 迁移段信息
        segments = old_state.get("segments", [])
        items = []
        for seg in segments:
            items.append({
                "id": seg.get("index", 0),
                "type": "segment",
                "status": seg.get("status", "pending"),
                "time_range": seg.get("time_range", ""),
                "scenes": seg.get("scenes", []),
                "video_path": seg.get("video_path"),
                "confirmed_at": seg.get("confirmed_at")
            })

        self.add_render_items(items)
        self.save()
        return True

    # ========== 决策记录 ==========

    def save_decision(self, key: str, value: str):
        """保存关键决策（如引入方式、证明方法等）"""
        if "decisions" not in self._state:
            self._state["decisions"] = {}
        self._state["decisions"][key] = value
        self.save()

    def get_decisions(self) -> Dict:
        """获取所有已保存的决策"""
        return self._state.get("decisions", {})

    def generate_session_brief(self) -> str:
        """生成会话简报文本（~150 token），写入 session_brief.md"""
        content = self._state["content"]
        title = content.get("title", "未知主题")
        level = content.get("knowledge_level", "")
        step = self._state.get("workflow_step", 0)
        decisions = self._state.get("decisions", {})

        current_step_name = STEP_NAMES.get(float(step), f"步骤{step}")

        lines = [
            f"# 会话简报：{title}（{level}）",
            f"",
            f"项目路径：{self.project_dir}",
            f"当前步骤：步骤 {step} - {current_step_name}",
            f"",
        ]

        # 已完成文件
        artifacts = {
            "outline.md": "大纲",
            "topic_analysis.md": "主题分析",
            "preview.html": "HTML预览",
            "分镜脚本.md": "分镜脚本",
            "script.py": "Manim脚本",
        }
        completed_files = []
        missing_files = []
        for filename, label in artifacts.items():
            if (self.project_dir / filename).exists():
                completed_files.append(f"- {label} ({filename}) ✅")
            else:
                missing_files.append(f"- {label} ({filename}) ⏳")

        if completed_files or missing_files:
            lines.append("## 关键文件")
            lines.extend(completed_files)
            lines.extend(missing_files)
            lines.append("")

        # 已保存决策
        if decisions:
            lines.append("## 已确认决策")
            for key, value in decisions.items():
                label = DECISION_LABELS.get(key, key)
                lines.append(f"- {label}：{value}")
            lines.append("")

        # 检查点反馈（用户拒绝原因）
        checkpoints = self._state.get("checkpoints", {})
        cp_labels = CHECKPOINT_LABELS
        cp_feedback_lines = []
        for key, label in cp_labels.items():
            cp = checkpoints.get(key, {})
            feedback = cp.get("user_feedback")
            attempts = cp.get("attempts", 0)
            if feedback:
                cp_feedback_lines.append(f"- 检查点{label}（第{attempts}次）：{feedback}")
        if cp_feedback_lines:
            lines.append("## 检查点反馈")
            lines.extend(cp_feedback_lines)
            lines.append("")

        # 失败历史
        failures = self.get_failures()
        if failures:
            lines.append("## 失败记录（避免重蹈覆辙）")
            for f in failures[-5:]:  # 只展示最近5条
                sname = STEP_NAMES.get(float(f["step"]), f"步骤{f['step']}")
                method = f"（尝试方法：{f['method_tried']}）" if f.get("method_tried") else ""
                lines.append(f"- 步骤{f['step']} {sname}：{f['reason']}{method}")
            lines.append("")

        # 下一步操作
        next_step = float(step)
        offline_steps = {2.0: "step2_analysis_prompt.md", 3.0: "step3_html_prompt.md", 4.0: "step4_storyboard_prompt.md"}
        script_steps = {5.0: "generate_tts.py", 6.0: "validate_audio.py", 9.0: "check.py + render.py"}

        lines.append("## 下一步")
        if next_step in offline_steps:
            prompt_file = offline_steps[next_step]
            lines.append(f"1. 导出离线 prompt：`python3 scripts/step_runner.py --export {int(next_step)} .`")
            lines.append(f"2. 复制 `{prompt_file}` 内容到 Claude.ai 或 ChatGPT")
            lines.append(f"3. 将结果保存到项目目录对应文件")
            lines.append(f"4. 标记完成：`python3 scripts/step_runner.py --done {int(next_step)} .`")
        elif next_step in script_steps:
            script = script_steps[next_step]
            lines.append(f"运行脚本：`python3 scripts/{script}`")
        else:
            lines.append(f"在 Claude Code 中继续步骤 {next_step}：`python3 scripts/step_runner.py --status .`")

        brief_text = "\n".join(lines)

        # 写入文件
        brief_file = self.project_dir / "session_brief.md"
        brief_file.write_text(brief_text, encoding="utf-8")

        return brief_text

    # ========== 状态查询 ==========

    def get_summary(self) -> str:
        """获取状态摘要（用于显示给用户）"""
        lines = []
        lines.append(f"📁 内容：{self._state['content'].get('title', '未知')}")
        lines.append(f"📊 当前阶段：{self._state['current_phase']}")
        lines.append(f"🎬 渲染模式：{self._state['render_mode']}")

        for phase in self.PHASES[:-1]:  # 排除 completed
            phase_data = self._state["phases"].get(phase, {})
            status = phase_data.get("status", "pending")
            icon = "✅" if status == "completed" else "⏳" if status == "in_progress" else "⏹"
            lines.append(f"  {icon} {phase}")

        progress = self.get_progress()
        if progress["total"] > 0:
            lines.append(f"\n📈 渲染进度：{progress['confirmed']}/{progress['total']} 已确认")

            # 显示各项状态
            items = self.get_render_items()
            for item in items[:10]:  # 只显示前 10 个
                status_icon = {
                    "confirmed": "✅",
                    "generated": "🎬",
                    "pending": "⏹",
                    "rejected": "📝",
                    "fixing": "🔧"
                }.get(item.get("status", ""), "⏳")
                item_name = f"段{item['id']}" if item.get("type") == "segment" else f"场景{item['id']}"
                lines.append(f"    {status_icon} {item_name}")

            if len(items) > 10:
                lines.append(f"    ... 还有 {len(items) - 10} 个")

        return "\n".join(lines)


def main():
    """命令行工具"""
    if len(sys.argv) < 3:
        print("用法：python3 state_manager.py <project_dir> <command> [args]")
        print("命令:")
        print("  status          - 显示状态摘要")
        print("  set-phase       - 设置阶段状态")
        print("  set-mode        - 设置渲染模式")
        print("  add-items       - 添加渲染项")
        print("  update-item     - 更新渲染项状态")
        print("  migrate         - 从旧状态文件迁移")
        sys.exit(1)

    project_dir = Path(sys.argv[1])
    command = sys.argv[2]

    manager = StateManager(project_dir)

    if command == "status":
        print(manager.get_summary())

    elif command == "set-phase":
        phase = sys.argv[3]
        status = sys.argv[4]
        manager.set_phase_status(phase, status)
        print(f"已设置 {phase} 状态为 {status}")

    elif command == "set-mode":
        mode = sys.argv[3]
        manager.set_render_mode(mode)
        print(f"已设置渲染模式为 {mode}")

    elif command == "migrate":
        workflow_file = project_dir / "workflow_state.json"
        pipeline_file = project_dir / "segment_pipeline.json"

        if workflow_file.exists():
            manager.migrate_from_workflow_state(workflow_file)
            print(f"已从 workflow_state.json 迁移")

        if pipeline_file.exists():
            manager.migrate_from_segment_pipeline(pipeline_file)
            print(f"已从 segment_pipeline.json 迁移")

        print("迁移完成")

    else:
        print(f"未知命令：{command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
