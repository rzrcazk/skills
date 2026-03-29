#!/usr/bin/env python3
"""
Manim 教学视频渲染脚本（支持系列项目）
完整流程: 检查代码 -> 渲染视频 -> 拷贝到output

使用方法:
    # 在内容目录内执行
    cd 数学/几何/勾股定理/
    python3 ../../../scripts/render.py [options]

    # 或指定路径
    python3 scripts/render.py 数学/几何/勾股定理/script.py [options]

选项:
    -f, --file      指定脚本文件 (默认: script.py)
    -s, --scene     指定场景类名 (默认: ExplainerScene)
    -q, --quality   渲染质量: l(ow)/m(edium)/h(igh)/k(4k) (默认: high)
    -p, --preview   渲染后预览 (默认: 开启)
    --no-check      跳过代码检查 (不推荐)

示例:
    python3 scripts/render.py                    # 默认渲染当前目录的 script.py
    python3 scripts/render.py -f my_script.py    # 渲染指定文件
    python3 scripts/render.py -s MyScene         # 指定场景类名
    python3 scripts/render.py -q k               # 4K质量渲染
"""

import subprocess
import sys
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import CONFIG
from logger import get_logger

logger = get_logger(__name__)


class RenderPipeline:
    """渲染流水线"""

    QUALITY_MAP = CONFIG.render.quality_map

    def __init__(self, script_file='script.py', scene_name='ExplainerScene',
                 quality='high', preview=False, skip_check=False, no_srt=False,
                 check_only=False):
        self.script_file = Path(script_file)
        self.scene_name = scene_name
        self.quality = self.QUALITY_MAP.get(quality, CONFIG.render.default_quality)
        self.preview = preview
        self.skip_check = skip_check
        self.no_srt = no_srt
        self.check_only = check_only

        # 检查脚本路径
        self.script_dir = Path(__file__).parent.parent
        self.check_script = self.script_dir / 'scripts' / 'check.py'

    def run_check(self):
        """第一步: 运行代码检查"""
        if self.skip_check:
            print("⚠️  跳过代码检查 (不推荐)")
            return True

        print("🔍 步骤 1/3: 代码结构检查")
        print("=" * 50)

        if not self.check_script.exists():
            print(f"❌ 检查脚本不存在: {self.check_script}")
            return False

        try:
            result = subprocess.run(
                [sys.executable, str(self.check_script), str(self.script_file)],
                cwd=self.script_file.parent,
                capture_output=False
            )
            return result.returncode == 0
        except Exception as e:
            print(f"❌ 检查失败: {e}")
            return False

    def run_render(self):
        """第二步: 运行 Manim 渲染"""
        print("\n🎬 步骤 2/3: 渲染视频")
        print("=" * 50)

        if not self.script_file.exists():
            print(f"❌ 脚本文件不存在: {self.script_file}")
            return False

        # 构建 manim 命令
        cmd = ['manim']

        # 质量参数
        cmd.extend(['-q', self.quality[0]])  # l/m/h/k

        # 预览参数
        if self.preview:
            cmd.append('-p')

        # 脚本和场景
        cmd.extend([str(self.script_file), self.scene_name])

        print(f"执行命令: {' '.join(cmd)}")
        print(f"工作目录: {self.script_file.parent}")
        print()

        try:
            result = subprocess.run(cmd, cwd=self.script_file.parent)
            return result.returncode == 0
        except FileNotFoundError:
            print("❌ 未找到 manim 命令，请确保已安装: pip install manim")
            return False
        except Exception as e:
            print(f"❌ 渲染失败: {e}")
            return False

    def copy_to_output(self):
        """第三步: 拷贝视频到output目录"""
        print("\n📁 步骤 3/3: 拷贝视频到output目录")
        print("=" * 50)

        # 查找生成的视频文件
        content_dir = self.script_file.parent
        media_dir = content_dir / 'media' / 'videos' / self.script_file.stem

        if not media_dir.exists():
            print(f"⚠️  媒体目录不存在: {media_dir}")
            return

        # 按分辨率优先级查找
        possible_paths = [
            media_dir / '2160p60' / f'{self.scene_name}.mp4',
            media_dir / '1920p60' / f'{self.scene_name}.mp4',
            media_dir / '1080p60' / f'{self.scene_name}.mp4',
            media_dir / '720p30' / f'{self.scene_name}.mp4',
            media_dir / '480p15' / f'{self.scene_name}.mp4',
        ]

        video_src = None
        for path in possible_paths:
            if path.exists():
                video_src = path
                break

        if video_src:
            import shutil
            output_dir = content_dir / 'output'
            output_dir.mkdir(exist_ok=True)
            video_dst = output_dir / f'{content_dir.name}.mp4'
            try:
                shutil.copy2(video_src, video_dst)
                print(f"✅ 视频已拷贝: {video_dst}")
                print(f"   源文件: {video_src}")

                # 更新_content_info.json状态
                self.update_content_status(content_dir)
            except Exception as e:
                print(f"⚠️  拷贝失败: {e}")
        else:
            print("⚠️  未找到生成的视频文件")

    def update_content_status(self, content_dir):
        """更新内容状态为completed"""
        import json
        info_path = content_dir / "_content_info.json"
        if info_path.exists():
            try:
                with open(info_path, 'r', encoding='utf-8') as f:
                    info = json.load(f)
                info['status'] = 'completed'
                info['updated_at'] = datetime.now().isoformat()
                with open(info_path, 'w', encoding='utf-8') as f:
                    json.dump(info, f, ensure_ascii=False, indent=2)
                print(f"✅ 内容状态已更新: completed")
            except Exception as e:
                print(f"⚠️  更新状态失败: {e}")

    def generate_srt_file(self):
        """步骤 4/4: 生成 SRT 字幕文件"""
        if self.no_srt:
            print("\n⏭  跳过 SRT 生成 (--no-srt)")
            return

        print("\n📝 步骤 4/4: 生成 SRT 字幕文件")
        print("=" * 50)

        content_dir = self.script_file.parent
        audio_dir = content_dir / 'audio'
        output_dir = content_dir / 'output'
        srt_output = output_dir / f'{content_dir.name}.srt'

        if not (audio_dir / 'audio_info.json').exists():
            print(f"⚠️  audio_info.json 不存在，跳过 SRT 生成")
            return

        srt_script = Path(__file__).parent / 'generate_srt.py'
        if not srt_script.exists():
            print(f"⚠️  generate_srt.py 不存在: {srt_script}")
            return

        output_dir.mkdir(exist_ok=True)
        try:
            result = subprocess.run(
                [sys.executable, str(srt_script), str(audio_dir), '--output', str(srt_output)],
                cwd=content_dir,
                capture_output=False
            )
            if result.returncode != 0:
                print("⚠️  SRT 生成失败")
        except Exception as e:
            print(f"⚠️  SRT 生成出错: {e}")

    def run(self):
        """运行完整流程"""
        print("\n" + "=" * 50)
        print("🎬 Manim 教学视频渲染流水线")
        print("=" * 50)
        print(f"脚本文件: {self.script_file}")
        print(f"场景类名: {self.scene_name}")
        print(f"渲染质量: {self.quality}")
        print("=" * 50 + "\n")

        # 步骤1: 检查
        if not self.run_check():
            print("\n⛔ 代码检查失败，终止渲染。")
            print("   请修复错误后重试，或使用 --no-check 跳过检查（不推荐）")
            return False

        if self.check_only:
            print("\n✅ 代码检查通过（--check-only，跳过渲染）")
            return True

        # 步骤2: 渲染
        if not self.run_render():
            print("\n⛔ 渲染失败。")
            return False

        # 步骤3: 拷贝到output
        self.copy_to_output()

        # 步骤4: 生成 SRT
        self.generate_srt_file()

        print("\n" + "=" * 50)
        print("✅ 渲染完成！")
        print("=" * 50)

        return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Manim 教学视频渲染流水线',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
    python scripts/render.py                    # 默认渲染 script.py
    python scripts/render.py -f my_script.py    # 渲染指定文件
    python scripts/render.py -s MyScene         # 指定场景类名
    python scripts/render.py -q k               # 4K质量渲染
    python scripts/render.py --no-check         # 跳过检查（不推荐）
        '''
    )

    parser.add_argument(
        '-f', '--file',
        default='script.py',
        help='要渲染的脚本文件 (默认: script.py)'
    )

    parser.add_argument(
        '-s', '--scene',
        default='ExplainerScene',
        help='场景类名 (默认: ExplainerScene)'
    )

    parser.add_argument(
        '-q', '--quality',
        default='high',
        choices=['l', 'low', 'm', 'medium', 'h', 'high', 'k', '4k'],
        help='渲染质量: l/low(480p), m/medium(720p), h/high(1080p), k/4k(2160p) (默认: high)'
    )

    parser.add_argument(
        '-p', '--preview',
        action='store_true',
        default=False,
        help='渲染后预览（默认关闭，Claude Code 无头模式不支持）'
    )

    parser.add_argument(
        '--no-preview',
        action='store_true',
        help='渲染后不预览（已是默认行为）'
    )

    parser.add_argument(
        '--no-check',
        action='store_true',
        help='跳过代码检查 (不推荐)'
    )

    parser.add_argument(
        '--no-srt',
        action='store_true',
        help='跳过 SRT 字幕文件生成'
    )

    parser.add_argument(
        '--check-only',
        action='store_true',
        help='只运行代码检查，不渲染'
    )

    args = parser.parse_args()

    # 处理 --no-preview
    preview = not args.no_preview

    # 创建流水线
    pipeline = RenderPipeline(
        script_file=args.file,
        scene_name=args.scene,
        quality=args.quality,
        preview=preview,
        skip_check=args.no_check,
        no_srt=args.no_srt,
        check_only=args.check_only
    )

    # 运行
    success = pipeline.run()

    # 退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
