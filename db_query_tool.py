#!/usr/bin/env python3
"""
数据库查询工具

用于查看和管理爬取链接的数据库记录
提供命令行界面来查询统计信息、查看链接状态等

使用方法:
    python3 db_query_tool.py stats          # 查看统计信息
    python3 db_query_tool.py pending        # 查看待处理链接
    python3 db_query_tool.py failed         # 查看失败链接
    python3 db_query_tool.py recent [数量]   # 查看最近链接
    python3 db_query_tool.py search <URL>   # 搜索特定链接

作者：AI助手
创建时间：2024
"""

import sys
import argparse
from link_database import LinkDatabase


def print_stats(db: LinkDatabase):
    """打印统计信息"""
    stats = db.get_crawl_statistics()
    print("\n=== 抓取统计信息 ===")
    print(f"总计链接: {stats['total']}")
    print(f"待处理: {stats['pending']}")
    print(f"成功: {stats['success']}")
    print(f"失败: {stats['failed']}")
    
    if stats['total'] > 0:
        success_rate = (stats['success'] / stats['total']) * 100
        print(f"成功率: {success_rate:.1f}%")
    print("=" * 25)


def print_links(links, title: str, max_display: int = 10):
    """打印链接列表"""
    if not links:
        print(f"\n{title}: 无记录")
        return
    
    print(f"\n{title} ({len(links)} 个):")
    print("-" * 50)
    
    for i, link in enumerate(links[:max_display], 1):
        print(f"{i}. {link['url']}")
        if link.get('title'):
            print(f"   标题: {link['title']}")
        if link.get('status') == 'failed' and link.get('error_message'):
            print(f"   错误: {link['error_message']}")
        if link.get('crawled_at'):
            print(f"   抓取时间: {link['crawled_at']}")
        print()
    
    if len(links) > max_display:
        print(f"... 还有 {len(links) - max_display} 个链接未显示")


def search_link(db: LinkDatabase, url: str):
    """搜索特定链接"""
    try:
        import sqlite3
        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM crawled_links 
                WHERE url = ?
            """, (url,))
            result = cursor.fetchone()
            
            if result:
                link = dict(result)
                print(f"\n找到链接: {link['url']}")
                print("-" * 50)
                print(f"标题: {link.get('title', '无')}")
                print(f"状态: {link['status']}")
                print(f"发现时间: {link['discovered_at']}")
                if link.get('crawled_at'):
                    print(f"抓取时间: {link['crawled_at']}")
                if link.get('error_message'):
                    print(f"错误信息: {link['error_message']}")
                if link.get('markdown_path'):
                    print(f"Markdown路径: {link['markdown_path']}")
                if link.get('html_path'):
                    print(f"HTML路径: {link['html_path']}")
                print(f"文件大小: {link.get('file_size', 0)} 字节")
                print(f"内容类型: {link.get('content_type', '未知')}")
            else:
                print(f"\n未找到链接: {url}")
    except Exception as e:
        print(f"搜索失败: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="数据库查询工具 - 查看和管理爬取链接记录",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python3 db_query_tool.py stats          # 查看统计信息
  python3 db_query_tool.py pending        # 查看待处理链接
  python3 db_query_tool.py failed         # 查看失败链接
  python3 db_query_tool.py recent 20      # 查看最近20个链接
  python3 db_query_tool.py search "https://example.com"  # 搜索特定链接
        """
    )
    
    parser.add_argument('command', 
                       choices=['stats', 'pending', 'failed', 'recent', 'search'],
                       help='要执行的命令')
    parser.add_argument('arg', nargs='?', 
                       help='命令参数（如数量或URL）')
    parser.add_argument('--db', default='crawl_links.db',
                       help='数据库文件路径（默认: crawl_links.db）')
    
    args = parser.parse_args()
    
    # 初始化数据库
    try:
        db = LinkDatabase(args.db)
    except Exception as e:
        print(f"无法连接数据库 {args.db}: {e}")
        sys.exit(1)
    
    # 执行命令
    if args.command == 'stats':
        print_stats(db)
    
    elif args.command == 'pending':
        links = db.get_links_by_status('pending')
        print_links(links, "待处理链接")
    
    elif args.command == 'failed':
        links = db.get_links_by_status('failed')
        print_links(links, "失败链接", max_display=20)
    
    elif args.command == 'recent':
        limit = 10
        if args.arg:
            try:
                limit = int(args.arg)
            except ValueError:
                print("错误: 数量必须是整数")
                sys.exit(1)
        links = db.get_recent_links(limit)
        print_links(links, f"最近 {limit} 个链接")
    
    elif args.command == 'search':
        if not args.arg:
            print("错误: 搜索命令需要提供URL参数")
            sys.exit(1)
        search_link(db, args.arg)


if __name__ == "__main__":
    main()
