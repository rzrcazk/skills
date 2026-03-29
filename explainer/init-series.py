#!/usr/bin/env python3
"""
Explainer 技能 - 系列视频项目初始化脚本

支持三级目录结构：
  大类（数学/物理） → 小类（几何/代数） → 具体内容（勾股定理）

功能：
1. 检查依赖环境
2. 创建三级目录结构
3. 生成元数据文件（_content_info.json, _category_info.json, _subcategory_info.json）
4. 自动维护 CLAUDE.md
5. 拷贝脚手架模板到内容目录

使用：
    python3 init-series.py [系列项目根目录]
    python3 init-series.py [系列项目根目录] --create-content 数学 几何 勾股定理

默认在当前目录创建系列项目结构。
"""

import os
import sys
import shutil
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple


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
        "check": ["manim", "version"],
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
        "required": False,
        "note": "LaTeX 用于渲染数学公式，建议安装以获得最佳效果",
    },
    "ffmpeg": {
        "check": ["ffmpeg", "-version"],
        "install_hint": "brew install ffmpeg (macOS) 或 apt install ffmpeg (Linux)",
        "required": False,
    },
}

# 状态图标映射
STATUS_ICONS = {
    "paused": "⏸️",
    "planned": "📋",
    "storyboard": "📝",
    "audio_pending": "🎙️",
    "rendering": "🎬",
    "completed": "✅",
}

STATUS_LABELS = {
    "paused": "已暂停",
    "planned": "已规划",
    "storyboard": "分镜完成",
    "audio_pending": "待录音",
    "rendering": "渲染中",
    "completed": "已完成",
}


# ========== 颜色输出 ==========
class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    RESET = "\033[0m"


def ok(msg):
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def warn(msg):
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {msg}")


def error(msg):
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


def info(msg):
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {msg}")


def section(title):
    print()
    print(f"{Colors.CYAN}{'=' * 50}{Colors.RESET}")
    print(f"{Colors.CYAN}{title}{Colors.RESET}")
    print(f"{Colors.CYAN}{'=' * 50}{Colors.RESET}")


# ========== 依赖检查 ==========
def check_dependency(name: str, config: dict) -> bool:
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


def check_all_dependencies() -> bool:
    """检查所有依赖"""
    section("检查依赖环境")

    all_ok = True
    for name, config in DEPENDENCIES.items():
        if not check_dependency(name, config):
            all_ok = False

    print()
    return all_ok


