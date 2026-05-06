"""
Character Narration Template
卡通小助手角色内心独白系统

角色：小数点 (Dotty)
- 性格：好奇、活泼、爱提问
- 声音：童声/轻快
- 作用：通过内心独白增加趣味性，帮助观众理解难点

功能：
- 角色定义和视觉表现
- 独白音频生成配置
- 时间轴同步
- 画面配合建议
"""

from manim import *
from dataclasses import dataclass
from typing import List, Optional, Dict
import json


@dataclass
class NarrationEntry:
    """独白条目"""
    timestamp: float          # 时间点（秒）
    text: str                 # 独白内容
    emotion: str              # 情绪：curious, excited, confused, happy, surprised
    action: str               # 画面动作描述
    duration: float = 2.0     # 持续时长


@dataclass
class CharacterProfile:
    """角色档案"""
    name: str = "小数点"
    nickname: str = "Dotty"
    age: str = "8岁"
    personality: List[str] = None
    voice_type: str = "童声/轻快"
    catchphrase: str = "哇！原来是这样！"

    def __post_init__(self):
        if self.personality is None:
            self.personality = ["好奇", "活泼", "爱提问", "容易兴奋"]


class CharacterNarration:
    """
    角色内心独白管理器

    使用方式：
    1. 创建角色实例
    2. 添加独白条目
    3. 生成配置文件
    4. 在Manim场景中使用
    """

    # 情绪对应的表情符号
    EMOTION_ICONS = {
        'curious': '🤔',
        'excited': '😃',
        'confused': '😵',
        'happy': '😊',
        'surprised': '😲',
        'thinking': '🧐',
        'amazed': '🤩',
    }

    # 情绪对应的TTS声音参数
    EMOTION_VOICE_PARAMS = {
        'curious': {'rate': '+0%', 'pitch': '+10%', 'volume': '100%'},
        'excited': {'rate': '+10%', 'pitch': '+20%', 'volume': '110%'},
        'confused': {'rate': '-5%', 'pitch': '-5%', 'volume': '90%'},
        'happy': {'rate': '+5%', 'pitch': '+15%', 'volume': '105%'},
        'surprised': {'rate': '+15%', 'pitch': '+25%', 'volume': '115%'},
        'thinking': {'rate': '-10%', 'pitch': '0%', 'volume': '95%'},
        'amazed': {'rate': '+20%', 'pitch': '+30%', 'volume': '120%'},
    }

    def __init__(self, profile: Optional[CharacterProfile] = None):
        self.profile = profile or CharacterProfile()
        self.narrations: List[NarrationEntry] = []

    def add_narration(self, timestamp: float, text: str, emotion: str = "curious",
                     action: str = "", duration: float = 2.0):
        """添加独白条目"""
        entry = NarrationEntry(
            timestamp=timestamp,
            text=text,
            emotion=emotion,
            action=action,
            duration=duration
        )
        self.narrations.append(entry)
        return self

    def add_curiosity(self, timestamp: float, question: str, action: str = "歪头思考"):
        """添加好奇型独白"""
        return self.add_narration(
            timestamp=timestamp,
            text=question,
            emotion="curious",
            action=action,
            duration=2.5
        )

    def add_excitement(self, timestamp: float, exclamation: str, action: str = "跳起来"):
        """添加兴奋型独白"""
        return self.add_narration(
            timestamp=timestamp,
            text=exclamation,
            emotion="excited",
            action=action,
            duration=2.0
        )

    def add_realization(self, timestamp: float, insight: str, action: str = "眼睛发光"):
        """添加顿悟型独白"""
        return self.add_narration(
            timestamp=timestamp,
            text=insight,
            emotion="amazed",
            action=action,
            duration=3.0
        )

    def generate_script(self) -> str:
        """生成独白脚本（Markdown格式）"""
        lines = [
            f"# 角色内心独白脚本",
            f"",
            f"## 角色信息",
            f"- **名字**: {self.profile.name} ({self.profile.nickname})",
            f"- **年龄**: {self.profile.age}",
            f"- **性格**: {', '.join(self.profile.personality)}",
            f"- **声音类型**: {self.profile.voice_type}",
            f"- **口头禅**: {self.profile.catchphrase}",
            f"",
            f"## 独白内容",
            f"",
        ]

        for entry in sorted(self.narrations, key=lambda x: x.timestamp):
            icon = self.EMOTION_ICONS.get(entry.emotion, '💬')
            lines.extend([
                f"### {icon} 时间点: {entry.timestamp:.1f}s",
                f"**独白**: \"{entry.text}\"",
                f"**情绪**: {entry.emotion}",
                f"**画面配合**: {entry.action}",
                f"**持续时长**: {entry.duration:.1f}s",
                f"",
            ])

        return "\n".join(lines)

    def generate_tts_config(self) -> List[Dict]:
        """生成TTS配置（用于generate_tts.py）"""
        config = []

        for i, entry in enumerate(sorted(self.narrations, key=lambda x: x.timestamp)):
            voice_params = self.EMOTION_VOICE_PARAMS.get(entry.emotion, {})

            config.append({
                'scene': f'narration_{i:03d}',
                'text': entry.text,
                'voice': 'xiaoxiao',  # 童声
                'rate': voice_params.get('rate', '+0%'),
                'pitch': voice_params.get('pitch', '+0%'),
                'volume': voice_params.get('volume', '100%'),
                'emotion': entry.emotion,
                'timestamp': entry.timestamp,
            })

        return config

    def save(self, output_path: str):
        """保存独白配置到文件"""
        data = {
            'profile': {
                'name': self.profile.name,
                'nickname': self.profile.nickname,
                'age': self.profile.age,
                'personality': self.profile.personality,
                'voice_type': self.profile.voice_type,
                'catchphrase': self.profile.catchphrase,
            },
            'narrations': [
                {
                    'timestamp': n.timestamp,
                    'text': n.text,
                    'emotion': n.emotion,
                    'action': n.action,
                    'duration': n.duration,
                }
                for n in self.narrations
            ]
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, input_path: str) -> 'CharacterNarration':
        """从文件加载独白配置"""
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        profile = CharacterProfile(**data['profile'])
        narration = cls(profile)

        for n in data['narrations']:
            narration.add_narration(
                timestamp=n['timestamp'],
                text=n['text'],
                emotion=n['emotion'],
                action=n['action'],
                duration=n['duration']
            )

        return narration


