# 应用镜像 Dockerfile
# 基于预构建的基础镜像，只复制应用代码
FROM crawl4ai-base:latest

# 设置工作目录
WORKDIR /app

# 复制项目文件到工作目录
COPY ai_haodaifu.py .
COPY gradio_app.py .
COPY link_database.py .
COPY db_query_tool.py .
COPY docker_utils.py .

# 创建必要的目录
RUN mkdir -p /app/output

# 设置权限
RUN chmod +x ai_haodaifu.py
RUN chmod +x gradio_app.py

# 设置 Python 路径，确保可以找到当前目录的模块
ENV PYTHONPATH=/app

# 默认命令：运行 Gradio Web 界面
CMD ["python", "gradio_app.py"]
