# Regression-JIRA智能集成系统

## 📖 项目概述

一个基于MCP (Model Context Protocol) 的智能系统，用于自动分析regression测试失败并在JIRA中查找解决方案。

### 核心功能

- 🔍 **智能日志分析** - 基于经过验证的analyzeFailure算法提取错误信息
- 🎯 **精准JIRA匹配** - 使用AI驱动的相似度算法匹配相关JIRA问题
- 💬 **自然语言交互** - 通过Cline AI直接用中文或英文查询
- 📊 **PostgreSQL集成** - 从现有数据库读取测试结果
- 🚀 **一键查找解决方案** - 自动化从测试失败到JIRA解决方案的完整流程

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────┐
│                   Cline AI                          │
│            (自然语言交互层)                           │
└──────────────┬──────────────────────────────────────┘
               │
               ▼
    ┌──────────────────────────────────────┐
    │  Regression-JIRA MCP Server          │
    │  (统一的PostgreSQL + JIRA服务器)      │
    └────────┬─────────────────┬───────────┘
             │                 │
             ▼                 ▼
    ┌─────────────────┐  ┌──────────────────┐
    │  PostgreSQL DB  │  │   JIRA Cloud     │
    │  (测试结果)      │  │   (问题追踪)      │
    └─────────────────┘  └──────────────────┘
```

## ✨ 主要特性

### 1. PostgreSQL工具 (5个)

- `query_failed_tests` - 查询失败的测试用例
- `get_test_details` - 获取测试详细信息
- `search_similar_failures` - 搜索历史相似失败
- `get_regression_summary` - 获取regression run统计
- `analyze_test_log` - 分析测试日志文件

### 2. JIRA工具 (15个)

#### 基础功能
- `search_jira_issues` - 使用JQL搜索JIRA问题
- `get_jira_issue` - 获取问题详情
- `search_jira_by_text` - 简单文本搜索
- `get_jira_comments` - 获取问题评论
- `get_related_jira_issues` - 获取相关问题
- `search_jira_by_labels` - 按标签搜索
- `get_jira_project_info` - 获取项目信息

#### 智能组合功能 ⭐
- `find_solutions_for_test` - 一键查找测试解决方案
- `batch_find_solutions` - 批量查找解决方案
- `compare_error_with_jira` - 错误与JIRA相似度比较
- `suggest_jira_search_query` - 建议搜索查询
- `analyze_jira_solution` - 深度分析解决方案

#### 统计分析
- `get_jira_statistics` - JIRA统计
- `find_frequent_issues` - 频繁问题分析
- `get_jira_resolution_time` - 解决时间分析

### 3. 智能错误分析

基于经过验证的analyzeFailure算法，包含：
- 60+ 错误检测正则表达式
- 自动识别错误类型和级别
- 提取错误签名和关键词
- 智能过滤噪音信息

## 🚀 快速开始

### 环境要求

- Python 3.8+
- PostgreSQL数据库访问权限
- JIRA Cloud账户和API Token

### 安装步骤

1. **创建虚拟环境**
```bash
cd c:\Users\nanyang2\Downloads\regression
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
```

2. **配置MCP服务器**

编辑 `C:\Users\nanyang2\AppData\Roaming\Code\User\globalStorage\slai.claude-dev\settings\cline_mcp_settings.json`

添加：
```json
{
  "mcpServers": {
    "regression-system": {
      "command": "c:/Users/nanyang2/Downloads/regression/venv/Scripts/python.exe",
      "args": ["-m", "regression_jira_mcp.server"],
      "cwd": "c:/Users/nanyang2/Downloads/regression",
      "env": {
        "PGDATABASE": "your_database",
        "PGHOST": "your_host",
        "PGPORT": "5432",
        "PGUSER": "your_user",
        "PGPASSWORD": "your_password",
        "JIRA_URL": "https://amd.atlassian.net",
        "JIRA_USERNAME": "Nan.Yang@amd.com",
        "JIRA_API_TOKEN": "your_api_token"
      }
    }
  }
}
```

3. **重启Cline**

重启VSCode或重新加载Cline扩展

## 📝 使用示例

### 示例1: 查询失败测试并找JIRA解决方案

```
您: "帮我查找最近失败的测试，并在JIRA中搜索相关解决方案"

AI会自动：
1. 调用 query_failed_tests() 获取失败测试列表
2. 对每个测试调用 analyze_test_log() 分析日志
3. 调用 find_solutions_for_test() 搜索JIRA
4. 展示匹配的JIRA问题和解决方案
```

### 示例2: 分析特定测试

```
您: "test_memory_allocation这个测试失败了，有没有相关的JIRA问题？"

AI会：
1. 查询测试详情
2. 分析错误日志，提取关键词
3. 在JIRA中搜索相关问题
4. 按相似度排序并展示结果
```

### 示例3: 批量分析regression run

```
您: "regression run 12345有哪些失败的测试？都有解决方案吗？"

AI会：
1. 获取run摘要统计
2. 查询所有失败测试
3. 批量搜索JIRA解决方案
4. 生成汇总报告
```

## 🔧 配置说明

### PostgreSQL配置

```bash
PGDATABASE=your_database_name
PGHOST=your_database_host
PGPORT=5432
PGUSER=your_username
PGPASSWORD=your_password
```

### JIRA配置

```bash
JIRA_URL=https://your-instance.atlassian.net
JIRA_USERNAME=your.email@example.com
JIRA_API_TOKEN=your_api_token
```

**获取JIRA API Token:**
1. 访问 https://id.atlassian.com/manage-profile/security/api-tokens
2. 点击"Create API token"
3. 复制生成的token

### 可选配置

```bash
# 日志分析选项
MAX_LOG_LINES=10000          # 最大扫描行数
LOG_ENDS_ONLY=100000         # 只扫描文件头尾N字节

