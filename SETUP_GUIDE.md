# 设置指南 (Setup Guide)

## 📋 快速设置步骤

### 1. 创建虚拟环境并安装依赖（推荐）

```bash
# 进入项目目录
cd c:\Users\nanyang2\Downloads\regression

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows CMD:
venv\Scripts\activate.bat
# Windows PowerShell:
venv\Scripts\Activate.ps1

# 升级pip（推荐）
python -m pip install --upgrade pip

# 安装依赖
pip install -r requirements.txt
```

**注意**: 激活成功后会看到 `(venv)` 前缀

### 2. 配置Cline MCP服务器

**重要**: 只需配置这一个文件，不需要创建.env文件！

打开文件：`C:\Users\nanyang2\AppData\Roaming\Code\User\globalStorage\slai.claude-dev\settings\cline_mcp_settings.json`

添加以下配置（使用虚拟环境的Python）：

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

**重要提示：** 
- 替换所有`your_*`占位符为实际值
- 可以同时保留原有的`mcp-atlassian`配置（如果已安装Docker）

### 3. 测试安装（可选）

```bash
# 确保虚拟环境已激活
python test_installation.py
```

应该看到所有测试通过✅

### 4. 重启Cline

- 重启VSCode，或
- 重新加载Cline扩展

### 6. 验证MCP服务器

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
1. 检查Python版本：`python --version` (需要3.8+)
2. 检查依赖：`pip list | findstr mcp`
3. 手动运行服务器：`python -m regression_jira_mcp.server`
4. 查看错误信息

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
