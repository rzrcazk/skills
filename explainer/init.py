#!/usr/bin/env python3
"""
Explainer 技能项目初始化脚本

功能：
1. 检查依赖环境（uv, manim, edge-tts等）
2. 创建项目目录结构
3. 拷贝脚手架模板
4. 生成示例CSV文件

使用：
    python3 init.py [项目目录]

默认在当前目录创建项目结构。
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path


# ========== 配置 ==========
SKILL_DIR = Path(__file__).parent.resolve()
TEMPLATES_DIR = SKILL_DIR / "templates"
SCRIPTS_DIR = SKILL_DIR / "scripts"

# 依赖检查配置
DEPENDENCIES = {
    "uv": {
        "check": ["uv", "--version"],
        "install_hint": "curl -LsSf https://astral.sh/uv/install.sh | sh",
        "required": True,
    },
    "manim": {
        "check": ["manim", "--version"],
        "install_hint": "uv pip install manim",
        "required": True,
    },
    "edge-tts": {
        "check": ["edge-tts", "--version"],
        "install_hint": "uv pip install edge-tts",
        "required": True,
    },
    "latex": {
        "check": ["latex", "--version"],
        "install_hint": "macOS: brew install --cask mactex-no-gui 或 Ubuntu: sudo apt install texlive",
        "required": True,  # 强制必需，不允许降级
        "note": "⚠️ LaTeX 是强制依赖，用于渲染数学公式，不允许使用降级方案",
    },
    "ffmpeg": {
        "check": ["ffmpeg", "-version"],
        "install_hint": "brew install ffmpeg (macOS) 或 apt install ffmpeg (Linux)",
        "required": False,  # 可选但推荐
    },
}

# 项目目录结构
PROJECT_STRUCTURE = {
    "audio": "音频文件目录",
    "media": "Manim渲染输出",
    "assets": "静态资源",
}


# ========== 颜色输出 ==========
class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    RESET = "\033[0m"


def ok(msg):
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def warn(msg):
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {msg}")


def error(msg):
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


def info(msg):
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {msg}")


# ========== 依赖检查 ==========
def check_dependency(name, config):
    """检查单个依赖"""
    try:
        result = subprocess.run(
            config["check"],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            version = result.stdout.decode().strip().split('\n')[0][:50]
            ok(f"{name}: {version}")
            return True
    except FileNotFoundError:
        pass

    if config["required"]:
        error(f"{name}: 未安装 (必需)")
        info(f"  安装: {config['install_hint']}")
    else:
        warn(f"{name}: 未安装 (可选)")
        info(f"  安装: {config['install_hint']}")
        if "note" in config:
            info(f"  说明: {config['note']}")

    return not config["required"]


def check_all_dependencies():
    """检查所有依赖"""
    print("=" * 50)
    print("检查依赖环境")
    print("=" * 50)

    all_ok = True
    for name, config in DEPENDENCIES.items():
        if not check_dependency(name, config):
            all_ok = False

    print()
    return all_ok


# ========== 项目初始化 ==========
def create_directory_structure(project_dir):
    """创建项目目录结构"""
    print("=" * 50)
    print("创建项目目录")
    print("=" * 50)

    project_path = Path(project_dir)
    project_path.mkdir(parents=True, exist_ok=True)

    for dirname, description in PROJECT_STRUCTURE.items():
        dirpath = project_path / dirname
        dirpath.mkdir(exist_ok=True)
        ok(f"{dirname}/ - {description}")

    print()


def copy_templates(project_dir):
    """拷贝脚手架模板"""
    print("=" * 50)
    print("拷贝模板文件")
    print("=" * 50)

    project_path = Path(project_dir)

    # 拷贝 script_scaffold.py
    scaffold_src = TEMPLATES_DIR / "script_scaffold.py"
    scaffold_dst = project_path / "script.py"

    if scaffold_src.exists():
        shutil.copy2(scaffold_src, scaffold_dst)
        ok(f"script.py - 脚手架模板 (从 script_scaffold.py)")
        info("  提示: 根据分镜实现 TODO 部分")
    else:
        error(f"模板不存在: {scaffold_src}")

    # 拷贝 script_example.py 作为参考
    example_src = TEMPLATES_DIR / "script_example.py"
    example_dst = project_path / "script_example.py"

    if example_src.exists():
        shutil.copy2(example_src, example_dst)
        ok(f"script_example.py - 完整示例 (参考用)")
    else:
        warn("script_example.py 模板不存在")

    print()


def generate_csv_template(project_dir):
    """生成示例CSV文件"""
    print("=" * 50)
    print("生成音频列表模板")
    print("=" * 50)

    project_path = Path(project_dir)
    csv_path = project_path / "audio_list.csv"

    csv_content = """filename,text
