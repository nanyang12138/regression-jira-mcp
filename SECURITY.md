# Security Documentation

## Overview

This MCP server implements **defense-in-depth security** to prevent database modifications, even if users know the database password. The security is designed to be **silent** - users won't know about read-only restrictions until they attempt a write operation.

## Multi-Layer Security Architecture

### Layer 1: PostgreSQL Connection Level (Primary Defense)

**All database connections are set to read-only mode:**

```python
conn.set_session(readonly=True, autocommit=True)
```

**How it works:**
- PostgreSQL enforces read-only at the connection level
- ANY write operation (INSERT, UPDATE, DELETE, etc.) is rejected by PostgreSQL
- Works even if application code is compromised
- No way to bypass at the application level

**PostgreSQL Error Example:**
```
ERROR: cannot execute INSERT in a read-only transaction
```

### Layer 2: Application Query Validation

**SQL query validation before execution:**

```python
from .security import validate_query

validate_query(query)  # Raises SecurityError if write detected
```

**Protected Operations:**
- INSERT
- UPDATE  
- DELETE
- DROP
- CREATE
- ALTER
- TRUNCATE
- GRANT/REVOKE
- MERGE/REPLACE
- File operations (INTO OUTFILE, LOAD DATA, COPY)

**Features:**
- Uses regex word boundaries to avoid false positives
- Case-insensitive matching
- Handles whitespace and comments
- Clear error messages when blocked

### Layer 3: Security Error Handling

**Clear feedback for blocked operations:**

```json
{
  "error": "SECURITY_VIOLATION",
  "message": "Database modification not permitted. This MCP server is configured for read-only access. Attempted operation: INSERT",
  "tool": "tool_name",
  "note": "This MCP server has read-only access to the database."
}
```

## User Experience Design

### Silent Operation

**Normal reads work transparently:**
- Users don't see any warnings
- No upfront disclaimers
- Zero performance impact
- Completely invisible for read operations

**Write attempts are blocked with clear messages:**
- Explicit error when modification attempted
- Explains the limitation
- Suggests read-only access
- No cryptic database errors

### Example User Flow

1. **User queries data** → Works perfectly, no indication of restrictions
2. **User attempts UPDATE** → Clear error: "Database modification not permitted"
3. **User understands** → They have read-only access

---

# JIRA Security Protection

## Overview

The JIRA client implements **identical defense-in-depth security** to the PostgreSQL layer. Even with valid JIRA API tokens, users and AI agents **cannot modify JIRA data** through this MCP server.

## Multi-Layer Security Architecture

### Layer 1: Operation Whitelist (Primary Defense)

**Only approved read-only JIRA operations are allowed:**

```python
ALLOWED_OPERATIONS = {
    'search_issues',  'issue',  'comments',  'project',
    'search_users',   'fields', 'priorities', 'statuses',
    # ... 25+ total read-only operations
}
```

**How it works:**
- Whitelist-based access control (default deny)
- Only explicitly approved operations can execute
- Covers all query, search, and retrieval needs
- Any operation not on whitelist is rejected

**Example blocked operations:**
```
❌ create_issue, update_issue, delete_issue
❌ add_comment, update_comment, delete_comment  
❌ add_attachment, delete_attachment
❌ transition_issue, assign_issue
❌ add_worklog, add_watcher, add_vote
```

### Layer 2: Method Call Interception

**Proxy pattern wraps JIRA client:**

```python
class ReadOnlyJiraProxy:
    def __getattr__(self, name):
        validate_jira_operation(name)  # Validate first
        return getattr(self._jira, name)  # Then execute
```

**How it works:**
- `ReadOnlyJiraProxy` intercepts ALL method calls
- Validates operation before forwarding to JIRA library
- Raises `SecurityError` for forbidden operations
- Cannot be bypassed at application level
- Works even if code is compromised

### Layer 3: Security Error Handling

**Clear feedback for blocked operations:**

```json
{
  "error": "SECURITY_VIOLATION",
  "message": "JIRA modification not permitted. This MCP server is configured for read-only access. Attempted operation: create_issue",
  "tool": "tool_name",
  "note": "This MCP server has read-only access to JIRA."
}
```

## Currently Used Operations (All Read-Only)

The following JIRA library methods are actively used by the MCP server:

✅ **`search_issues`** - Search for JIRA issues using JQL  
✅ **`issue`** - Get detailed information about a single issue  
✅ **`comments`** - Retrieve all comments on an issue  
✅ **`project`** - Get project information and metadata  