# ========== 元数据管理 ==========
def create_category_info(category_dir: Path, name: str, icon: str = "📚", description: str = "") -> dict:
    """创建/读取大类元数据"""
    info_path = category_dir / "_category_info.json"

    if info_path.exists():
        with open(info_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    data = {
        "name": name,
        "name_en": "",
        "description": description or f"{name}科普系列",
        "icon": icon,
        "order": 1,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data


def create_subcategory_info(subcategory_dir: Path, name: str, parent_category: str, description: str = "") -> dict:
    """创建/读取小类元数据"""
    info_path = subcategory_dir / "_subcategory_info.json"

    if info_path.exists():
        with open(info_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    data = {
        "name": name,
        "name_en": "",
        "parent_category": parent_category,
        "description": description or f"{name}相关内容",
        "order": 1,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data


def create_content_info(
    content_dir: Path,
    title: str,
    category: str,
    subcategory: str,
    knowledge_level: str = "初中"
) -> dict:
    """创建内容元数据"""
    info_path = content_dir / "_content_info.json"

    # 生成ID
    content_id = f"{category}-{subcategory}-{title}".lower().replace(" ", "-").replace("_", "-")

    data = {
        "id": content_id,
        "title": title,
        "title_en": "",
        "category": category,
        "subcategory": subcategory,
        "knowledge_level": knowledge_level,
        "status": "planned",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "duration_seconds": 0,
        "duration_formatted": "0:00",
        "files": {
            "storyboard": "分镜脚本.md",
            "script": "script.py",
            "audio_dir": "audio/",
            "output_video": f"output/{title}.mp4"
        },
        "dependencies": [],
        "prerequisites": [],
        "next_episodes": [],
        "tags": [],
    }

    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data


def update_content_status(content_dir: Path, status: str, duration_seconds: int = 0):
    """更新内容状态"""
    info_path = content_dir / "_content_info.json"

    if not info_path.exists():
        return

    with open(info_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    data["status"] = status
    data["updated_at"] = datetime.now().isoformat()

    if duration_seconds > 0:
        data["duration_seconds"] = duration_seconds
        minutes = duration_seconds // 60
        seconds = duration_seconds % 60
        data["duration_formatted"] = f"{minutes}:{seconds:02d}"

    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ========== 目录结构管理 ==========
def ensure_content_structure(
    project_dir: Path,
    category: str,
    subcategory: str,
    content_title: str,
    knowledge_level: str = "初中"
) -> Path:
    """
    确保三级目录结构存在，返回内容目录路径
    """
    # 1. 创建大类目录
    category_dir = project_dir / category
    category_dir.mkdir(parents=True, exist_ok=True)
    create_category_info(category_dir, category)
    ok(f"大类目录: {category}/")

    # 2. 创建小类目录
    subcategory_dir = category_dir / subcategory
    subcategory_dir.mkdir(parents=True, exist_ok=True)
    create_subcategory_info(subcategory_dir, subcategory, category)
    ok(f"小类目录: {category}/{subcategory}/")

    # 3. 创建内容目录
    content_dir = subcategory_dir / content_title
    content_dir.mkdir(parents=True, exist_ok=True)
    create_content_info(content_dir, content_title, category, subcategory, knowledge_level)
    ok(f"内容目录: {category}/{subcategory}/{content_title}/")

    # 4. 创建子目录
    (content_dir / "audio").mkdir(exist_ok=True)
    (content_dir / "media").mkdir(exist_ok=True)
    (content_dir / "output").mkdir(exist_ok=True)
    (content_dir / "assets").mkdir(exist_ok=True)

    return content_dir


def copy_templates_to_content(content_dir: Path):
    """拷贝脚手架模板到内容目录"""
    # 拷贝 script_scaffold.py
    scaffold_src = TEMPLATES_DIR / "script_scaffold.py"
    scaffold_dst = content_dir / "script.py"

    if scaffold_src.exists():
        shutil.copy2(scaffold_src, scaffold_dst)
        ok(f"script.py - 脚手架模板")
    else:
        warn(f"模板不存在: {scaffold_src}")

    # 拷贝示例文件（如果存在）
    example_src = TEMPLATES_DIR / "script_example.py"
    example_dst = content_dir / "script_example.py"

    if example_src.exists():
        shutil.copy2(example_src, example_dst)
        ok(f"script_example.py - 参考示例")


def generate_csv_template(content_dir: Path, title: str):
    """生成音频列表CSV模板"""
    csv_path = content_dir / "audio_list.csv"

    csv_content = f"""filename,text
audio_000_开场.wav,"嗨~欢迎来到3分钟数学科普！我是你们的老朋友~今天我们要聊的是：{title}！"
audio_001_引入.wav,"话说啊，{title}是一个非常有意思的知识点..."
audio_002_概念.wav,"首先，我们来了解一下什么是{title}..."
audio_003_演示.wav,"让我们通过一个动画来理解..."
audio_004_例子.wav,"来看一个具体的例子..."
audio_998_总结.wav,"好~今天的{title}就讲到这里！"
audio_999_结尾.wav,"下期我们要聊的是...敬请期待！拜拜~"
"""

    if not csv_path.exists():
        csv_path.write_text(csv_content, encoding='utf-8')
        ok(f"audio_list.csv - 音频列表模板")
    else:
        warn("audio_list.csv 已存在，跳过")


def generate_gitignore(project_dir: Path):
    """生成根目录 .gitignore 文件"""
    gitignore_path = project_dir / ".gitignore"

    if not gitignore_path.exists():
        content = """# Manim
media/
__pycache__/
*.pyc

# Audio
*/audio/*.wav
*/audio/*.mp3
!*/audio/audio_info.json

# Video output
*/output/*.mp4
*/output/*.mov

# Manim media
*/media/

# Temp
.DS_Store
*.log

# Metadata (keep these)
!*/_category_info.json
!*/_subcategory_info.json
!*/_content_info.json
"""
        gitignore_path.write_text(content)
        ok(".gitignore")


# ========== CLAUDE.md 管理 ==========
def scan_all_contents(project_dir: Path) -> list:
    """扫描所有内容目录，返回内容列表"""
    contents = []

    for category_dir in project_dir.iterdir():
        if not category_dir.is_dir():
            continue
        if category_dir.name.startswith('.') or category_dir.name.startswith('_'):
            continue
        if category_dir.name in ['templates', 'scripts', 'shared_assets']:
            continue

        category_info_path = category_dir / "_category_info.json"
        category_info = {}
        if category_info_path.exists():
            with open(category_info_path, 'r', encoding='utf-8') as f:
                category_info = json.load(f)

        for subcategory_dir in category_dir.iterdir():
            if not subcategory_dir.is_dir() or subcategory_dir.name.startswith('_'):
                continue

            subcategory_info_path = subcategory_dir / "_subcategory_info.json"
            subcategory_info = {}
            if subcategory_info_path.exists():
                with open(subcategory_info_path, 'r', encoding='utf-8') as f:
                    subcategory_info = json.load(f)

            for content_dir in subcategory_dir.iterdir():
                if not content_dir.is_dir() or content_dir.name.startswith('_'):
                    continue

                content_info_path = content_dir / "_content_info.json"
                if content_info_path.exists():
                    with open(content_info_path, 'r', encoding='utf-8') as f:
                        content_info = json.load(f)

                    contents.append({
                        "category": category_info.get("name", category_dir.name),
                        "subcategory": subcategory_info.get("name", subcategory_dir.name),
                        "title": content_info.get("title", content_dir.name),
                        "status": content_info.get("status", "planned"),
                        "knowledge_level": content_info.get("knowledge_level", ""),
                        "duration_formatted": content_info.get("duration_formatted", "-"),
                        "updated_at": content_info.get("updated_at", ""),
                        "path": f"{category_dir.name}/{subcategory_dir.name}/{content_dir.name}/",
                    })

    return contents


def update_claude_md(project_dir: Path):
    """更新 CLAUDE.md 文件"""
    claude_path = project_dir / "CLAUDE.md"
    contents = scan_all_contents(project_dir)

    # 按类别组织
    categories = {}
    for c in contents:
        cat = c["category"]
        sub = c["subcategory"]
        if cat not in categories:
            categories[cat] = {}
        if sub not in categories[cat]:
            categories[cat][sub] = []
        categories[cat][sub].append(c)

    # 统计
    total_videos = len(contents)
    completed = sum(1 for c in contents if c["status"] == "completed")

    # 生成内容
    lines = [
        "# 科普视频系列项目",
        "",
        "## 项目概览",
        f"- 创建时间: {datetime.now().strftime('%Y-%m-%d')}",
        f"- 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- 视频总数: {total_videos}",
        f"- 已完成: {completed}",
        "",
        "## 目录结构",
        "",
    ]

    for category, subcategories in sorted(categories.items()):
        total_in_cat = sum(len(videos) for videos in subcategories.values())
        lines.append(f"### {category} ({total_in_cat}个视频)")
        lines.append("")

        for subcategory, videos in sorted(subcategories.items()):
            lines.append(f"#### {subcategory} ({len(videos)}个视频)")
            lines.append("")
            lines.append("| 内容 | 状态 | 时长 | 知识水平 | 文件路径 |")
            lines.append("|------|------|------|----------|----------|")

            for video in sorted(videos, key=lambda x: x["title"]):
                icon = STATUS_ICONS.get(video["status"], "⏸️")
                label = STATUS_LABELS.get(video["status"], video["status"])
                lines.append(
                    f"| {video['title']} | {icon} {label} | {video['duration_formatted']} | "
                    f"{video['knowledge_level']} | {video['path']} |"
                )

            lines.append("")

    # 添加状态说明
    lines.extend([
        "## 状态说明",
        "",
    ])
    for status, label in STATUS_LABELS.items():
        icon = STATUS_ICONS.get(status, "")
        lines.append(f"- {icon} {label}")

    lines.extend([
        "",
        "## 快速导航",
        "",
        "### 最近更新",
    ])

    # 最近更新（按时间倒序）
    recent = sorted(
        [c for c in contents if c["updated_at"]],
        key=lambda x: x["updated_at"],
        reverse=True
    )[:5]

    for i, video in enumerate(recent, 1):
        date_str = video["updated_at"][:10] if video["updated_at"] else ""
        lines.append(f"{i}. [{video['title']}]({video['path']}分镜脚本.md) - {date_str}")

    if not recent:
        lines.append("暂无更新记录")

    lines.extend([
        "",
        "---",
        "*此文件由 init-series.py 自动生成*",
    ])

    claude_path.write_text('\n'.join(lines), encoding='utf-8')
    ok("CLAUDE.md - 项目索引已更新")


# ========== 主流程 ==========
def init_series_project(project_dir: Path):
    """初始化系列项目根目录"""
    section("初始化系列项目")

    project_dir.mkdir(parents=True, exist_ok=True)
    info(f"项目目录: {project_dir.resolve()}")
    print()

    # 创建共享资源目录
    (project_dir / "shared_assets" / "logo").mkdir(parents=True, exist_ok=True)
    (project_dir / "shared_assets" / "bgm").mkdir(parents=True, exist_ok=True)
    ok("shared_assets/ - 共享资源目录")

    # 生成 gitignore
    generate_gitignore(project_dir)

    # 生成初始 CLAUDE.md
    update_claude_md(project_dir)


def create_content(
    project_dir: Path,
    category: str,
    subcategory: str,
    title: str,
    knowledge_level: str = "初中"
) -> Path:
    """创建新内容"""
    section(f"创建新内容: {category} / {subcategory} / {title}")

    # 确保目录结构
    content_dir = ensure_content_structure(project_dir, category, subcategory, title, knowledge_level)

    # 拷贝模板
    copy_templates_to_content(content_dir)

    # 生成CSV
    generate_csv_template(content_dir, title)

    # 更新 CLAUDE.md
    update_claude_md(project_dir)

    return content_dir


def main():
    # 解析参数
    args = sys.argv[1:]

    # 检查是否是创建内容模式
    if "--create-content" in args:
        idx = args.index("--create-content")
        project_dir = Path(args[0] if idx > 0 else ".")
        category = args[idx + 1]
        subcategory = args[idx + 2]
        title = args[idx + 3]

        # 可选参数：知识水平
        knowledge_level = "初中"
        if idx + 4 < len(args):
            knowledge_level = args[idx + 4]

        # 检查依赖
        if not check_all_dependencies():
            section("依赖检查失败")
            error("请先安装必需依赖")
            info("快速安装: uv pip install manim edge-tts mutagen")
            sys.exit(1)

        # 初始化项目（如果不存在）
        if not (project_dir / "CLAUDE.md").exists():
            init_series_project(project_dir)

        # 创建内容
        content_dir = create_content(project_dir, category, subcategory, title, knowledge_level)

        section("内容创建完成")
        info(f"内容目录: {content_dir}")
        info(f"\n下一步:")
        info(f"  1. 确认用户知识水平（当前: {knowledge_level}）")
        info(f"  2. 编辑 {content_dir}/audio_list.csv 填写对白")
        info(f"  3. 生成音频: python3 {SCRIPTS_DIR}/generate_tts.py {content_dir}/audio_list.csv {content_dir}/audio")
        info(f"  4. 创建分镜脚本: {content_dir}/分镜脚本.md")
        info(f"  5. 实现动画: {content_dir}/script.py")
        info(f"  6. 渲染视频: cd {content_dir} && manim -pqh script.py ExplainerScene")
        info(f"\n查看项目状态: {project_dir}/CLAUDE.md")

    else:
        # 初始化模式
        project_dir = Path(args[0] if args else ".")

        section("Explainer 系列视频项目初始化")
        info(f"项目目录: {project_dir.resolve()}")
        info(f"技能目录: {SKILL_DIR}")
        print()

        # 检查依赖
        if not check_all_dependencies():
            section("依赖检查失败")
            error("请先安装必需依赖")
            info("快速安装: uv pip install manim edge-tts mutagen")
            sys.exit(1)

        # 初始化项目
        init_series_project(project_dir)

        section("项目初始化完成")
        info("\n使用方法:")
        info(f"  创建内容: python3 {SKILL_DIR}/init-series.py . --create-content 数学 几何 勾股定理")
        info(f"  或: python3 {SKILL_DIR}/init-series.py . --create-content 数学 几何 勾股定理 初中")
        info(f"\n项目状态: {project_dir}/CLAUDE.md")


if __name__ == "__main__":
    main()
