# 设置指南 (Setup Guide)

## 📋 快速设置步骤

### 1. 创建Python虚拟环境 (推荐)

**为什么使用虚拟环境？**
- ✅ 依赖隔离，避免与系统Python包冲突
- ✅ 更安全，不影响其他项目
- ✅ 易于管理和复现环境

```bash
cd /proj/gfx_meth_user0/nanyang2/regression-jira-mcp

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
(or source venv/bin/activate.csh)

激活虚拟环境后，命令提示符前会显示 `(venv)`。

### 2. 安装Python依赖

```bash
# 确保虚拟环境已激活
pip install -r requirements.txt
```

### 3. 配置环境变量

创建`.env`文件（从模板复制）：

```bash
copy config.env.example .env
```

编辑`.env`文件，填入您的实际配置：

```bash
# PostgreSQL配置
PGDATABASE=your_actual_database_name
PGHOST=your_actual_host
PGPORT=5432
PGUSER=your_username
PGPASSWORD=your_password

# JIRA配置
JIRA_URL=https://amd.atlassian.net
JIRA_USERNAME=Nan.Yang@amd.com
JIRA_API_TOKEN=your_actual_api_token
```

### 4. 配置Cline MCP服务器

打开文件：`~/.config/Code/User/globalStorage/slai.claude-dev/settings/cline_mcp_settings.json`

添加以下配置：

```json
{
  "mcpServers": {
    "regression-system": {
      "command": "/proj/gfx_meth_user0/nanyang2/regression-jira-mcp/venv/bin/python",
      "args": ["-m", "regression_jira_mcp.server"],
      "cwd": "/proj/gfx_meth_user0/nanyang2/regression-jira-mcp",
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

**重要提示：**
- 替换所有`your_*`占位符为实际值
- 如果使用虚拟环境，`command` 必须指向虚拟环境中的Python：
  - Linux/Mac: `/path/to/project/venv/bin/python`
  - Windows: `c:/path/to/project/venv/Scripts/python.exe`
- 可以同时保留原有的`mcp-atlassian`配置（如果已安装Docker）

### 5. 测试连接

**注意：** 在测试前，确保虚拟环境已激活！


测试PostgreSQL连接：
```bash
python -c "import psycopg2; conn = psycopg2.connect(dbname='your_db', host='your_host', port=5432, user='your_user', password='your_pass'); print('PostgreSQL OK'); conn.close()"
```

测试JIRA连接：
```bash
python -c "from jira import JIRA; j = JIRA(server='https://amd.atlassian.net', basic_auth=('your_email', 'your_token')); print('JIRA OK')"
```

### 6. 重启Cline

- 重启VSCode，或
- 重新加载Cline扩展

### 7. 验证MCP服务器

在Cline中询问：
```
"列出所有可用的regression-system MCP工具"
```

应该看到10个工具：
- query_failed_tests
- get_test_details
- get_regression_summary
- analyze_test_log
- search_jira_issues
- search_jira_by_text
- get_jira_issue
- find_solutions_for_test ⭐
- batch_find_solutions
- list_regression_runs

## 🎯 使用示例

### 示例1: 查找测试失败的解决方案
```
您: "test_memory_allocation失败了，帮我在JIRA找解决方案"

系统会自动：
1. 从PostgreSQL查询测试信息
2. 分析错误日志
3. 在JIRA搜索相关问题
4. 返回匹配的解决方案
```

### 示例2: 批量分析
```
您: "regression run 12345有哪些失败测试？都有JIRA解决方案吗？"

系统会：
1. 查询所有失败测试
2. 为每个测试搜索JIRA
3. 生成汇总报告
```

### 示例3: 分析特定测试
```
您: "分析test_dma_transfer的错误日志"

系统会：
1. 查询测试详情
2. 读取并分析日志文件
3. 提取错误签名和关键词
4. 显示错误上下文
```

## 🔧 故障排除

### 问题1: "Failed to connect to PostgreSQL"

**检查：**
- 环境变量是否正确
- 数据库服务器是否可访问
- 用户名和密码是否正确

**测试：**
```bash
python -c "from regression_jira_mcp.db_queries import RegressionDB; db = RegressionDB(); print('DB OK')"
```

### 问题2: "Failed to connect to JIRA"

**检查：**
- JIRA_URL是否正确（https://amd.atlassian.net）
- API Token是否有效
- 网络连接是否正常

**更新API Token：**
1. 访问 https://id.atlassian.com/manage-profile/security/api-tokens
2. 删除旧token，创建新token
3. 更新.env文件

### 问题3: "Log file not accessible"

这是正常的降级行为。如果日志文件不可访问，系统会：
- 使用test_name提取关键词
- 仍然可以搜索JIRA
- 但匹配精度会略低

### 问题4: MCP服务器无法启动

**调试步骤：**
1. 确保虚拟环境已激活：`source venv/bin/activate` (Linux/Mac) 或 `venv\Scripts\activate` (Windows)
2. 检查Python版本：`python --version` (需要3.8+)
3. 检查依赖：`pip list | grep mcp` (Linux/Mac) 或 `pip list | findstr mcp` (Windows)
4. 手动运行服务器：`python -m regression_jira_mcp.server`
5. 查看错误信息

### 问题5: "找不到mcp模块"

**原因：** 虚拟环境未激活或MCP配置未指向虚拟环境的Python

**解决：**
1. 检查MCP配置中的`command`是否指向venv中的Python
2. 确保依赖已在虚拟环境中安装：
   ```bash
   source venv/bin/activate  # 激活虚拟环境
   pip list  # 确认mcp已安装
   ```

## 📊 性能建议

### 优化日志分析速度

编辑`.env`文件：
```bash
# 只扫描前10000行（默认）
MAX_LOG_LINES=10000

# 或只扫描文件头尾（更快）
LOG_ENDS_ONLY=50000
```

### 限制JIRA搜索结果

```bash
JIRA_MAX_RESULTS=20
```

## 🔐 安全提示

1. **.env文件安全**
   - 不要提交到git
   - 不要分享给他人
   - 定期更新API Token

2. **数据库权限**
   - 只需要SELECT权限（只读）
   - 不需要INSERT/UPDATE/DELETE权限

3. **JIRA访问**
   - API Token只给必要的权限
   - 定期审查API使用情况

## 🚀 开始使用

完成设置后，在Cline中直接用自然语言查询：

```
"帮我查找最近失败的测试"
"test_xxx有JIRA解决方案吗？"
"regression run 12345的结果怎么样？"
```

系统会自动调用合适的MCP工具并返回结果！
