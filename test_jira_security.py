"""
Test JIRA Security Protection

This script tests that the JIRA read-only protection is working correctly.
"""

import sys
from regression_jira_mcp.security import validate_jira_operation, SecurityError


def test_jira_operation_validator():
    """Test JIRA operation validator"""
    print("=" * 60)
    print("Testing JIRA Operation Validator")
    print("=" * 60)
    
    # Test allowed operations
    print("\n✅ Testing Allowed Operations:")
    allowed_ops = ['search_issues', 'issue', 'comments', 'project']
    for op in allowed_ops:
        try:
            validate_jira_operation(op)
            print(f"   ✓ {op}: ALLOWED (correct)")
        except SecurityError as e:
            print(f"   ❌ {op}: BLOCKED (should be allowed!)")
            print(f"      Error: {e}")
            return False
    
    # Test forbidden operations
    print("\n❌ Testing Forbidden Operations:")
    forbidden_ops = [
        'create_issue',
        'update_issue', 
        'delete_issue',
        'add_comment',
        'add_attachment',
        'transition_issue',
        'add_worklog'
    ]
    for op in forbidden_ops:
        try:
            validate_jira_operation(op)
            print(f"   ❌ {op}: ALLOWED (security failure!)")
            return False
        except SecurityError as e:
            print(f"   ✓ {op}: BLOCKED (correct)")
    
    # Test unknown operations (not in whitelist)
    print("\n⚠️  Testing Unknown Operations:")
    unknown_ops = ['some_random_method', 'hack_the_system']
    for op in unknown_ops:
        try:
            validate_jira_operation(op)
            print(f"   ❌ {op}: ALLOWED (security failure!)")
            return False
        except SecurityError as e:
            print(f"   ✓ {op}: BLOCKED (correct)")
    
    return True


def test_readonly_jira_proxy():
    """Test ReadOnlyJiraProxy"""
    print("\n" + "=" * 60)
    print("Testing ReadOnlyJiraProxy")
    print("=" * 60)
    
    try:
        from regression_jira_mcp.jira_client import ReadOnlyJiraProxy
        
        # Create a mock JIRA object
        class MockJIRA:
            def search_issues(self, jql, maxResults=50):
                return []
            
            def create_issue(self, fields):
                return {"key": "TEST-123"}
        
        mock_jira = MockJIRA()
        proxy = ReadOnlyJiraProxy(mock_jira)
        
        # Test allowed operation
        print("\n✅ Testing Allowed Operation (search_issues):")
        try:
            method = proxy.search_issues
            print(f"   ✓ search_issues: Method accessible (correct)")
        except SecurityError as e:
            print(f"   ❌ search_issues: Blocked (should be allowed!)")
            print(f"      Error: {e}")
            return False
        
        # Test forbidden operation
        print("\n❌ Testing Forbidden Operation (create_issue):")
        try:
            method = proxy.create_issue
            print(f"   ❌ create_issue: Method accessible (security failure!)")
            return False
        except SecurityError as e:
            print(f"   ✓ create_issue: Blocked (correct)")
            print(f"      Message: {str(e)[:80]}...")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error testing proxy: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all security tests"""
    print("\n" + "=" * 60)
    print("JIRA SECURITY PROTECTION TEST SUITE")
    print("=" * 60)
    
    results = []
    
    # Test 1: Operation Validator
    results.append(("Operation Validator", test_jira_operation_validator()))
    
    # Test 2: ReadOnly Proxy
    results.append(("ReadOnly Proxy", test_readonly_jira_proxy()))
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n🎉 ALL JIRA SECURITY TESTS PASSED! 🎉")
        print("\nConclusion:")
        print("  ✅ Read-only operations are allowed")
        print("  ✅ Write operations are blocked")
        print("  ✅ Unknown operations are blocked")
        print("  ✅ Proxy interception is working")
        print("\nYour MCP server is secure against JIRA modifications!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED - SECURITY MAY BE COMPROMISED")
        return 1


if __name__ == "__main__":
    sys.exit(main())

