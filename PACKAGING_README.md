# 打包说明

## macOS

### 快速开始

```bash
cd wechat-publisher
bash build_dmg.sh
```

### 输出文件

- **位置**：`dist/WeChatPublisher-1.0.0-arm64.dmg`
- **大小**：约 44MB
- **架构**：arm64（Apple Silicon 原生）

### 用户安装方式

1. 双击 `WeChatPublisher-1.0.0-arm64.dmg`
2. 将「微信公众号发布助手」拖入右侧 **Applications** 文件夹
3. **首次打开**：右键 → 打开（绕过 Gatekeeper）
4. 浏览器自动打开 `http://localhost:5678`

---

## Windows

### 方式一：纯 EXE 打包（推荐，无需安装）

双击 `build_exe.bat`，输出单个 `dist\WeChatPublisher.exe`（约 50MB）

**特点：**
- 单个可执行文件，无需安装
- 复制到任意位置即可运行
- 适合便携分发

### 方式二：NSIS 安装包

双击 `build_installer.bat`，输出 `WeChatPublisher-Setup.exe`

**特点：**
- 标准安装向导
- 自动创建开始菜单和桌面快捷方式
- 支持卸载

**前置依赖：**
- 需要安装 NSIS：https://nsis.sourceforge.io/Download

### 用户使用方式

1. 双击 `WeChatPublisher.exe` 运行
2. 首次运行自动打开浏览器访问 `http://localhost:5678`

---

## 重新打包

### macOS

```bash
cd wechat-publisher
bash build_dmg.sh
```

### Windows

```cmd
cd wechat-publisher
REM 纯 EXE
build_exe.bat

REM 或 NSIS 安装包
build_installer.bat
```

---

## 前置依赖

### macOS
- **Homebrew**（如果未安装会提示）
- **create-dmg**：`brew install create-dmg`

### Windows
- **Python 3.8+**
- **NSIS**（仅安装包需要）

---

## 自定义

### macOS

编辑 `build_dmg.sh` 开头：

```bash
APP_NAME="微信公众号发布助手"
DMG_NAME="WeChatPublisher-1.0.0-arm64"
```

### Windows

编辑 `build_exe.bat` 或 `build_installer.bat` 开头：

```batch
set APP_NAME=微信公众号发布助手
set APP_VERSION=1.0.0
```
