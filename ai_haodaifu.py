from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler,CrawlerRunConfig,BrowserConfig
import asyncio
import re
import os
from urllib.parse import urlparse
from link_database import LinkDatabase


def _sanitize_filename(name: str) -> str:
    """将任意字符串清洗为适合文件名的形式。
    - 去掉不安全字符，如 \/:*?"<>| 和控制字符
    - 将空字符串回退为下划线
    """
    unsafe_chars = "\\/:*?\"<>|\n\r\t"
    sanitized = ''.join('_' if ch in unsafe_chars else ch for ch in name)
    sanitized = sanitized.strip()
    return sanitized or "_"


def url_to_file_paths(base_dir: str, target_url: str, filename_stem_override: str | None = None):
    """根据 URL 生成建议的保存路径（含 markdown 与 html 两个候选）。

    规则（尽量直观、便于新手理解）：
    - 根目录为 base_dir
    - 一级目录为域名 host，如 example.com
    - 子目录按 URL 路径逐级展开
    - 若 URL 以 / 结尾或路径为空，则使用 index 作为文件名
    - 否则使用路径最后一段作为文件名
    - 最终给出两个候选文件（.md 与 .html）
    """
    parsed = urlparse(target_url)
    host = _sanitize_filename(parsed.netloc or "unknown-host")

    # 拆分路径，忽略多余的空段
    raw_segments = [seg for seg in (parsed.path or '').split('/') if seg]
    safe_segments = [_sanitize_filename(seg) for seg in raw_segments]

    # 目录路径：base_dir/host/<segments...>
    dir_path = os.path.join(base_dir, host, *safe_segments[:-1]) if len(safe_segments) > 1 else os.path.join(base_dir, host)

    # 文件名：最后一段；若没有段或以 / 结尾，则用 index
    if not safe_segments:
        filename_stem = "index"
    else:
        last = safe_segments[-1]
        filename_stem = last if last else "index"

    # 若提供了覆盖文件名（例如用页面标题），则以该名称为准
    if filename_stem_override:
        filename_stem = _sanitize_filename(filename_stem_override)

    md_path = os.path.join(dir_path, f"{filename_stem}.md")
    html_path = os.path.join(dir_path, f"{filename_stem}.html")
    return md_path, html_path


def extract_page_title_from_html(html_text: str) -> str | None:
    """从 HTML 中提取页面标题（主题）。
    优先顺序：
    1) 第一个 <h1> 文本
    2) <title> 标签
    取到后去掉首尾空白。
    """
    if not html_text:
        return None
    soup = BeautifulSoup(html_text, "html.parser")
    # 1) 第一个 <h1>
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
        if title:
            return title
    # 2) <title>
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        if title:
            return title
    return None


def extract_page_title_from_markdown(md_text: str) -> str | None:
    """从 Markdown 文本中提取首个一级/二级标题。
    匹配以 # 或 ## 开头的标题行。
    """
    if not md_text:
        return None
    for line in md_text.splitlines():
        s = line.strip()
        if s.startswith("# ") or s.startswith("## "):
            return s.lstrip('#').strip()
    return None


