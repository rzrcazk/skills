#!/usr/bin/env python3
"""
Scene Agent - 单场景生成Agent

功能：
为单个场景生成完整内容：
- 主旁白音频（TTS）
- 角色独白音频（卡通小助手）
- Manim脚本并渲染预览视频
- 时间轴文档（timeline.md）
- 独白脚本（narration_script.md）
- 场景说明（README.md）

输出目录结构：
    scene_XXX_name/
    ├── audio_main.wav              # 主旁白音频
    ├── audio_narration.wav         # 角色独白音频
    ├── audio_bg.wav                # 背景音乐（可选）
    ├── video_preview.mp4           # 预览视频
    ├── script.py                   # Manim脚本
    ├── timeline.md                 # 时间轴文档
    ├── narration_script.md         # 独白脚本
    ├── README.md                   # 场景说明
    └── status.json                 # 生成状态

使用方式（由 parallel_generator.py 调用）：
    python3 scripts/scene_agent.py --project . --scene-dir scenes/scene_001_intro --config '{...}'
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class SceneAgent:
    """单场景生成Agent"""

    def __init__(self, project_dir: Path, scene_dir: Path, config: Dict):
        self.project_dir = Path(project_dir)
        self.scene_dir = Path(scene_dir)
        self.config = config

        self.skill_dir = Path(__file__).parent.parent
        self.scene_id = config.get("scene_id", 0)
        self.scene_name = config.get("name", f"scene_{self.scene_id}")
        self.template_type = config.get("template_type", "content")
        self.description = config.get("description", "")

        # 音频文件路径
        self.audio_main_path = self.scene_dir / "audio_main.wav"
        self.audio_narration_path = self.scene_dir / "audio_narration.wav"
        self.audio_bg_path = self.scene_dir / "audio_bg.wav"

        # 视频文件路径
        self.video_path = self.scene_dir / "video_preview.mp4"
        self.script_path = self.scene_dir / "script.py"

        # 文档路径
        self.timeline_path = self.scene_dir / "timeline.md"
        self.narration_script_path = self.scene_dir / "narration_script.md"
        self.readme_path = self.scene_dir / "README.md"

        # 状态文件
        self.status_path = self.scene_dir / "status.json"

    def generate(self) -> bool:
        """生成场景的所有内容"""
        print(f"\n{'='*60}")
        print(f"🎬 生成场景 {self.scene_id}: {self.scene_name}")
        print(f"   类型: {self.template_type}")
        print(f"{'='*60}")

        try:
            # 1. 生成主旁白音频
            self._generate_main_audio()

            # 2. 生成角色独白音频
            self._generate_narration_audio()

            # 3. 创建Manim脚本
            self._create_manim_script()

            # 4. 渲染视频（无头模式）
            self._render_video()

            # 5. 生成时间轴文档
            self._generate_timeline()

            # 6. 生成独白脚本
            self._generate_narration_script()

            # 7. 生成README
            self._generate_readme()

            # 8. 更新状态
            self._update_status("completed")

            print(f"\n✅ 场景 {self.scene_id} 生成完成!")
            print(f"   目录: {self.scene_dir}")
            return True

        except Exception as e:
            print(f"\n❌ 场景 {self.scene_id} 生成失败: {e}")
            self._update_status("failed", error=str(e))
            import traceback
            traceback.print_exc()
            return False

    def _generate_main_audio(self):
        """生成主旁白音频"""
        print(f"\n🔊 生成主旁白音频...")

        # 根据场景类型和描述生成旁白文本
        narration_text = self._generate_narration_text()

        # 使用 edge-tts 生成音频
        try:
            import edge_tts
            import asyncio

            async def generate():
                voice = "zh-CN-XiaoxiaoNeural"  # 女声
                communicate = edge_tts.Communicate(narration_text, voice)
                await communicate.save(str(self.audio_main_path))

            asyncio.run(generate())

            print(f"   ✓ 主旁白: {self.audio_main_path}")

        except ImportError:
            # 如果没有edge_tts，创建占位音频
            print(f"   ⚠️ edge_tts 未安装，创建占位音频")
            self._create_placeholder_audio(self.audio_main_path, duration=5.0)

        except Exception as e:
            print(f"   ⚠️ 音频生成失败: {e}，创建占位音频")
            self._create_placeholder_audio(self.audio_main_path, duration=5.0)

    def _generate_narration_text(self) -> str:
        """根据场景生成旁白文本"""
        if self.template_type == "opening":
            return f"欢迎来到{self.scene_name}。今天我们将探索{self.description}。"
        elif self.template_type == "ending":
            return f"这就是{self.scene_name}的核心内容。下期我们将继续探索更多知识。"
        else:
            # 内容场景
            return f"现在我们来学习{self.scene_name}。{self.description[:100]}"

    def _generate_narration_audio(self):
        """生成角色独白音频"""
        print(f"\n🎭 生成角色独白音频...")

        # 卡通小助手独白
        narration_text = self._generate_character_narration_text()

        if not narration_text:
            print(f"   ℹ️ 此场景无独白")
            return

        try:
            import edge_tts
            import asyncio

            async def generate():
                voice = "zh-CN-XiaoyiNeural"  # 童声
                communicate = edge_tts.Communicate(narration_text, voice)
                await communicate.save(str(self.audio_narration_path))

            asyncio.run(generate())

            print(f"   ✓ 独白音频: {self.audio_narration_path}")

        except Exception as e:
            print(f"   ⚠️ 独白生成失败: {e}")
            # 独白是可选的

    def _generate_character_narration_text(self) -> str:
        """生成卡通小助手独白文本"""
        # 根据场景类型生成不同风格的独白
        if self.template_type == "opening":
            return "哇！又要开始新的冒险了，好期待呀！"
        elif self.template_type == "content":
            return f"咦？{self.scene_name}听起来好有趣！"
        elif self.template_type == "ending":
            return "今天的学习真开心！下次见！"
        return ""

    def _create_placeholder_audio(self, output_path: Path, duration: float = 5.0):
        """创建占位音频（静音）"""
        try:
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"anullsrc=r=44100:cl=stereo",
                "-t", str(duration),
                "-acodec", "pcm_s16le",
                str(output_path)
            ]
            subprocess.run(cmd, capture_output=True, check=True)
        except:
            # 如果ffmpeg失败，创建空文件
            output_path.touch()

    def _create_manim_script(self):
        """创建Manim脚本"""
        print(f"\n📝 创建Manim脚本...")

        # 根据模板类型选择不同的脚本模板
        if self.template_type == "opening":
            script = self._create_opening_script()
        elif self.template_type == "ending":
            script = self._create_ending_script()
        else:
            script = self._create_content_script()

        # 保存脚本
        self.script_path.write_text(script, encoding='utf-8')
        print(f"   ✓ 脚本: {self.script_path}")

    def _create_opening_script(self) -> str:
        """创建开场场景脚本

        ManimCE 最佳实践：
        - 使用 Create() 而不是 ShowCreation()
        - 使用 .animate 进行变换动画
        - 使用 rate_func 控制动画节奏
        - 使用 next_to() 进行相对定位
        """
        return f'''#!/usr/bin/env python3
"""
{self.scene_name} - 开场场景
使用 ManimCE 最佳实践
"""
from manim import *
import os

class Scene{self.scene_id:03d}(Scene):
    """{self.scene_name} - 开场场景"""

    def construct(self):
        # 背景颜色
        self.camera.background_color = "#1a1a2e"

        # 添加音频
        audio_path = "audio_main.wav"
        if os.path.exists(audio_path):
            self.add_sound(audio_path)

        # ========== 使用 VGroup 组合对象 ==========
        # Logo 组
        logo = Circle(radius=1.2, color="#4ecca3", stroke_width=4)
        symbol = MathTex(r"\\sum", font_size=60, color="#ffc107")
        logo_group = VGroup(logo, symbol)
        logo_group.center()

        # ========== 标题使用相对定位 ==========
        # 主标题
        title = Text("{self.scene_name}", font_size=48, color="#4ecca3")
        title.next_to(logo_group, DOWN, buff=0.5)

        # 副标题
        subtitle = Text("数学之旅", font_size=32, color="#aaaaaa")
        subtitle.next_to(title, DOWN, buff=0.3)

        # ========== 使用 Create() 和 FadeIn 进行动画 ==========
        # 创建 Logo
        self.play(Create(logo), run_time=1.5, rate_func=smooth)
        self.play(FadeIn(symbol), run_time=1.0, rate_func=smooth)

        # 标题动画
        self.play(FadeIn(title, shift=DOWN), run_time=1.5, rate_func=smooth)
        self.play(FadeIn(subtitle), run_time=1.0, rate_func=smooth)

        # 等待（音画同步）
        self.wait(1)

        # ========== 淡出动画 ==========
        self.play(
            FadeOut(logo_group),
            FadeOut(title),
            FadeOut(subtitle),
            run_time=1.0,
            rate_func=smooth
        )
'''

    def _create_ending_script(self) -> str:
        """创建结束场景脚本"""
        return f'''#!/usr/bin/env python3
from manim import *
import os

class Scene{self.scene_id:03d}(Scene):
    """{self.scene_name} - 结束场景"""

    def construct(self):
        # 背景
        self.camera.background_color = "#1a1a2e"

        # 添加音频
        audio_path = "audio_main.wav"
        if os.path.exists(audio_path):
            self.add_sound(audio_path)

        # 标题
        title = Text("本集要点", font_size=40, color="#4ecca3")
        title.to_edge(UP, buff=1)
        self.play(FadeIn(title, shift=DOWN), run_time=0.5)

        # 要点
        points = VGroup(
            Text("• {self.description[:30]}...", font_size=28, color="white"),
            Text("• 下期预告: 更多精彩", font_size=28, color="white"),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.4)
        points.next_to(title, DOWN, buff=0.8)

        for point in points:
            self.play(FadeIn(point, shift=RIGHT), run_time=0.5)

        self.wait(2)

        # 结束语
        ending = Text("感谢观看", font_size=36, color="#ffc107")
        self.play(
            FadeOut(title),
            FadeOut(points),
            FadeIn(ending),
            run_time=1
        )
        self.wait(1)

        self.play(FadeOut(ending), run_time=0.5)
'''

    def _create_content_script(self) -> str:
        """创建内容场景脚本

        ManimCE 最佳实践：
        - 使用 .animate 进行变换动画
        - 使用 MathTex 渲染数学公式
        - 使用 VGroup 组合相关对象
        - 使用 next_to(), to_edge() 相对定位
        - 使用 rate_func 控制动画节奏
        - 音画同步：动画时长匹配音频
        """
        return f'''#!/usr/bin/env python3
"""
{self.scene_name} - 内容场景
使用 ManimCE 最佳实践
"""
from manim import *
import os

class Scene{self.scene_id:03d}(Scene):
    """{self.scene_name} - 内容场景"""

    def construct(self):
        # ========== 背景颜色 ==========
        self.camera.background_color = "#1a1a2e"

        # ========== 音频管理（音画同步） ==========
        # 添加主旁白音频
        audio_main = "audio_main.wav"
        if os.path.exists(audio_main):
            self.add_sound(audio_main)

        # 添加独白音频（如果有）
        audio_narration = "audio_narration.wav"
        if os.path.exists(audio_narration):
            self.wait(2)  # 延迟 2 秒添加独白
            self.add_sound(audio_narration)

        # ========== 场景标题 ==========
        title = Text("{self.scene_name}", font_size=36, color="#4ecca3")
        title.to_edge(UP, buff=0.5)
        self.play(FadeIn(title), run_time=0.5, rate_func=smooth)

        # ========== 内容区域 ==========
        # 内容文本（限制长度）
        content_text = {repr(self.description[:100])}
        content = Text(
            content_text,
            font_size=28,
            color="white",
            line_spacing=1.5
        )
        content.scale(0.8)
        content.center()

        # 淡入内容
        self.play(FadeIn(content), run_time=1.0, rate_func=smooth)
        self.wait(3)  # 给观众阅读时间

        # ========== 几何图形装饰 ==========
        circle = Circle(radius=0.5, color="#e94560", stroke_width=2)
        circle.to_corner(DL, buff=1)

        # 使用 Create() 动画
        self.play(Create(circle), run_time=0.5, rate_func=smooth)
        self.wait(1)

        # ========== 淡出所有对象 ==========
        self.play(
            FadeOut(title),
            FadeOut(content),
            FadeOut(circle),
            run_time=0.8,
            rate_func=smooth
        )
'''

    def _render_video(self):
        """渲染视频（无头模式）"""
        print(f"\n🎬 渲染视频...")

        # 使用manim渲染
        cmd = [
            "manim",
            "-qh",  # 高质量
            "--fps", "60",
            "--format", "mp4",
            str(self.script_path),
            f"Scene{self.scene_id:03d}"
        ]

        try:
            result = subprocess.run(
                cmd,
                cwd=self.scene_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )

            if result.returncode == 0:
                # 查找生成的视频
                media_dir = self.scene_dir / "media" / "videos" / "script"
                for quality in ["1080p60", "720p30"]:
                    video_src = media_dir / quality / f"Scene{self.scene_id:03d}.mp4"
                    if video_src.exists():
                        shutil.copy2(video_src, self.video_path)
                        print(f"   ✓ 视频: {self.video_path}")
                        return

                print(f"   ⚠️ 找不到生成的视频文件")
            else:
                print(f"   ⚠️ 渲染失败: {result.stderr[:200]}")

        except subprocess.TimeoutExpired:
            print(f"   ⚠️ 渲染超时")
        except FileNotFoundError:
            print(f"   ⚠️ manim 命令未找到")
        except Exception as e:
            print(f"   ⚠️ 渲染异常: {e}")

        # 如果渲染失败，创建占位视频
        self._create_placeholder_video()

    def _create_placeholder_video(self):
        """创建占位视频"""
        try:
            # 使用ffmpeg创建黑屏视频
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"color=c=black:s=1920x1080:d=5",
                "-f", "lavfi",
                "-i", "anullsrc=r=44100:cl=stereo",
                "-shortest",
                "-c:v", "libx264",
                "-c:a", "aac",
                str(self.video_path)
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            print(f"   ✓ 占位视频: {self.video_path}")
        except:
            self.video_path.touch()

    def _generate_timeline(self):
        """生成时间轴文档"""
        print(f"\n📄 生成时间轴文档...")

        # 获取音频时长
        main_duration = self._get_audio_duration(self.audio_main_path)
        narration_duration = self._get_audio_duration(self.audio_narration_path)

        total_duration = max(main_duration, narration_duration + 2.0 if narration_duration > 0 else 0)

        timeline_content = f"""# 场景时间轴: {self.scene_name}

