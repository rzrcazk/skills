#!/usr/bin/env python3
"""
Step Runner - 步骤管理器（Token 节省模式）

将工作流步骤分为三类：
  offline - 导出 prompt，用户去网页 AI 完成，手动保存文件
  online  - 在 Claude Code 中执行（需要 AI 上下文）
  script  - 直接运行脚本，无需 AI

用法：
    python3 scripts/step_runner.py --status [project_dir]
    python3 scripts/step_runner.py --export 2 [project_dir]
    python3 scripts/step_runner.py --done 2 [project_dir]
    python3 scripts/step_runner.py --brief [project_dir]
    python3 scripts/step_runner.py --decide key value [project_dir]

project_dir 默认为当前目录 (.)
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from state_manager import StateManager
from constants import LEVEL_CONSTRAINTS, DECISION_LABELS

# ========== 步骤定义 ==========

STEPS = [
    {"id": 0,   "name": "类别选择",        "mode": "online",  "output": None},
    {"id": 1,   "name": "知识水平确认",     "mode": "online",  "output": None},
    {"id": 2,   "name": "主题分析",         "mode": "offline", "output": "topic_analysis.md",
     "prompt_tpl": "step2_analysis_prompt.md.tpl",
     "prompt_out": "step2_analysis_prompt.md"},
    {"id": 2.5, "name": "检查点1-大纲确认", "mode": "online",  "output": "outline.md"},
    {"id": 3,   "name": "HTML可视化预览",   "mode": "offline", "output": "preview.html",
     "prompt_tpl": "step3_html_prompt.md.tpl",
     "prompt_out": "step3_html_prompt.md"},
    {"id": 3.5, "name": "检查点2-图形确认", "mode": "online",  "output": None},
    {"id": 4,   "name": "分镜脚本",         "mode": "offline", "output": "分镜脚本.md",
     "prompt_tpl": "step4_storyboard_prompt.md.tpl",
     "prompt_out": "step4_storyboard_prompt.md"},
    {"id": 4.5, "name": "检查点3-分镜确认", "mode": "online",  "output": None},
    {"id": 5,   "name": "TTS生成",          "mode": "script",  "output": "audio/",
     "script": "generate_tts.py"},
    {"id": 6,   "name": "验证更新",         "mode": "script",  "output": None,
     "script": "validate_audio.py"},
    {"id": 7,   "name": "脚手架",           "mode": "online",  "output": "script.py"},
    {"id": 8,   "name": "生成代码",         "mode": "online",  "output": "script.py"},
    {"id": 9,   "name": "检查渲染",         "mode": "script",  "output": "output/",
     "script": "check.py && python3 scripts/render.py"},
    {"id": 10,  "name": "更新索引",         "mode": "online",  "output": "CLAUDE.md"},
]

SCRIPTS_DIR = Path(__file__).parent
PROMPTS_DIR = SCRIPTS_DIR / "prompts"


# ========== 工具函数 ==========

def get_step(step_id: float) -> dict:
    for s in STEPS:
        if float(s["id"]) == float(step_id):
            return s
    return None


def get_current_step(manager: StateManager) -> float:
    return manager.get_workflow_step()


def is_step_done(step: dict, project_dir: Path, current_step: float) -> bool:
    """判断步骤是否已完成"""
    if float(step["id"]) < float(current_step):
        return True
    if step["output"] and (project_dir / step["output"]).exists():
        return float(step["id"]) <= float(current_step)
    return False


def fill_template(template_path: Path, replacements: dict) -> str:
    """填充模板占位符"""
    content = template_path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        content = content.replace(f"{{{{{key}}}}}", value)
    return content


def read_file_safe(path: Path, max_chars: int = 3000) -> str:
    """安全读取文件，超长截断"""
    if not path.exists():
        return "(文件不存在)"
    text = path.read_text(encoding="utf-8")
    if len(text) > max_chars:
        return text[:max_chars] + f"\n\n...(内容已截断，完整内容见 {path.name})"
    return text


# ========== 命令实现 ==========

def cmd_status(project_dir: Path):
    """显示工作流进度表"""
    manager = StateManager(project_dir)
    content = manager.get_content_info()
    title = content.get("title") or project_dir.name
    level = content.get("knowledge_level", "")
    current_step = get_current_step(manager)

    header = f"{title}"
    if level:
        header += f"（{level}）"
    print(f"\n📊 {header}")
    print(f"   项目路径：{project_dir.resolve()}")
    print()

    # 统计完成数
    done_count = sum(1 for s in STEPS if float(s["id"]) < float(current_step))
    total_main = len([s for s in STEPS if float(s["id"]) == int(s["id"])])
    print(f"   进度：{done_count}/{len(STEPS)} 步骤（主步骤 {total_main} 个）")
    print()

    mode_icons = {"offline": "📤", "online": "💻", "script": "⚙️ "}
    print(f"   {'步骤':<5} {'名称':<18} {'模式':<8} 状态")
    print(f"   {'─'*50}")

    for step in STEPS:
        sid = float(step["id"])
        name = step["name"]
        mode = step["mode"]
        icon = mode_icons.get(mode, "  ")

        is_current = abs(sid - float(current_step)) < 0.01
        is_done = sid < float(current_step)

        # 检查输出文件是否存在
        output_exists = False
        if step["output"]:
            output_path = project_dir / step["output"]
            output_exists = output_path.exists()

        if is_done or output_exists:
            status = "✅ 完成"
            if step["output"] and output_exists:
                status += f" ({step['output']})"
        elif is_current:
            status = "⏳ 当前"
        else:
            status = "⏹  未开始"

        arrow = "→" if is_current else " "
        step_str = f"{step['id']:.1f}" if step["id"] != int(step["id"]) else str(int(step["id"]))
        print(f"  {arrow} {step_str:<5} {icon} {name:<16} [{mode:<7}] {status}")

    print()

    # 下一步提示
    current = get_step(current_step)
    if current:
        mode = current["mode"]
        if mode == "offline":
            print(f"   ▶ 下一步（离线）：python3 scripts/step_runner.py --export {int(current_step)} .")
            print(f"     将生成的 prompt 复制到 Claude.ai 或 ChatGPT 完成")
        elif mode == "script":
            script = current.get("script", "")
            print(f"   ▶ 下一步（脚本）：python3 scripts/{script}")
        else:
            print(f"   ▶ 下一步（在线）：在 Claude Code 中继续步骤 {current_step}")
            print(f"     建议：python3 scripts/step_runner.py --brief . 获取上下文简报")
    print()


def cmd_export(step_id: float, project_dir: Path):
    """导出离线步骤的 prompt 文件"""
    step = get_step(step_id)
    if not step:
        print(f"❌ 步骤 {step_id} 不存在")
        sys.exit(1)

    if step["mode"] != "offline":
        print(f"❌ 步骤 {step_id}（{step['name']}）不是离线步骤，无需导出 prompt")
        print(f"   该步骤模式：{step['mode']}")
        sys.exit(1)

    tpl_path = PROMPTS_DIR / step["prompt_tpl"]
    if not tpl_path.exists():
        print(f"❌ 模板文件不存在：{tpl_path}")
        sys.exit(1)

    manager = StateManager(project_dir)
    content = manager.get_content_info()
    decisions = manager.get_decisions()

    topic = content.get("title") or project_dir.name
    level = content.get("knowledge_level", "初中")
    level_constraints = LEVEL_CONSTRAINTS.get(level, "")

    # 读取已有文件内容
    outline_content = read_file_safe(project_dir / "topic_analysis.md")
    html_notes = ""
    if (project_dir / "preview.html").exists():
        html_notes = f"已有 HTML 预览文件 preview.html（请参考其中的图形设计）"

    replacements = {
        "TOPIC": topic,
        "LEVEL": level,
        "LEVEL_CONSTRAINTS": level_constraints,
        "INTRODUCTION_METHOD": decisions.get("introduction_method", "（待确认）"),
        "PROOF_METHOD": decisions.get("proof_method", "（待确认）"),
        "DURATION": decisions.get("duration_estimate", "2-3分钟"),
        "OUTLINE_CONTENT": outline_content,
        "HTML_NOTES": html_notes,
    }

    filled = fill_template(tpl_path, replacements)

    out_path = project_dir / step["prompt_out"]
    out_path.write_text(filled, encoding="utf-8")

    print(f"\n✅ 已生成离线 prompt：{out_path}")
    print(f"\n📋 操作步骤：")
    print(f"   1. 打开 {out_path}")
    print(f"   2. 复制全部内容到 Claude.ai（claude.ai/new）或 ChatGPT")
    print(f"   3. 将 AI 的回复保存到：{project_dir / step['output']}")
    print(f"   4. 完成后执行：python3 scripts/step_runner.py --done {int(step_id)} .")
    print()


def cmd_done(step_id: float, project_dir: Path):
    """标记步骤完成，更新状态和会话简报"""
    step = get_step(step_id)
    if not step:
        print(f"❌ 步骤 {step_id} 不存在")
        sys.exit(1)

    manager = StateManager(project_dir)
    current = get_current_step(manager)

    # 验证输出文件存在（如果有要求）
    if step["output"] and not (project_dir / step["output"]).exists():
        print(f"⚠️  警告：输出文件不存在 {step['output']}")
        print(f"   请确认已将 AI 的回复保存到该文件后再标记完成")
        confirm = input("   仍要标记为完成？[y/N] ").strip().lower()
        if confirm != "y":
            print("   已取消")
            return

    # 推进到下一步
    next_steps = [s for s in STEPS if float(s["id"]) > float(step_id)]
    next_step_id = next_steps[0]["id"] if next_steps else step_id

    manager.set_workflow_step(next_step_id, "in_progress")
    manager.generate_session_brief()

    print(f"\n✅ 步骤 {step_id}（{step['name']}）已标记完成")
    print(f"   下一步：步骤 {next_step_id}（{get_step(next_step_id)['name'] if get_step(next_step_id) else '完成'}）")
    print(f"   会话简报已更新：{project_dir / 'session_brief.md'}")
    print()

    # 在 session boundary 自动展示接力 prompt
    reason = SESSION_BOUNDARY_AFTER.get(float(step_id), "")
    if reason:
        cmd_handoff(project_dir, reason=reason)


def cmd_brief(project_dir: Path):
    """打印会话简报（供新会话粘贴使用）"""
    manager = StateManager(project_dir)
    brief = manager.generate_session_brief()
    print("\n" + "=" * 60)
    print("会话简报（复制以下内容到新的 Claude Code 会话）：")
    print("=" * 60)
    print(brief)
    print("=" * 60)
    print()


def cmd_handoff(project_dir: Path, reason: str = ""):
    """生成接力 prompt（完整的新会话启动指令）"""
    manager = StateManager(project_dir)
    content = manager.get_content_info()
    decisions = manager.get_decisions()
    current_step = get_current_step(manager)

    title = content.get("title") or project_dir.name
    level = content.get("knowledge_level", "")
    current = get_step(current_step)
    step_name = current["name"] if current else f"步骤{current_step}"
    step_mode = current["mode"] if current else "online"

    # 收集已完成文件
    artifacts = [
        ("topic_analysis.md", "主题分析"),
        ("outline.md", "大纲"),
        ("preview.html", "HTML预览"),
        ("分镜脚本.md", "分镜脚本"),
        ("audio/", "音频文件"),
        ("script.py", "Manim脚本"),
    ]
    done_files = [f"{label}({fname}) ✅" for fname, label in artifacts
                  if (project_dir / fname).exists()]
    missing_files = [f"{label}({fname}) ⏳" for fname, label in artifacts
                     if not (project_dir / fname).exists()]

    # 决策摘要
    decision_lines = [f"- {DECISION_LABELS.get(k, k)}：{v}" for k, v in decisions.items()]

    # 下一步操作说明
    if step_mode == "offline":
        next_action = (
            f"执行步骤 {current_step}（{step_name}）：\n"
            f"1. 运行：`python3 scripts/step_runner.py --export {int(current_step)} .`\n"
            f"2. 复制生成的 prompt 文件内容到 Claude.ai 完成\n"
            f"3. 将结果保存到项目目录\n"
            f"4. 运行：`python3 scripts/step_runner.py --done {int(current_step)} .`"
        )
    elif step_mode == "script":
        script = current.get("script", "")
        next_action = f"运行脚本完成步骤 {current_step}：\n`python3 scripts/{script}`"
    else:
        next_action = f"继续执行步骤 {current_step}（{step_name}）"

    # 组装完整接力 prompt
    lines = [
        f"继续制作《{title}》科普视频。",
        f"",
        f"**项目路径**：`{project_dir}`",
        f"**当前步骤**：步骤 {current_step} - {step_name}",
        f"",
        f"先运行以下命令确认当前状态：",
        f"```bash",
        f"cd {project_dir}",
        f"python3 scripts/step_runner.py --status .",
        f"```",
        f"",
    ]

    if decision_lines:
        lines += ["**已确认决策**："] + decision_lines + [""]

    if done_files:
        lines += [f"**已完成文件**：{', '.join(done_files)}", ""]

    lines += [
        f"**下一步任务**：",
        next_action,
    ]

    handoff_text = "\n".join(lines)

    # 写入文件
    handoff_file = project_dir / "handoff_prompt.md"
    handoff_file.write_text(handoff_text, encoding="utf-8")

    # 打印大字警告 + prompt
    width = 62
    print()
    print("╔" + "═" * width + "╗")
    if reason:
        print(f"║  ⚠️  {reason:<{width-5}}║")
        print("║" + " " * width + "║")
    print(f"║  🔄  建议开启新会话以节省 Token{' ' * (width - 31)}║")
    print("╚" + "═" * width + "╝")
    print()
    print("─" * (width + 2))
    print("📋 复制以下内容，粘贴到新的 Claude Code 会话：")
    print("─" * (width + 2))
    print()
    print(handoff_text)
    print()
    print("─" * (width + 2))
    print(f"💾 已保存到：{handoff_file}")
    print()


# 需要在 --done 后自动触发换会话提示的步骤
SESSION_BOUNDARY_AFTER = {
    1.0: "步骤 2-4 均为离线步骤，建议新会话处理检查点",
    2.5: "检查点1 完成，下一步为离线步骤",
    3.5: "检查点2 完成，下一步为离线步骤",
    4.5: "检查点3 完成，接下来是 TTS 生成（脚本）",
    6.0: "TTS 验证完成，下一步是最重的代码生成，强烈建议新会话",
}


def cmd_decide(key: str, value: str, project_dir: Path):
    """保存关键决策"""
    manager = StateManager(project_dir)
    manager.save_decision(key, value)
    manager.generate_session_brief()

    label = DECISION_LABELS.get(key, key)
    print(f"✅ 已保存决策：{label} = {value}")
    print(f"   会话简报已更新：{project_dir / 'session_brief.md'}")


# ========== 主入口 ==========

def main():
    parser = argparse.ArgumentParser(
        description="Step Runner - Explainer 工作流步骤管理（Token 节省模式）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 scripts/step_runner.py --status .
  python3 scripts/step_runner.py --export 2 .
  python3 scripts/step_runner.py --done 2 .
  python3 scripts/step_runner.py --handoff .
  python3 scripts/step_runner.py --brief .
  python3 scripts/step_runner.py --decide introduction_method "直角三角形楼梯问题" .
        """
    )
    parser.add_argument("--status", action="store_true", help="显示工作流进度")
    parser.add_argument("--export", type=float, metavar="STEP", help="导出离线步骤的 prompt 文件")
    parser.add_argument("--done", type=float, metavar="STEP", help="标记步骤完成")
    parser.add_argument("--handoff", action="store_true", help="生成接力 prompt（新会话启动指令）")
    parser.add_argument("--brief", action="store_true", help="打印会话简报")
    parser.add_argument("--decide", nargs=2, metavar=("KEY", "VALUE"), help="保存关键决策")
    parser.add_argument("project_dir", nargs="?", default=".", help="项目目录（默认当前目录）")

    args = parser.parse_args()
    project_dir = Path(args.project_dir).resolve()

    if not project_dir.exists():
        print(f"❌ 项目目录不存在：{project_dir}")
        sys.exit(1)

    if args.status:
        cmd_status(project_dir)
    elif args.export is not None:
        cmd_export(args.export, project_dir)
    elif args.done is not None:
        cmd_done(args.done, project_dir)
    elif args.handoff:
        cmd_handoff(project_dir)
    elif args.brief:
        cmd_brief(project_dir)
    elif args.decide:
        cmd_decide(args.decide[0], args.decide[1], project_dir)
    else:
        # 默认显示状态
        cmd_status(project_dir)


if __name__ == "__main__":
    main()
