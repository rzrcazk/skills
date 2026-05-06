"""Opening Scene Template — 系列开场场景模板"""

from manim import *
import os
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from templates.shared import COLORS, CANVAS_CONFIG


class OpeningScene(Scene):
    """系列开场模板"""

    # 画布配置
    config.pixel_width = CANVAS_CONFIG["pixel_width"]
    config.pixel_height = CANVAS_CONFIG["pixel_height"]
    config.frame_rate = CANVAS_CONFIG["frame_rate"]

    # 配色方案
    COLORS = COLORS

    # 系列信息（可配置）
    SERIES_NAME = "数学之旅"          # 系列名称
    EPISODE_NUMBER = 1                # 集数
    EPISODE_TITLE = "勾股定理"        # 本期标题
    SUBTITLE = "初中数学科普系列"     # 副标题

    # Logo配置
    LOGO_PATH = "assets/logo.png"     # Logo图片路径
    LOGO_FALLBACK = True              # 如果没有图片，使用几何Logo

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.audio_dir = "audio"

    def add_watermark(self):
        """添加AI生成水印"""
        watermark = Text(
            "AI生成",
            font_size=20,
            color="#888888"
        )
        watermark.to_edge(DOWN + RIGHT, buff=0.3)
        watermark.set_opacity(0.5)
        self.add(watermark)

    def construct(self):
        """开场动画主流程"""
        # 设置背景
        self.camera.background_color = self.COLORS['background']

        # 添加水印
        self.add_watermark()

        # 添加开场音频（如果有）
        self._add_audio_if_exists()

        # 1. Logo淡入动画（2秒）
        logo = self._create_logo()
        logo.set_opacity(0)

        self.play(
            logo.animate.set_opacity(1).scale(1.1),
            run_time=2,
            rate_func=smooth
        )

        # 2. 系列名称打字机效果（3秒）
        series_title = Text(
            self.SERIES_NAME,
            font_size=72,
            color=self.COLORS['primary'],
            weight=BOLD
        )
        series_title.next_to(logo, DOWN, buff=0.8)

        # 打字机动画
        self.play(
            AddTextLetterByLetter(series_title, run_time=2.5),
            run_time=3
        )

        # 3. 副标题显示（1.5秒）
        subtitle = Text(
            self.SUBTITLE,
            font_size=32,
            color=self.COLORS['text_secondary']
        )
        subtitle.next_to(series_title, DOWN, buff=0.5)

        self.play(
            FadeIn(subtitle, shift=DOWN * 0.5),
            run_time=1.5
        )

        # 4. 集数信息（1秒）
        episode_info = Text(
            f"第 {self.EPISODE_NUMBER} 期：{self.EPISODE_TITLE}",
            font_size=40,
            color=self.COLORS['highlight']
        )
        episode_info.next_to(subtitle, DOWN, buff=0.6)

        self.play(
            FadeIn(episode_info, scale=0.8),
            run_time=1
        )

        # 停留一下
        self.wait(0.5)

        # 5. 整体淡出（可选，如果后面紧接内容）
        # self.play(
        #     FadeOut(logo),
        #     FadeOut(series_title),
        #     FadeOut(subtitle),
        #     FadeOut(episode_info),
        #     run_time=0.8
        # )

    def _create_logo(self):
        """创建Logo（图片或几何图形）"""
        logo_path = os.path.join(self.audio_dir, "..", self.LOGO_PATH)

        if os.path.exists(logo_path) and not self.LOGO_FALLBACK:
            # 使用图片Logo
            logo = ImageMobject(logo_path)
            logo.scale(0.8)
            return logo
        else:
            # 使用几何Logo作为备选
            return self._create_geometric_logo()

    def _create_geometric_logo(self):
        """创建几何Logo（备选方案）"""
        # 创建一个数学符号风格的Logo
        # 例如：一个圆形内嵌几何图形

        logo_group = VGroup()

        # 外圈
        outer_circle = Circle(
            radius=1.2,
            color=self.COLORS['primary'],
            stroke_width=4
        )
        logo_group.add(outer_circle)

        # 内嵌几何元素（根据系列主题变化）
        # 数学系列：使用 π 符号或几何图形
        inner_symbol = MathTex(r"\sum", font_size=60, color=self.COLORS['highlight'])
        logo_group.add(inner_symbol)

        # 装饰点
        for angle in [0, 90, 180, 270]:
            dot = Dot(
                point=outer_circle.point_at_angle(angle * DEGREES),
                color=self.COLORS['secondary'],
                radius=0.08
            )
            logo_group.add(dot)

        return logo_group

    def _add_audio_if_exists(self):
        """添加开场音频（如果存在）"""
        audio_path = os.path.join(self.audio_dir, "audio_000_开场.wav")
        if os.path.exists(audio_path):
            try:
                self.add_sound(audio_path)
            except Exception as e:
                print(f"Warning: Failed to add opening audio: {e}")


class OpeningSceneMinimal(OpeningScene):
    """
    极简开场模板 - 更简洁的版本
    总时长：约5秒
    """

    def construct(self):
        """极简开场动画"""
        self.camera.background_color = self.COLORS['background']

        # 快速淡入Logo和标题
        logo = self._create_logo()
        title = Text(
            f"{self.SERIES_NAME} - {self.EPISODE_TITLE}",
            font_size=48,
            color=self.COLORS['primary']
        )
        title.next_to(logo, DOWN, buff=0.5)

        self.play(
            FadeIn(logo, scale=0.5),
            FadeIn(title, shift=UP),
            run_time=2
        )

        self.wait(1)

        # 显示集数
        episode = Text(
            f"第 {self.EPISODE_NUMBER} 期",
            font_size=32,
            color=self.COLORS['text_secondary']
        )
        episode.next_to(title, DOWN, buff=0.3)

        self.play(FadeIn(episode), run_time=1)
        self.wait(1)
