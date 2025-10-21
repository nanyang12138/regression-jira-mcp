"""
Installation Test Script

Run this script to verify that all components are properly installed and configured.
"""

import sys
import os


def test_python_version():
    """Check Python version"""
    print("Testing Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} - OK")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} - Need 3.8+")
        return False


def test_dependencies():
    """Check if all required packages are installed"""
    print("\nTesting dependencies...")
    
    required = [
        ('mcp', 'MCP SDK'),
        ('psycopg2', 'PostgreSQL driver'),
        ('jira', 'JIRA client'),
        ('dotenv', 'Python-dotenv'),
        ('sklearn', 'Scikit-learn (optional)'),
        ('Levenshtein', 'Python-Levenshtein (optional)')
    ]
    
    all_ok = True
    for module, name in required:
        try:
            __import__(module)
            print(f"✅ {name} - Installed")
        except ImportError:
            if module in ['sklearn', 'Levenshtein']:
                print(f"⚠️  {name} - Not installed (optional, will use fallback)")
            else:
                print(f"❌ {name} - NOT INSTALLED (required)")
                all_ok = False
    
    return all_ok


def test_env_variables():
    """Check if environment variables are set"""
    print("\nTesting environment variables...")
    
    # Try to load .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ .env file loaded")
    except Exception as e:
        print(f"⚠️  Could not load .env file: {e}")
    
    required_vars = [
        ('PGDATABASE', 'PostgreSQL database name'),
        ('PGHOST', 'PostgreSQL host'),
        ('PGUSER', 'PostgreSQL user'),
        ('PGPASSWORD', 'PostgreSQL password'),
        ('JIRA_URL', 'JIRA URL'),
        ('JIRA_USERNAME', 'JIRA username'),
        ('JIRA_API_TOKEN', 'JIRA API token')
    ]
    
    all_ok = True
    for var, desc in required_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if 'PASSWORD' in var or 'TOKEN' in var:
                masked = value[:4] + '****' + value[-4:] if len(value) > 8 else '****'
                print(f"✅ {var}: {masked}")
            else:
                print(f"✅ {var}: {value}")
        else:
            print(f"❌ {var} - NOT SET")
            all_ok = False
    
    return all_ok


def test_postgresql_connection():
    """Test PostgreSQL database connection"""
    print("\nTesting PostgreSQL connection...")
    
    try:
        import psycopg2
        conn = psycopg2.connect(
            database=os.getenv('PGDATABASE'),
            host=os.getenv('PGHOST'),
            port=int(os.getenv('PGPORT', 5432)),
            user=os.getenv('PGUSER'),
            password=os.getenv('PGPASSWORD')
        )
        print("✅ PostgreSQL connection - OK")
        
        # Test query
        cur = conn.cursor()
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        print(f"   PostgreSQL version: {version.split(',')[0]}")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {str(e)}")
        return False


def test_jira_connection():
    """Test JIRA connection"""
    print("\nTesting JIRA connection...")
    
    try:
        from jira import JIRA
        jira_client = JIRA(
            server=os.getenv('JIRA_URL'),
            basic_auth=(
                os.getenv('JIRA_USERNAME'),
                os.getenv('JIRA_API_TOKEN')
            )
        )
        
        # Test by getting current user
        myself = jira_client.myself()
        print(f"✅ JIRA connection - OK")
        print(f"   Logged in as: {myself.get('displayName', 'Unknown')}")
        return True
    except Exception as e:
        print(f"❌ JIRA connection failed: {str(e)}")
        return False


def test_package_import():
    """Test importing the regression_jira_mcp package"""
    print("\nTesting package import...")
    
    try:
        from regression_jira_mcp import __version__
        print(f"✅ regression_jira_mcp package - OK")
        print(f"   Version: {__version__}")
        return True
    except Exception as e:
        print(f"❌ Package import failed: {str(e)}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Regression-JIRA MCP Installation Test")
    print("=" * 60)
    
    results = []
    
    results.append(("Python Version", test_python_version()))
    results.append(("Dependencies", test_dependencies()))
    results.append(("Environment Variables", test_env_variables()))
    results.append(("Package Import", test_package_import()))
    results.append(("PostgreSQL Connection", test_postgresql_connection()))
    results.append(("JIRA Connection", test_jira_connection()))
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:.<40} {status}")
    
    all_passed = all(result for _, result in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All tests passed! System is ready to use.")
        print("\nNext steps:")
        print("1. Configure MCP server in Cline settings")
        print("2. Restart Cline/VSCode")
        print("3. Start using with natural language queries!")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        print("\nRefer to SETUP_GUIDE.md for troubleshooting tips.")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
