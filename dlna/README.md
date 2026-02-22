# DLNA 媒体控制工具

用于控制局域网内 DLNA/UPnP 媒体渲染设备的 Python 库和命令行工具。

## 功能特性

- 🔍 自动发现局域网内的 DLNA 设备
- ▶️ 在智能电视和音箱上播放媒体 URL
- ⏹️ 控制播放（播放、停止、状态查询）
- ⚙️ 设置默认设备，简化操作
- 🐍 同时提供 CLI 和 Python API

## 安装

需要 Python 3.10+

```bash
# 进入项目目录
cd dlna

# 使用 uv 安装
uv pip install -e .

# 或使用 pip 安装
pip install -e .
```

## 快速开始

```bash
# 发现网络中的 DLNA 设备
uv run dlna discover

# 设置默认设备（可选，但推荐）
uv run dlna config --device "客厅电视"

# 播放媒体 URL
uv run dlna play "http://example.com/video.mp4"

# 或明确指定设备
uv run dlna play "http://example.com/video.mp4" "客厅电视"

# 停止播放
uv run dlna stop
```

## CLI 命令

| 命令 | 说明 |
|---------|-------------|
| `discover` | 扫描网络中的 DLNA 设备 |
| `play <url> [device]` | 在设备上播放媒体 URL |
| `stop [device]` | 停止播放 |
| `status [device]` | 获取当前播放状态 |
| `config` | 显示当前配置 |
| `config --device <name>` | 设置默认设备 |
| `config --unset-device` | 清除默认设备 |

## 播放本地文件

DLNA 设备只能播放 URL，不能直接访问本地文件路径。要播放本地文件，需要通过 HTTP 服务：

```bash
# 启动本地 HTTP 服务器
python3 -m http.server 8000

# 获取本机 IP 地址
ifconfig | grep "inet " | grep -v 127.0.0.1 | head -1

# 使用本机 IP 播放文件
uv run dlna play "http://192.168.1.100:8000/video.mp4"
```

### 使用示例脚本

项目中提供了一个示例脚本来简化本地文件投屏：

```bash
# 在后台启动 HTTP 服务器，然后播放文件
python3 -m http.server 8765 &
uv run dlna play "http://$(hostname -I | awk '{print $1}'):8765/1.mp4" "酷喵电视"
```

## Python API

```python
import asyncio
from dlna import discover_devices, find_device, play_url, set_default_device

async def main():
    # 设置默认设备
    set_default_device("客厅电视")

    # 查找设备（如果不指定名称，则使用默认设备）
    device = await find_device()
    if device:
        # 播放远程 URL
        await play_url(device, "http://example.com/video.mp4")

asyncio.run(main())
```

## 支持的设备

- **智能电视**：索尼 BRAVIA、三星、LG 等
- **智能音箱**：支持 DLNA 的 Soundbar、音箱
- **投屏软件**：乐播投屏等 DLNA 应用
- **其他设备**：任何支持 UPnP MediaRenderer 的设备

## 实际使用案例

### 案例 1：投屏到索尼电视

```bash
# 1. 发现设备
uv run dlna discover
# 输出：
#   1. 酷喵电视_索尼(EC)
#   2. 乐播投屏（SONY XR-65X91J）
#   3. HT-Z9F

# 2. 通过乐播投屏播放（推荐用于索尼电视）
uv run dlna play "http://192.168.100.207:8765/video.mp4" "乐播投屏（SONY XR-65X91J）"

# 3. 检查播放状态
uv run dlna status "乐播投屏（SONY XR-65X91J）"
```

### 案例 2：设置默认设备

```bash
# 设置默认设备
uv run dlna config --device "HT-Z9F"

# 之后播放无需指定设备名
uv run dlna play "http://example.com/music.mp3"
```

## 项目结构

```
dlna/
├── src/dlna/           # 源代码
│   ├── __init__.py     # 公共 API 导出
│   ├── cli.py          # 命令行接口
│   ├── config.py       # 配置管理
│   ├── discover.py     # 设备发现
│   └── player.py       # 播放控制
├── scripts/            # 工具脚本
├── pyproject.toml      # 项目配置
├── SKILL.md            # Claude Code 技能文档
└── README.md           # 本文件
```

## 依赖项

- [async-upnp-client](https://github.com/StevenLooman/async_upnp_client) - UPnP/DLNA 客户端库
- [aiohttp](https://docs.aiohttp.org/) - 异步 HTTP 客户端/服务器
- [click](https://click.palletsprojects.com/) - CLI 框架

## 许可证

MIT