## 基本信息
- **场景ID**: {self.scene_id}
- **场景名称**: {self.scene_name}
- **场景类型**: {self.template_type}
- **总时长**: {total_duration:.1f}秒
- **主旁白时长**: {main_duration:.1f}秒
- **独白时长**: {narration_duration:.1f}秒

## 场景描述
{self.description}

## 时间轴详情

| 时间 | 音频类型 | 音频内容 | 画面内容 | 同步状态 |
|------|----------|----------|----------|----------|
| 0.0-{main_duration:.1f}s | 主旁白 | {self._generate_narration_text()[:50]}... | 场景标题和内容 | ✅ |
"""

        if narration_duration > 0:
            timeline_content += f"""| 2.0-{2.0 + narration_duration:.1f}s | 独白 | {self._generate_character_narration_text()} | 角色动画 | ✅ |
"""

        timeline_content += f"""
## 音频文件
- **主旁白**: `audio_main.wav` ({main_duration:.1f}s)
- **角色独白**: `audio_narration.wav` ({narration_duration:.1f}s)

## 审核检查项

### 音频同步
- [ ] 主旁白与画面切换同步
- [ ] 独白时间点准确（约2.0s处）
- [ ] 背景音乐音量适中（如有）

### 画面质量
- [ ] 文字清晰可读
- [ ] 动画流畅无卡顿
- [ ] 颜色搭配协调

