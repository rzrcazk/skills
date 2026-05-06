"""Shared constants used across explainer scripts."""

STEP_NAMES = {
    0: "类别选择",
    1: "知识水平确认",
    2: "主题分析",
    2.5: "检查点1-大纲确认",
    3: "HTML预览",
    3.5: "检查点2-图形确认",
    4: "分镜脚本",
    4.5: "检查点3-分镜确认",
    5: "TTS生成",
    6: "验证更新",
    7: "脚手架",
    8: "生成代码",
    9: "检查渲染",
    10: "更新索引",
}

DECISION_LABELS = {
    "introduction_method": "引入方式",
    "proof_method": "证明方法",
    "duration_estimate": "预计时长",
    "scene_count": "场景数量",
}

CHECKPOINT_LABELS = {
    "checkpoint1": "大纲确认",
    "checkpoint2": "图形确认",
    "checkpoint3": "分镜确认",
}

LEVEL_CONSTRAINTS = {
    "初中": "可以使用：基础代数、简单几何、具体数字运算。禁止使用：三角函数、坐标几何、复杂证明。",
    "高中": "可以使用：三角函数、坐标几何、向量、数学归纳法。禁止使用：微积分、线性代数、群论。",
    "大学": "可以使用：微积分、线性代数、微分方程。禁止使用：泛函分析、拓扑学、测度论。",
}