# JIRA搜索选项
JIRA_MAX_RESULTS=50          # 最大搜索结果数
JIRA_DEFAULT_PROJECT=PROJ    # 默认项目key
```

## 🛠️ MCP工具参考

### query_failed_tests

查询失败的测试用例

**参数:**
- `regression_run_id`: int (可选) - Regression run ID
- `project_name`: str (可选) - 项目名称
- `regression_name`: str (可选) - Regression名称
- `limit`: int = 10 - 最大返回数量
- `include_logs`: bool = True - 是否包含日志分析

**返回:**
```json
{
  "total_failed": 15,
  "tests": [
    {
      "test_name": "test_memory_allocation",
      "status": "failed",
      "error_summary": "Memory allocation failed",
      "error_keywords": ["memory", "allocation", "failed"],
      "log_file": "/path/to/log"
    }
  ]
}
```

### find_solutions_for_test ⭐

一键查找测试失败的JIRA解决方案（最常用）

**参数:**
- `test_name`: str - 测试名称
- `regression_run_id`: int (可选) - Regression run ID
- `max_jira_results`: int = 10 - 最大JIRA结果数

**返回:**
```json
{
  "test_info": {
    "test_name": "test_memory_allocation",
    "error_signature": "Memory allocation failed at line 234"
  },
  "jira_matches": [
    {
      "issue_key": "PROJ-1234",
      "similarity_score": 0.92,
      "summary": "Fix memory allocation bug",
      "status": "Resolved",
      "solution": "Applied patch v2.3.1...",
      "link": "https://amd.atlassian.net/browse/PROJ-1234"
    }
  ]
}
```

## 🐛 故障排除

### 问题: MCP服务器无法启动

**检查:**
1. Python版本是否>=3.8
2. 所有依赖是否已安装: `pip list`
3. 环境变量是否正确配置
4. PostgreSQL是否可以连接

**解决:**
```bash
# 测试Python模块
python -c "import mcp, psycopg2, jira; print('OK')"

# 测试数据库连接
python -c "import psycopg2; conn = psycopg2.connect('your_connection_string'); print('DB OK')"
```

### 问题: 无法读取日志文件

**原因:** 日志文件路径不可访问

**解决方案:**
1. 确认日志文件路径是否正确
2. 检查文件访问权限
3. 如果是网络路径，确认网络连接

### 问题: JIRA搜索返回空结果

**检查:**
1. JIRA API Token是否有效
2. 项目key是否正确
3. 尝试简化搜索关键词

**调试:**
```
在Cline中询问: "测试JIRA连接，搜索任何一个issue"
```

## 📚 高级用法

### 自定义错误模式

如果需要添加自定义错误检测模式，编辑 `regression_jira_mcp/error_patterns.py`:

```python
# 添加到ERROR_PATTERNS列表
{
    'pattern': re.compile(r'YOUR_CUSTOM_PATTERN'),
    'level': 5,
    'pos': 'custom:my_pattern'
}
```

### 扩展JIRA工具

在 `regression_jira_mcp/jira_client.py` 中添加新方法，然后在 `server.py` 中注册为MCP工具。

## 🤝 与现有系统集成

```
现有Ruby脚本 (regression_db_pg.rb)
    ↓ 写入测试结果
PostgreSQL数据库
    ↑ 读取测试结果
新的Python MCP服务器
    ↓ 查询
JIRA Cloud
```

**重要:** 
- ✅ `regression_db_pg.rb` 继续运行，负责写入数据
- ✅ 新系统只读取数据库，不修改
- ✅ 两个系统可以同时运行

## 📄 项目结构

```
regression/
├── regression_jira_mcp/          # MCP服务器包
│   ├── __init__.py              # 包初始化
│   ├── server.py                # MCP服务器主入口
│   ├── db_queries.py            # 数据库查询
│   ├── jira_client.py           # JIRA客户端
│   ├── log_analyzer.py          # 日志分析器
│   ├── error_patterns.py        # 错误模式
│   ├── error_matcher.py         # 智能匹配
│   └── utils.py                 # 工具函数
├── requirements.txt             # Python依赖
├── config.env.example           # 配置模板
├── .env                         # 实际配置(不提交)
├── .gitignore                   # Git忽略文件
└── README.md                    # 本文档
```

## 🔒 安全注意事项

1. **不要提交.env文件** - 包含敏感信息
2. **定期更新API Token** - 建议每90天更换
3. **使用只读数据库用户** - MCP服务器只需读权限
4. **限制JIRA访问范围** - 只访问必要的项目

## 📊 性能优化

- **日志文件大小限制:** 默认只读取最后10000行
- **数据库查询缓存:** 常用查询结果缓存5分钟
- **并发处理:** 支持批量查询的并发处理
- **智能过滤:** 自动过滤无关错误信息

## 🆘 获取帮助

如果遇到问题：

1. 查看本README的故障排除章节
2. 检查日志输出: `python -m regression_jira_mcp.server --debug`
3. 在Cline中询问: "regression-system MCP服务器有问题，如何调试？"

## 📝 更新日志

### v1.0.0 (2025-01-21)
- ✅ 初始版本发布
- ✅ PostgreSQL集成
- ✅ JIRA集成
- ✅ 智能日志分析
- ✅ 15个JIRA工具
- ✅ 自然语言交互

## 📄 许可证

内部使用项目

## 👥 贡献者

AMD Verification Team

---

**祝使用愉快！如有问题，随时在Cline中提问。** 🚀