class DottyCharacter(Scene):
    """
    小数点 (Dotty) 角色视觉表现

    使用VMobject绘制简单的卡通角色
    """

    COLORS = {
        'body': '#4ecca3',
        'face': '#ffffff',
        'eye': '#1a1a2e',
        'cheek': '#ffb6c1',
        'mouth': '#e94560',
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.character_group = None

    def create_character(self, scale=1.0):
        """创建角色图形"""
        group = VGroup()

        # 身体（圆形）
        body = Circle(radius=0.8, color=self.COLORS['body'], fill_opacity=1)
        body.set_fill(self.COLORS['body'])
        group.add(body)

        # 脸部（白色圆形）
        face = Circle(radius=0.6, color=self.COLORS['face'], fill_opacity=1)
        face.set_fill(self.COLORS['face'])
        face.shift(UP * 0.1)
        group.add(face)

        # 左眼
        left_eye = Circle(radius=0.08, color=self.COLORS['eye'], fill_opacity=1)
        left_eye.set_fill(self.COLORS['eye'])
        left_eye.move_to(face.get_center() + LEFT * 0.2 + UP * 0.1)
        group.add(left_eye)

        # 右眼
        right_eye = Circle(radius=0.08, color=self.COLORS['eye'], fill_opacity=1)
        right_eye.set_fill(self.COLORS['eye'])
        right_eye.move_to(face.get_center() + RIGHT * 0.2 + UP * 0.1)
        group.add(right_eye)

        # 腮红
        left_cheek = Circle(radius=0.06, color=self.COLORS['cheek'], fill_opacity=0.6)
        left_cheek.set_fill(self.COLORS['cheek'])
        left_cheek.move_to(face.get_center() + LEFT * 0.25 + DOWN * 0.15)
        group.add(left_cheek)

        right_cheek = Circle(radius=0.06, color=self.COLORS['cheek'], fill_opacity=0.6)
        right_cheek.set_fill(self.COLORS['cheek'])
        right_cheek.move_to(face.get_center() + RIGHT * 0.25 + DOWN * 0.15)
        group.add(right_cheek)

        # 嘴巴（根据情绪变化）
        mouth = Arc(radius=0.15, angle=PI, color=self.COLORS['mouth'])
        mouth.move_to(face.get_center() + DOWN * 0.2)
        group.add(mouth)

        # 缩放
        group.scale(scale)

        self.character_group = group
        return group

    def animate_emotion(self, emotion: str, duration: float = 1.0):
        """根据情绪播放动画"""
        if self.character_group is None:
            return

        animations = []

        if emotion == 'curious':
            # 好奇：歪头
            animations.append(
                self.character_group.animate.rotate(15 * DEGREES).scale(1.05)
            )
        elif emotion == 'excited':
            # 兴奋：跳动
            animations.append(
                self.character_group.animate.shift(UP * 0.3).scale(1.1)
            )
        elif emotion == 'surprised':
            # 惊讶：睁大眼睛
            animations.append(
                self.character_group.animate.scale(1.2)
            )
        elif emotion == 'happy':
            # 开心：摇摆
            animations.append(
                self.character_group.animate.rotate(-10 * DEGREES)
            )
        elif emotion == 'amazed':
            # 惊叹：发光效果
            animations.append(
                self.character_group.animate.scale(1.15).set_color(YELLOW)
            )

        if animations:
            self.play(*animations, run_time=duration * 0.5)
            self.play(
                self.character_group.animate.restore(),
                run_time=duration * 0.5
            )

    def show_thought_bubble(self, text: str, duration: float = 2.0):
        """显示思考气泡"""
        if self.character_group is None:
            return

        # 气泡
        bubble = Ellipse(width=3, height=1.5, color=WHITE, fill_opacity=0.9)
        bubble.set_fill(WHITE)
        bubble.next_to(self.character_group, UP + RIGHT, buff=0.5)

        # 文字
        text_obj = Text(text, font_size=24, color=BLACK)
        text_obj.move_to(bubble.get_center())

        # 连接线
        connector = Line(
            self.character_group.get_top(),
            bubble.get_bottom(),
            color=WHITE
        )

        thought_group = VGroup(bubble, text_obj, connector)

        self.play(FadeIn(thought_group), run_time=0.5)
        self.wait(duration - 1)
        self.play(FadeOut(thought_group), run_time=0.5)


# ========== 预设独白场景 ==========

class NarrationScenarios:
    """预设独白场景模板"""

    @staticmethod
    def pythagorean_theorem() -> CharacterNarration:
        """勾股定理主题的预设独白"""
        narration = CharacterNarration()

        narration.add_curiosity(
            timestamp=15.0,
            question="咦？直角三角形的两条边相乘，和斜边有什么关系呢？",
            action="歪头思考，手指点下巴"
        )

        narration.add_realization(
            timestamp=45.0,
            insight="哇！原来是这样！a² + b² = c²，太神奇了！",
            action="跳起来，眼睛发光"
        )

        narration.add_excitement(
            timestamp=60.0,
            exclamation="这个定理可以用来测量金字塔的高度呢！",
            action="挥舞手臂，指向金字塔图形"
        )

        return narration

    @staticmethod
    def geometry_basics() -> CharacterNarration:
        """几何基础主题的预设独白"""
        narration = CharacterNarration()

        narration.add_curiosity(
            timestamp=10.0,
            question="为什么三角形是最稳定的形状呢？",
            action="托腮思考"
        )

        narration.add_excitement(
            timestamp=30.0,
            exclamation="因为三角形有三个角，不会变形！",
            action="拍手跳起"
        )

        return narration
