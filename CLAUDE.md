# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 提供在操作本代码库时的指导。

## 仓库概览

这是一个 Claude Code 技能集合，包含三个独立的技能，分别用于视频生成和媒体控制。每个技能都是自包含的，拥有独立的依赖和工作流。

## 技能结构

```
skills/
├── explainer/          # 教育视频生成（科普视频）
├── tutor/              # 数学辅导视频生成（数学辅导）
└── dlna/               # DLNA 媒体设备控制
```

## 依赖管理

所有技能都使用 `uv` 进行 Python 依赖管理：

```bash
# 安装 uv（如尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建虚拟环境并安装依赖
uv venv .venv
uv pip install -r requirements.txt
```

## 技能：explainer

使用 Manim 和 TTS 音频创建数学/科学讲解视频。

### 关键命令

```bash
# 初始化新项目（带依赖检查）
python3 init.py [project_dir]

# 初始化系列项目（推荐用于多视频）
python3 init-series.py my-series/
python3 init-series.py my-series/ --create-content 数学 几何 勾股定理 初中

# 从 CSV 生成 TTS 音频
python3 scripts/generate_tts.py audio_list.csv ./audio --voice xiaoxiao

# 验证音频并更新分镜时长
python3 scripts/validate_audio.py 分镜脚本.md ./audio

# 渲染前检查脚本
python3 scripts/check.py script.py

# 检查工作流状态
python3 scripts/step_runner.py --status [content_dir]

# 渲染视频（Claude Code 可使用无头模式）
python3 scripts/render.py
# 或手动（避免 -p 预览参数）：manim -qh script.py ExplainerScene
```

### 分段流水线（推荐工作流）

Explainer 支持分段视频生成以便增量审批：

```bash
# 初始化分段流水线
cd my-series/数学/几何/勾股定理/
python3 ../../../scripts/segment_pipeline.py --project . --init

# 生成分段（无头模式 - Claude Code 兼容）
python3 ../../../scripts/segment_generator.py --project . --segment 0

# 以无头模式运行完整流水线
python3 ../../../scripts/run_segment_pipeline.py --project . --headless

# 标记分段为已渲染（渲染完成后执行，Claude Code 或用户终端均可）
python3 ../../../scripts/mark_segment_rendered.py --project . --segment 0
```

### 关键约束

1. **必须安装 LaTeX** - 用于公式渲染。安装方式：
   - macOS: `brew install --cask mactex-no-gui`
   - Ubuntu: `sudo apt install texlive texlive-fonts-extra texlive-latex-extra`

2. **Claude Code 使用无头模式渲染** - Manim 需要避免 `-p` (preview) 参数。使用：
   - `manim -qh script.py ExplainerScene`（Claude Code 可直接执行）
   - `python3 scripts/render.py`（脚本已配置无头模式）

3. **音频是必需的** - 每个场景都必须调用 `self.add_sound()`。没有音频的视频是无效的。

4. **动画时长** - 动画时长必须 >= 音频时长，以防止音频被截断。

### 内容标准（五段式结构）

视频遵循严格的五段式格式：
1. **引入** (15%) - 用现实例子或历史背景吸引注意力
2. **定义** (20%) - 清晰的概念解释和公式
3. **探索** (40%) - 证明/推导配合动态动画
4. **拓展** (15%) - 应用和常见错误
5. **总结** (10%) - 关键要点和下集预告

## 技能：tutor

创建解决特定数学问题的辅导视频。

### 关键命令

与 explainer 相同，但工作流针对单题解答：

```bash
# 初始化项目
python3 init.py [project_dir]

# 与 explainer 相同的 TTS、验证、检查、渲染脚本
python3 scripts/generate_tts.py audio_list.csv ./audio
python3 scripts/validate_audio.py 分镜.md ./audio
python3 scripts/check.py
python3 scripts/render.py
```

### 工作流步骤

1. **分析题目** → `math_analysis.md`
2. **HTML 可视化** → `数学_日期_题目.html`
3. **分镜脚本** → `日期_题目_分镜.md`
4. **生成 TTS** → `audio/*.wav` + `audio_info.json`
5. **验证音频** → 更新分镜时长
6. **脚手架** → `script.py`（模板）
7. **实现** → 完整的 `script.py`
8. **检查与渲染** → 视频文件

### 与 Explainer 的关键区别

- **不需要 LaTeX** - 使用 Unicode 文本表示公式（如 `x²` 代替 `x^2`）
- **以问题为中心** - 每个视频一个数学题
- **几何证明** - 强调纯几何推理（不使用坐标法）

## 技能：dlna

DLNA/UPnP 媒体渲染器控制库和 CLI。

### 关键命令

```bash
# 通过 uv 安装并运行
uv run dlna discover
uv run dlna play "http://example.com/video.mp4" [device_name]
uv run dlna stop [device_name]
uv run dlna status [device_name]

# 配置
uv run dlna config --device "客厅电视"
uv run dlna config --unset-device
```

### 项目结构

```
dlna/
├── pyproject.toml      # 包配置
├── src/dlna/
│   ├── __init__.py     # 公共 API 导出
│   ├── cli.py          # Click CLI 实现
│   ├── player.py       # 核心 DLNA 控制逻辑
│   ├── discover.py     # 设备发现
│   └── config.py       # 默认设备配置
```

### 播放本地文件

DLNA 设备需要 HTTP URL。播放本地文件：

```python
# 在后台启动 HTTP 服务器（使用 Bash 的 run_in_background）
# 然后构造带本地 IP 的 URL 并播放
import socket
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip

url = f"http://{get_ip()}:8000/video.mp4"
# uv run dlna play url
```

## 通用模式

### Manim 场景结构（explainer/tutor）

```python
class MathScene(Scene):
    COLORS = {...}           # 配色方案
    SCENES = [...]           # 场景时长信息

    def calculate_geometry(self):
        """计算所有几何坐标"""
        pass

    def assert_geometry(self, geometry):
        """验证几何约束 + 画布边界"""
        pass

    def construct(self):
        """主动画流程"""
        geometry = self.calculate_geometry()
        self.assert_geometry(geometry)
        # 播放带音频的场景
```

### 音频文件命名

```
audio_001_幕名.wav   # tutor: 从 001 开始连续编号
audio_000_开场.wav   # explainer: 从 000 开始（引入）
audio_999_结尾.wav   # explainer: 以 999 结束（收尾）
```

### 工作流状态文件

explainer 和 tutor 都使用 `workflow_state.json` 跟踪进度：

```json
{
  "current_step": 5,
  "steps_completed": [1, 2, 3, 4],
  "status": "in_progress"
}
```

## 测试与验证

### 渲染前检查清单（explainer/tutor）

```bash
# 1. 代码结构检查
python3 scripts/check.py

# 2. 音频验证
python3 scripts/validate_audio.py 分镜.md ./audio

# 3. 状态检查
python3 scripts/step_runner.py --status [dir]
```

### DLNA 测试

```bash
# 首先发现设备
uv run dlna discover

# 测试播放并检查状态
uv run dlna play "http://..." && sleep 2 && uv run dlna status
```
