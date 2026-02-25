#!/usr/bin/env python
"""
Database initialization script.
This script creates all missing tables, including the new 'ayats' table.
Run this when you see: "Table 'tanse_db.ayats' doesn't exist"
"""

import sys
import os

# Add the parent directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from my_app.app import app, db
from my_app.models import User, School, Student, Classroom, Violation, ViolationRule, ViolationCategory, Ayat, ViolationPhoto

def init_database():
    """Initialize database by creating all tables."""
    with app.app_context():
        print("🔧 Initializing database...")
        
        try:
            # Create all tables that don't exist
            db.create_all()
            print("✅ Database initialized successfully!")
            print("   - All tables created (Ayat table included)")
            
        except Exception as e:
            print(f"❌ Error initializing database: {e}")
            return False
    
    return True

if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)
