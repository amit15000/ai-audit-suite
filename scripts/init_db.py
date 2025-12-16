"""Initialize database and create test user."""
from __future__ import annotations

from app.core.database import init_db, get_session_factory
from app.core.config import get_settings
from app.services.core.auth_service import create_user, get_user_by_email

def main():
    """Initialize database and create test user."""
    print("Initializing database...")
    init_db()
    print("Database initialized!")
    
    # Create test user
    db = get_session_factory()()
    try:
        # Check if user already exists
        existing_user = get_user_by_email(db, "test@example.com")
        if existing_user:
            print("Test user already exists!")
            return
        
        user = create_user(db, "test@example.com", "test123", "Test User")
        print(f"Test user created: {user.email}")
        print("You can now login with:")
        print("  Email: test@example.com")
        print("  Password: test123")
    finally:
        db.close()

if __name__ == "__main__":
    main()

