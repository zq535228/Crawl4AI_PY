#!/usr/bin/env python3
"""
Gradio 应用启动脚本
支持热重载功能

使用方法：
1. 普通启动：python3 start_gradio.py
2. 热重载启动：python3 start_gradio.py --hot-reload
3. 环境变量启动：GRADIO_HOT_RELOAD=true python3 start_gradio.py

作者：AI助手
创建时间：2024
"""

import os
import sys
import subprocess
import argparse


def check_dependencies():
    """检查依赖是否安装"""
    required_packages = ['gradio', 'watchdog']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ 缺少依赖包: {', '.join(missing_packages)}")
        print("请运行以下命令安装：")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='启动 Gradio 爬虫管理系统')
    parser.add_argument('--hot-reload', action='store_true', 
                       help='启用热重载功能')
    parser.add_argument('--port', type=int, default=7861,
                       help='指定端口号 (默认: 7861)')
    parser.add_argument('--host', default='0.0.0.0',
                       help='指定主机地址 (默认: 0.0.0.0)')
    
    args = parser.parse_args()
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 设置环境变量
    if args.hot_reload:
        os.environ['GRADIO_HOT_RELOAD'] = 'true'
    
    # 构建启动命令
    cmd = [sys.executable, 'gradio_app.py']
    
    if args.hot_reload:
        cmd.append('--hot-reload')
    
    print("🚀 正在启动 Gradio 应用...")
    print(f"📍 地址: http://{args.host}:{args.port}")
    
    if args.hot_reload:
        print("🔥 热重载模式已启用")
        print("💡 修改 Python 文件后会自动重新加载")
    
    try:
        # 启动应用
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n👋 应用程序已停止")
    except subprocess.CalledProcessError as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
