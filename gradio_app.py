#!/usr/bin/env python3
"""
Gradio Web 界面
为爬虫项目提供友好的 Web 操作界面

功能包括：
- 爬取控制与监控
- 数据统计与可视化
- 链接管理与查询
- 文件浏览与下载

作者：AI助手
创建时间：2024
"""

import gradio as gr
import asyncio
import threading
import os
import time
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import queue
import json
import sys
from matplotlib import rcParams

# Matplotlib 中文显示与负号处理设置，避免图表中文字乱码与负号变成方块
# 优先使用常见的中文字体，按顺序回退；最后回退到 DejaVu Sans（覆盖不全但通用）
rcParams['font.sans-serif'] = [
    'Noto Sans CJK SC',      # Linux 常见
    'SimHei',                # 黑体（部分系统可用）
    'WenQuanYi Zen Hei',     # 文泉驿正黑（Linux 常见）
    'Microsoft YaHei',       # 微软雅黑（Windows）
    'Arial Unicode MS',      # 跨平台大字符集
    'DejaVu Sans'            # 兜底字体
]
rcParams['axes.unicode_minus'] = False

# 导入项目模块
from link_database import LinkDatabase
from ai_haodaifu import (
    _sanitize_filename, 
    url_to_file_paths, 
    extract_page_title_from_html,
    extract_page_title_from_markdown
)
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse
from docker_utils import is_docker_environment


def get_domain_without_www(domain: str) -> str:
    """获取域名的变体（不带www）
    例如：
    - 输入: 'www.taobao.com' -> 返回: 'taobao.com'
    - 输入: 'taobao.com' -> 返回: 'taobao.com'
    """
    if not domain:
        return ""
    
    domain_without_www = domain  # 原始域名
    
    if domain.startswith('www.'):
        # 如果域名以www开头，添加不带www的版本
        without_www = domain[4:]  # 移除'www.'
        domain_without_www = without_www
    
    return domain_without_www

