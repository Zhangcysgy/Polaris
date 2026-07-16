#!/usr/bin/env python3
"""
微信公众号文章 → Obsidian 剪藏工具（合并版）

提取策略（由简到繁）：
  Tier 1: 从原始 HTML 的 JS 变量中提取元数据 + 正文（allow_redirects=False 绕过验证码）
  Tier 2: 正文不完整时用 Playwright 渲染后提取（备用）

用法:
  python clipper.py <URL>                        # 单篇
  python clipper.py <URL1> <URL2> ...            # 批量
  python clipper.py <URL> --vault D:/path        # 指定 vault

依赖:
  pip install requests beautifulsoup4 lxml html2text
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
import html2text

# ============================================================
# 配置
# ============================================================
DEFAULT_VAULT = r"D:\500_Obsidian\Archive"
OUTPUT_SUBDIR = r"000_INBOX\010_Web_Clipper\011_微信公众号"

FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
IMG_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://mp.weixin.qq.com/",
}
SUPPORTED_EXTS = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')

# 全局 Session：跨请求保持 cookie，降低限流概率
_SESSION = requests.Session()
_SESSION.headers.update(FETCH_HEADERS)


# ============================================================
# 工具函数
# ============================================================
def clean_url(url: str) -> str:
    """清理微信 URL：去 #rd 锚点 + 去掉追踪参数，保留必要参数"""
    url = url.split('#')[0]
    parsed = urlparse(url)
    # 如果是短格式 /s/{sn} 直接返回
    if parsed.path.startswith('/s/') and not parsed.query:
        return url
    # 长格式：从原始 URL 中只保留 __biz, mid, idx, sn 参数
    if parsed.path in ('/s', '/s/') and parsed.query:
        raw_params = parsed.query.split('&')
        keep = [p for p in raw_params if p.split('=')[0] in ('__biz', 'mid', 'idx', 'sn')]
        if keep:
            return f"{parsed.scheme}://{parsed.netloc}/s?{'&'.join(keep)}"
    return url


def sanitize_name(name: str, max_len: int = 60) -> str:
    """净化文件名，移除 Windows 非法字符"""
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:max_len].rstrip() if len(name) > max_len else name


def guess_extension(img_url: str) -> str:
    """从 URL 推断图片扩展名（优先 wx_fmt 参数）"""
    wx_fmt = re.search(r'wx_fmt=(\w+)', img_url)
    if wx_fmt:
        ext = f".{wx_fmt.group(1)}"
        if ext.lower() in SUPPORTED_EXTS:
            return ext
    path = urlparse(img_url).path
    ext = os.path.splitext(path)[1].lower()
    return ext if ext in SUPPORTED_EXTS else '.webp'


# ============================================================
# Tier 1: 从 HTML 提取（allow_redirects=False 绕过验证码）
# ============================================================
def fetch_html(url: str, max_retries: int = 3) -> tuple[str, str | None]:
    """获取文章 HTML（allow_redirects=False + 重试机制）

    微信有限流机制：同一 IP 短时间内多次请求会触发 302 → captcha。
    策略：检测到重定向后等待 3-5 秒重试，最多重试 max_retries 次。
    """
    for attempt in range(max_retries):
        try:
            resp = _SESSION.get(url, timeout=30, allow_redirects=False)
            if resp.status_code == 200:
                if 'msg_title' in resp.text:
                    return resp.text, None
                # 200 但没有 msg_title，可能是限流页面
                if attempt < max_retries - 1:
                    wait = 3 + attempt * 2
                    print(f"  ⚠️  返回 200 但无文章内容，{wait}秒后重试 ({attempt+1}/{max_retries})...")
                    time.sleep(wait)
                    continue
                return "", "多次重试后仍无法获取文章内容（可能已被限流）"
            # 302 重定向到验证码 → 限流了
            location = resp.headers.get("Location", "")
            if resp.status_code == 302 and location:
                if attempt < max_retries - 1:
                    wait = 4 + attempt * 3
                    print(f"  ⚠️  被限流（302→captcha），等待{wait}秒后重试 ({attempt+1}/{max_retries})...")
                    time.sleep(wait)
                    continue
                return "", f"被限流，多次重试后仍被重定向到验证码"
            return "", f"HTTP {resp.status_code}，无法获取文章"
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            return "", str(e)
    return "", "重试耗尽"