audio_000_开场.wav,"嗨~欢迎来到3分钟数学科普！我是你们的老朋友~今天我们要聊的是：勾股定理！"
audio_001_引入.wav,"话说啊，勾股定理可以说是几何学里最著名的定理之一了"
audio_002_公式.wav,"勾股定理说：在直角三角形中，两条直角边的平方和，等于斜边的平方"
audio_003_动画演示.wav,"让我们来看看这个动画..."
audio_004_历史故事.wav,"这个定理啊，其实中国古代周朝就已经发现了..."
audio_998_总结.wav,"好~今天的勾股定理就讲到这里！记住，直角边平方和等于斜边平方！"
audio_999_结尾.wav,"下期我们要聊的是相似三角形，敬请期待！拜拜~"
"""

    if not csv_path.exists():
        csv_path.write_text(csv_content, encoding='utf-8')
        ok(f"audio_list.csv - 音频列表模板")
        info("  使用: python3{}/scripts/generate_tts.py audio_list.csv ./audio".format(SKILL_DIR))
    else:
        warn("audio_list.csv 已存在，跳过")

    print()


def generate_gitignore(project_dir):
    """生成 .gitignore 文件"""
    project_path = Path(project_dir)
    gitignore_path = project_path / ".gitignore"

    if not gitignore_path.exists():
        content = """# Manim
media/
__pycache__/
*.pyc

# Audio
audio/*.wav
audio/*.mp3
!audio/audio_info.json

# Video
*.mp4
*.mov

# Temp
.DS_Store
*.log
"""
        gitignore_path.write_text(content)
        ok(".gitignore")


# ========== 主流程 ==========
def main():
    # 解析参数
    project_dir = sys.argv[1] if len(sys.argv) > 1 else "."

    print("\n" + "=" * 50)
    print("Explainer 技能 - 科普视频项目初始化")
    print("=" * 50)
    print(f"项目目录: {Path(project_dir).resolve()}")
    print(f"技能目录: {SKILL_DIR}")
    print()

    # 1. 检查依赖
    if not check_all_dependencies():
        print("=" * 50)
        error("依赖检查失败，请先安装必需依赖")
        print()
        print("快速安装:")
        print("  uv pip install manim edge-tts mutagen")
        sys.exit(1)

    # 2. 创建目录结构
    create_directory_structure(project_dir)

    # 3. 拷贝模板
    copy_templates(project_dir)

    # 4. 生成CSV
    generate_csv_template(project_dir)

    # 5. 生成gitignore
    generate_gitignore(project_dir)

    # 完成
    print("=" * 50)
    ok("项目初始化完成！")
    print("=" * 50)
    print()
    print("下一步:")
    print("  1. 确认用户知识水平（初中/高中/大学）")
    print("  2. 编辑 audio_list.csv 填写对白")
    print("  3. 生成音频: python3{}/scripts/generate_tts.py audio_list.csv ./audio".format(SKILL_DIR))
    print("  4. 编辑 script.py 实现动画")
    print("  5. 渲染视频: manim -pqh script.py ExplainerScene")
    print()


if __name__ == "__main__":
    main()
