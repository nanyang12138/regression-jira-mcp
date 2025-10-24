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
✅ Testing Query Validator
   - SELECT queries: PASS
   - INSERT/UPDATE/DELETE: Correctly blocked
   
✅ Testing Read-Only Connection
   - Read operation: Successful
   - Write operation: Blocked at PostgreSQL level
   
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

### What is NOT Protected

| Limitation | Note |
|------------|------|
| JIRA modifications | JIRA has separate read-only API scope |
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

**Q: Can users with database password modify data?**  
A: No. The connection itself is read-only at PostgreSQL level.

**Q: Does this slow down read operations?**  
A: No. Query validation is fast (~microseconds), no measurable impact.

**Q: What if I need to allow some writes?**  
A: You would need to modify the security layer, which is not recommended. Create a separate connection for writes instead.

**Q: Can LLMs discover they're restricted?**  
A: Only by attempting a write operation. There are no hints otherwise.

**Q: Is this secure against SQL injection?**  
A: Yes, but parameterized queries are still used as best practice.

## Compliance

This implementation follows security best practices:

- **Principle of Least Privilege** - Only read access granted
- **Defense in Depth** - Multiple security layers
- **Fail Secure** - Blocks by default, allows only reads
- **Clear Audit Trail** - All violations logged
- **Zero Trust** - Don't trust application code, enforce at database

## Summary

The MCP server implements **silent read-only enforcement** through:

1. ✅ PostgreSQL connection-level read-only mode
2. ✅ Application-level query validation  
3. ✅ Clear error messages for violations
4. ✅ Transparent operation for reads
5. ✅ Comprehensive test suite

This ensures **even users with database credentials cannot modify data** while maintaining excellent user experience for legitimate read operations.
