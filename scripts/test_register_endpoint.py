"""Test the registration endpoint to diagnose 400 errors."""
from __future__ import annotations

import json
import sys

import httpx


def test_register(email: str, password: str, name: str | None = None) -> None:
    """Test the registration endpoint."""
    url = "http://localhost:8001/api/v1/auth/register"
    
    payload = {
        "email": email,
        "password": password,
    }
    if name:
        payload["name"] = name
    
    print(f"Testing registration endpoint: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print()
    
    try:
        response = httpx.post(url, json=payload, timeout=10.0)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print()
        
        try:
            response_data = response.json()
            print(f"Response Body:")
            print(json.dumps(response_data, indent=2))
        except Exception:
            print(f"Response Body (raw):")
            print(response.text)
        
        print()
        
        if response.status_code == 201:
            print("✅ Registration successful!")
            return
        elif response.status_code == 400:
            print("❌ 400 Bad Request - Possible causes:")
            print("  1. Validation error (check email format, password length >= 6)")
            print("  2. User already exists")
            print("  3. Invalid request format")
            if "response_data" in locals():
                error_code = response_data.get("detail", {}).get("error", {}).get("code", "UNKNOWN")
                error_msg = response_data.get("detail", {}).get("error", {}).get("message", "Unknown error")
                print(f"\n  Error Code: {error_code}")
                print(f"  Error Message: {error_msg}")
        elif response.status_code == 500:
            print("❌ 500 Internal Server Error - Check:")
            print("  1. Database connection (run: python scripts/test_db_connection.py)")
            print("  2. Database tables initialized (run: python scripts/init_db.py)")
            print("  3. Server logs for detailed error")
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
        
    except httpx.ConnectError:
        print("❌ Connection Error: Could not connect to server")
        print("   Make sure the server is running on http://localhost:8001")
        print("   Start with: uvicorn app.main:app --reload --port 8001")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def main():
    """Run registration tests."""
    print("=" * 60)
    print("Registration Endpoint Test")
    print("=" * 60)
    print()
    
    # Test 1: Valid registration
    print("Test 1: Valid Registration")
    print("-" * 60)
    test_register("test@example.com", "test123", "Test User")
    print()
    
    # Test 2: Invalid email
    print("Test 2: Invalid Email Format")
    print("-" * 60)
    test_register("invalid-email", "test123", "Test User")
    print()
    
    # Test 3: Short password
    print("Test 3: Password Too Short")
    print("-" * 60)
    test_register("test2@example.com", "12345", "Test User")
    print()
    
    # Test 4: Missing password
    print("Test 4: Missing Password")
    print("-" * 60)
    try:
        url = "http://localhost:8001/api/v1/auth/register"
        response = httpx.post(url, json={"email": "test3@example.com"}, timeout=10.0)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")
    
    print()
    print("=" * 60)
    print("Tests Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