### 内容准确性
- [ ] 场景标题正确
- [ ] 内容描述准确
- [ ] 语言表达清晰

## 问题记录
<!-- 审核时在此处记录问题 -->

## 审核结论
- [ ] 通过，可进入合并流程
- [ ] 需要修改（详见问题记录）

---
*生成时间: {datetime.now().isoformat()}*
"""

        self.timeline_path.write_text(timeline_content, encoding='utf-8')
        print(f"   ✓ 时间轴: {self.timeline_path}")

    def _get_audio_duration(self, audio_path: Path) -> float:
        """获取音频时长"""
        if not audio_path.exists():
            return 0.0

        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return float(result.stdout.strip())
        except:
            return 5.0  # 默认5秒

    def _generate_narration_script(self):
        """生成独白脚本"""
        print(f"\n🎭 生成独白脚本...")

        narration_text = self._generate_character_narration_text()

        if not narration_text:
            content = f"""# 角色内心独白脚本

## 角色: 小数点 (Dotty)
- **性格**: 好奇、活泼、爱提问
- **声音**: 童声/轻快

## 独白内容

本场景无角色独白。

---
*生成时间: {datetime.now().isoformat()}*
"""
        else:
            content = f"""# 角色内心独白脚本

## 角色: 小数点 (Dotty)
- **性格**: 好奇、活泼、爱提问
- **声音**: 童声/轻快
- **口头禅**: "哇！原来是这样！"

