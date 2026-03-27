---
name: explainer
description: |
  科普视频生成技能。制作有趣生动的数学/物理/科学讲解视频。
  逐幕生成：每幕独立生成+渲染+用户确认，确认后再下一幕，最后合并。
  触发条件：用户想了解科学概念、原理、定理（不是做题）。
---

# Explainer - 科普视频生成

## 核心工作流

| 步骤 | 名称 | 输出 | 类型 |
|------|------|------|------|
| 0 | 类别选择 | 初始化目录 | online |
| 1 | 知识水平确认 | 初中/高中/大学 | online |
| 2 | 主题分析 | topic_analysis.md | offline |
| **2.5** | **检查点1：大纲确认** | outline.md | online |
| 3 | HTML预览 | preview.html | offline |
| **3.5** | **检查点2：图形确认** | 确认后的preview.html | online |
| 4 | 分镜脚本 | 分镜脚本.md | offline |
| **4.5** | **检查点3：分镜确认** | 确认后的分镜 | online |
| 5 | TTS生成 | audio/*.wav | script |
| 6 | 验证更新 | 更新时长后的分镜 | script |
| 7 | 脚手架 | script.py框架（含共享工具函数）| online |
| **8** | **逐幕循环（默认工作流）** | scenes/幕N.py + 幕N.mp4 | online |
| 9 | 合并所有幕 | output/视频.mp4 | script |
| 10 | 更新索引 | CLAUDE.md | online |

**offline**：导出 prompt 到 Claude.ai 完成；**script**：直接运行脚本；**online**：Claude Code 执行

---

## 步骤8：逐幕生成（默认，强制执行）

**每幕一个循环，不得跳过确认：**

```
生成 幕N 的 Scene 类代码
  → manim -qh script.py Scene_幕N
  → 告知用户：预览命令 / 幕名 / 时长
  → 等待用户回复 "OK" 或描述问题
  → OK：进入幕N+1
  → 有问题：修改幕N代码 → 重渲幕N → 再次等待确认
```

**禁止行为：**
- 禁止一次生成所有幕的代码
- 禁止在用户确认前生成下一幕
- 禁止跳过渲染步骤直接要求用户想象效果

**offline**：导出 prompt 到 Claude.ai 完成；**script**：直接运行脚本；**online**：Claude Code 执行

---

## 项目初始化

```bash
# 初始化系列项目
python3 init-series.py my-series/

# 创建内容目录（大类 小类 标题 知识水平）
python3 init-series.py my-series/ --create-content 数学 几何 勾股定理 初中
```

**目录结构**：
```
my-series/
├── CLAUDE.md                    # 视频清单（自动维护）
├── shared_assets/
└── 数学/几何/勾股定理/
    ├── topic_analysis.md
    ├── outline.md
    ├── preview.html
    ├── 分镜脚本.md
    ├── script.py
    ├── audio/                   # audio_XXX_幕名.wav
    ├── media/                   # Manim输出
    └── output/                  # 最终视频
```

---

## Token 节省：step_runner.py

每个步骤完成后生成会话简报（~150 token），新会话粘贴简报即可恢复：

```bash
# 导出离线步骤 prompt（步骤2/3/4用此命令）
python3 scripts/step_runner.py --export 2 [project_dir]

# 标记完成 + 生成简报
python3 scripts/step_runner.py --done 2 [project_dir]

# 获取简报（新会话粘贴）
python3 scripts/step_runner.py --brief [project_dir]

# 查看进度
python3 scripts/step_runner.py --status [project_dir]

# 保存关键决策
python3 scripts/step_runner.py --decide proof_method "面积拼图法" [project_dir]

# 检查点完成后自动触发换会话提示
python3 scripts/step_runner.py --handoff [project_dir]
```

**换会话时机**（满足任意一条自动运行 `--handoff`）：

1. 刚完成检查点（步骤 1、2.5、3.5、4.5、6）
2. 即将执行步骤 7 或 8
3. 当前会话 context 已经很长

---

---

## 关键命令

```bash
# TTS 生成
python3 scripts/generate_tts.py audio_list.csv ./audio --voice xiaoxiao

# 验证音频并更新分镜时长
python3 scripts/validate_audio.py 分镜脚本.md ./audio

# 代码检查（渲染前必须通过）
python3 scripts/check.py script.py

# 只检查不渲染
python3 scripts/render.py --check-only

# 渲染（无头模式，默认不预览，Claude Code 可直接执行）
python3 scripts/render.py
# 或：manim -qh script.py ExplainerScene

# 状态管理
python3 scripts/step_runner.py --status [dir]
```

---

## 内容标准

### 知识水平

| 级别 | 允许               | 禁止             |
|------|--------------------|------------------|
| 初中 | 代数基础、几何入门 | 导数、极限、微积分 |
| 高中 | +三角函数、解析几何 | 实变函数、抽象代数 |
| 大学 | +极限、导数、积分  | —                |

### 五段式结构

| 段落 | 时长占比 | 核心目标 |
|------|----------|----------|
| 引入 | 15% | 生活实例/历史故事激发兴趣 |
| 定义 | 20% | 文字定义 + 公式 + 图形标注 |
| 探究 | 40% | 动态演示 + 步骤标注 |
| 拓展 | 15% | 应用场景 + 易错点 |
| 总结 | 10% | 核心结论 + 下期预告 |

超过 8 分钟时自动提供压缩方案（精简到 8 分钟内）。

### 分镜规范

- 音频文件命名：`audio_{三位幕号}_{幕名}.wav`（000=开场，999=结尾）
- 字幕 Y 坐标：-3.5；公式 Y 坐标：-4.5
- 读白风格：幽默、口语化，用日常比喻，避免"显然""易得"

### 系列开场/结尾

```
开场：系列Logo动画 + "嗨~欢迎来到3分钟数学科普！今天我们要聊的是：{主题}！" (~5秒)
结尾：核心公式动画 + "今天的{主题}就讲到这里。下期我们要聊{下期主题}，敬请期待！"
注意：下期预告主题必须用户确认
```

---

## 代码规范（script.py）

**每幕对应一个独立 Scene 类**，命名格式：`Scene_{三位幕号}_{幕名}`

```python
# script.py 结构

# ── 共享工具（步骤7脚手架生成，不变）─────────────────────
COLORS = {...}

def make_subtitle(text): ...        # 字幕工具函数
def make_formula(latex): ...        # 公式工具函数

# ── 每幕独立 Scene 类（步骤8逐幕生成）────────────────────
class Scene_000_开场(Scene):
    def construct(self):
        self.add_sound("audio/audio_000_开场.wav")
        # 动画时长 >= 音频时长

class Scene_001_引入(Scene):
    def construct(self):
        self.add_sound("audio/audio_001_引入.wav")
        # ...

# 每幕单独渲染命令：
#   manim -qh script.py Scene_000_开场
#   manim -qh script.py Scene_001_引入
```

**强制约束**：

- 每个 Scene 类的第一行：`self.add_sound("audio/audio_NNN_幕名.wav")`
- 使用 `MathTex(r"a^2 + b^2 = c^2")`，禁止 Text 代替公式
- 避免 `-p` (preview) 参数，Claude Code 用 `-qh`（无头高质量）
- 每幕渲染完告知用户：`open media/videos/script/1080p60/Scene_NNN_幕名.mp4`

---

## 质量检查清单（渲染前必核）

- [ ] 公式/定理表述无错误，证明逻辑完整
- [ ] LaTeX 渲染清晰，图形颜色对比度足够
- [ ] 配音语速 220-260 字/分钟，公式前后有 0.3-0.5 秒停顿
- [ ] 所有音频文件存在且时长 > 0
- [ ] `check.py` 通过（含五段式结构检查）

---

## 强制原则

| 原则 | 说明 |
|------|------|
| 逐幕确认 | 每幕生成→渲染→等用户确认，禁止批量生成所有幕 |
| LaTeX 强制 | 必须安装，禁止降级到 Text |
| 音频强制 | 每幕必须 `self.add_sound()`，无音频视频无效 |
| 音画同步 | 动画时长 >= 音频时长 |
| 错误透明 | 遇到问题必须报告，禁止隐藏 |
| 检查点确认 | 3个检查点必须用户确认后才继续 |

---

## 依赖安装

```bash
uv venv .venv && uv pip install -r requirements.txt

# LaTeX（必须）
brew install --cask mactex-no-gui  # macOS
sudo apt install texlive texlive-fonts-extra texlive-latex-extra  # Ubuntu
```

---

## 相关技能

- **manimce-best-practices**: ManimCE 动画详细写法参考
- **manim-composer**: 将模糊想法转化为详细分镜计划
- **tutor**: 数学解题辅导视频（类似工作流，专注解题）
