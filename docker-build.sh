#!/bin/bash

# Crawl4AI Docker 构建脚本
# 用于构建基础镜像和应用镜像

set -e  # 遇到错误立即退出

echo "🚀 开始构建 Crawl4AI Docker 镜像..."

# 检查 Docker 是否运行
if ! docker info > /dev/null 2>&1; then
    echo "❌ 错误：Docker 未运行，请先启动 Docker"
    exit 1
fi

# 构建基础镜像（包含所有依赖）
echo "📦 构建基础镜像（包含系统依赖和 Python 包）..."
docker build -f Dockerfile.base -t crawl4ai-base:latest .

if [ $? -eq 0 ]; then
    echo "✅ 基础镜像构建成功！"
else
    echo "❌ 基础镜像构建失败！"
    exit 1
fi

# 构建应用镜像（基于基础镜像）
echo "📦 构建应用镜像（基于基础镜像）..."
docker build -f Dockerfile -t crawl4ai-app:latest .

if [ $? -eq 0 ]; then
    echo "✅ 应用镜像构建成功！"
else
    echo "❌ 应用镜像构建失败！"
    exit 1
fi

echo ""
echo "🎉 所有镜像构建完成！"
echo ""
echo "📋 可用的镜像："
echo "  - crawl4ai-base:latest  (基础镜像，包含所有依赖)"
echo "  - crawl4ai-app:latest   (应用镜像，包含应用代码)"
echo ""
echo "🚀 运行应用："
echo "  docker run -v \$(pwd)/output:/app/output crawl4ai-app:latest"
echo ""
echo "🔧 或者使用 docker-compose："
echo "  docker-compose up crawl4ai"
