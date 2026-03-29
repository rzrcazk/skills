#!/usr/bin/env python3
"""
Explainer Config - 统一配置模块

所有魔法数字和常量集中在此处管理。
各脚本通过 `from config import CONFIG` 引用配置。

环境变量覆盖：
    EXPLAINER_SEGMENT_DURATION=30 python segment_generator.py ...
"""

import os
from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class SegmentConfig:
    """分段相关配置"""
    default_duration: int = int(os.getenv("EXPLAINER_SEGMENT_DURATION", "20"))
    max_retries: int = int(os.getenv("EXPLAINER_MAX_RETRIES", "3"))
    retry_delay: float = float(os.getenv("EXPLAINER_RETRY_DELAY", "2.0"))


@dataclass(frozen=True)
class RenderConfig:
    """渲染相关配置"""
    default_quality: str = os.getenv("EXPLAINER_RENDER_QUALITY", "1080p60")
    short_video_threshold: float = float(os.getenv("EXPLAINER_SHORT_THRESHOLD", "60.0"))
    medium_video_threshold: float = float(os.getenv("EXPLAINER_MEDIUM_THRESHOLD", "180.0"))
    max_scenes_for_standard: int = int(os.getenv("EXPLAINER_MAX_SCENES_STANDARD", "5"))

    @property
    def quality_map(self) -> Dict[str, str]:
        return {
            'l': '480p15', 'low': '480p15',
            'm': '720p30', 'medium': '720p30',
            'h': '1080p60', 'high': '1080p60',
            'k': '2160p60', '4k': '2160p60',
        }


@dataclass(frozen=True)
class TTSConfig:
    """TTS 相关配置"""
    default_voice: str = os.getenv("EXPLAINER_TTS_VOICE", "xiaoxiao")
    max_concurrent: int = int(os.getenv("EXPLAINER_TTS_CONCURRENT", "5"))

    @property
    def voice_map(self) -> Dict[str, str]:
        return {
            'xiaoxiao': 'zh-CN-XiaoxiaoNeural',
            'xiaoyi': 'zh-CN-XiaoyiNeural',
            'yunyang': 'zh-CN-YunyangNeural',
            'yunjian': 'zh-CN-YunjianNeural',
            'xiaoxiao-dialect': 'zh-CN-XiaoxiaoNeural',
            'xiaoxiao-multilingual': 'zh-CN-XiaoxiaoMultilingualNeural',
        }


@dataclass(frozen=True)
class ConcurrencyConfig:
    """并发相关配置"""
    max_scene_workers: int = int(os.getenv("EXPLAINER_MAX_SCENE_WORKERS", "5"))
    scene_timeout: int = int(os.getenv("EXPLAINER_SCENE_TIMEOUT", "600"))


@dataclass(frozen=True)
class StateConfig:
    """状态文件名配置"""
    production_state_file: str = "production_state.json"
    workflow_state_file: str = "workflow_state.json"
    segment_pipeline_file: str = "segment_pipeline.json"


@dataclass(frozen=True)
class AudioConfig:
    """音频相关配置"""
    min_duration: float = 1.0


@dataclass(frozen=True)
class ExplainerConfig:
    """顶层配置聚合"""
    segment: SegmentConfig = field(default_factory=SegmentConfig)
    render: RenderConfig = field(default_factory=RenderConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    state: StateConfig = field(default_factory=StateConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)


# 全局单例
CONFIG = ExplainerConfig()
