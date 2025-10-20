from app import app, db
from sqlalchemy import text

print("🚀 Spúšťam úpravu databázy...")

with app.app_context():
    try:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE users ALTER COLUMN password TYPE VARCHAR(200);'))
            conn.commit()
        print("✅ Stĺpec 'password' bol upravený na VARCHAR(200).")
    except Exception as e:
        print(f"❌ Chyba počas úpravy databázy: {e}")