All four operations are read-only and included in the whitelist.

## Additional Whitelisted Operations

The following read-only operations are pre-approved for future use:

**User & Metadata:**
- `search_users`, `myself`, `user` - User information queries
- `fields`, `createmeta`, `editmeta` - Field metadata (read-only)

**Issue Metadata:**
- `priorities`, `resolutions`, `statuses` - Configuration queries
- `versions`, `components` - Project component queries
- `issue_link_types`, `transitions` - Metadata queries

**Advanced Queries:**
- `worklogs`, `watchers`, `votes` - Get information (no modifications)
- `dashboards`, `filters`, `favourite_filters` - Dashboard queries
- `projects`, `groups`, `applicationroles` - Organization queries

**Total:** 25+ read-only operations approved

## Blocked Operations (Examples)

### Issue Modifications
❌ `create_issue`, `create_issues` - Cannot create issues  
❌ `update_issue`, `update_issue_field` - Cannot modify issues  
❌ `delete_issue` - Cannot delete issues  
❌ `assign_issue` - Cannot assign issues  

### Comment Modifications
❌ `add_comment` - Cannot add comments  
❌ `update_comment` - Cannot edit comments  
❌ `delete_comment` - Cannot remove comments  

### Attachment Operations
❌ `add_attachment` - Cannot upload files  
❌ `delete_attachment` - Cannot remove attachments  

### Workflow Operations
❌ `transition_issue` - Cannot change issue status  

### Worklog Operations
❌ `add_worklog` - Cannot log work  
❌ `update_worklog` - Cannot modify work logs  
❌ `delete_worklog` - Cannot delete work logs  

### Link Operations
❌ `create_issue_link` - Cannot link issues  
❌ `delete_issue_link` - Cannot remove links  

### Other Modifications
❌ `add_vote`, `remove_vote` - Cannot vote  
❌ `add_watcher`, `remove_watcher` - Cannot watch  
❌ `add_label`, `remove_label` - Cannot modify labels  

## Implementation Details

### Security Module (`regression_jira_mcp/security.py`)

**JiraOperationValidator Class:**
- Maintains whitelist of allowed operations (25+ operations)
- Maintains blacklist of forbidden operations
- Validates operations using defense-in-depth:
  1. Reject if explicitly forbidden (blacklist)
  2. Reject if not explicitly allowed (whitelist)
  3. Log all security violations

**validate_jira_operation() Function:**
- Convenience wrapper for operation validation
- Called by ReadOnlyJiraProxy before every operation
- Raises SecurityError for forbidden operations

### JIRA Client Module (`regression_jira_mcp/jira_client.py`)

**ReadOnlyJiraProxy Class:**
```python
class ReadOnlyJiraProxy:
    def __init__(self, jira_instance):
        object.__setattr__(self, '_jira', jira_instance)
    
    def __getattr__(self, name):
        validate_jira_operation(name)  # Security check
        return getattr(self._jira, name)  # Forward if allowed
    
    def __setattr__(self, name, value):
        if name != '_jira':
            raise SecurityError("Cannot modify JIRA client")
        object.__setattr__(self, name, value)
```

**JiraClient Integration:**
```python
class JiraClient:
    def _connect(self):
        # Create raw JIRA connection
        self._raw_jira = JIRA(server=..., basic_auth=...)
        
        # Wrap with read-only proxy
        self.jira = ReadOnlyJiraProxy(self._raw_jira)
```

All methods in `JiraClient` use `self.jira` which is the protected proxy, ensuring all operations are validated.

## Benefits

### For System Administrators

✅ **Multiple security layers** - Whitelist + Blacklist + Proxy interception  
✅ **JIRA-level protection** - Works even if code is modified  
✅ **No JIRA permission changes needed** - Application-level enforcement  
✅ **Clear audit trail** - All security violations are logged  
✅ **Zero configuration** - Security is always on  
✅ **Consistent with PostgreSQL** - Same security philosophy  

### For Users

✅ **Transparent operation** - No warnings for normal queries  
✅ **Clear feedback** - Understand why modifications fail  
✅ **No performance impact** - Validation is instant (microseconds)  
✅ **Intuitive errors** - Know exactly what's not allowed  
✅ **Full functionality** - All read operations work perfectly  

### For LLMs/AI Agents

