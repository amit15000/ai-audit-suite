"""Test database connection and diagnose connection issues."""
from __future__ import annotations

import socket
import sys
from urllib.parse import urlparse

from app.core.config import get_settings
from app.core.database import get_engine
from sqlalchemy import text


def test_dns_resolution(hostname: str) -> tuple[bool, str]:
    """Test if hostname can be resolved."""
    try:
        ip = socket.gethostbyname(hostname)
        return True, f"✓ DNS resolution successful: {hostname} -> {ip}"
    except socket.gaierror as e:
        return False, f"✗ DNS resolution failed: {e}"


def test_port_connectivity(hostname: str, port: int, timeout: int = 5) -> tuple[bool, str]:
    """Test if port is accessible."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((hostname, port))
        sock.close()
        if result == 0:
            return True, f"✓ Port {port} is accessible"
        else:
            return False, f"✗ Port {port} is not accessible (connection refused)"
    except Exception as e:
        return False, f"✗ Port connectivity test failed: {e}"


def test_database_connection() -> tuple[bool, str]:
    """Test database connection."""
    try:
        settings = get_settings()
        db_url = settings.database.url
        
        print(f"\n📋 Database Configuration:")
        print(f"   URL: {db_url.split('@')[0]}@*** (password hidden)")
        
        # Parse URL to extract hostname
        parsed = urlparse(db_url)
        hostname = parsed.hostname
        port = parsed.port or 5432
        
        if not hostname:
            return False, "✗ Could not parse hostname from database URL"
        
        print(f"   Hostname: {hostname}")
        print(f"   Port: {port}")
        print(f"   Database: {parsed.path.lstrip('/')}")
        
        # Test DNS resolution
        print(f"\n🔍 Testing DNS Resolution...")
        dns_ok, dns_msg = test_dns_resolution(hostname)
        print(f"   {dns_msg}")
        
        if not dns_ok:
            return False, (
                "DNS resolution failed. Possible causes:\n"
                "  - Supabase project might be paused or deleted\n"
                "  - Network connectivity issues\n"
                "  - Incorrect hostname in database URL\n"
                "  - DNS server issues\n\n"
                "Please verify:\n"
                "  1. Your Supabase project is active (not paused)\n"
                "  2. The database URL in your .env file is correct\n"
                "  3. You can access the Supabase dashboard\n"
                "  4. Your network connection is working"
            )
        
        # Test port connectivity
        print(f"\n🔍 Testing Port Connectivity...")
        port_ok, port_msg = test_port_connectivity(hostname, port)
        print(f"   {port_msg}")
        
        if not port_ok:
            return False, (
                f"Port {port} is not accessible. Possible causes:\n"
                "  - Firewall blocking the connection\n"
                "  - Supabase database is not accepting connections\n"
                "  - Network restrictions"
            )
        
        # Test actual database connection
        print(f"\n🔍 Testing Database Connection...")
        try:
            engine = get_engine()
            with engine.connect() as conn:
                result = conn.execute(text("SELECT version()"))
                version = result.fetchone()[0]
                print(f"   ✓ Database connection successful!")
                print(f"   PostgreSQL version: {version.split(',')[0]}")
        except Exception as conn_error:
            error_str = str(conn_error)
            if "SSL" in error_str or "ssl" in error_str.lower():
                return False, (
                    "SSL connection error. Supabase requires SSL connections.\n"
                    "The connection has been configured with SSL support.\n"
                    f"Original error: {error_str}\n\n"
                    "If this persists, check:\n"
                    "  1. Your Supabase project SSL settings\n"
                    "  2. Network/firewall settings that might block SSL connections"
                )
            raise
        
        return True, "✓ All connection tests passed!"
        
    except Exception as e:
        error_msg = str(e)
        if "getaddrinfo failed" in error_msg or "failed to resolve host" in error_msg:
            return False, (
                "DNS resolution error. The hostname cannot be resolved.\n"
                "Please check:\n"
                "  1. Your Supabase project status in the dashboard\n"
                "  2. The database URL is correct\n"
                "  3. Your internet connection"
            )
        elif "authentication failed" in error_msg.lower() or "password" in error_msg.lower():
            return False, (
                "Authentication failed. Please verify:\n"
                "  1. The database password in your .env file is correct\n"
                "  2. The username is correct (usually 'postgres')\n"
                "  3. Your Supabase credentials are up to date"
            )
        elif "server closed the connection" in error_msg:
            return False, (
                "Connection was closed by the server. Possible causes:\n"
                "  - Database server is overloaded\n"
                "  - Connection timeout\n"
                "  - Server-side restrictions"
            )
        else:
            return False, f"Connection error: {error_msg}"


def main():
    """Run database connection tests."""
    print("=" * 60)
    print("Database Connection Diagnostic Tool")
    print("=" * 60)
    
    success, message = test_database_connection()
    
    print(f"\n{'=' * 60}")
    if success:
        print("✅ RESULT: All tests passed!")
        print(message)
        sys.exit(0)
    else:
        print("❌ RESULT: Connection test failed!")
        print("\n" + message)
        print("\n💡 Troubleshooting Tips:")
        print("  1. Check your Supabase dashboard to ensure the project is active")
        print("  2. Verify the database URL in your .env file matches your Supabase settings")
        print("  3. Try accessing your Supabase project in the web dashboard")
        print("  4. Check if your Supabase project has been paused (free tier projects pause after inactivity)")
        print("  5. Verify your network connection and DNS settings")
        sys.exit(1)


if __name__ == "__main__":
    main()