async def main():
    # 初始化数据库
    db = LinkDatabase()
    print("数据库初始化完成")
    
    # 使用 AsyncWebCrawler 异步爬虫
    browser_cfg = BrowserConfig(
        headless=True,  # 是否无头模式；新手建议先开可视化便于观察
    )

    async with AsyncWebCrawler(config=browser_cfg) as crawl:
        # 发起一次爬取任务
        result = await crawl.arun(
            url="https://www.msdmanuals.cn/professional/infectious-diseases",
            config=CrawlerRunConfig(
            )
        )
        # print(result.markdown)
        # 获取所有链接（从 markdown 与 html 提取），并进行去重与打印

        # 1) 从 markdown 文本中提取链接
        def extract_links_from_markdown(md_text: str):
            """从 markdown 文本中提取链接：
            - 匹配 [可见文本](https://example.com)
            - 也匹配裸露 URL，如 https://example.com
            """
            if not md_text:
                return []

            links = []

            def drop_fragment(u: str) -> str:
                """去掉 URL 中的片段标识符（# 及其后内容）"""
                return u.split('#', 1)[0]

            # a. 匹配 [text](url) 形式的链接
            pattern_md_link = re.compile(r"\[[^\]]*\]\((https?://[^\s)]+)\)")
            for m in pattern_md_link.finditer(md_text):
                links.append(drop_fragment(m.group(1)))

            # b. 匹配裸露 URL（http/https 开头）
            pattern_bare_url = re.compile(r"(https?://[^\s)]+)")
            for m in pattern_bare_url.finditer(md_text):
                links.append(drop_fragment(m.group(1)))

            return links

        # 2) 从 HTML 中提取 <a href="...">
        def extract_links_from_html(html_text: str):
            """从 HTML 的 a 标签中提取 href，仅保留 http/https 绝对链接"""
            if not html_text:
                return []
            soup = BeautifulSoup(html_text, "html.parser")
            hrefs = []

            def drop_fragment(u: str) -> str:
                """去掉 URL 中的片段标识符（# 及其后内容）"""
                return u.split('#', 1)[0]
            for a in soup.find_all("a"):
                href = a.get("href")
                if href and isinstance(href, str):
                    if href.startswith("http://") or href.startswith("https://"):
                        hrefs.append(drop_fragment(href))
            return hrefs

        markdown_text = getattr(result, "markdown", "")
        html_text = getattr(result, "html", "") if hasattr(result, "html") else ""

        all_links = []
        all_links.extend(extract_links_from_markdown(markdown_text))
        all_links.extend(extract_links_from_html(html_text))

        # 去重并保持顺序
        deduped_links = list(dict.fromkeys(all_links))

        print("\n共提取到链接数量:", len(deduped_links))
        
        # 记录所有发现的链接到数据库
        for url in deduped_links:
            db.record_link_discovered(url)
        
        # 显示抓取前的统计信息
        print("\n开始抓取前的统计信息:")
        db.print_statistics()
        
        for idx, url in enumerate(deduped_links, start=1):
            print(f"\n{idx}. 处理链接: {url}")
            
            # 检查是否已经处理过
            if db.is_link_processed(url):
                print(f"  链接已处理过，跳过: {url}")
                continue
            
            # 解析url，并保存到目录中
            try:
                # 目标根目录（可根据需要自定义）。建议使用项目内的 output 目录
                output_root = os.path.join(os.path.dirname(__file__), "output")

                # 确保目录存在
                # 先构造一个占位路径，用于提前创建目录（若必要）。
                tmp_md_path, tmp_html_path = url_to_file_paths(output_root, url)
                os.makedirs(os.path.dirname(tmp_md_path), exist_ok=True)

                # 使用同一个 crawler 实例请求该链接
                page = await crawl.arun(url=url, config=CrawlerRunConfig())

                # 优先获取 markdown；若无则备选 html；若都没有则保存纯文本占位
                page_markdown = getattr(page, "markdown", None)
                page_html = getattr(page, "html", None) if hasattr(page, "html") else None

                # 提取页面标题，作为文件名（主题）
                title_from_html = extract_page_title_from_html(page_html or "")
                title_from_md = extract_page_title_from_markdown(page_markdown or "")
                filename_stem = title_from_html or title_from_md

                # 使用标题作为文件名生成最终保存路径；若没有标题，则退回 URL 文件名
                md_path, html_path = url_to_file_paths(output_root, url, filename_stem_override=filename_stem)

                if page_markdown:
                    with open(md_path, "w", encoding="utf-8") as f:
                        f.write(page_markdown)
                    print(f"  已保存 Markdown → {md_path}")
                    # 更新数据库状态为成功
                    db.update_link_success(url, filename_stem, md_path, html_path, "markdown")
                elif page_html:
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(page_html)
                    print(f"  已保存 HTML → {html_path}")
                    # 更新数据库状态为成功
                    db.update_link_success(url, filename_stem, md_path, html_path, "html")
                else:
                    # 两者都没有时，至少写入占位内容，便于排查
                    with open(md_path, "w", encoding="utf-8") as f:
                        f.write(f"无法获取可保存的内容：{url}\n")
                    print(f"  内容为空，占位写入 → {md_path}")
                    # 更新数据库状态为成功（占位内容也算成功）
                    db.update_link_success(url, filename_stem, md_path, html_path, "placeholder")

            except Exception as e:
                # 单个链接失败不影响其他链接的保存
                error_msg = str(e)
                print(f"  保存失败：{url}，原因：{error_msg}")
                # 更新数据库状态为失败
                db.update_link_failed(url, error_msg)
        
        # 显示最终统计信息
        print("\n" + "="*50)
        print("抓取完成！最终统计信息:")
        db.print_statistics()
        
        # 显示失败的链接（如果有）
        failed_links = db.get_links_by_status('failed')
        if failed_links:
            print(f"\n失败的链接 ({len(failed_links)} 个):")
            for link in failed_links[:5]:  # 只显示前5个
                print(f"  - {link['url']}: {link['error_message']}")
            if len(failed_links) > 5:
                print(f"  ... 还有 {len(failed_links) - 5} 个失败链接")


if __name__ == "__main__":
    asyncio.run(main())