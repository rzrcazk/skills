"""Ending Scene Template — 系列结束场景模板（总结预告式）"""

from manim import *
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from templates.shared import COLORS, CANVAS_CONFIG


class EndingScene(Scene):
    """系列结束模板 — 总结预告式"""

    # 画布配置
    config.pixel_width = CANVAS_CONFIG["pixel_width"]
    config.pixel_height = CANVAS_CONFIG["pixel_height"]
    config.frame_rate = CANVAS_CONFIG["frame_rate"]

    # 配色方案
    COLORS = COLORS

    # 系列信息
    SERIES_NAME = "数学之旅"
    EPISODE_TITLE = "勾股定理"
    NEXT_EPISODE = "相似三角形"       # 下集预告（必须用户确认）

    # 本集要点（列表形式）
    KEY_POINTS = [
        "勾股定理：a² + b² = c²",
        "仅适用于直角三角形",
        "中国古代称为'商高定理'",
    ]

    # Logo配置
    LOGO_PATH = "assets/logo.png"
    LOGO_FALLBACK = True

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
        """结束动画主流程"""
        # 设置背景
        self.camera.background_color = self.COLORS['background']

        # 添加水印
        self.add_watermark()

        # 添加结束音频（如果有）
        self._add_audio_if_exists()

        # 1. 本集要点回顾（5秒）
        self._play_summary()

        # 2. 下集预告（3秒）
        self._play_preview()

        # 3. Logo淡出（2秒）
        self._play_outro()

    def _play_summary(self):
        """播放本集要点回顾"""
        # 标题
        title = Text(
            "本集要点",
            font_size=48,
            color=self.COLORS['primary'],
            weight=BOLD
        )
        title.to_edge(UP, buff=1.0)

        self.play(FadeIn(title, shift=DOWN), run_time=0.5)

        # 要点列表
        points_group = VGroup()
        for i, point in enumerate(self.KEY_POINTS):
            # 序号
            number = Text(f"{i+1}.", font_size=28, color=self.COLORS['highlight'])
            # 内容
            content = Text(point, font_size=28, color=self.COLORS['text'])
            # 组合
            point_line = VGroup(number, content)
            point_line.arrange(RIGHT, aligned_edge=UP, buff=0.3)
            points_group.add(point_line)

        # 垂直排列
        points_group.arrange(DOWN, aligned_edge=LEFT, buff=0.4)
        points_group.next_to(title, DOWN, buff=0.8)
        points_group.to_edge(LEFT, buff=2.0)

        # 逐个显示要点
        for point_line in points_group:
            self.play(FadeIn(point_line, shift=RIGHT), run_time=0.4)
            self.wait(0.3)

        self.wait(1.5)

        # 淡出要点
        self.play(
            FadeOut(title),
            FadeOut(points_group),
            run_time=0.5
        )

    def _play_preview(self):
        """播放下集预告"""
        # 预告标题
        preview_title = Text(
            "下期预告",
            font_size=40,
            color=self.COLORS['secondary'],
            weight=BOLD
        )
        preview_title.to_edge(UP, buff=1.5)

        self.play(FadeIn(preview_title, scale=0.8), run_time=0.5)

        # 下集标题
        next_title = Text(
            self.NEXT_EPISODE,
            font_size=56,
            color=self.COLORS['highlight']
        )
        next_title.center()

        self.play(
            FadeIn(next_title, shift=UP),
            run_time=1
        )

        # 提示文字
        hint = Text(
            "敬请期待...",
            font_size=24,
            color=self.COLORS['text_secondary']
        )
        hint.next_to(next_title, DOWN, buff=0.5)

        self.play(FadeIn(hint), run_time=0.5)
        self.wait(1)

        # 淡出
        self.play(
            FadeOut(preview_title),
            FadeOut(next_title),
            FadeOut(hint),
            run_time=0.5
        )

    def _play_outro(self):
        """播放Logo淡出"""
        # 创建Logo
        logo = self._create_logo()

        # Logo淡入
        self.play(FadeIn(logo, scale=0.8), run_time=0.8)

        # 系列名称
        series_name = Text(
            self.SERIES_NAME,
            font_size=36,
            color=self.COLORS['primary']
        )
        series_name.next_to(logo, DOWN, buff=0.5)

        self.play(FadeIn(series_name), run_time=0.5)

        # 停留
        self.wait(0.5)

        # 整体淡出
        self.play(
            FadeOut(logo),
            FadeOut(series_name),
            run_time=1
        )

        # 结束语
        ending = Text(
            "感谢观看",
            font_size=32,
            color=self.COLORS['text_secondary']
        )
        ending.center()

        self.play(FadeIn(ending), run_time=0.5)
        self.wait(0.5)

        self.play(FadeOut(ending), run_time=0.5)

    def _create_logo(self):
        """创建Logo"""
        logo_path = os.path.join(self.audio_dir, "..", self.LOGO_PATH)

        if os.path.exists(logo_path) and not self.LOGO_FALLBACK:
            logo = ImageMobject(logo_path)
            logo.scale(0.6)
            return logo
        else:
            return self._create_geometric_logo()

    def _create_geometric_logo(self):
        """创建几何Logo"""
        logo_group = VGroup()

        outer_circle = Circle(
            radius=0.8,
            color=self.COLORS['primary'],
            stroke_width=3
        )
        logo_group.add(outer_circle)

        inner_symbol = MathTex(r"\sum", font_size=40, color=self.COLORS['highlight'])
        logo_group.add(inner_symbol)

        return logo_group

    def _add_audio_if_exists(self):
        """添加结束音频（如果存在）"""
        # 检查可能的结束音频文件
        possible_audio_files = [
            "audio_999_结尾.wav",
            "audio_098_总结.wav",
            "audio_099_结尾.wav",
        ]

        for audio_file in possible_audio_files:
            audio_path = os.path.join(self.audio_dir, audio_file)
            if os.path.exists(audio_path):
                try:
                    self.add_sound(audio_path)
                    return
                except Exception as e:
                    print(f"Warning: Failed to add ending audio: {e}")


class EndingSceneWithExercise(EndingScene):
    """
    结束模板（练习引导式）
    包含一道练习题，鼓励学生思考
    """

    # 练习题
    EXERCISE_QUESTION = "一个直角三角形的两条直角边分别为3和4，斜边是多少？"
    EXERCISE_HINT = "（提示：使用勾股定理）"

    def _play_summary(self):
        """播放要点回顾 + 练习题"""
        # 调用父类的要点回顾
        super()._play_summary()

        # 添加练习题
        self._play_exercise()

    def _play_exercise(self):
        """播放练习题"""
        # 标题
        exercise_title = Text(
            "课后练习",
            font_size=40,
            color=self.COLORS['secondary'],
            weight=BOLD
        )
        exercise_title.to_edge(UP, buff=1.0)

        self.play(FadeIn(exercise_title, shift=DOWN), run_time=0.5)

        # 题目
        question = Text(
            self.EXERCISE_QUESTION,
            font_size=28,
            color=self.COLORS['text']
        )
        question.scale(0.9)
        question.center()

        self.play(FadeIn(question), run_time=0.8)

        # 提示
        hint = Text(
            self.EXERCISE_HINT,
            font_size=24,
            color=self.COLORS['text_secondary']
        )
        hint.next_to(question, DOWN, buff=0.5)

        self.play(FadeIn(hint), run_time=0.5)
        self.wait(2)

        # 淡出
        self.play(
            FadeOut(exercise_title),
            FadeOut(question),
            FadeOut(hint),
            run_time=0.5
        )