def extract_js_vars(html: str) -> dict:
    """从 JS 变量提取元数据"""
    meta = {}
    patterns = [
        ("title",     r'var\s+msg_title\s*=\s*([\'"])(.*?)\1\s*(?:\.html\s*\(\s*false\s*\))?\s*;'),
        ("author",    r'var\s+msg_author\s*=\s*([\'"])(.*?)\1\s*;'),
        ("nickname",  r'var\s+msg_nickname\s*=\s*([\'"])(.*?)\1\s*;'),
        ("desc",      r'var\s+msg_desc\s*=\s*(?:htmlDecode\s*\()?\s*([\'"])(.*?)\1\s*(?:\))?\s*;'),
        ("cover_url", r'var\s+msg_cdn_url\s*=\s*([\'"])(.*?)\1\s*;'),
        ("timestamp", r'var\s+ct\s*=\s*([\'"])(\d+)\1\s*;'),
    ]
    for key, pattern in patterns:
        m = re.search(pattern, html)
        if m:
            meta[key] = m.group(2).strip()

    if "timestamp" in meta:
        try:
            ts = int(meta["timestamp"])
            meta["published"] = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        except Exception:
            pass

    # fallback: 从页面 HTML 提取公众号名
    if not meta.get("nickname") and not meta.get("author"):
        soup = BeautifulSoup(html, "lxml")
        nick = soup.find(id="js_name") or soup.find(class_="rich_media_meta_nickname")
        if nick:
            meta["nickname"] = nick.get_text(strip=True)

    return meta


def extract_body_html(html: str) -> str | None:
    """从 HTML 中提取 js_content 正文"""
    soup = BeautifulSoup(html, "lxml")
    div = soup.find("div", id="js_content") or soup.find("div", class_="rich_media_content")
    if div:
        text = div.get_text(strip=True)
        if text and len(text) > 30:
            return str(div)
    return None


def extract_images(html: str) -> list[str]:
    """提取所有微信图片 URL（使用 BeautifulSoup 确保与后续处理一致）"""
    soup = BeautifulSoup(html, "lxml")
    seen = set()
    images = []
    for img in soup.find_all("img"):
        url = img.get("data-src") or img.get("src", "")
        if url and "qpic.cn" in url and url not in seen:
            seen.add(url)
            images.append(url)
    return images


