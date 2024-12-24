from app import app, db
from datetime import datetime

def recreate_database():
    with app.app_context():
        # Drop all tables
        db.drop_all()
        
        # Create all tables
        db.create_all()
        
        print("Database recreated successfully!")

if __name__ == '__main__':
    recreate_database()
