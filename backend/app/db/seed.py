"""
FinSight AI — Database Seeding Stub
===================================
Demo/mock dataset disabled. Live companies are fetched on-demand or seeded via nse_live_sync.
"""

from app.db.session import SessionLocal

def seed_database():
    """No-op seed function: Phase 4 operates exclusively on live fetched and authenticated data."""
    print("Database seeding: Phase 4 live mode active. Mock seed skipped.")
    return True

if __name__ == "__main__":
    seed_database()
