"""
链接状态数据库管理模块

使用 SQLite 数据库记录所有获取到的链接状态，包括：
- 链接发现时间
- 抓取状态（成功/失败/待处理）
- 抓取时间
- 错误信息
- 文件保存路径

作者：AI助手
创建时间：2024
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple


class LinkDatabase:
    """链接状态数据库管理类"""
    
    def __init__(self, db_path: str = "crawl_links.db"):
        """
        初始化数据库连接
        
        Args:
            db_path: 数据库文件路径，默认为项目根目录下的 crawl_links.db
        """
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """初始化数据库，创建表结构（如果不存在）"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 创建 crawled_links 表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS crawled_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,                    -- 链接URL
                    title TEXT,                                  -- 页面标题
                    status TEXT NOT NULL DEFAULT 'pending',      -- 状态：pending/success/failed
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 发现时间
                    crawled_at TIMESTAMP,                        -- 抓取时间
                    error_message TEXT,                          -- 错误信息（如果有）
                    markdown_path TEXT,                          -- Markdown文件保存路径
                    html_path TEXT,                              -- HTML文件保存路径
                    file_size INTEGER,                           -- 文件大小（字节）
                    content_type TEXT                            -- 内容类型：markdown/html/placeholder
                )
            """)
            
            # 创建索引以提高查询性能
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_url ON crawled_links(url)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_status ON crawled_links(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_discovered_at ON crawled_links(discovered_at)
            """)
            
            conn.commit()
    
    def record_link_discovered(self, url: str, title: Optional[str] = None) -> bool:
        """
        记录新发现的链接
        
        Args:
            url: 链接URL
            title: 页面标题（可选）
            
        Returns:
            bool: 是否成功记录（如果链接已存在则返回False）
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO crawled_links (url, title, status)
                    VALUES (?, ?, 'pending')
                """, (url, title))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"记录链接失败：{url}，错误：{e}")
            return False
    
    def update_link_success(self, url: str, title: Optional[str] = None, 
                          markdown_path: Optional[str] = None, 
                          html_path: Optional[str] = None,
                          content_type: str = "markdown") -> bool:
        """
        更新链接抓取成功状态
        
        Args:
            url: 链接URL
            title: 页面标题
            markdown_path: Markdown文件路径
            html_path: HTML文件路径
            content_type: 内容类型（markdown/html/placeholder）
            
        Returns:
            bool: 是否成功更新
        """
        try:
            # 计算文件大小
            file_size = 0
            if markdown_path and os.path.exists(markdown_path):
                file_size = os.path.getsize(markdown_path)
            elif html_path and os.path.exists(html_path):
                file_size = os.path.getsize(html_path)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE crawled_links 
                    SET status = 'success', 
                        title = COALESCE(?, title),
                        crawled_at = CURRENT_TIMESTAMP,
                        markdown_path = ?,
                        html_path = ?,
                        file_size = ?,
                        content_type = ?,
                        error_message = NULL
                    WHERE url = ?
                """, (title, markdown_path, html_path, file_size, content_type, url))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"更新链接成功状态失败：{url}，错误：{e}")
            return False
    
    def update_link_failed(self, url: str, error_message: str) -> bool:
        """
        更新链接抓取失败状态
        
        Args:
            url: 链接URL
            error_message: 错误信息
            
        Returns:
            bool: 是否成功更新
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE crawled_links 
                    SET status = 'failed', 
                        crawled_at = CURRENT_TIMESTAMP,
                        error_message = ?
                    WHERE url = ?
                """, (error_message, url))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"更新链接失败状态失败：{url}，错误：{e}")
            return False
    
    def get_links_by_status(self, status: str = None) -> List[Dict]:
        """
        根据状态获取链接列表
        
        Args:
            status: 状态（pending/success/failed），如果为None或空字符串则获取所有链接
            
        Returns:
            List[Dict]: 链接信息列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row  # 使结果可以按列名访问
                cursor = conn.cursor()
                
                # 如果status为None或空字符串，获取所有链接
                if not status or status.strip() == "":
                    cursor.execute("""
                        SELECT * FROM crawled_links 
                        ORDER BY discovered_at DESC
                    """)
                else:
                    cursor.execute("""
                        SELECT * FROM crawled_links 
                        WHERE status = ? 
                        ORDER BY discovered_at DESC
                    """, (status,))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"查询链接失败，状态：{status}，错误：{e}")
            return []
    
    def get_crawl_statistics(self) -> Dict[str, int]:
        """
        获取抓取统计信息
        
        Returns:
            Dict[str, int]: 包含各种状态的统计信息
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT status, COUNT(*) as count 
                    FROM crawled_links 
                    GROUP BY status
                """)
                stats = dict(cursor.fetchall())
                
                # 确保所有状态都有值
                result = {
                    'total': sum(stats.values()),
                    'pending': stats.get('pending', 0),
                    'success': stats.get('success', 0),
                    'failed': stats.get('failed', 0)
                }
                return result
        except sqlite3.Error as e:
            print(f"获取统计信息失败，错误：{e}")
            return {'total': 0, 'pending': 0, 'success': 0, 'failed': 0}
    
    def get_recent_links(self, limit: int = 10) -> List[Dict]:
        """
        获取最近发现的链接
        
        Args:
            limit: 返回数量限制
            
        Returns:
            List[Dict]: 最近链接信息列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM crawled_links 
                    ORDER BY discovered_at DESC 
                    LIMIT ?
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"获取最近链接失败，错误：{e}")
            return []
    
    def is_link_processed(self, url: str) -> bool:
        """
        检查链接是否已经处理过（成功或失败）
        
        Args:
            url: 链接URL
            
        Returns:
            bool: 是否已处理
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT status FROM crawled_links 
                    WHERE url = ? AND status IN ('success', 'failed')
                """, (url,))
                return cursor.fetchone() is not None
        except sqlite3.Error as e:
            print(f"检查链接状态失败：{url}，错误：{e}")
            return False
    
    def is_link_exists(self, url: str) -> bool:
        """
        检查链接是否已存在于数据库中（任何状态）
        
        Args:
            url: 链接URL
            
        Returns:
            bool: 是否已存在
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id FROM crawled_links 
                    WHERE url = ?
                """, (url,))
                return cursor.fetchone() is not None
        except sqlite3.Error as e:
            print(f"检查链接是否存在失败：{url}，错误：{e}")
            return False
    
    def get_pending_links(self) -> List[str]:
        """
        获取所有待处理的链接URL列表
        
        Returns:
            List[str]: 待处理链接URL列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT url FROM crawled_links 
                    WHERE status = 'pending' 
                    ORDER BY discovered_at ASC
                """)
                return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"获取待处理链接失败，错误：{e}")
            return []
    
    def print_statistics(self):
        """打印抓取统计信息到控制台"""
        stats = self.get_crawl_statistics()
        print("\n=== 抓取统计信息 ===")
        print(f"总计链接: {stats['total']}")
        print(f"待处理: {stats['pending']}")
        print(f"成功: {stats['success']}")
        print(f"失败: {stats['failed']}")
        
        if stats['total'] > 0:
            success_rate = (stats['success'] / stats['total']) * 100
            print(f"成功率: {success_rate:.1f}%")
        print("=" * 25)


# 便捷函数，用于快速创建数据库实例
def create_database(db_path: str = "crawl_links.db") -> LinkDatabase:
    """
    创建数据库实例的便捷函数
    
    Args:
        db_path: 数据库文件路径
        
    Returns:
        LinkDatabase: 数据库实例
    """
    return LinkDatabase(db_path)


if __name__ == "__main__":
    # 测试数据库功能
    print("测试数据库功能...")
    
    # 创建数据库实例
    db = create_database("test_crawl_links.db")
    
    # 测试记录链接
    test_url = "https://example.com/test"
    print(f"记录测试链接: {test_url}")
    db.record_link_discovered(test_url, "测试页面")
    
    # 测试更新成功状态
    print("更新为成功状态...")
    db.update_link_success(test_url, "测试页面", "test.md", "test.html", "markdown")
    
    # 打印统计信息
    db.print_statistics()
    
    # 清理测试数据库
    if os.path.exists("test_crawl_links.db"):
        os.remove("test_crawl_links.db")
        print("测试完成，已清理测试数据库")