✅ **Cannot discover restrictions** - Only revealed when attempting writes  
✅ **Cannot bypass** - Multiple enforcement layers  
✅ **Cannot prompt inject** - Security at code level, not prompt level  
✅ **Clear feedback** - Understand limitation when encountered  
✅ **Intelligent use** - Can use 25+ read-only operations effectively  

## User Experience

### Silent for Reads

```python
# Normal query - works perfectly, no indication of restrictions
issues = jira.search_issues("project = PROJ AND status = Open")
# ✓ Success - Returns issue list

issue = jira.issue("PROJ-123")
# ✓ Success - Returns issue details

comments = jira.comments("PROJ-123")
# ✓ Success - Returns comments
```

### Clear Errors for Writes

```python
# Attempt to create issue
jira.create_issue(...)
# ❌ SecurityError: "JIRA modification not permitted. 
#    This MCP server is configured for read-only access. 
#    Attempted operation: create_issue"

# Attempt to add comment
jira.add_comment("PROJ-123", "Test comment")
# ❌ SecurityError: "JIRA modification not permitted. 
#    This MCP server is configured for read-only access. 
#    Attempted operation: add_comment"
```

## Security Testing

### Manual Testing

Test read operations work:
```python
from regression_jira_mcp.jira_client import JiraClient

client = JiraClient()
issues = client.search_issues("project = PROJ", max_results=5)
print(f"✓ Found {len(issues)} issues")
```

Test write operations are blocked:
```python
try:
    client.jira.create_issue(...)
    print("❌ SECURITY FAILURE - Create allowed!")
except SecurityError as e:
    print(f"✓ Create blocked: {e}")
```

### Expected Behavior

```
✅ search_issues: Works (whitelisted)
✅ issue: Works (whitelisted)
✅ comments: Works (whitelisted)
✅ project: Works (whitelisted)
❌ create_issue: Blocked (blacklisted)
❌ add_comment: Blocked (blacklisted)
❌ unknown_operation: Blocked (not whitelisted)
```

---

# Combined Security Summary

## Overall Architecture

This MCP server implements **comprehensive read-only protection** for both data sources:

| Component | Protection Mechanism | Result |
|-----------|---------------------|--------|
| **PostgreSQL** | Connection-level read-only + Query validation | ✅ No database modifications possible |
| **JIRA** | Operation whitelist + Method interception | ✅ No JIRA modifications possible |
| **File System** | Read-only design | ✅ No log modifications |
| **Error Handling** | Clear security messages | ✅ Transparent for reads, explicit for writes |

## Security Testing

### Running Security Tests

```bash
python test_security.py
```

This tests:
1. Query validator catches all write operations
2. Read operations pass through
3. PostgreSQL connection enforces read-only
4. Error messages are clear

### Expected Output

```
✅ Testing PostgreSQL Query Validator
   - SELECT queries: PASS
   - INSERT/UPDATE/DELETE: Correctly blocked
   
✅ Testing PostgreSQL Read-Only Connection
   - Read operation: Successful
   - Write operation: Blocked at PostgreSQL level

✅ Testing JIRA Operation Validator
   - Read operations (search_issues, issue, comments): PASS
   - Write operations (create_issue, add_comment): Correctly blocked
   
✅ Testing JIRA Read-Only Proxy
   - Allowed operations: Successful
   - Forbidden operations: Blocked at proxy level
   
✅ ALL SECURITY TESTS PASSED
```

## Implementation Details

### Security Module (`regression_jira_mcp/security.py`)

**QueryValidator Class:**
- Validates SQL queries before execution
- Maintains list of forbidden keywords
- Checks for dangerous patterns
- Silent for reads, explicit for writes

**SecurityError Exception:**
- Custom exception for security violations
- Provides clear error messages
- Includes context about attempted operation

### Database Module (`regression_jira_mcp/db_queries.py`)

**Read-Only Connection:**
```python
@contextmanager
def get_connection(self):
    conn = self.connection_pool.getconn()
    try:
        conn.set_session(readonly=True, autocommit=True)
        yield conn
    finally:
        self.connection_pool.putconn(conn)
```

**Safe Execute Wrapper:**
```python
def _execute_safe(self, cursor, query: str, params=None):
    validate_query(query)  # Validate first
    cursor.execute(query, params)  # Then execute
```

### Server Module (`regression_jira_mcp/server.py`)

**Security Error Handling:**
```python
try:
    result = await tool_implementation(arguments)
except SecurityError as e:
    return clear_security_error_message(e)
```

## Benefits

