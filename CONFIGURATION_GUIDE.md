# 配置说明 (Configuration Guide)

## ❓ 为什么有两个配置文件？

您提出了一个很好的问题！让我解释清楚：

### 📋 两种配置方式

#### **方式1: 只配置cline_mcp_settings.json** ⭐ **推荐！最简单！**

**适用场景**: 只在Cline中使用MCP服务器

**优点**: ✅ 只需配置一个文件
**缺点**: ❌ 无法独立运行Python脚本测试

**配置步骤**:
1. 编辑 `C:\Users\nanyang2\AppData\Roaming\Code\User\globalStorage\slai.claude-dev\settings\cline_mcp_settings.json`
2. 添加以下内容（替换`your_*`为实际值）：

```json
{
  "mcpServers": {
    "regression-system": {
      "command": "python",
      "args": ["-m", "regression_jira_mcp.server"],
      "cwd": "c:/Users/nanyang2/Downloads/regression",
      "env": {
        "PGDATABASE": "your_actual_database",
        "PGHOST": "your_actual_host",
        "PGPORT": "5432",
        "PGUSER": "your_actual_user",
        "PGPASSWORD": "your_actual_password",
        "JIRA_URL": "https://amd.atlassian.net",
        "JIRA_USERNAME": "Nan.Yang@amd.com",
        "JIRA_API_TOKEN": "your_actual_jira_token"
      }
    }
  }
}
```

3. 重启Cline
4. ✅ 完成！

---

#### **方式2: 同时配置.env和cline_mcp_settings.json**

**适用场景**: 需要独立运行Python脚本测试（如test_installation.py）

**优点**: ✅ 可以独立测试，可以运行测试脚本
**缺点**: ❌ 需要配置两个文件

**配置步骤**:

**步骤A: 创建.env文件**
```bash
# 复制模板
copy config.env.example .env

# 编辑.env，填入实际配置
notepad .env
```

.env文件内容：
```bash
PGDATABASE=your_actual_database
PGHOST=your_actual_host
PGPORT=5432
PGUSER=your_actual_user
PGPASSWORD=your_actual_password

JIRA_URL=https://amd.atlassian.net
JIRA_USERNAME=Nan.Yang@amd.com
JIRA_API_TOKEN=your_actual_jira_token
```

**步骤B: 配置cline_mcp_settings.json**

编辑配置文件，但这次可以使用特殊语法让它读取.env：

**选项1（简单）- 直接写配置**：
```json
{
  "mcpServers": {
    "regression-system": {
      "command": "python",
      "args": ["-m", "regression_jira_mcp.server"],
      "cwd": "c:/Users/nanyang2/Downloads/regression",
      "env": {
        "PGDATABASE": "your_actual_database",
        "PGHOST": "your_actual_host",
        "PGPORT": "5432",
        "PGUSER": "your_actual_user",
        "PGPASSWORD": "your_actual_password",
        "JIRA_URL": "https://amd.atlassian.net",
        "JIRA_USERNAME": "Nan.Yang@amd.com",
        "JIRA_API_TOKEN": "your_actual_jira_token"
      }
    }
  }
}
```

**选项2（高级）- 留空，让Python从.env读取**：
```json
{
  "mcpServers": {
    "regression-system": {
      "command": "python",
      "args": ["-m", "regression_jira_mcp.server"],
      "cwd": "c:/Users/nanyang2/Downloads/regression"
    }
  }
}
```
（Python代码会自动从.env文件加载配置）

---

## 💡 推荐配置方案

### **对于大多数用户（只用Cline）**

**只需配置 `cline_mcp_settings.json`**

1. 打开文件：`C:\Users\nanyang2\AppData\Roaming\Code\User\globalStorage\slai.claude-dev\settings\cline_mcp_settings.json`

2. 添加配置（替换实际值）：
```json
{
  "mcpServers": {
    "regression-system": {
      "command": "python",
      "args": ["-m", "regression_jira_mcp.server"],
      "cwd": "c:/Users/nanyang2/Downloads/regression",
      "env": {
        "PGDATABASE": "实际数据库名",
        "PGHOST": "实际主机地址",
        "PGPORT": "5432",
        "PGUSER": "实际用户名",
        "PGPASSWORD": "实际密码",
        "JIRA_URL": "https://amd.atlassian.net",
        "JIRA_USERNAME": "Nan.Yang@amd.com",
        "JIRA_API_TOKEN": "实际的JIRA_API_TOKEN"
      }
    }
  }
}
```

3. 重启Cline
4. ✅ 完成！

**不需要创建.env文件！**

---

## 🔧 什么时候需要.env文件？

只有在以下情况才需要创建.env文件：

1. ✅ 运行测试脚本：`python test_installation.py`
2. ✅ 独立调试Python代码
3. ✅ 开发和测试新功能

**日常使用Cline时，不需要.env文件！**

---

## 📝 配置示例（实际场景）

假设您的实际配置是：
- 数据库：gcb_regression
- 主机：db.example.com
- 用户：test_user
- 密码：mypassword123
- JIRA Token：ATATT3xFfGF0...（很长的字符串）

**只需在cline_mcp_settings.json中配置：**

```json
{
  "mcpServers": {
    "regression-system": {
      "command": "python",
      "args": ["-m", "regression_jira_mcp.server"],
      "cwd": "c:/Users/nanyang2/Downloads/regression",
      "env": {
        "PGDATABASE": "gcb_regression",
        "PGHOST": "db.example.com",
        "PGPORT": "5432",
        "PGUSER": "test_user",
        "PGPASSWORD": "mypassword123",
        "JIRA_URL": "https://amd.atlassian.net",
        "JIRA_USERNAME": "Nan.Yang@amd.com",
        "JIRA_API_TOKEN": "ATATT3xFfGF0..."
      }
    }
  }
}
```

保存后重启Cline，就可以使用了！

**不需要.env文件！**

---

## 🎯 总结

| 问题 | 答案 |
|------|------|
| 需要配置两个文件吗？ | ❌ 不需要！只配置cline_mcp_settings.json即可 |
| .env文件是必需的吗？ | ❌ 不是！只有测试脚本需要 |
| 配置在哪个文件中？ | ✅ cline_mcp_settings.json（在"env"字段中） |
| 两个文件的参数一样吗？ | ✅ 是的，如果都配置的话，参数应该一样 |

**最简单的方法：只配置cline_mcp_settings.json！**
