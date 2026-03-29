"""
Explainer Video Scene Scaffold
科普视频场景脚手架

根据分镜脚本和音频信息生成完整动画

关键区别于 tutor：
- 固定开场/结尾格式（系列感）
- 更幽默的动画风格
- 无需题目.html，直接从分镜生成
- 支持分段渲染（通过 SCENE_RANGE 控制）

使用方式：
1. 复制此文件为 script.py
2. 根据分镜实现 TODO 部分
3. 运行 manim -pqh script.py ExplainerScene
4. 分段渲染时，脚本会自动只渲染 SCENE_RANGE 指定的 scenes

常见问题：
- 渲染卡住：通常是音频文件问题，尝试禁用 add_scene_audio
- deepcopy 错误：不要存储 self 引用到 Mobject 中
- 视频未生成：检查 copy_video_to_root 路径是否正确

ManimCE 最佳实践：
- 使用 .animate 进行变换动画
- 使用 MathTex 渲染数学公式
- 使用 rate_func 控制动画节奏
- 使用 next_to, to_edge 等相对定位
"""

from manim import *
import json
import os

# 分段渲染支持：如果没有定义 SCENE_RANGE，则渲染所有 scenes
if 'SCENE_RANGE' not in globals():
    SCENE_RANGE = None  # None 表示渲染所有 scenes