### For System Administrators

✅ **Multiple security layers** - Defense in depth approach  
✅ **PostgreSQL-level protection** - Works even if code compromised  
✅ **No database permission changes needed** - Application-level enforcement  
✅ **Clear audit trail** - Security violations are logged  
✅ **Zero configuration** - Security is always on  

### For Users

✅ **Transparent operation** - No warnings for normal use  
✅ **Clear feedback** - Understand why writes fail  
✅ **No performance impact** - Only validates queries, doesn't slow reads  
✅ **Intuitive errors** - Know exactly what's not allowed  

### For LLMs/AI Agents

✅ **Cannot discover restrictions** - Only revealed when attempting writes  
✅ **Cannot bypass** - Multiple enforcement layers  
✅ **Clear feedback** - Understand the limitation when encountered  
✅ **No prompt injection** - Security at code/database level  

## Threat Model

### What is Protected

| Threat | Protection |
|--------|------------|
| Direct SQL injection | PostgreSQL read-only + Query validation |
| LLM-crafted write queries | Both layers catch and block |
| Code compromise | PostgreSQL level still enforces |
| Password knowledge | Doesn't matter - connections are read-only |
| Malicious tools | Cannot execute writes |
| **JIRA modifications** | **Operation whitelist + Method interception** |
| **JIRA API token abuse** | **Proxy validates all operations** |

### What is NOT Protected

| Limitation | Note |
|------------|------|
| File system writes | Not database-related, separate concern |
| Log file modifications | Read-only by design, no write code |
| Network operations | Separate security domain |

## Maintenance

### Adding New Security Checks

1. Add keyword to `WRITE_KEYWORDS` in `security.py`
2. Add test case to `test_security.py`
3. Run tests to verify

### Monitoring Security Events

Security violations are logged:
```python
logger.warning(f"Blocked write operation attempt: {keyword}")
```

Monitor logs for:
- Frequency of blocked operations
- Patterns in attempted writes
- Specific keywords being blocked

## FAQ

### Database Security

**Q: Can users with database password modify data?**  
A: No. The connection itself is read-only at PostgreSQL level.

**Q: Does this slow down read operations?**  
A: No. Query validation is fast (~microseconds), no measurable impact.

**Q: Is this secure against SQL injection?**  
A: Yes, but parameterized queries are still used as best practice.

### JIRA Security

**Q: Can users with JIRA API token modify issues?**  
A: No. All JIRA operations are validated through ReadOnlyJiraProxy before execution.

**Q: Does JIRA protection slow down searches?**  
A: No. Operation validation is instant, no measurable impact on performance.

**Q: What if AI tries to create an issue?**  
A: The proxy intercepts the call, validates it's forbidden, and raises SecurityError before reaching JIRA.

**Q: Can someone bypass the proxy by accessing _raw_jira?**  
A: No. The _raw_jira is private and not exposed through any MCP tools.

### General

**Q: What if I need to allow some writes?**  
A: You would need to modify the security layer, which is not recommended. Create a separate tool/server for writes instead.

**Q: Can LLMs discover they're restricted?**  
A: Only by attempting a write operation. There are no hints otherwise for read operations.

**Q: Are all current features still working?**  
A: Yes. All 4 currently used JIRA operations (search_issues, issue, comments, project) are whitelisted.

## Compliance

This implementation follows security best practices:

- **Principle of Least Privilege** - Only read access granted
- **Defense in Depth** - Multiple security layers
- **Fail Secure** - Blocks by default, allows only reads
- **Clear Audit Trail** - All violations logged
- **Zero Trust** - Don't trust application code, enforce at database

## Summary

The MCP server implements **comprehensive silent read-only enforcement** for all data sources:

### PostgreSQL Protection
1. ✅ Connection-level read-only mode (enforced by PostgreSQL)
2. ✅ Application-level query validation (double protection)
3. ✅ Blocks all write keywords (INSERT, UPDATE, DELETE, etc.)

### JIRA Protection
4. ✅ Operation whitelist (25+ read-only operations approved)
5. ✅ Method call interception (proxy pattern)
6. ✅ Blocks all modification operations (create, update, delete, etc.)

### User Experience
7. ✅ Transparent operation for all read operations
8. ✅ Clear error messages for blocked modifications
9. ✅ Comprehensive test coverage

This ensures **even users with database credentials and JIRA API tokens cannot modify any data** through the MCP server, while maintaining excellent user experience for legitimate read operations.
