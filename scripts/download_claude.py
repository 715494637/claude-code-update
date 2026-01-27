#!/usr/bin/env python3
"""
Claude Code 版本自动同步下载脚本

功能:
- 从 GCS 存储桶获取最新版本信息
- 下载所有平台的 Claude Code 二进制文件
- 验证 SHA256 checksum
- 生成版本信息和校验和列表

特性:
- 使用 aiohttp 实现异步并发下载
- 实时进度条显示
- 自动重试机制
- 连接池复用
"""

import os
import sys
import json
import hashlib
import asyncio
from pathlib import Path
from typing import Optional

import aiohttp
from tqdm import tqdm

# GCS 存储桶地址
GCS_BUCKET = os.environ.get(
    'GCS_BUCKET',
    'https://storage.googleapis.com/claude-code-dist-86c565f3-f756-42ad-8dfa-d59b1c096819/claude-code-releases'
)

# 平台映射
PLATFORMS = {
    'darwin-arm64': 'claude-darwin-arm64',
    'darwin-x64': 'claude-darwin-x64',
    'linux-arm64': 'claude-linux-arm64',
    'linux-x64': 'claude-linux-x64',
    'linux-arm64-musl': 'claude-linux-arm64-musl',
    'linux-x64-musl': 'claude-linux-x64-musl',
    'win32-x64': 'claude-win32-x64.exe'
}

# 输出目录
OUTPUT_DIR = Path('releases')

# 配置
MAX_RETRIES = 3
RETRY_DELAY = 2
CHUNK_SIZE = 8192
TIMEOUT = aiohttp.ClientTimeout(total=120, connect=30)


def print_step(message: str):
    """打印步骤信息"""
    print(f"\n{'='*70}")
    print(f"  {message}")
    print(f"{'='*70}")


def print_success(message: str):
    """打印成功信息"""
    print(f"  ✓ {message}")


def print_error(message: str):
    """打印错误信息"""
    print(f"  ✗ {message}", file=sys.stderr)