class ExplainerScene(Scene):
    """
    科普视频场景

    核心原则：
    1. 知识水平适配 - 严格遵守用户知识水平
    2. 幽默生动 - 用比喻、拟人、夸张
    3. 音画同步 - 画面等待音频，确保讲解和动画同步
    4. 高亮对应 - 配音提到什么，画面高亮什么
    5. 系列统一 - 固定开场结尾格式

    ManimCE 最佳实践：
    - 使用 .animate 进行变换动画
    - 使用 MathTex 渲染数学公式
    - 使用 rate_func 控制动画节奏
    - 使用 next_to, to_edge 等相对定位
    """

    # ========== 1. 配置参数 ==========
    # 画布配置 (横屏 1920x1080)
    config.pixel_width = 1920
    config.pixel_height = 1080
    config.frame_rate = 60

    # 颜色定义
    COLORS = {
        'background': '#1a1a2e',      # 深蓝背景
        'primary': '#4ecca3',          # 主色（青色）
        'secondary': '#e94560',        # 辅助色（红色）
        'highlight': '#ffc107',        # 高亮色（黄色/金色）
        'text': '#ffffff',             # 文字白色
        'text_secondary': '#aaaaaa',   # 次要文字
        'grid': '#2a2a4e',             # 网格线
        'axis': '#444466',             # 坐标轴
    }

    # ========== 1.1 布局约束（防止重叠）==========
    # 字幕位置：固定在下部，不与图形重叠
    SUBTITLE_Y = -3.5      # 字幕Y坐标
    FORMULA_Y = -4.5       # 公式Y坐标
    GRAPHIC_CENTER = (0, 0.5)  # 图形中心

    # 安全间距要求
    MIN_SPACING = 0.8      # 文字与图形最小间距

    # 字幕最大长度
    MAX_SUBTITLE_LENGTH = 20  # 每行最多20字

    # ========== 1.2 字幕渲染开关 ==========
    # False（默认）= 不在画面中渲染字幕，使用外部 SRT 文件在剪映处理
    # True = 在 Manim 画面中烧录字幕（旧工作流）
    # 推荐使用 False：SRT 文件由 scripts/generate_srt.py 自动生成
    RENDER_SUBTITLES = False

    # ========== 2. 系列信息 ==========
    SERIES_NAME = "3分钟数学科普"  # 系列名称（每个系列固定）
    HOST_NAME = "大魔王"            # 主持人名字（固定）
    EPISODE_TITLE = "勾股定理"     # 本期标题
    NEXT_EPISODE = "相似三角形"    # 下期预告（必须用户确认）

    # ========== 3. 幕信息数组（从分镜读取） ==========
    # 格式：(幕号，幕名，音频文件名，时长秒数)
    # 注意：
    # - 幕号 0 = 系列开场
    # - 幕号 98 = 本期总结
    # - 幕号 99 = 系列结尾+下期预告
    # - 时长从 audio/audio_info.json 读取
    # 从 audio_info.json 自动填充，无需手动填写
    SCENES = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.audio_dir = "audio"
        self.audio_info_file = os.path.join(self.audio_dir, "audio_info.json")
        # 若 SCENES 为空则从 audio_info.json 自动加载
        if not self.SCENES:
            self.SCENES = self._load_scenes_from_audio_info()
        else:
            self._fill_scene_durations()
        self._active_subtitles = []  # 跟踪当前显示的字幕
        self._active_formulas = []   # 跟踪当前显示的公式
        self._segment_scenes = globals().get('SCENE_RANGE', None)  # 分段渲染支持

    def _clear_all_text(self):
        """
        清除所有当前显示的文字（字幕和公式）- 在幕切换时调用

        ManimCE 最佳实践：
        - 使用 Play 同时播放多个淡出动画
        - 使用 rate_func=smooth 让退场更自然
        """
        if not self.RENDER_SUBTITLES:
            self._active_subtitles = []
            self._active_formulas = []
            return

        animations = []

        # 淡出所有字幕（使用 smooth 缓动函数）
        for subtitle in self._active_subtitles:
            if subtitle is not None:
                animations.append(FadeOut(subtitle, run_time=0.3, rate_func=smooth))
        self._active_subtitles = []

        # 淡出所有公式
        for formula in self._active_formulas:
            if formula is not None:
                animations.append(FadeOut(formula, run_time=0.3, rate_func=smooth))
        self._active_formulas = []

        # 播放退场动画（同时执行）
        if animations:
            self.play(*animations)

    # ========== 4. 音频管理 ==========
    def _parse_audio_filename(self, filename):
        """
        从音频文件名解析幕号和幕名。
        格式：audio_{三位幕号}_{幕名}.wav → (int(幕号), 幕名)
        """
        import re
        m = re.match(r'audio_(\d+)_(.+)\.wav', filename)
        if m:
            return int(m.group(1)), m.group(2)
        return None, None

    def _load_scenes_from_audio_info(self):
        """
        从 audio_info.json 自动生成 SCENES 列表。
        格式：[(幕号, 幕名, 音频文件名, 时长), ...]
        """
        if not os.path.exists(self.audio_info_file):
            print(f"Warning: {self.audio_info_file} 不存在，SCENES 为空")
            return []
        try:
            with open(self.audio_info_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            scenes = []
            for item in data.get('files', []):
                filename = item.get('filename', '')
                duration = item.get('duration')
                scene_num, name = self._parse_audio_filename(filename)
                if scene_num is not None:
                    scenes.append((scene_num, name, filename, duration))
            scenes.sort(key=lambda x: x[0])
            return scenes
        except Exception as e:
            print(f"Warning: 自动加载 SCENES 失败: {e}")
            return []

    def _fill_scene_durations(self):
        """当 SCENES 已手动定义时，补全缺失的时长（从 audio_info.json 读取）"""
        if not os.path.exists(self.audio_info_file):
            return
        try:
            with open(self.audio_info_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            duration_map = {
                item['filename']: item.get('duration')
                for item in data.get('files', [])
                if 'filename' in item
            }
            self.SCENES = [
                (sn, name, audio_file, duration_map.get(audio_file, dur))
                for sn, name, audio_file, dur in self.SCENES
            ]
        except Exception as e:
            print(f"Warning: 补全时长失败: {e}")

    def add_scene_audio(self, scene_num):
        """
        添加指定幕的音频 - 强制要求！

        ⚠️ 警告：禁止注释 self.add_sound()，否则视频将没有声音！
        如果遇到渲染问题，应该检查音频文件是否存在，而不是注释音频。

        使用：在每幕开始时调用 self.add_scene_audio(幕号)
        """
        for sn, name, audio_file, duration in self.SCENES:
            if sn == scene_num:
                audio_path = os.path.join(self.audio_dir, audio_file)
                if os.path.exists(audio_path):
                    self.add_sound(audio_path)  # ✅ 必须启用，禁止注释！
                    return duration
                else:
                    raise RuntimeError(f"❌ 音频文件不存在: {audio_path} - 必须先生成音频才能渲染视频！")
        return 0

    # ========== 5. 几何计算（必须实现） ==========
    def calculate_geometry(self):
        """
        计算所有几何元素的位置和属性

        坐标系说明（重要）：
        - Manim 使用 3D 坐标系，但本脚手架只使用 2D
        - 所有点的格式：(x, y, 0) - 使用 Manim 的 3D 坐标
        - 建议将几何图形放在 (-5, 5) x (-4, 4) 区域内

        ManimCE 最佳实践：
        - 使用 ORIGIN, UP, DOWN, LEFT, RIGHT 等方向常量
        - 使用 shift() 进行相对移动
        - 使用 next_to() 进行相对定位

        返回：dict 包含所有几何对象的数据
        """
        geometry = {
            'points': {},      # {'A': ORIGIN, 'B': RIGHT * 2, ...}
            'lines': {},       # {'AB': Line(A, B), ...}
            'circles': {},     # {'circle1': {'center': ORIGIN, 'radius': 1}, ...}
            'arcs': {},        # 圆弧定义
            'polygons': {},    # 多边形
        }

        # TODO: 【必须实现】根据科普内容计算所有点的坐标
        # 示例：使用 ManimCE 方向常量
        # points['A'] = ORIGIN
        # points['B'] = ORIGIN + RIGHT * 2
        # points['C'] = ORIGIN + UP * 2
        return geometry

    # ========== 6. 几何验证（必须实现）==========
    def assert_geometry(self, geometry):
        """
        验证几何计算的正确性（最小验证原则）

        验证内容：
        1. 几何关系是否正确（如勾股定理 a² + b² = c²）
        2. 精度问题：使用相对误差比较
        3. 画布范围检查：确保图形在可视区域内
        4. 布局检查：确保文字标注不会与图形重叠
        5. 几何标记检查：直角标记、角度标注位置正确
        """
        def approx_equal(a, b, epsilon=1e-4):
            return abs(a - b) < epsilon

        # TODO: 【必须实现】验证几何计算的正确性

        # 画布范围检查
        def check_canvas_bounds(geometry):
            all_points = list(geometry['points'].values())
            for circle in geometry['circles'].values():
                cx, cy = circle['center']
                r = circle['radius']
                all_points.extend([(cx+r, cy), (cx-r, cy), (cx, cy+r), (cx, cy-r)])

            if not all_points:
                return True

            xs = [p[0] for p in all_points]
            ys = [p[1] for p in all_points]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)

            CANVAS_MIN_X, CANVAS_MAX_X = -6, 6
            CANVAS_MIN_Y, CANVAS_MAX_Y = -5, 5
            MARGIN = 0.5

            assert min_x >= CANVAS_MIN_X + MARGIN, f"图形超出左边界：{min_x}"
            assert max_x <= CANVAS_MAX_X - MARGIN, f"图形超出右边界：{max_x}"
            assert min_y >= CANVAS_MIN_Y + MARGIN, f"图形超出下边界：{min_y}"
            assert max_y <= CANVAS_MAX_Y - MARGIN, f"图形超出上边界：{max_y}"

            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
            assert abs(center_x) < 1.5, f"图形中心偏离 x 轴：{center_x}"
            assert abs(center_y) < 1.0, f"图形中心偏离 y 轴：{center_y}"
            return True

        # 布局检查：文字标注不重叠
        def check_label_spacing(geometry):
            """检查文字标注与图形的最小间距"""
            points = geometry.get('points', {})
            labels = geometry.get('labels', {})

            for label_name, label_pos in labels.items():
                min_dist = float('inf')
                for point_name, point_pos in points.items():
                    dist = ((label_pos[0] - point_pos[0])**2 +
                           (label_pos[1] - point_pos[1])**2)**0.5
                    min_dist = min(min_dist, dist)

                if min_dist < 0.3:
                    print(f"Warning: 标签 '{label_name}' 与点重叠，距离={min_dist:.2f}")

            return True

        # 几何标记检查：直角标记位置
        def check_right_angle_marks(geometry):
            """
            验证直角标记位置正确

            直角标记应该：
            1. 位于直角顶点处
            2. 大小合适（不遮挡图形）
            3. 方向正确（在直角内部或外部）
            """
            right_angles = geometry.get('right_angles', [])
            points = geometry.get('points', {})

            for ra in right_angles:
                vertex = ra.get('vertex')  # 顶点名称
                size = ra.get('size', 0.3)  # 标记大小
                position = ra.get('position', 'inside')  # 'inside' 或 'outside'

                if vertex and vertex in points:
                    vx, vy = points[vertex]
                    # 验证标记大小合适
                    assert 0.1 <= size <= 0.5, f"直角标记 '{vertex}' 大小不合适：{size}，建议 0.1-0.5"

                    # TODO: 可以添加更多验证，如检查标记是否在画布内

            return True

        # 边长标注位置检查
        def check_edge_label_positions(geometry):
            """
            验证边长标注位置正确

            边长标注应该：
            1. 位于边的中点附近
            2. 在图形外侧（不与图形重叠）
            3. 与边平行或垂直
            """
            edge_labels = geometry.get('edge_labels', [])
            points = geometry.get('points', {})
            lines = geometry.get('lines', {})

            for el in edge_labels:
                edge = el.get('edge')  # 边名称，如 'AB'
                label_pos = el.get('position')  # 标注位置

                if edge and edge in lines and label_pos:
                    line = lines[edge]
                    start = line['start']
                    end = line['end']

                    # 计算边中点
                    mid_x = (start[0] + end[0]) / 2
                    mid_y = (start[1] + end[1]) / 2

                    # 验证标注位置在中点附近
                    dist_to_mid = ((label_pos[0] - mid_x)**2 + (label_pos[1] - mid_y)**2)**0.5
                    assert dist_to_mid <= 1.0, f"边 '{edge}' 标注距离中点太远：{dist_to_mid:.2f}"

            return True

        check_canvas_bounds(geometry)
        check_label_spacing(geometry)
        check_right_angle_marks(geometry)
        check_edge_label_positions(geometry)
        print("Geometry validation passed!")

    # ========== 7. 图形元素定义 ==========
    def define_elements(self, geometry):
        """
        定义 Manim 图形对象（但不创建动画）

        ManimCE 最佳实践：
        - 使用 Circle(), Square(), Triangle() 等内置形状
        - 使用 VGroup() 组合多个对象
        - 使用 set_stroke(), set_fill() 设置样式
        - 使用 add() 将子对象添加到组

        返回：dict 包含所有 Manim Mobject
        """
        elements = {
            'points': {},      # {'A': Dot(point_A), ...}
            'lines': {},       # {'AB': Line(A, B), ...}
            'circles': {},     # {'circle1': Circle(radius=r), ...}
            'labels': {},      # {'label_A': Text("A"), ...}
            'groups': {},      # {'triangle': VGroup(A, B, C), ...}
        }

        # 辅助函数：2D 坐标转 3D（Manim 需要）
        def to_3d(p):
            return (p[0], p[1], 0.0)

        # TODO: 根据分镜需求定义图形元素
        # 示例：
        # from manim import Dot, Line, Circle, VGroup, Text
        # elements['points']['A'] = Dot(geometry['points']['A'], color=self.COLORS['primary'])
        # elements['lines']['AB'] = Line(A, B, color=self.COLORS['text'])
        # elements['circles']['circle1'] = Circle(center=center, radius=r, color=self.COLORS['highlight'])
        # elements['groups']['triangle'] = VGroup(A, B, C, line_AB, line_BC, line_CA)
        return elements

    # ========== 8. 系列开场（固定格式） ==========
    def play_intro(self, audio_file, duration):
        """
        播放系列开场（统一格式）

        画面：系列Logo动画 + 标题
        读白：欢迎词 + 本期主题
        """
        # 1. 添加音频
        self.add_scene_audio(0)

        # 2. 显示系列名称
        series_title = Text(
            self.SERIES_NAME,
            font_size=48,
            color=self.COLORS['primary']
        )
        series_title.to_edge(UP, buff=1.0)

        # 3. 显示本期标题
        episode_title = Text(
            f"第{self._get_episode_number()}期：{self.EPISODE_TITLE}",
            font_size=36,
            color=self.COLORS['text']
        )
        episode_title.next_to(series_title, DOWN, buff=0.5)

        # 4. 动画
        self.play(
            FadeIn(series_title, run_time=0.5),
            FadeIn(episode_title, run_time=0.5),
            run_time=1.0
        )
        self.wait(duration - 1.5)
        self.play(
            FadeOut(series_title, run_time=0.5),
            FadeOut(episode_title, run_time=0.5),
        )

    def _get_episode_number(self):
        """获取本期编号（可以从文件名解析或硬编码）"""
        # TODO: 实现或硬编码
        return 1

    # ========== 9. 系列结尾（固定格式） ==========
    def play_outro(self, audio_file, duration):
        """
        播放系列结尾（统一格式）

        画面：核心结论 + 下期预告 + Logo
        """
        # 1. 添加音频（分两段：总结 + 下期预告）
        # 这里简单处理，实际可以分幕

        # 2. 显示核心结论
        conclusion = Text(
            self._get_conclusion_text(),
            font_size=36,
            color=self.COLORS['highlight']
        )
        conclusion.center()

        # 3. 显示下期预告
        next_episode = Text(
            f"下期预告：{self.NEXT_EPISODE}",
            font_size=28,
            color=self.COLORS['text_secondary']
        )
        next_episode.next_to(conclusion, DOWN, buff=1.0)

        # 4. 动画
        self.play(FadeIn(conclusion, run_time=0.5))
        self.wait(2.0)
        self.play(FadeIn(next_episode, run_time=0.5))
        self.wait(2.0)
        self.play(
            FadeOut(conclusion, run_time=0.5),
            FadeOut(next_episode, run_time=0.5),
        )

    def _get_conclusion_text(self):
        """获取本期核心结论"""
        # TODO: 实现或硬编码
        return "直角边平方和等于斜边平方"

    # ========== 10. 字幕工具（增强退场管理）==========
    def create_subtitle(self, text, position=None, auto_clear=True):
        """
        创建字幕对象（自动退场管理，防止重叠）

        注意：当 RENDER_SUBTITLES = False 时返回 None。
        建议使用 show_subtitle_with_audio() 或 show_subtitle_timed() 替代直接调用本方法。

        布局约束：
        - 字幕固定在 SUBTITLE_Y 位置，避免与图形重叠
        - 文字长度限制在 MAX_SUBTITLE_LENGTH 以内
        - 可选自动清除之前的字幕

        参数：
            text: 字幕文本
            position: 字幕位置（默认 SUBTITLE_Y）
            auto_clear: 是否自动清除之前的字幕（默认 True）
        """
        if not self.RENDER_SUBTITLES:
            return None

        # 可选：清除之前的字幕和公式
        if auto_clear:
            self._clear_all_text()

        # 使用默认位置
        if position is None:
            position = DOWN * abs(self.SUBTITLE_Y)

        # 检查字幕长度
        if len(text) > self.MAX_SUBTITLE_LENGTH:
            print(f"Warning: 字幕过长 ({len(text)} > {self.MAX_SUBTITLE_LENGTH}): {text[:20]}...")

        # 创建字幕文本，添加描边提高可读性
        subtitle = Text(text, font_size=36, color=self.COLORS['text'])
        subtitle.to_edge(position, buff=0.5)
        subtitle.set_stroke(BLACK, width=2, opacity=0.5)  # 添加黑色描边

        # 跟踪当前字幕
        self._active_subtitles.append(subtitle)

        return subtitle

    def create_formula(self, text, position=None, use_latex=True, auto_clear=True):
        """
        创建公式/算式对象（自动退场管理，防止重叠）

        布局约束：
        - 公式固定在 FORMULA_Y 位置，与字幕分离
        - 可选自动清除之前的公式

        参数：
            text: 公式文本（LaTeX格式或纯文本）
            position: 位置（默认 FORMULA_Y）
            use_latex: 是否使用 LaTeX 渲染（默认 True，需要安装 LaTeX）
            auto_clear: 是否自动清除之前的公式（默认 True，保留字幕）
        """
        # 可选：只清除之前的公式，保留字幕
        if auto_clear:
            for formula in self._active_formulas:
                if formula is not None:
                    self.play(FadeOut(formula, run_time=0.3))
            self._active_formulas = []

        if position is None:
            position = DOWN * abs(self.FORMULA_Y)

        if use_latex:
            # 使用 LaTeX 渲染（推荐，需要安装 LaTeX）
            formula = MathTex(text, font_size=32, color=self.COLORS['highlight'])
        else:
            # 降级方案：纯文本（当 LaTeX 无法安装时使用）
            formula = Text(text, font_size=32, color=self.COLORS['highlight'])

        formula.to_edge(position)

        # 跟踪当前公式
        self._active_formulas.append(formula)

        return formula

    def create_formula_latex(self, latex_text, position=None, auto_clear=True):
        """
        使用 LaTeX 创建数学公式（默认推荐，带退场管理）

        示例：
            self.create_formula_latex(r"a^2 + b^2 = c^2")
            self.create_formula_latex(r"\sum_{i=1}^{n} x_i = \frac{1}{n}\sum_{i=1}^{n} x_i")
        """
        return self.create_formula(latex_text, position, use_latex=True, auto_clear=auto_clear)

    def fade_in(self, mobject, run_time=0.5):
        """辅助方法：淡入动画"""
        return FadeIn(mobject, run_time=run_time)

    def fade_out(self, mobject, run_time=0.5):
        """辅助方法：淡出动画"""
        return FadeOut(mobject, run_time=run_time)

    def show_subtitle_timed(self, text, duration, position=DOWN * 3.5, fade_in_time=0.5, fade_out_time=0.5, auto_clear=True):
        """
        显示字幕并在指定时间后自动退场（防止重叠）

        当 RENDER_SUBTITLES = False 时，仅等待 duration 秒后返回 None。

        参数：
            text: 字幕文本
            duration: 显示总时长（秒），包含淡入淡出时间
            position: 字幕位置
            fade_in_time: 淡入时间
            fade_out_time: 淡出时间
            auto_clear: 是否自动清除之前的字幕（默认 True）
        """
        if not self.RENDER_SUBTITLES:
            self.wait(duration)
            return None

        # 验证时长，防止负数等待
        min_duration = fade_in_time + fade_out_time
        if duration < min_duration:
            print(f"Warning: duration {duration:.1f}s too short, using {min_duration}s")
            duration = min_duration

        subtitle = self.create_subtitle(text, position, auto_clear=auto_clear)
        self.play(self.fade_in(subtitle), run_time=fade_in_time)
        self.wait(max(0, duration - fade_in_time - fade_out_time))
        self.play(self.fade_out(subtitle), run_time=fade_out_time)
        # 从跟踪列表中移除
        if subtitle in self._active_subtitles:
            self._active_subtitles.remove(subtitle)
        return subtitle

    def show_subtitle_with_audio(self, text, audio_duration, position=DOWN * 3.5, auto_clear=True):
        """
        显示字幕并持续到音频结束（防止重叠）

        当 RENDER_SUBTITLES = False 时，仅等待 audio_duration 秒后返回 None。

        参数：
            text: 字幕文本
            audio_duration: 音频时长（秒）
            position: 字幕位置
            auto_clear: 是否自动清除之前的字幕（默认 True）
        """
        if not self.RENDER_SUBTITLES:
            self.wait(audio_duration)
            return None

        subtitle = self.create_subtitle(text, position, auto_clear=auto_clear)
        self.play(self.fade_in(subtitle), run_time=0.5)
        self.wait(audio_duration - 1.0)
        self.play(self.fade_out(subtitle), run_time=0.5)
        # 从跟踪列表中移除
        if subtitle in self._active_subtitles:
            self._active_subtitles.remove(subtitle)
        return subtitle

    # ========== 11. 高亮工具 ==========
    def highlight_element(self, element, color=None, scale=1.3, duration=0.8):
        """高亮指定元素"""
        color = color or self.COLORS['highlight']
        original_color = element.get_color()

        self.play(
            element.animate.scale(scale).set_color(color),
            run_time=0.4
        )
        self.wait(duration - 0.4)
        self.play(
            element.animate.scale(1/scale).set_color(original_color),
            run_time=0.4
        )

    # ========== 12. 主流程 ==========
    def add_watermark(self):
        """
        添加"АI生成"水印

        位置：右下角（不起眼的位置）
        样式：半透明浅灰色，小字号
        """
        watermark = Text(
            "AI生成",
            font_size=20,
            color="#888888"
        )
        # 放在右下角，留一些边距
        watermark.to_edge(DOWN + RIGHT, buff=0.3)
        watermark.set_opacity(0.5)  # 半透明，不影响主内容
        self.add(watermark)  # 直接添加，不动画，持续显示

    def construct(self):
        """主构造流程"""
        # 设置背景
        self.camera.background_color = self.COLORS['background']

        # 添加水印（全局显示，持续整个视频）
        self.add_watermark()

        # 计算和验证几何
        geometry = self.calculate_geometry()
        self.assert_geometry(geometry)

        # 定义元素
        elements = self.define_elements(geometry)

        # 确定要渲染的 scenes（分段渲染支持）
        scenes_to_render = self._segment_scenes if self._segment_scenes else [s[0] for s in self.SCENES]

        # 按场景执行
        for scene_num, scene_name, audio_file, duration in self.SCENES:
            # 跳过不在当前段的 scenes
            if scene_num not in scenes_to_render:
                continue

            # 每幕开始时清除之前的字幕（防止重叠）
            self._clear_all_text()

            if scene_num == 0:
                # 系列开场
                self.play_intro(audio_file, duration)
            elif scene_num >= 98:
                # 系列结尾
                self.play_outro(audio_file, duration)
            else:
                # 正式内容
                method_name = f"play_scene_{scene_num}"
                if hasattr(self, method_name):
                    getattr(self, method_name)(elements, geometry)
                else:
                    print(f"Warning: play_scene_{scene_num} not implemented")

            # 每幕结束时清除所有文字（确保不残留到下一幕）
            self._clear_all_text()

        # 最后再次清除所有文字
        self._clear_all_text()

        # 拷贝视频到根目录
        self.copy_video_to_root()

    def copy_video_to_root(self):
        """渲染完成后拷贝视频到项目根目录"""
        import shutil
        from pathlib import Path

        scene_name = self.__class__.__name__
        possible_paths = [
            Path(f"media/videos/script/1920p60/{scene_name}.mp4"),
            Path(f"media/videos/script/1080p60/{scene_name}.mp4"),
            Path(f"media/videos/script/720p30/{scene_name}.mp4"),
        ]

        video_src = None
        for path in possible_paths:
            if path.exists():
                video_src = path
                break

        if video_src:
            video_dst = Path(f"科普视频_{self.EPISODE_TITLE}.mp4")
            try:
                shutil.copy2(video_src, video_dst)
                print(f"\n✓ 视频已拷贝到：{video_dst.absolute()}")
            except Exception as e:
                print(f"\n⚠️ 视频拷贝失败：{e}")
        else:
            print(f"\n⚠️ 未找到视频文件")


# ========== 使用说明 ==========
"""
关键提醒：
1. 所有几何计算必须在 calculate_geometry() 中完成
2. assert_geometry() 必须检查画布范围
3. 每幕动画时长必须 >= 音频时长
4. 配音提到什么，画面就高亮什么
5. 使用 create_subtitle() 创建字幕，不要用 Subtitle 类
6. 如果渲染卡住，禁用 add_scene_audio 中的 self.add_sound()
7. 所有点坐标使用 2D (x, y)，define_elements 中用 to_3d() 转换
8. 字幕退场：使用 show_subtitle_timed() 或 show_subtitle_with_audio()
9. 系列开场固定格式：play_intro() - 0号幕，必须说"我是老朋友大魔王"
10. 系列结尾固定格式：play_outro() - 98/99号幕，下期预告必须用户确认

LaTeX 公式（默认使用）：
11. 使用 create_formula_latex() 渲染数学公式（需要安装 LaTeX）
12. LaTeX 安装：macOS: brew install --cask mactex-no-gui
13. LaTeX 安装：Ubuntu: sudo apt install texlive texlive-fonts-extra
14. 示例：self.create_formula_latex(r"a^2 + b^2 = c^2")

分段渲染（可选）：
15. 分段流水线会自动设置 SCENE_RANGE = [0, 1, 2] 等
16. 脚本只渲染 SCENE_RANGE 中指定的 scenes
17. 用于将长视频拆分为小段生成和确认
18. 不分段时 SCENE_RANGE = None，渲染所有 scenes

布局约束（避免重叠）：
15. 使用 SUBTITLE_Y 和 FORMULA_Y 固定字幕/公式位置
16. 边长标注放在图形外侧，与图形保持 MIN_SPACING 间距
17. 算式/公式使用 create_formula_latex()，不与字幕重叠
18. 提到生活例子时，必须画出示意图

内容深度（初中水平）：
19. 跳过基础计算展示（如 3²=9），直接给出结果
20. 重点在概念理解和证明过程
21. 证明动画必须分步骤，每步对应图形变化

角色与下期预告：
22. 主持人固定为"大魔王"，开场必须说"我是你们的老朋友大魔王"
23. 下期预告必须用户确认，在生成第6幕前询问"下期您想听什么？"
"""
