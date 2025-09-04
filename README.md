# 🕷️ 智慧爬虫系统 - 让数据成为AI的核心动力

基于 Crawl4AI 的智能网页爬虫系统，支持批量抓取、数据管理和文件浏览。通过友好的 Web 界面，让网页数据抓取变得简单高效。

## ✨ 主要特性

- 🚀 **智能递归爬取**：从起始 URL 开始，自动发现并抓取相关链接
- 📊 **实时监控**：Web 界面实时显示爬取进度和统计信息
- 🗄️ **数据管理**：SQLite 数据库记录所有链接状态和抓取历史
- 📁 **文件浏览**：支持 Markdown 和 HTML 文件预览与下载
- 🎯 **链接过滤**：支持关键词过滤，精确控制抓取范围
- 🐳 **Docker 支持**：提供完整的 Docker 化部署方案
- 🔄 **断点续传**：支持失败链接重试和断点续传

## 🏗️ 项目结构

```
Crawl4AI/
├── ai_haodaifu.py          # 主入口脚本（命令行爬虫）
├── gradio_app.py           # Web 界面应用
├── link_database.py        # 数据库管理模块
├── docker_utils.py         # Docker 环境检测工具
├── requirements.txt        # Python 依赖包
├── Dockerfile              # 应用镜像构建文件
├── Dockerfile.base         # 基础镜像构建文件
├── docker-compose.yml      # Docker Compose 配置
├── output/                 # 抓取结果输出目录
│   └── <域名>/             # 按域名分层的文件结构
├── myenv/                  # Python 虚拟环境（可选）
├── crawl_links.db          # SQLite 数据库文件
└── crawler_logs.txt        # 爬虫运行日志
```

## 🚀 快速开始

### 方式一：直接运行

1. **克隆项目**
   ```bash
   git clone <项目地址>
   cd Crawl4AI
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **启动 Web 界面**
   ```bash
   python gradio_app.py
   ```

4. **访问界面**
   - 本地环境：http://localhost:7862
   - Docker 环境：http://localhost:7861

### 方式二：使用虚拟环境

1. **激活虚拟环境**
   ```bash
   # macOS/Linux
   source myenv/bin/activate
   
   # Windows PowerShell
   ./myenv/Scripts/Activate.ps1
   ```

2. **运行应用**
   ```bash
   python gradio_app.py
   ```

### 方式三：Docker 部署（推荐）

1. **构建并启动**
   ```bash
   chmod +x docker-build.sh
   ./docker-build.sh
   chmod +x docker-auto.sh
   ./docker-auto.sh
   ```

2. **访问界面**
   - 浏览器打开：http://localhost:7861

## 📖 使用指南

### Web 界面操作

#### 🚀 爬取控制
1. **配置爬取参数**
   - 起始 URL：输入要爬取的网页地址
   - 链接过滤：设置关键词过滤条件（逗号分隔）
   - 无头模式：选择是否显示浏览器界面
   - 最大递归深度：控制爬取的深度（1-10层）

2. **开始爬取**
   - 点击"🚀 开始爬取"按钮
   - 实时查看爬取日志和进度
   - 可随时点击"⏹️ 停止爬取"中断任务

#### 📊 数据统计
- 查看抓取状态分布图
- 监控成功率、失败率等关键指标
- 浏览最近抓取的链接列表

#### 🔗 链接管理
- 按状态筛选链接（成功/失败/待处理）
- 搜索特定 URL
- 重试失败的链接
- 清空所有链接数据

#### 📁 文件浏览
- 浏览所有抓取的文件
- 支持 Markdown 渲染和原始文本预览
- 下载单个文件
- 清空所有输出文件

### 命令行使用

```bash
# 直接运行爬虫脚本
python ai_haodaifu.py
```

## ⚙️ 配置说明

### 爬取配置

- **起始 URL**：爬取的起始网页地址
- **链接过滤**：支持多个关键词，用逗号分隔
  - 例如：`news,article,blog` 表示只抓取包含这些关键词的链接
- **递归深度**：控制从起始页面开始的链接跳转层数
- **无头模式**：后台运行浏览器，不显示界面（推荐生产环境）

### 输出目录结构

```
output/
└── <域名>/
    └── <路径>/
        ├── <文件名>.md      # Markdown 格式
        └── <文件名>.html    # HTML 格式
