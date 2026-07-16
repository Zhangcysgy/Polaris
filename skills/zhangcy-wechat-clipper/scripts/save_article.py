#!/usr/bin/env python3
"""
微信公众号文章 → Obsidian 保存脚本

用法:
    python save_article.py <文章URL> [--vault <目标目录>]
"""

import subprocess
import re
import os
import sys
import json
from datetime import date
from urllib.parse import urlparse
import requests

# 默认配置
DEFAULT_VAULT = r"D:\500_Obsidian\Archive\000_INBOX\010_Web_Clipper\011_微信公众号"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)
SUPPORTED_EXTS = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')


def extract_title(url: str) -> str:
    """提取文章标题。优先级: defuddle metadata > HTML og:title > HTML title"""
    # 1. defuddle -p title
    r = subprocess.run(
        ['npx.cmd', 'defuddle', 'parse', url, '-p', 'title'],
        capture_output=True, text=True, timeout=15, shell=True
    )
    title = r.stdout.strip()
    if title:
        return title

    # 2. HTML og:title
    try:
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=15)
        html = resp.text

        og = re.search(
            r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']',
            html
        )
        if og:
            return og.group(1)

        # 3. <title>
        t = re.search(r'<title>([^<]+)</title>', html)
        if t:
            return t.group(1).strip()
    except Exception:
        pass

    return ""


def sanitize_title(title: str) -> str:
    """净化标题为安全的文件夹名"""
    safe = re.sub(r'[^\u4e00-\u9fff\w\-]', '', title).strip()
    if not safe:
        safe = f"wechat-article-{date.today().isoformat()}"
    if len(safe) > 80:
        safe = safe[:80]
    return safe


def clean_content(md_content: str) -> str:
    """清理微信 UI 噪音内容"""
    ui_noise = [
        "在小说阅读器读本章",
        "去阅读",
        "阅读原文",
        "继续滑动看下一个",
        "微信扫一扫",
        "使用小程序",
        "轻点两下取消赞",
        "轻点两下取消在看",
        "分享 留言 收藏 听过",
        "： ， ， ， ， ， ， ， ， ， ， ， ， 。",
    ]
    for noise in ui_noise:
        md_content = re.sub(rf'^{re.escape(noise)}\s*$', '', md_content, flags=re.MULTILINE)
    # 清理多余空行
    md_content = re.sub(r'\n{3,}', '\n\n', md_content)
    md_content = md_content.strip()
    return md_content


def extract_images(md_content: str) -> list:
    """从 Markdown 中提取图片 URL"""
    return re.findall(r'!\[.*?\]\((https?://[^\s)]+)\)', md_content)


def get_image_extension(img_url: str) -> str:
    """从图片 URL 推断扩展名"""
    # 优先 wx_fmt 参数（微信图片专用）
    wx_fmt = re.search(r'wx_fmt=(\w+)', img_url)
    if wx_fmt:
        ext = f".{wx_fmt.group(1)}"
        if ext.lower() in SUPPORTED_EXTS:
            return ext

    # URL 路径扩展名
    path = urlparse(img_url).path
    ext = os.path.splitext(path)[1].lower()
    if ext in SUPPORTED_EXTS:
        return ext

    return '.jpg'


def download_images(image_urls: list, attachments_dir: str,
                    referer: str) -> tuple[dict[str, str], int, int]:
    """下载所有图片到本地，返回 (url_map, success_count, fail_count)"""
    os.makedirs(attachments_dir, exist_ok=True)

    headers = {
        "User-Agent": USER_AGENT,
        "Referer": referer
    }

    url_map = {}
    success = 0
    failed = 0

    for idx, img_url in enumerate(image_urls, 1):
        ext = get_image_extension(img_url)
        filename = f"image-{idx:04d}{ext}"
        filepath = os.path.join(attachments_dir, filename)

        # 重试 2 次
        downloaded = False
        for attempt in range(3):
            try:
                resp = requests.get(img_url, headers=headers, timeout=15)
                if resp.status_code == 200:
                    with open(filepath, 'wb') as f:
                        f.write(resp.content)
                    url_map[img_url] = f"attachments/{filename}"
                    success += 1
                    downloaded = True
                    print(f"  ✅ [{idx}/{len(image_urls)}] {filename} ({len(resp.content):,} bytes)")
                    break
                else:
                    print(f"  ⚠️  [{idx}] HTTP {resp.status_code}, 重试 {attempt+1}/2")
            except Exception as e:
                print(f"  ⚠️  [{idx}] {e}, 重试 {attempt+1}/2")

        if not downloaded:
            failed += 1
            print(f"  ❌ [{idx}] 下载失败，保留原始 URL")

    return url_map, success, failed


