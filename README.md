# Claude Code 版本自动同步项目

> 自动同步 Claude Code 最新版本到 GitHub Release 的项目

## 项目简介

本项目通过 GitHub Actions 每天自动检查 Claude Code 最新版本，如果有更新则下载所有平台版本并发布到 GitHub Release，方便用户快速获取最新版本。

## 功能特性

- ✅ 每天自动检查最新版本
- ✅ 下载所有 7 个平台的 Claude Code 二进制文件
- ✅ 自动验证 SHA256 checksum
- ✅ 创建格式化的 GitHub Release
- ✅ 包含完整的版本信息和校验和

## 支持的平台

| 平台 | 文件名 |
|------|--------|
| macOS Apple Silicon | `claude-darwin-arm64` |
| macOS Intel | `claude-darwin-x64` |
| Linux x64 (glibc) | `claude-linux-x64` |
| Linux x64 (musl) | `claude-linux-x64-musl` |
| Linux arm64 (glibc) | `claude-linux-arm64` |
| Linux arm64 (musl) | `claude-linux-arm64-musl` |
| Windows x64 | `claude-win32-x64.exe` |

## 使用方法

### 下载 Claude Code

1. 访问本项目的 [Releases](../../releases) 页面
2. 选择最新版本
3. 根据你的平台下载对应的文件
4. 下载后添加执行权限（macOS/Linux）：
   ```bash
   chmod +x claude-*
   ```
5. 移动到 PATH 目录：
   ```bash
   sudo mv claude-* /usr/local/bin/claude
   ```

### 验证下载的文件

每个 Release 都包含 SHA256 校验和，你可以验证下载的文件：

```bash
# macOS/Linux
sha256sum claude-*

# Windows (PowerShell)
Get-FileHash claude-win32-x64.exe -Algorithm SHA256
```

## 本地测试

如果你想本地测试下载脚本：

```bash
# 安装依赖
pip install requests

# 运行下载脚本
python scripts/download_claude.py
```

## 工作流说明

GitHub Actions 工作流每天 UTC 00:00 自动运行，执行以下步骤：

1. 获取 Claude Code 最新版本号
2. 检查是否已存在对应 Release
3. 如果版本更新：
   - 下载所有平台版本
   - 验证 SHA256 checksum
   - 创建 GitHub Release
   - 上传所有文件作为 Assets

你也可以在 GitHub Actions 页面手动触发工作流。

## 数据来源

本项目的数据来源于 Claude Code 官方 GCS 存储桶：
```
https://storage.googleapis.com/claude-code-dist-86c565f3-f756-42ad-8dfa-d59b1c096819/claude-code-releases
```

## License

本项目仅用于同步 Claude Code 官方版本，Claude Code 的版权和 License 归 Anthropic 所有。

---

*此项目由 GitHub Actions 自动维护*