```

例如：`https://example.com/news/article1` 会保存为：
```
output/example.com/news/article1.md
output/example.com/news/article1.html
```

## 🛠️ 技术栈

- **爬虫引擎**：Crawl4AI 0.7.4
- **Web 框架**：Gradio 4.0+
- **数据库**：SQLite
- **数据处理**：Pandas, BeautifulSoup4
- **可视化**：Matplotlib
- **容器化**：Docker, Docker Compose

## 📋 依赖包

### 核心依赖
- `crawl4ai==0.7.4` - 异步网页爬虫
- `beautifulsoup4==4.13.5` - HTML 解析
- `gradio>=4.0.0` - Web 界面框架

### 数据处理
- `pandas>=1.5.0` - 数据处理
- `matplotlib>=3.5.0` - 图表绘制
- `lxml==5.4.0` - XML/HTML 解析

### 网络请求
- `aiohttp==3.12.15` - 异步 HTTP 客户端
- `httpx==0.28.1` - 现代 HTTP 客户端
- `requests==2.32.5` - 同步 HTTP 客户端

## 🐳 Docker 部署

### 构建镜像

```bash
# 构建基础镜像
docker build -f Dockerfile.base -t crawl4ai-base:latest .

# 构建应用镜像
docker build -f Dockerfile -t crawl4ai-app:latest .
```

### 使用 Docker Compose

```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 环境变量

- `PYTHONUNBUFFERED=1` - 确保 Python 输出不被缓冲

## 📊 数据库结构

### crawled_links 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| url | TEXT | 链接 URL（唯一） |
| title | TEXT | 页面标题 |
| status | TEXT | 状态：pending/success/failed |
| discovered_at | TIMESTAMP | 发现时间 |
| crawled_at | TIMESTAMP | 抓取时间 |
| error_message | TEXT | 错误信息 |
| markdown_path | TEXT | Markdown 文件路径 |
| html_path | TEXT | HTML 文件路径 |
| file_size | INTEGER | 文件大小（字节） |
| content_type | TEXT | 内容类型 |

## 🔧 开发指南

### 代码风格

- 优先可读性，适当忽略性能细节
- 详细的中文注释
- 遵循 Python PEP 8 规范

### 添加新功能

1. 在 `gradio_app.py` 中添加新的界面组件
2. 在 `link_database.py` 中添加数据库操作方法
3. 在 `ai_haodaifu.py` 中添加爬虫逻辑

### 调试技巧

- 使用 `headless=False` 查看浏览器操作
- 查看 `crawler_logs.txt` 了解详细日志
- 使用数据库查询工具检查链接状态

## 🚨 注意事项

### 使用限制

- 请遵守网站的 robots.txt 协议
- 避免过于频繁的请求，建议添加延迟
- 注意版权和隐私保护

### 性能优化

- 生产环境建议使用无头模式
- 合理设置递归深度避免无限爬取
- 定期清理日志文件避免占用过多空间

### 故障排除

1. **浏览器启动失败**
   - 检查 Playwright 是否正确安装
   - 运行 `playwright install` 安装浏览器

2. **数据库连接错误**
   - 检查文件权限
   - 确保有足够的磁盘空间

3. **内存不足**
   - 减少并发请求数量
   - 降低递归深度

## 📝 更新日志

### v1.0.0 (2024)
- ✨ 初始版本发布
- 🚀 支持递归爬取和 Web 界面
- 📊 完整的统计和监控功能
- 🐳 Docker 化部署支持

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- [Crawl4AI](https://github.com/unclecode/crawl4ai) - 强大的异步爬虫框架
- [Gradio](https://gradio.app/) - 优秀的 Web 界面框架
- [Playwright](https://playwright.dev/) - 现代浏览器自动化工具

---

**让数据成为AI的核心动力！** 🚀