class CrawlerManager:
    """爬虫管理器，处理异步爬虫操作"""
    
    def __init__(self):
        self.db = LinkDatabase()
        self.is_running = False
        self.current_task = None
        self.log_queue = queue.Queue()
        self.progress_callback = None
        self.log_history = []  # 存储历史日志
        self.max_log_history = 1000  # 最大保留日志条数
        self.log_file_path = os.path.join(os.path.dirname(__file__), "crawler_logs.txt")  # 日志文件路径
        
        # 启动时加载历史日志
        self.load_logs_from_file()
        # 清理过旧的日志文件
        self._cleanup_old_logs()
        
    def log_message(self, message: str):
        """记录日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        
        # 添加到队列（用于实时显示）
        self.log_queue.put(log_entry)
        
        # 添加到历史记录
        self.log_history.append(log_entry)
        
        # 限制历史记录长度
        if len(self.log_history) > self.max_log_history:
            self.log_history = self.log_history[-self.max_log_history:]
        
        # 写入日志文件
        self._write_log_to_file(log_entry)
        
        print(log_entry)  # 同时输出到控制台
    
    def _write_log_to_file(self, log_entry: str):
        """将日志写入文件"""
        try:
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(log_entry + '\n')
        except Exception as e:
            print(f"写入日志文件失败: {e}")
    
    def _cleanup_old_logs(self):
        """清理过旧的日志文件内容"""
        try:
            if os.path.exists(self.log_file_path):
                # 读取文件内容
                with open(self.log_file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # 如果文件过大（超过5000行），只保留最近的一半
                if len(lines) > 5000:
                    lines = lines[-2500:]
                    
                    # 重写文件
                    with open(self.log_file_path, 'w', encoding='utf-8') as f:
                        f.writelines(lines)
                        
        except Exception as e:
            print(f"清理日志文件失败: {e}")
        
    def set_progress_callback(self, callback):
        """设置进度回调函数"""
        self.progress_callback = callback
        
    def update_progress(self, current: int, total: int, message: str = ""):
        """更新进度"""
        if self.progress_callback:
            self.progress_callback(current, total, message)
            
    async def crawl_single_url(self, url: str, crawler: AsyncWebCrawler, link_filters: str = "", skip_processed_check: bool = False) -> Tuple[bool, List[str]]:
        """爬取单个 URL，返回 (是否成功, 新发现的链接列表)
        参数 skip_processed_check=True 时跳过“是否已处理过”的检查（用于起始 URL）。
        """
        try:
            # 检查是否已经处理过（起始URL可跳过）
            if not skip_processed_check and self.db.is_link_processed(url):
                self.log_message(f"🔍 链接已处理过，跳过: {url}")
                return True, []
            
            # 解析 URL 并准备保存路径
            output_root = os.path.join(os.path.dirname(__file__), "output")
            tmp_md_path, tmp_html_path = url_to_file_paths(output_root, url)
            os.makedirs(os.path.dirname(tmp_md_path), exist_ok=True)
            
            # 爬取页面
            page = await crawler.arun(url=url, config=CrawlerRunConfig())
            
            # 获取内容
            page_markdown = getattr(page, "markdown", None)
            page_html = getattr(page, "html", None) if hasattr(page, "html") else None
            
            # 提取页面标题
            title_from_html = extract_page_title_from_html(page_html or "")
            title_from_md = extract_page_title_from_markdown(page_markdown or "")
            filename_stem = title_from_html or title_from_md
            
            # 生成最终保存路径
            md_path, html_path = url_to_file_paths(output_root, url, filename_stem_override=filename_stem)
            
            # 保存内容
            if page_markdown:
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(page_markdown)
                self.log_message(f"🔍 已保存 Markdown → {os.path.basename(md_path)}")
                self.db.update_link_success(url, filename_stem, md_path, html_path, "markdown")
            elif page_html:
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(page_html)
                self.log_message(f"🔍 已保存 HTML → {os.path.basename(html_path)}")
                self.db.update_link_success(url, filename_stem, md_path, html_path, "html")
            else:
                # 保存占位内容
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(f"无法获取可保存的内容：{url}\n")
                self.log_message(f"🔍 内容为空，占位写入 → {os.path.basename(md_path)}")
                self.db.update_link_success(url, filename_stem, md_path, html_path, "placeholder")
            
            # 从当前页面提取新的链接
            new_links = []
            if page_markdown or page_html:
                self.log_message(f"🔍 正在从页面提取新链接...")
                extracted_links = self.extract_links_from_content(page_markdown or "", page_html or "")
                
                if extracted_links:
                    # 应用链接过滤（如果设置了过滤条件）
                    if link_filters and link_filters.strip():
                        original_count = len(extracted_links)
                        extracted_links = filter_links(extracted_links, link_filters)
                        filtered_count = len(extracted_links)
                        if original_count != filtered_count:
                            self.log_message(f"🔍 过滤后剩余 {filtered_count} 个新链接（过滤掉 {original_count - filtered_count} 个）")
                    
                    # 筛选出真正的新链接（未在数据库中存在）
                    for new_url in extracted_links:
                        if not self.db.is_link_exists(new_url):
                            new_links.append(new_url)
                    
                    if new_links:
                        self.log_message(f"🔍 对照数据库，发现 {filtered_count} -> {len(new_links)} 个链接")
                    else:
                        self.log_message(f"🔍 对照数据库，未发现新的链接")
                else:
                    self.log_message(f"🔍 页面中未发现链接")
            
            return True, new_links
            
        except Exception as e:
            error_msg = str(e)
            self.log_message(f"❌ 爬取失败：{url}")
            self.log_message(f"   原因：{error_msg}")
            self.db.update_link_failed(url, error_msg)
            return False, []
    
    def extract_links_from_content(self, markdown_text: str, html_text: str) -> List[str]:
        """从内容中提取链接"""
        all_links = []
        
        # 从 Markdown 提取链接
        if markdown_text:
            # 匹配 [text](url) 形式的链接
            pattern_md_link = re.compile(r"\[[^\]]*\]\((https?://[^\s)]+)\)")
            for m in pattern_md_link.finditer(markdown_text):
                url = m.group(1).split('#', 1)[0]  # 去掉片段标识符
                all_links.append(url)
            
            # 匹配裸露 URL
            pattern_bare_url = re.compile(r"(https?://[^\s)]+)")
            for m in pattern_bare_url.finditer(markdown_text):
                url = m.group(1).split('#', 1)[0]
                all_links.append(url)
        
        # 从 HTML 提取链接
        if html_text:
            soup = BeautifulSoup(html_text, "html.parser")
            for a in soup.find_all("a"):
                href = a.get("href")
                if href and isinstance(href, str):
                    if href.startswith("http://") or href.startswith("https://"):
                        url = href.split('#', 1)[0]
                        all_links.append(url)
        
        # 去重并保持顺序
        return list(dict.fromkeys(all_links))
    
    async def crawl_from_url(self, start_url: str, headless: bool = True, link_filters: str = "", max_depth: int = 3):
        """从起始 URL 开始递归爬取"""
        if self.is_running:
            self.log_message("爬虫已在运行中，请先停止当前任务")
            return
        
        self.is_running = True
        self.log_message(f"🚀 开始递归爬取任务")
        self.log_message(f"📍 起始URL: {start_url}")
        self.log_message(f"⚙️ 配置: 无头模式={headless}, 最大递归深度={max_depth}")
        
        try:
            # 配置浏览器
            self.log_message("🔧 正在初始化浏览器...")
            browser_cfg = BrowserConfig(headless=headless)
            
            async with AsyncWebCrawler(config=browser_cfg) as crawler:
                # 初始化爬取队列
                crawl_queue = []  # 待爬取链接队列
                processed_count = 0  # 已处理链接计数
                success_count = 0    # 成功爬取计数
                
                # 从数据库中获取待处理的链接
                pending_links = self.db.get_links_by_status('pending')
                for link in pending_links:
                    crawl_queue.append((link['url'], 0))
                
                # 将起始URL添加到队列并记录到数据库
                crawl_queue.append((start_url, 0))  # (url, depth)
                
                # 记录起始URL到数据库
                try:
                    self.db.record_link_discovered(start_url)
                except Exception as e:
                    self.log_message(f"记录起始URL到数据库时出错: {e}")
                self.log_message(f"📋 已将起始URL添加到爬取队列")
                
                # 开始递归爬取
                while crawl_queue and self.is_running:
                    self.log_message("---------------start-----------------")
                    # 从队列中取出一个链接
                    current_url, current_depth = crawl_queue.pop(0)
                    processed_count += 1
                    
                    self.log_message(f"📝 队列[{processed_count}] 正在处理 (深度{current_depth}): {current_url}")
                    self.update_progress(processed_count, processed_count + len(crawl_queue), f"正在处理: {current_url}")
                    
                    # 爬取当前链接
                    # 添加当前域名的变体（带www和不带www）
                    current_domain = urlparse(current_url).netloc
                    domain_variants = get_domain_without_www(current_domain)
                    if domain_variants not in link_filters:
                        link_filters = link_filters + "," + domain_variants
                    
                    self.log_message(f"🔍 链接过滤条件: {link_filters}")
                    
                    success, new_links = await self.crawl_single_url(
                        current_url,
                        crawler,
                        link_filters,
                        skip_processed_check=(current_depth == 0)
                    )

                    if success:
                        success_count += 1
                        self.log_message(f"✅ 队列[{processed_count}] 处理成功")
                        
                        # 如果还没达到最大深度，将新发现的链接添加到队列
                        if current_depth < max_depth and new_links:
                            # 将新链接添加到队列（深度+1）
                            added_count = 0
                            for new_url in new_links:
                                if not self.is_url_in_queue(crawl_queue, new_url):
                                    try:
                                        crawl_queue.append((new_url, current_depth + 1))
                                        self.db.record_link_discovered(new_url)
                                        self.log_message(f"🆕 队列[{processed_count}] 发现新链接: {new_url}")
                                    except Exception as e:
                                        self.log_message(f"记录新链接到数据库时出错: {e}")
                                    added_count += 1
                            
                            if added_count > 0:
                                self.log_message(f"🆕 {len(new_links)} 个新链接，已添加 {added_count} 入库，并添加到到队列中（深度 {current_depth + 1}）")
                        elif current_depth >= max_depth:
                            self.log_message(f"🛑 已达到最大递归深度 {max_depth}，不再继续深入")
                    else:
                        self.log_message(f"❌ 队列[{processed_count}] 处理失败")
                    
                    # 添加小延迟避免过于频繁的请求
                    await asyncio.sleep(0.5)
                    
                    # 显示当前队列状态
                    if len(crawl_queue) > 0:
                        self.log_message(f"📋 队列中还有 {len(crawl_queue)} 个链接待处理")
                    self.log_message("---------------- end ----------------")
                
                # 显示最终统计
                if not self.is_running:
                    self.log_message("⏹️ 爬取任务被用户停止")
                else:
                    self.log_message("🎉 递归爬取任务完成！")
                
                self.log_message(f"📊 队列统计: 成功 {success_count}/{processed_count}")
                stats = self.db.get_crawl_statistics()
                self.log_message(f"🗄️ 数据库统计 - 总计: {stats['total']}, 成功: {stats['success']}, 失败: {stats['failed']}")
                
        except Exception as e:
            self.log_message(f"💥 爬取过程中发生错误: {str(e)}")
        finally:
            self.is_running = False
            self.log_message("🏁 爬取任务结束")
    
    def is_url_in_queue(self, queue: List[Tuple[str, int]], url: str) -> bool:
        """检查URL是否已在队列中"""
        return any(queue_url == url for queue_url, _ in queue)
    
    def stop_crawling(self):
        """停止爬取"""
        if self.is_running:
            self.is_running = False
            self.log_message("正在停止爬取任务...")
            return "已发送停止信号"
        else:
            return "当前没有运行中的爬取任务"
    
    def get_logs(self) -> str:
        """获取日志内容"""
        # 获取队列中的新日志
        new_logs = []
        while not self.log_queue.empty():
            try:
                new_logs.append(self.log_queue.get_nowait())
            except queue.Empty:
                break
        
        # 如果没有新日志，返回历史日志
        if not new_logs and not self.log_history:
            return "[系统] 爬虫管理器已就绪"
        
        # 合并历史日志和新日志
        all_logs = self.log_history + new_logs
        
        # 返回最近500条日志
        return "\n".join(all_logs[-500:])
    
    def clear_logs(self):
        """清空日志历史"""
        self.log_history.clear()
        # 清空队列
        while not self.log_queue.empty():
            try:
                self.log_queue.get_nowait()
            except queue.Empty:
                break
        self.log_message("日志已清空")
    
    def load_logs_from_file(self):
        """从日志文件加载历史日志"""
        try:
            if os.path.exists(self.log_file_path):
                with open(self.log_file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # 加载最近的日志到历史记录
                recent_lines = lines[-self.max_log_history:] if len(lines) > self.max_log_history else lines
                self.log_history = [line.strip() for line in recent_lines if line.strip()]
                
        except Exception as e:
            print(f"加载日志文件失败: {e}")


# 全局爬虫管理器实例
crawler_manager = CrawlerManager()


def validate_url(url: str) -> str:
    """验证 URL 格式"""
    if not url or not url.strip():
        raise gr.Error("请输入 URL")
    
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        raise gr.Error("请输入有效的 URL（以 http:// 或 https:// 开头）")
    
    return url


def validate_link_filters(filter_text: str) -> str:
    """验证链接过滤条件"""
    if not filter_text or not filter_text.strip():
        return ""  # 空过滤条件有效
    
    # 检查是否包含特殊字符（可选，根据需要调整）
    keywords = [keyword.strip() for keyword in filter_text.split(',')]
    if any(len(keyword) == 0 for keyword in keywords):
        raise gr.Error("过滤关键词不能为空，请检查逗号分隔的格式")
    
    return filter_text.strip()


def filter_links(links: List[str], filter_text: str) -> List[str]:
    """根据包含字符过滤链接列表,支持逗号分隔的多个关键词"""
    if not filter_text or not filter_text.strip():
        return links  # 如果没有过滤条件，返回所有链接
    
    # 解析过滤条件（支持逗号分隔的多个关键词）
    keywords = [keyword.strip().lower() for keyword in filter_text.split(',') if keyword.strip()]
    
    filtered_links = []
    for link in links:
        link_lower = link.lower()
        # 检查链接是否包含任一关键词
        if all(keyword in link_lower for keyword in keywords):
            filtered_links.append(link)
    
    return filtered_links


def format_url_for_display(url: str, max_length: int = 80) -> str:
    """格式化URL用于显示，根据长度智能截断"""
    if not url:
        return ""
    
    url_length = len(url)
    
    # 如果URL长度小于等于最大长度，直接返回
    if url_length <= max_length:
        return url
    
    # 智能截断：保留协议、域名和路径的重要部分
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        
        # 构建基础部分（协议 + 域名）
        base = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path
        query = parsed.query
        fragment = parsed.fragment
        
        # 如果基础部分已经很长，直接截断
        if len(base) > max_length - 10:
            return url[:max_length-3] + "..."
        
        # 计算剩余可用长度
        remaining_length = max_length - len(base) - 3  # 3 for "..."
        
        # 如果有查询参数或片段，优先保留
        if query or fragment:
            # 保留路径的一部分和查询参数
            if len(path) > remaining_length // 2:
                path = path[:remaining_length//2] + "..."
            query_part = f"?{query}" if query else ""
            fragment_part = f"#{fragment}" if fragment else ""
            return base + path + query_part + fragment_part
        else:
            # 只有路径，智能截断
            if len(path) > remaining_length:
                # 尝试保留路径的开头和结尾
                if remaining_length > 20:
                    start_len = remaining_length // 2
                    end_len = remaining_length - start_len - 3
                    return base + path[:start_len] + "..." + path[-end_len:]
                else:
                    return base + path[:remaining_length] + "..."
            else:
                return base + path
                
    except Exception:
        # 如果解析失败，使用简单截断
        return url[:max_length-3] + "..."


def start_crawling(url: str, headless: bool, link_filters: str = "", max_depth: int = 10) -> Tuple[str, str]:
    """开始爬取"""
    try:
        # 验证输入参数
        validated_url = validate_url(url)
        validated_filters = validate_link_filters(link_filters)

        # 清空crawler_logs
        crawler_manager.clear_logs()
        crawler_manager.log_message("============ 开始爬取 ============")
        
        # 在后台线程中运行异步爬虫
        def run_crawler():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    crawler_manager.crawl_from_url(validated_url, headless, validated_filters, max_depth)
                )
            finally:
                loop.close()
        
        thread = threading.Thread(target=run_crawler)
        thread.daemon = True
        thread.start()
        
        return "递归爬取任务已启动", "正在初始化..."
        
    except gr.Error as e:
        return f"输入错误: {str(e)}", ""
    except Exception as e:
        return f"启动失败: {str(e)}", ""


def stop_crawling() -> str:
    """停止爬取"""
    return crawler_manager.stop_crawling()


def get_crawling_logs() -> str:
    """获取爬取日志"""
    return crawler_manager.get_logs()


def clear_crawling_logs() -> str:
    """清空爬取日志"""
    crawler_manager.clear_logs()
    return "日志已清空"


def get_buttons_state():
    """根据运行状态返回按钮可交互性设置"""
    running = crawler_manager.is_running
    # running=True: 禁用开始，启用停止；反之亦然
    start_update = gr.update(interactive=not running)
    stop_update = gr.update(interactive=running)
    return start_update, stop_update


def start_crawling_and_update_buttons(url: str, headless: bool, link_filters: str = "", max_depth: int = 10):
    """开始爬取并更新开始/停止按钮的可交互状态"""
    status_msg, logs_msg = start_crawling(url, headless, link_filters, max_depth)
    start_update, stop_update = get_buttons_state()
    return status_msg, logs_msg, start_update, stop_update


def stop_crawling_and_update_buttons():
    """停止爬取并更新开始/停止按钮的可交互状态"""
    status_msg = stop_crawling()
    start_update, stop_update = get_buttons_state()
    return status_msg, start_update, stop_update


def get_statistics() -> Tuple[int, int, int, int, float]:
    """获取统计信息"""
    stats = crawler_manager.db.get_crawl_statistics()
    success_rate = (stats['success'] / stats['total'] * 100) if stats['total'] > 0 else 0
    return (
        stats['total'],
        stats['success'],
        stats['failed'],
        stats['pending'],
        success_rate
    )


def get_links_by_status(status: str = None) -> pd.DataFrame:
    """根据状态获取链接列表，如果status为None、空字符串或'None'则获取所有链接"""
    # 如果status是字符串'None'，转换为None
    if status == 'None':
        status = None
    links = crawler_manager.db.get_links_by_status(status)
    if not links:
        return pd.DataFrame(columns=['URL', '标题', '状态', '发现时间', '抓取时间', '错误信息'])
    
    # 转换为 DataFrame
    data = []
    for link in links:
        # 使用智能URL格式化函数
        display_url = format_url_for_display(link['url'], max_length=100)
            
        data.append({
            'URL': display_url,
            '标题': link.get('title', '无'),
            '状态': link['status'],
            '发现时间': link['discovered_at'],
            '抓取时间': link.get('crawled_at', '未抓取'),
            '错误信息': link.get('error_message', '无')
        })
    
    return pd.DataFrame(data)


def search_links(query: str) -> pd.DataFrame:
    """搜索链接"""
    if not query or not query.strip():
        return get_links_by_status('success')  # 默认显示成功的链接
    
    # 简单的 URL 包含搜索
    all_links = crawler_manager.db.get_recent_links(1000)  # 获取最近1000个链接
    filtered_links = [link for link in all_links if query.lower() in link['url'].lower()]
    
    if not filtered_links:
        return pd.DataFrame(columns=['URL', '标题', '状态', '发现时间', '抓取时间', '错误信息'])
    
    # 转换为 DataFrame
    data = []
    for link in filtered_links:
        # 使用智能URL格式化函数
        display_url = format_url_for_display(link['url'], max_length=100)
            
        data.append({
            'URL': display_url,
            '标题': link.get('title', '无'),
            '状态': link['status'],
            '发现时间': link['discovered_at'],
            '抓取时间': link.get('crawled_at', '未抓取'),
            '错误信息': link.get('error_message', '无')
        })
    
    return pd.DataFrame(data)


def create_statistics_plot() -> plt.Figure:
    """创建统计图表"""
    stats = crawler_manager.db.get_crawl_statistics()
    
    # 创建饼图
    fig, ax = plt.subplots(figsize=(8, 6))
    
    if stats['total'] > 0:
        labels = ['成功', '失败', '待处理']
        sizes = [stats['success'], stats['failed'], stats['pending']]
        colors = ['#2ecc71', '#e74c3c', '#f39c12']
        
        # 过滤掉0值
        filtered_data = [(label, size, color) for label, size, color in zip(labels, sizes, colors) if size > 0]
        if filtered_data:
            labels, sizes, colors = zip(*filtered_data)
            
            wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
            
            # 美化文本
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')
    else:
        ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', fontsize=16)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
    
    ax.set_title('抓取状态分布', fontsize=16, fontweight='bold')
    plt.tight_layout()
    return fig


def get_output_files() -> List[str]:
    """获取输出文件列表"""
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    if not os.path.exists(output_dir):
        return []
    
    files = []
    for root, dirs, filenames in os.walk(output_dir):
        for filename in filenames:
            if filename.endswith(('.md', '.html')):
                rel_path = os.path.relpath(os.path.join(root, filename), output_dir)
                files.append(rel_path)
    
    return sorted(files)


def preview_file(file_path: str, preview_mode: str = "Markdown 渲染") -> str:
    """预览文件内容（不截断，完整显示，支持 Markdown 渲染和原始文本模式）"""
    if not file_path:
        return "请选择一个文件"
    
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    full_path = os.path.join(output_dir, file_path)
    
    if not os.path.exists(full_path):
        return "❌ 文件不存在"
    
    try:
        # 获取文件信息
        file_size = os.path.getsize(full_path)
        file_size_str = format_file_size(file_size)
        
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 添加文件信息头部
        file_info = f"📄 **文件信息**\n- 路径: `{file_path}`\n- 大小: {file_size_str}\n- 类型: {get_file_type(file_path)}\n- 模式: {preview_mode}\n\n---\n\n"
        
        # 如果是原始文本模式，直接返回原始内容
        if preview_mode == "原始文本":
            if file_path.endswith('.html'):
                return f"{file_info}```html\n{content}\n```"
            elif file_path.endswith('.md'):
                return f"{file_info}```markdown\n{content}\n```"
            else:
                return f"{file_info}```\n{content}\n```"
        
        # Markdown 渲染模式
        if file_path.endswith('.md'):
            # Markdown 文件处理，移除图片引用
            cleaned_content = remove_images_from_markdown(content)
            return file_info + cleaned_content
        elif file_path.endswith('.html'):
            # HTML 文件转换为 Markdown 格式
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, 'html.parser')
                
                # 提取标题
                title = soup.find('title')
                title_text = title.get_text().strip() if title else "无标题"
                
                # 提取主要内容
                main_content = soup.find('main') or soup.find('article') or soup.find('body')
                if main_content:
                    # 简单的 HTML 到 Markdown 转换
                    markdown_content = html_to_markdown_simple(main_content)
                else:
                    markdown_content = html_to_markdown_simple(soup)
                
                # 组合最终内容
                result = f"{file_info}# {title_text}\n\n{markdown_content}"
                return result
                
            except Exception as e:
                # 如果转换失败，返回原始 HTML 内容（用代码块包装）
                return f"{file_info}⚠️ HTML 转换失败，显示原始内容：\n\n```html\n{content}\n```"
        else:
            # 其他文件类型，用代码块包装
            return f"{file_info}```\n{content}\n```"
            
    except UnicodeDecodeError:
        return f"{file_info}❌ 文件编码错误，无法读取文本内容"
    except Exception as e:
        return f"❌ 读取文件失败: {str(e)}"


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def get_file_type(file_path: str) -> str:
    """获取文件类型描述"""
    if file_path.endswith('.md'):
        return "Markdown 文档"
    elif file_path.endswith('.html'):
        return "HTML 网页"
    elif file_path.endswith('.txt'):
        return "纯文本"
    else:
        return "未知类型"


def download_file(file_path: str) -> str:
    """下载文件功能（返回文件路径供 Gradio 下载）"""
    if not file_path:
        return None
    
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    full_path = os.path.join(output_dir, file_path)
    
    if not os.path.exists(full_path):
        return None
    
    return full_path


def remove_images_from_markdown(content: str) -> str:
    """从 Markdown 内容中移除图片引用，用文本替代"""
    import re
    
    # 匹配 Markdown 图片语法 ![alt](src "title")
    img_pattern = r'!\[([^\]]*)\]\(([^)]+)(?:\s+"([^"]*)")?\)'
    
    def replace_image(match):
        alt_text = match.group(1) if match.group(1) else ""
        src = match.group(2)
        title = match.group(3) if match.group(3) else ""
        
        if alt_text:
            return f"🖼️ [图片: {alt_text}]"
        elif title:
            return f"🖼️ [图片: {title}]"
        else:
            return f"🖼️ [图片: {src}]"
    
    # 替换所有图片引用
    cleaned_content = re.sub(img_pattern, replace_image, content)
    
    # 也处理 HTML 格式的图片标签（如果 Markdown 中包含）
    html_img_pattern = r'<img[^>]*alt=["\']([^"\']*)["\'][^>]*>'
    cleaned_content = re.sub(html_img_pattern, r'🖼️ [图片: \1]', cleaned_content)
    
    # 处理没有 alt 属性的 HTML 图片
    html_img_pattern_no_alt = r'<img[^>]*src=["\']([^"\']*)["\'][^>]*>'
    cleaned_content = re.sub(html_img_pattern_no_alt, r'🖼️ [图片: \1]', cleaned_content)
    
    return cleaned_content


def html_to_markdown_simple(element) -> str:
    """简单的 HTML 到 Markdown 转换（不渲染图片）"""
    if not element:
        return ""
    
    result = []
    
    for child in element.children:
        if hasattr(child, 'name') and child.name:
            tag_name = child.name.lower()
            text = child.get_text().strip()
            
            # 跳过图片标签，不渲染图片
            if tag_name == 'img':
                # 显示图片的替代文本或路径信息
                alt_text = child.get('alt', '')
                src = child.get('src', '')
                if alt_text:
                    result.append(f"🖼️ [图片: {alt_text}]")
                elif src:
                    result.append(f"🖼️ [图片: {src}]")
                else:
                    result.append("🖼️ [图片]")
                continue
            
            # 跳过其他媒体元素
            if tag_name in ['video', 'audio', 'iframe', 'embed', 'object']:
                result.append(f"📺 [媒体内容: {tag_name}]")
                continue
            
            if not text:  # 跳过空文本
                continue
                
            if tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                level = int(tag_name[1])
                result.append(f"{'#' * level} {text}")
            elif tag_name == 'p':
                result.append(f"{text}")
            elif tag_name == 'a':
                href = child.get('href', '')
                if href:
                    result.append(f"[{text}]({href})")
                else:
                    result.append(text)
            elif tag_name in ['strong', 'b']:
                result.append(f"**{text}**")
            elif tag_name in ['em', 'i']:
                result.append(f"*{text}*")
            elif tag_name == 'code':
                result.append(f"`{text}`")
            elif tag_name == 'pre':
                result.append(f"```\n{text}\n```")
            elif tag_name == 'ul':
                for li in child.find_all('li', recursive=False):
                    result.append(f"- {li.get_text().strip()}")
            elif tag_name == 'ol':
                for i, li in enumerate(child.find_all('li', recursive=False), 1):
                    result.append(f"{i}. {li.get_text().strip()}")
            elif tag_name == 'blockquote':
                result.append(f"> {text}")
            elif tag_name == 'hr':
                result.append("---")
            else:
                # 对于其他标签，递归处理子元素
                child_markdown = html_to_markdown_simple(child)
                if child_markdown:
                    result.append(child_markdown)
        else:
            # 处理文本节点
            text = str(child).strip()
            if text:
                result.append(text)
    
    return '\n\n'.join(result)


def retry_failed_links() -> str:
    """重新抓取失败的链接"""
    failed_links = crawler_manager.db.get_links_by_status('failed')
    if not failed_links:
        return "没有失败的链接需要重新抓取"
    
    # 重置失败链接的状态为待处理
    count = 0
    import sqlite3
    try:
        with sqlite3.connect(crawler_manager.db.db_path) as conn:
            cursor = conn.cursor()
            for link in failed_links:
                try:
                    cursor.execute("""
                        UPDATE crawled_links 
                        SET status = 'pending', error_message = NULL, crawled_at = NULL
                        WHERE url = ?
                    """, (link['url'],))
                    count += 1
                except Exception as e:
                    print(f"重置链接状态失败: {link['url']}, 错误: {e}")
            conn.commit()
    except Exception as e:
        return f"重置失败链接状态时发生错误: {str(e)}"
    
    return f"已重置 {count} 个失败链接的状态为待处理"


def clear_all_links(confirm: bool = False) -> str:
    """清空所有链接数据"""
    if not confirm:
        return "⚠️ 请确认是否要清空所有链接数据？此操作不可恢复！\n点击确认后再次点击清空按钮。"
    
    import sqlite3
    try:
        with sqlite3.connect(crawler_manager.db.db_path) as conn:
            cursor = conn.cursor()
            
            # 获取清空前的统计信息
            cursor.execute("SELECT COUNT(*) FROM crawled_links")
            total_count = cursor.fetchone()[0]
            
            if total_count == 0:
                return "数据库中没有链接数据需要清空"
            
            # 清空所有链接数据
            cursor.execute("DELETE FROM crawled_links")
            conn.commit()
            
            return f"✅ 已成功清空 {total_count} 条链接记录"
            
    except Exception as e:
        return f"❌ 清空链接数据时发生错误: {str(e)}"


def confirm_clear_links() -> str:
    """确认清空链接数据"""
    return clear_all_links(confirm=True)


def clear_all_files(confirm: bool = False) -> str:
    """清空所有输出文件"""
    if not confirm:
        return "⚠️ 请确认是否要清空所有输出文件？此操作不可恢复！\n点击确认后再次点击清空按钮。"
    
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    if not os.path.exists(output_dir):
        return "输出目录不存在，无需清空"
    
    try:
        import shutil
        
        # 获取清空前的文件统计
        file_count = 0
        total_size = 0
        
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                if file.endswith(('.md', '.html')):
                    file_path = os.path.join(root, file)
                    file_count += 1
                    total_size += os.path.getsize(file_path)
        
        if file_count == 0:
            return "输出目录中没有文件需要清空"
        
        # 清空输出目录
        shutil.rmtree(output_dir)
        os.makedirs(output_dir, exist_ok=True)
        
        # 格式化文件大小
        if total_size < 1024:
            size_str = f"{total_size} B"
        elif total_size < 1024 * 1024:
            size_str = f"{total_size / 1024:.1f} KB"
        else:
            size_str = f"{total_size / (1024 * 1024):.1f} MB"
        
        return f"✅ 已成功清空 {file_count} 个文件（总大小: {size_str}）"
        
    except Exception as e:
        return f"❌ 清空文件时发生错误: {str(e)}"


def confirm_clear_files() -> str:
    """确认清空文件数据"""
    return clear_all_files(confirm=True)


# 创建 Gradio 界面
def create_interface():
    """创建 Gradio 界面"""
    
    with gr.Blocks(
        theme=gr.themes.Soft(),
        title="智慧爬虫系统 - 让数据成为AI的核心动力",
        css="""

        .gradio-container {
            width: 1400px;
            max-width: 1400px !important;
            margin: 0 auto !important;
            padding: 20px !important;
        }
        .metric-container {
            text-align: center;
        }
        .main-container {
            display: flex;
            justify-content: center;
            align-items: flex-start;
            min-height: 100vh;
            padding: 20px;
        }
        .content-wrapper {
            width: 100%;
            max-width: 1400px;
            margin: 0 auto;
        }
        """
    ) as demo:
        
        gr.Markdown("# 🕷️ 智慧爬虫系统 - 让数据成为AI的核心动力")
        gr.Markdown("[Crawl4AI_PY](https://crawl4ai.renzhe.org) 基于 Crawl4AI 的智能网页爬虫，支持批量抓取、数据管理和文件浏览  [开源地址](https://github.com/zq535228/Crawl4AI_PY)")
        
        with gr.Tabs():
            # 爬取控制标签页
            with gr.Tab("🚀 爬取控制"):
                with gr.Row():
                    with gr.Column(scale=2):
                        gr.Markdown("### 爬取配置")
                        
                        url_input = gr.Textbox(
                            label="起始 URL",
                            placeholder="请输入要爬取的网页 URL，例如：https://example.com",
                            value="https://www.msdmanuals.cn/professional/infectious-diseases"
                        )
                        
                        link_filter_input = gr.Textbox(
                            label="链接包含字符过滤",
                            placeholder="输入关键词过滤链接，多个关键词用逗号分隔，例如：news,article,blog,professional/infectious-diseases",
                            value="/infectious-diseases"
                        )
                        
                        with gr.Row():
                            headless_checkbox = gr.Checkbox(
                                label="无头模式",
                                value=True,
                                info="勾选后浏览器将在后台运行，不显示界面"
                            )
                            
                            max_depth_slider = gr.Slider(
                                minimum=1,
                                maximum=10,
                                value=3,
                                step=1,
                                label="最大递归深度",
                                info="控制爬取的递归深度，避免无限递归"
                            )
                        
                        with gr.Row():
                            start_btn = gr.Button("🚀 开始爬取", variant="primary", size="lg")
                            stop_btn = gr.Button("⏹️ 停止爬取", variant="stop", size="lg")
                        
                        status_text = gr.Textbox(
                            label="状态",
                            value="就绪",
                            interactive=False
                        )
                    
                    with gr.Column(scale=1):
                        gr.Markdown("### 实时统计")
                        
                        with gr.Row():
                            total_metric = gr.Number(label="总链接数", value=0, precision=0)
                            success_metric = gr.Number(label="成功数", value=0, precision=0)
                        
                        with gr.Row():
                            failed_metric = gr.Number(label="失败数", value=0, precision=0)
                            pending_metric = gr.Number(label="待处理", value=0, precision=0)
                        
                        success_rate_metric = gr.Number(label="成功率(%)", value=0, precision=1)
                        
                        refresh_stats_btn = gr.Button("🔄 刷新统计", size="sm")
                        clear_logs_btn = gr.Button("🗑️ 清空日志", variant="secondary", size="sm")
                
                gr.Markdown("### 实时日志")
                logs_output = gr.Textbox(
                    label="爬取日志",
                    lines=15,
                    max_lines=30,
                    interactive=False,
                    show_copy_button=True,
                    autoscroll=True  # 自动滚动到底部
                )
                
                # 事件绑定
                start_btn.click(
                    fn=start_crawling_and_update_buttons,
                    inputs=[url_input, headless_checkbox, link_filter_input, max_depth_slider],
                    outputs=[status_text, logs_output, start_btn, stop_btn]
                )
                
                stop_btn.click(
                    fn=stop_crawling_and_update_buttons,
                    outputs=[status_text, start_btn, stop_btn]
                )
                
                refresh_stats_btn.click(
                    fn=get_statistics,
                    outputs=[total_metric, success_metric, failed_metric, pending_metric, success_rate_metric]
                )
                
                clear_logs_btn.click(
                    fn=clear_crawling_logs,
                    outputs=[logs_output]
                )
                
                # 实时日志更新功能
                def update_logs_stats_and_buttons():
                    """更新日志、统计与按钮可交互状态"""
                    logs = get_crawling_logs()
                    stats = get_statistics()
                    start_update, stop_update = get_buttons_state()
                    return (
                        logs,
                        stats[0], stats[1], stats[2], stats[3], stats[4],
                        start_update, stop_update
                    )
                
                # 使用定时器组件实现实时更新
                timer = gr.Timer(value=2)  # 每2秒更新一次
                timer.tick(
                    fn=update_logs_stats_and_buttons,
                    outputs=[
                        logs_output, total_metric, success_metric, failed_metric, pending_metric, success_rate_metric,
                        start_btn, stop_btn
                    ]
                )
                # 页面加载时初始化按钮交互状态
                demo.load(
                    fn=get_buttons_state,
                    outputs=[start_btn, stop_btn]
                )

            # 数据统计标签页
            with gr.Tab("📊 数据统计"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 统计概览")
                        
                        stats_total = gr.Number(label="总链接数", value=0, precision=0)
                        stats_success = gr.Number(label="成功数", value=0, precision=0)
                        stats_failed = gr.Number(label="失败数", value=0, precision=0)
                        stats_pending = gr.Number(label="待处理", value=0, precision=0)
                        stats_rate = gr.Number(label="成功率(%)", value=0, precision=1)
                        
                        refresh_stats_btn2 = gr.Button("🔄 刷新统计", variant="secondary")
                    
                    with gr.Column(scale=2):
                        gr.Markdown("### 状态分布图")
                        plot_output = gr.Plot(label="抓取状态分布")
                
                gr.Markdown("### 最近抓取的链接")
                recent_links_df = gr.Dataframe(
                    label="最近链接",
                    headers=['URL', '标题', '状态', '发现时间', '抓取时间', '错误信息'],
                    interactive=True,
                    wrap=False,
                    column_widths=[900, 250, 100, 180, 180, 300],
                    datatype=["str", "str", "str", "str", "str", "str"],
                    max_height=1000
                )
                
                # 事件绑定
                refresh_stats_btn2.click(
                    fn=get_statistics,
                    outputs=[stats_total, stats_success, stats_failed, stats_pending, stats_rate]
                )
                
                refresh_stats_btn2.click(
                    fn=create_statistics_plot,
                    outputs=[plot_output]
                )
                
                refresh_stats_btn2.click(
                    fn=lambda: get_links_by_status('success'),
                    outputs=[recent_links_df]
                )
                
                # 页面加载时自动刷新
                demo.load(
                    fn=get_statistics,
                    outputs=[stats_total, stats_success, stats_failed, stats_pending, stats_rate]
                )
                
                demo.load(
                    fn=create_statistics_plot,
                    outputs=[plot_output]
                )
                
                demo.load(
                    fn=lambda: get_links_by_status('success'),
                    outputs=[recent_links_df]
                )
            
            # 链接管理标签页
            with gr.Tab("🔗 链接管理"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 筛选和搜索")
                        
                        status_filter = gr.Dropdown(
                            choices=['None', 'pending', 'success', 'failed'],
                            value='None',
                            label="按状态筛选",
                            info="选择要查看的链接状态"
                        )
                        
                        search_input = gr.Textbox(
                            label="搜索 URL",
                            placeholder="输入关键词搜索链接...",
                            info="支持 URL 模糊搜索"
                        )
                        
                        with gr.Row():
                            search_btn = gr.Button("🔍 搜索", variant="primary")
                            retry_btn = gr.Button("🔄 重试失败链接", variant="secondary")
                        
                        with gr.Row():
                            clear_btn = gr.Button("🗑️ 清空所有链接", variant="stop", size="sm")
                            confirm_clear_btn = gr.Button("✅ 确认清空", variant="stop", size="sm", visible=False)
                    
                    with gr.Column(scale=1):
                        gr.Markdown("### 操作结果")
                        operation_result = gr.Textbox(
                            label="操作结果",
                            interactive=False,
                            lines=3
                        )
                
                gr.Markdown("### 链接列表")
                links_df = gr.Dataframe(
                    label="链接列表",
                    headers=['URL', '标题', '状态', '发现时间', '抓取时间', '错误信息'],
                    interactive=True,
                    wrap=False,
                    column_widths=[900, 250, 100, 180, 180, 300],
                    datatype=["str", "str", "str", "str", "str", "str"],
                    max_height=1000
                )
                
                # 事件绑定
                status_filter.change(
                    fn=get_links_by_status,
                    inputs=[status_filter],
                    outputs=[links_df]
                )
                
                search_btn.click(
                    fn=search_links,
                    inputs=[search_input],
                    outputs=[links_df]
                )
                
                retry_btn.click(
                    fn=retry_failed_links,
                    outputs=[operation_result]
                )
                
                def show_confirm_clear():
                    """显示确认清空按钮"""
                    return gr.update(visible=True)
                
                def hide_confirm_clear():
                    """隐藏确认清空按钮"""
                    return gr.update(visible=False)
                
                clear_btn.click(
                    fn=clear_all_links,
                    outputs=[operation_result]
                ).then(
                    fn=show_confirm_clear,
                    outputs=[confirm_clear_btn]
                )
                
                confirm_clear_btn.click(
                    fn=confirm_clear_links,
                    outputs=[operation_result]
                ).then(
                    fn=hide_confirm_clear,
                    outputs=[confirm_clear_btn]
                )
                
                # 页面加载时显示所有链接
                demo.load(
                    fn=lambda: get_links_by_status(),
                    outputs=[links_df]
                )
            
            # 文件浏览标签页
            with gr.Tab("📁 文件浏览"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 文件列表")
                        
                        file_list = gr.Dropdown(
                            choices=get_output_files(),
                            label="选择文件",
                            info="选择要预览的文件"
                        )
                        
                        with gr.Row():
                            refresh_files_btn = gr.Button("🔄 刷新文件列表", size="sm")
                            download_file_btn = gr.Button("📥 下载文件", size="sm", variant="secondary")
                            clear_files_btn = gr.Button("🗑️ 清空所有文件", variant="stop", size="sm")
                            confirm_clear_files_btn = gr.Button("✅ 确认清空", variant="stop", size="sm", visible=False)
                    
                    with gr.Column(scale=2):
                        gr.Markdown("### 文件预览")
                        
                        # 添加预览模式选择
                        preview_mode = gr.Radio(
                            choices=["Markdown 渲染", "原始文本"],
                            value="Markdown 渲染",
                            label="预览模式",
                            info="选择文件内容的显示方式"
                        )
                        
                        file_preview = gr.Markdown(
                            label="文件内容",
                            value="请选择一个文件进行预览",
                            show_copy_button=True
                        )
                        
                        gr.Markdown("### 操作结果")
                        file_operation_result = gr.Textbox(
                            label="操作结果",
                            interactive=False,
                            lines=3
                        )
                
                # 事件绑定
                def update_preview(file_path, mode):
                    """更新文件预览"""
                    return preview_file(file_path, mode)
                
                file_list.change(
                    fn=update_preview,
                    inputs=[file_list, preview_mode],
                    outputs=[file_preview]
                )
                
                preview_mode.change(
                    fn=update_preview,
                    inputs=[file_list, preview_mode],
                    outputs=[file_preview]
                )
                
                def refresh_file_list():
                    """刷新文件列表"""
                    files = get_output_files()
                    return gr.update(choices=files, value=None)
                
                def show_confirm_clear_files():
                    """显示确认清空文件按钮"""
                    return gr.update(visible=True)
                
                def hide_confirm_clear_files():
                    """隐藏确认清空文件按钮"""
                    return gr.update(visible=False)
                
                refresh_files_btn.click(
                    fn=refresh_file_list,
                    outputs=[file_list]
                )
                
                download_file_btn.click(
                    fn=download_file,
                    inputs=[file_list],
                    outputs=gr.File(label="下载文件")
                )
                
                clear_files_btn.click(
                    fn=clear_all_files,
                    outputs=[file_operation_result]
                ).then(
                    fn=show_confirm_clear_files,
                    outputs=[confirm_clear_files_btn]
                )
                
                confirm_clear_files_btn.click(
                    fn=confirm_clear_files,
                    outputs=[file_operation_result]
                ).then(
                    fn=hide_confirm_clear_files,
                    outputs=[confirm_clear_files_btn]
                ).then(
                    fn=refresh_file_list,
                    outputs=[file_list]
                )
                
                # 页面加载时获取文件列表
                demo.load(
                    fn=refresh_file_list,
                    outputs=[file_list]
                )
    
    return demo




def main():
    """主函数"""
    print("正在启动爬虫管理系统...")
    
    # 创建界面
    demo = create_interface()

    # 端口配置逻辑
    # 检测是否在 Docker 环境中运行（使用导入的函数）
    
    # 根据运行环境选择端口
    if is_docker_environment():
        server_port = 7861
        print("🐳 检测到 Docker 环境，使用端口: 7861")
    else:
        server_port = 7862
        print("💻 检测到本地环境，使用端口: 7862")
    
    # 启动应用
    try:
        demo.launch(
            server_name="0.0.0.0",  # 允许外部访问
            server_port=server_port,       # 使用不同端口避免冲突
            share=False,            # 不创建公共链接
            debug=True,             # 开启调试模式
            show_error=True,        # 显示错误信息
            quiet=False             # 显示启动信息
        )
    except KeyboardInterrupt:
        print("\n👋 应用程序已停止")


if __name__ == "__main__":
    main()