def format_size(size: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


def calculate_sha256(file_path: Path) -> str:
    """计算文件的 SHA256 校验和"""
    sha256_hash = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


async def get_latest_version(session: aiohttp.ClientSession) -> str:
    """获取最新版本号"""
    print_step("获取最新版本号")

    url = f"{GCS_BUCKET}/latest"
    async with session.get(url) as response:
        response.raise_for_status()
        version = (await response.text()).strip()
        print_success(f"最新版本: {version}")
        return version


async def get_manifest(session: aiohttp.ClientSession, version: str) -> dict:
    """获取版本清单"""
    print_step("获取版本清单")

    url = f"{GCS_BUCKET}/{version}/manifest.json"
    async with session.get(url) as response:
        response.raise_for_status()
        manifest = await response.json()

        print_success(f"版本: {manifest['version']}")
        print_success(f"构建日期: {manifest['buildDate']}")
        print_success(f"支持平台数: {len(manifest['platforms'])}")

        # 显示各平台文件大小
        print("\n  平台文件大小:")
        for platform, info in manifest['platforms'].items():
            filename = PLATFORMS.get(platform, platform)
            size = format_size(info['size'])
            print(f"    • {filename:30} {size}")

        return manifest


async def download_file_with_progress(
    session: aiohttp.ClientSession,
    url: str,
    output_path: Path,
    filename: str,
    expected_size: int
) -> bool:
    """
    下载文件并显示进度条

    Returns:
        下载是否成功
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(MAX_RETRIES):
        try:
            async with session.get(url) as response:
                response.raise_for_status()

                total_size = int(response.headers.get('Content-Length', expected_size))

                # 创建进度条
                progress = tqdm(
                    total=total_size,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                    desc=f"  {filename}",
                    ncols=70,
                    bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'
                )

                # 下载文件
                with open(output_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                        f.write(chunk)
                        progress.update(len(chunk))

                progress.close()
                return True

        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                print(f"  重试 {attempt + 1}/{MAX_RETRIES}: {filename} - {str(e)}")
                await asyncio.sleep(RETRY_DELAY)
            else:
                print_error(f"{filename} 下载失败: {e}")
                return False

    return False


async def download_platform(
    session: aiohttp.ClientSession,
    version: str,
    platform: str,
    info: dict,
    semaphore: asyncio.Semaphore
) -> tuple[bool, str, str]:
    """
    下载指定平台的 Claude Code

    Args:
        session: aiohttp 会话
        version: 版本号
        platform: 平台标识
        info: 平台信息（包含 checksum 和 size）
        semaphore: 并发控制信号量

    Returns:
        (success, platform, message)
    """
    async with semaphore:  # 限制并发数
        filename = 'claude.exe' if 'win32' in platform else 'claude'
        output_filename = PLATFORMS.get(platform, filename)
        url = f"{GCS_BUCKET}/{version}/{platform}/{filename}"
        output_path = OUTPUT_DIR / version / output_filename

        # 下载文件
        print(f"\n  开始下载: {output_filename}")
        success = await download_file_with_progress(
            session, url, output_path, output_filename, info['size']
        )

        if not success:
            return False, platform, f"下载失败: {output_filename}"

        # 验证 checksum
        print(f"  验证校验和: {output_filename}", end=' ')
        actual_checksum = calculate_sha256(output_path)

        if actual_checksum.lower() == info['checksum'].lower():
            print_success("校验通过")
            return True, platform, f"{actual_checksum}  {output_filename}"
        else:
            print_error("校验失败")
            print_error(f"  期望: {info['checksum']}")
            print_error(f"  实际: {actual_checksum}")
            output_path.unlink()
            return False, platform, f"校验失败: {output_filename}"


async def download_all_platforms(version: str, manifest: dict) -> dict:
    """异步下载所有平台版本"""
    print_step("异步下载所有平台版本")

    platforms = manifest.get('platforms', {})
    results = {}
    checksums = []

    # 创建 aiohttp 会话（连接池）
    connector = aiohttp.TCPConnector(
        limit=10,  # 最大连接数
        limit_per_host=7,  # 每个主机最大连接数
        force_close=False,  # 保持连接
        enable_cleanup_closed=True
    )

    # 信号量控制并发数
    semaphore = asyncio.Semaphore(7)

    async with aiohttp.ClientSession(connector=connector, timeout=TIMEOUT) as session:
        # 创建所有下载任务
        tasks = [
            download_platform(session, version, platform, info, semaphore)
            for platform, info in platforms.items()
        ]

        # 并发执行所有任务
        completed = await asyncio.gather(*tasks)

        # 处理结果
        for success, platform, message in completed:
            results[platform] = (success, message)
            if success:
                checksums.append(message)

    # 统计结果
    success_count = sum(1 for success, _ in results.values() if success)
    total_count = len(results)

    print(f"\n  下载完成: {success_count}/{total_count} 个平台")

    if success_count < total_count:
        print_error("部分平台下载失败，请检查日志")
        sys.exit(1)

    return results, checksums


def save_version_info(version: str, manifest: dict, checksums: list):
    """保存版本信息到文件"""
    print_step("保存版本信息")

    # 保存版本号
    with open('.version', 'w') as f:
        f.write(version)
    print_success("版本号已保存")

    # 保存构建日期
    with open('.build_date', 'w') as f:
        f.write(manifest['buildDate'])
    print_success("构建日期已保存")

    # 保存校验和列表
    with open('.checksums', 'w') as f:
        f.write('\n'.join(checksums))
    print_success("校验和列表已保存")


async def main_async():
    """异步主函数"""
    print("\n" + "="*70)
    print("  Claude Code 版本自动同步下载脚本 (异步版)")
    print("  使用 aiohttp + tqdm 实现高效下载和进度显示")
    print("="*70)

    try:
        # 创建 aiohttp 会话
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            # 获取最新版本
            version = await get_latest_version(session)

            # 获取版本清单
            manifest = await get_manifest(session, version)

            # 下载所有平台
            results, checksums = await download_all_platforms(version, manifest)

            # 保存版本信息
            save_version_info(version, manifest, checksums)

            print_step("完成!")
            print_success(f"所有文件已保存到: {OUTPUT_DIR / version}")
            print("\n")

    except aiohttp.ClientError as e:
        print_error(f"网络请求失败: {e}")
        sys.exit(1)
    except Exception as e:
        print_error(f"发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """主函数"""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print_error("\n用户中断下载")
        sys.exit(1)


if __name__ == '__main__':
    main()