from app import app, db
from sqlalchemy import text

print("🚀 Upravujem databázu podľa nových modelov...")

with app.app_context():
    try:
        with db.engine.connect() as conn:
            # 1️⃣ Pridať unit_type do records
            conn.execute(text("""
                ALTER TABLE records ADD COLUMN IF NOT EXISTS unit_type VARCHAR(10);
            """))

            # 2️⃣ Odstrániť unit_type z projects (ak existuje)
            try:
                conn.execute(text("""
                    ALTER TABLE projects DROP COLUMN IF EXISTS unit_type;
                """))
            except Exception as e:
                print(f"⚠️ Nepodarilo sa odstrániť projects.unit_type: {e}")

            conn.commit()
        print("✅ Úpravy databázy dokončené.")
    except Exception as e:
        print(f"❌ Chyba počas úpravy: {e}")