## 独白内容

### 🤔 时间点: 2.0s
**独白**: "{narration_text}"
**情绪**: 好奇
**画面配合**: 角色出现，歪头思考

### 声音参数
- **语速**: +0%
- **音调**: +10%
- **音量**: 100%

---
*生成时间: {datetime.now().isoformat()}*
"""

        self.narration_script_path.write_text(content, encoding='utf-8')
        print(f"   ✓ 独白脚本: {self.narration_script_path}")

    def _generate_readme(self):
        """生成README说明"""
        print(f"\n📖 生成场景说明...")

        readme_content = f"""# 场景 {self.scene_id}: {self.scene_name}

## 概述
- **场景类型**: {self.template_type}
- **场景描述**: {self.description[:100]}

## 文件清单
- `audio_main.wav` - 主旁白音频
- `audio_narration.wav` - 角色独白音频（可选）
- `video_preview.mp4` - 预览视频
- `script.py` - Manim脚本
- `timeline.md` - 时间轴文档
- `narration_script.md` - 独白脚本
- `status.json` - 生成状态

## 审核指南

### 快速检查
1. 播放 `video_preview.mp4` 检查音画同步
2. 阅读 `timeline.md` 核对时间轴
3. 检查 `narration_script.md` 确认独白风格

### 问题反馈
如有问题，请在 `timeline.md` 的"问题记录"部分添加说明。