def build_frontmatter(title: str, url: str) -> str:
    """构建 YAML frontmatter"""
    today = date.today().isoformat()
    return f"""---
title: "{title}"
source: "{url}"
date: {today}
tags:
  - 微信公众号
  - clipper
  - 待整理
status: inbox
---

"""


def clean_wechat_url(url: str) -> str:
    """清理微信文章 URL，只保留必要参数"""
    url = url.split('#')[0]
    parts = url.split('?')
    if len(parts) == 2:
        params = parts[1].split('&')
        keep = [p for p in params if p.split('=')[0] in ('__biz', 'mid', 'idx', 'sn')]
        if keep:
            return parts[0] + '?' + '&'.join(keep)
    return url


def save_article(url: str, base_dir: str = DEFAULT_VAULT) -> dict:
    """完整的公众号文章保存流程"""
    # 清理 URL：去掉追踪参数
    url = clean_wechat_url(url)
    print(f"\n📥 正在处理: {url}")
    print("=" * 50)

    # Step 2: Defuddle
    print("\n📄 抓取文章内容...")
    r = subprocess.run(
        ['npx.cmd', 'defuddle', 'parse', url, '--md'],
        capture_output=True, text=True, timeout=30, shell=True
    )
    md_content = r.stdout.strip()
    if not md_content:
        raise Exception(f"无法获取文章内容。Defuddle 返回空。\nSTDERR: {r.stderr}")
    print(f"   内容长度: {len(md_content)} 字符")

    # Step 2.5: 清理 UI 噪音
    md_content = clean_content(md_content)
    print(f"   清理后长度: {len(md_content)} 字符")

    # Step 3: 提取标题
    print("\n🏷️  提取标题...")
    title = extract_title(url)
    if not title:
        # 最后回退：Markdown 中的第一个 H1
        for line in md_content.split('\n'):
            if line.startswith('# ') and len(line) > 5:
                title = line[2:].strip()
                break
    if not title:
        title = "未命名文章"
    print(f"   标题: {title}")

    # Step 4: 净化
    safe_name = sanitize_title(title)
    print(f"   文件夹名: {safe_name}")

    # Step 5: 路径
    article_dir = os.path.join(base_dir, safe_name)
    attachments_dir = os.path.join(article_dir, "attachments")
    md_path = os.path.join(article_dir, f"{safe_name}.md")

    # 检查冲突
    if os.path.exists(article_dir):
        # 非交互环境默认创建副本
        i = 2
        while os.path.exists(f"{article_dir}-{i}"):
            i += 1
        article_dir = f"{article_dir}-{i}"
        attachments_dir = os.path.join(article_dir, "attachments")
        md_path = os.path.join(article_dir, f"{safe_name}.md")
        print(f"⚠️  目录已存在，创建副本: {article_dir}")

    # Step 6: 提取并下载图片
    print(f"\n🖼️  下载图片...")
    images = extract_images(md_content)
    print(f"   找到 {len(images)} 张图片")

    url_map, success, failed = download_images(
        images, attachments_dir, referer=url
    )

    # Step 7: 替换图片引用
    new_md = md_content
    for old_url, local_path in url_map.items():
        new_md = new_md.replace(f"]({old_url})", f"]({local_path})")

    # Step 8: Frontmatter
    frontmatter = build_frontmatter(title, url)
    final_content = frontmatter + new_md

    # Step 9: 保存
    os.makedirs(article_dir, exist_ok=True)
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(final_content)

    # Step 10: 报告
    print("\n" + "=" * 50)
    print(f"✅ 文章已保存到 Obsidian")
    print(f"📁 位置: 011_微信公众号/{safe_name}/")
    print(f"📄 文件: {safe_name}.md")
    print(f"🖼️  图片: {success} 张已下载", end="")
    if failed:
        print(f" (失败 {failed} 张)")
    else:
        print()
    print(f"🔗 来源: {url}")
    print("=" * 50)

    return {
        "success": True,
        "title": title,
        "safe_name": safe_name,
        "path": f"011_微信公众号/{safe_name}/",
        "images_downloaded": success,
        "images_failed": failed
    }


def main():
    """命令行入口"""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    url = sys.argv[1]

    base_dir = DEFAULT_VAULT
    if '--vault' in sys.argv:
        idx = sys.argv.index('--vault')
        if idx + 1 < len(sys.argv):
            base_dir = sys.argv[idx + 1]

    try:
        result = save_article(url, base_dir)
        if not result.get("success"):
            print(f"⚠️  {result.get('reason', '未知错误')}")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