# ============================================================
# Tier 2: Playwright 回退
# ============================================================
def fetch_with_playwright(url: str) -> str | None:
    """使用 Playwright 渲染后提取正文"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(3)
            html = page.content()
            browser.close()
            return extract_body_html(html)
    except Exception:
        return None


# ============================================================
# 图片下载
# ============================================================
def download_images(image_urls: list[str], att_dir: str) -> tuple[dict[str, str], int]:
    """批量下载图片，返回 (url_map, success_count)"""
    os.makedirs(att_dir, exist_ok=True)
    url_map = {}
    success = 0

    for idx, img_url in enumerate(image_urls, 1):
        ext = guess_extension(img_url)
        filename = f"image-{idx:04d}{ext}"
        filepath = os.path.join(att_dir, filename)

        for attempt in range(3):
            try:
                r = requests.get(img_url, headers=IMG_HEADERS, timeout=15)
                if r.status_code == 200:
                    with open(filepath, "wb") as f:
                        f.write(r.content)
                    url_map[img_url] = f"attachments/{filename}"
                    success += 1
                    print(f"      ✅ [{idx}/{len(image_urls)}] {filename} ({len(r.content):,} bytes)")
                    break
                elif attempt < 2:
                    time.sleep(1)
            except Exception:
                if attempt < 2:
                    time.sleep(1)
        else:
            print(f"      ⚠️  [{idx}] 下载失败，保留原始链接")
            url_map[img_url] = img_url

    return url_map, success


def download_one(img_url: str, save_path: str) -> bool:
    """下载单张图片"""
    try:
        r = requests.get(img_url, headers=IMG_HEADERS, timeout=15)
        if r.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(r.content)
            return True
    except Exception:
        pass
    return False


# ============================================================
# HTML → Markdown 转换
# ============================================================
def html_to_markdown(body_html: str, img_map: dict[str, str]) -> str:
    """将文章正文 HTML 转为干净 Markdown"""
    soup = BeautifulSoup(body_html, "lxml")

    for tag in soup.find_all(["script", "style"]):
        tag.decompose()

    # 替换图片：直接插入 Markdown 图片语法文本节点
    # （html2text 对复杂微信 HTML 中的 <img> 标签转换不稳定）
    for img in soup.find_all("img"):
        src = img.get("data-src") or img.get("src", "")
        local_src = img_map.get(src, src)
        alt = img.get("alt", "")
        md_img = f"\n![{alt}]({local_src})\n"
        img.insert_before(soup.new_string(md_img))
        img.decompose()

    # 微信特有结构 → 标准 HTML
    for tag in soup.find_all("section"):
        tag.name = "p"
    for tag in soup.find_all("span", leaf=True):
        tag.unwrap()
    for tag in soup.find_all([
        "mp-common-profile", "mp-style-type", "mp-common-product",
        "mp-common-poster", "mp-common-propmpt",
    ]):
        tag.decompose()

    clean_html = str(soup)

    conv = html2text.HTML2Text()
    conv.body_width = 0
    conv.ignore_links = False
    conv.ignore_images = False
    conv.unicode_snob = True
    conv.images_to_alt = False
    conv.single_line_break = False

    md = conv.handle(clean_html)
    md = md.replace('\r\n', '\n')
    md = re.sub(r'\n{3,}', '\n\n', md)
    return md.strip()


# ============================================================
# 单篇处理
# ============================================================
def process_article(url: str, output_dir: str) -> dict:
    """处理单篇文章，返回结果字典"""
    url = clean_url(url)
    result = {
        "success": False, "title": "", "file_path": "",
        "nickname": "", "published": "", "cover_path": None,
        "images_downloaded": 0, "images_total": 0, "error": None,
    }

    print(f"\n{'='*60}")
    print(f"📥 正在处理")
    print(f"  链接: {url[:80]}...")

    # --- Step 1: 获取 HTML ---
    html, error = fetch_html(url)
    if error:
        print(f"  ❌ {error}")
        result["error"] = error
        return result
    print(f"  ✅ HTML 获取成功 ({len(html):,} 字符)")

    # --- Step 2: 提取元数据 ---
    meta = extract_js_vars(html)
    title = meta.get("title", "未命名文章")
    nickname = meta.get("nickname") or meta.get("author", "")
    published = meta.get("published", "")
    cover_url = meta.get("cover_url", "")
    desc = meta.get("desc", "")
    print(f"  标题: {title}")
    if nickname:
        print(f"  公众号: {nickname}")
    if published:
        print(f"  日期: {published}")

    # --- Step 3: 提取正文 ---
    body_html = extract_body_html(html)
    has_body = body_html is not None

    if not has_body:
        print(f"  ⚠️  HTML 正文不完整，尝试 Playwright 回退...")
        body_html = fetch_with_playwright(url)
        has_body = body_html is not None

    if has_body:
        print(f"  ✅ 正文提取成功")
    else:
        print(f"  ⚠️  无法提取正文")

    # --- Step 4: 提取图片 ---
    all_images = []
    if body_html:
        all_images = extract_images(body_html)
    print(f"  🖼️  找到 {len(all_images)} 张图片")

    # --- Step 5: 创建目录 ---
    safe_name = sanitize_name(title)
    if not safe_name or safe_name == "未命名文章":
        safe_name = f"wechat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    article_dir = os.path.join(output_dir, safe_name)
    att_dir = os.path.join(article_dir, "attachments")
    os.makedirs(att_dir, exist_ok=True)

    # --- Step 6: 下载封面图 ---
    cover_path = None
    if cover_url:
        ext = guess_extension(cover_url)
        cover_file = f"cover{ext}"
        if download_one(cover_url, os.path.join(att_dir, cover_file)):
            cover_path = f"attachments/{cover_file}"
            print(f"  🖼️  封面已下载")

    # --- Step 7: 下载正文图片 ---
    img_map = {}
    dl_count = 0
    if all_images:
        print(f"  📥 下载图片中...")
        img_map, dl_count = download_images(all_images, att_dir)
        # 等待外部工具（如 Obsidian 插件）完成文件重命名
        time.sleep(2)
    print(f"     {dl_count}/{len(all_images)} 张下载成功")

    # --- Step 8: 正文转 Markdown ---
    body_md = ""
    if has_body and body_html:
        body_md = html_to_markdown(body_html, img_map)

    # --- Step 9: 构建 frontmatter ---
    lines = ["---"]
    lines.append(f'title: "{title}"')
    lines.append(f'source: "{url}"')
    if nickname:
        lines.append("author:")
        lines.append(f'  - "[[{nickname}]]"')
        lines.append(f'wechat_account: "{nickname}"')
    if published:
        lines.append(f'published: "{published}"')
    lines.append(f'date: "{datetime.now().strftime("%Y-%m-%d")}"')
    if cover_path:
        lines.append(f'cover: "{cover_path}"')
    if desc:
        lines.append(f'description: "{desc[:200]}"')
    lines.append("tags:")
    lines.append('  - "微信公众号"')
    lines.append('  - "clipper"')
    lines.append('  - "待整理"')
    lines.append("status: inbox")
    lines.append("---")
    lines.append("")

    if nickname or published:
        lines.append(f'*{" ".join(p for p in [nickname, published] if p)}*')
        lines.append("")
    if cover_path:
        lines.append(f"![]({cover_path})")
        lines.append("")
    lines.append(body_md)

    # --- Step 10: 写入文件 ---
    content = "\n".join(lines)
    md_path = os.path.join(article_dir, f"{safe_name}.md")
    with open(md_path, "w", encoding="utf-8-sig") as f:
        f.write(content)

    print(f"\n  ✅ 已保存!")
    print(f"  📁 {safe_name}/")
    print(f"  📄 {safe_name}.md")
    print(f"{'='*60}")

    result.update({
        "success": True,
        "title": title,
        "nickname": nickname,
        "published": published,
        "file_path": md_path,
        "cover_path": cover_path,
        "images_downloaded": dl_count,
        "images_total": len(all_images),
    })
    return result


# ============================================================
# 入口
# ============================================================
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    vault = DEFAULT_VAULT
    urls = []

    # 解析参数
    for arg in sys.argv[1:]:
        if arg.startswith("--vault="):
            vault = arg.split("=", 1)[1]
        elif arg == "--vault" and sys.argv.index(arg) + 1 < len(sys.argv):
            vault = sys.argv[sys.argv.index(arg) + 1]
        elif arg.startswith("http"):
            urls.append(arg)

    if not urls:
        print("❌ 请提供至少一个文章 URL")
        sys.exit(1)

    output_dir = os.path.join(vault, OUTPUT_SUBDIR)
    print(f"\n📚 共 {len(urls)} 篇文章")
    print(f"📂 保存到: {output_dir}")

    success_count = 0
    results = []

    for i, url in enumerate(urls, 1):
        result = process_article(url, output_dir)
        results.append(result)
        if result.get("success"):
            success_count += 1
        time.sleep(3)  # 微信限流：每篇文章间隔至少 3 秒

    # 汇总
    print(f"\n{'='*60}")
    print(f"📊 完成: {success_count}/{len(urls)} 篇成功")
    for i, r in enumerate(results, 1):
        mark = "✅" if r.get("success") else "❌"
        t = (r.get("title") or "失败")[:40]
        print(f"  {mark} [{i}] {t}")
    print(f"{'='*60}")

    sys.exit(0 if success_count == len(urls) else 1)


if __name__ == "__main__":
    main()
