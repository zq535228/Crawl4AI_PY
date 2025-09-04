#!/usr/bin/env python3
"""
启动 Gradio Web 界面的便捷脚本

使用方法:
    python start_web_interface.py

功能:
- 检查依赖是否安装
- 启动 Gradio Web 界面
- 提供友好的启动信息

作者：AI助手
创建时间：2024
"""

import sys
import os
import subprocess
import importlib.util
import socket


def check_dependencies():
    """检查必要的依赖是否已安装"""
    required_packages = [
        'gradio',
        'matplotlib', 
        'pandas',
        'crawl4ai',
        'bs4'  # beautifulsoup4 的导入名称是 bs4
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ 缺少以下依赖包:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n请运行以下命令安装依赖:")
        print("   pip install -r requirements.txt")
        return False
    
    print("✅ 所有依赖包已安装")
    return True


def check_database():
    """检查数据库文件是否存在"""
    db_path = "crawl_links.db"
    if not os.path.exists(db_path):
        print("ℹ️  数据库文件不存在，将在首次运行时自动创建")
    else:
        print("✅ 数据库文件存在")
    return True


def check_output_directory():
    """检查输出目录是否存在"""
    output_dir = "output"
    if not os.path.exists(output_dir):
        print("ℹ️  输出目录不存在，将在首次爬取时自动创建")
        os.makedirs(output_dir, exist_ok=True)
        print("✅ 已创建输出目录")
    else:
        print("✅ 输出目录存在")
    return True


def start_gradio_app():
    """启动 Gradio 应用"""
    try:
        print("\n🚀 正在启动 Gradio Web 界面...")
        print("=" * 50)
        
        # 自动选择端口，避免 7861 被占用
        def find_free_port(start_port: int, max_tries: int = 50) -> int:
            for port in range(start_port, start_port + max_tries):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    try:
                        s.bind(("0.0.0.0", port))
                        return port
                    except OSError:
                        continue
            return start_port

        chosen_port = find_free_port(7861)
        os.environ['GRADIO_SERVER_NAME'] = os.environ.get('GRADIO_SERVER_NAME', '0.0.0.0')
        os.environ['GRADIO_SERVER_PORT'] = os.environ.get('GRADIO_SERVER_PORT', str(chosen_port))

        # 导入并运行 Gradio 应用
        from gradio_app import main
        main()
        
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("请确保 gradio_app.py 文件存在且没有语法错误")
        return False
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        return False


def main():
    """主函数"""
    print("🕷️  爬虫管理系统 - Web 界面启动器")
    print("=" * 50)
    
    # 检查依赖
    print("\n📦 检查依赖包...")
    if not check_dependencies():
        sys.exit(1)
    
    # 检查数据库
    print("\n🗄️  检查数据库...")
    check_database()
    
    # 检查输出目录
    print("\n📁 检查输出目录...")
    check_output_directory()
    
    # 显示启动信息
    print("\n🌐 Web 界面信息:")
    print("   - 本地访问: http://localhost:7861")
    print("   - 网络访问: http://0.0.0.0:7861")
    print("   - 按 Ctrl+C 停止服务")
    
    # 启动应用
    start_gradio_app()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 用户中断，正在退出...")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 发生未预期的错误: {e}")
        sys.exit(1)