## 使用说明

将此目录打包发送给其他AI进行审核：
```bash
tar czf scene_{self.scene_id:03d}_{self.scene_name}.tar.gz scenes/scene_{self.scene_id:03d}_{self.scene_name}/
```

其他AI可以独立检查此场景，无需了解整个项目结构。

---
*生成时间: {datetime.now().isoformat()}*
"""

        self.readme_path.write_text(readme_content, encoding='utf-8')
        print(f"   ✓ README: {self.readme_path}")

    def _update_status(self, status: str, error: Optional[str] = None):
        """更新状态文件"""
        data = {
            "scene_id": self.scene_id,
            "name": self.scene_name,
            "template_type": self.template_type,
            "status": status,
            "error": error,
            "updated_at": datetime.now().isoformat(),
        }

        if status == "completed":
            data["files"] = {
                "audio_main": str(self.audio_main_path.relative_to(self.scene_dir)),
                "audio_narration": str(self.audio_narration_path.relative_to(self.scene_dir)) if self.audio_narration_path.exists() else None,
                "video": str(self.video_path.relative_to(self.scene_dir)),
                "script": str(self.script_path.relative_to(self.scene_dir)),
                "timeline": str(self.timeline_path.relative_to(self.scene_dir)),
                "narration_script": str(self.narration_script_path.relative_to(self.scene_dir)),
                "readme": str(self.readme_path.relative_to(self.scene_dir)),
            }

        self.status_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Scene Agent - 单场景生成")
    parser.add_argument("--project", required=True, help="项目目录")
    parser.add_argument("--scene-dir", required=True, help="场景输出目录")
    parser.add_argument("--config", required=True, help="场景配置(JSON)")

    args = parser.parse_args()

    project_dir = Path(args.project)
    scene_dir = Path(args.scene_dir)
    config = json.loads(args.config)

    # 创建场景目录
    scene_dir.mkdir(parents=True, exist_ok=True)

    # 创建agent并生成
    agent = SceneAgent(project_dir, scene_dir, config)
    success = agent.generate()

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
