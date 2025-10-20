from app import db, User
from app import app

with app.app_context():
    try:
        db.create_all()  # vytvorí všetky tabuľky
        if not User.query.filter_by(name="admin").first():
            admin = User(name='admin', email='admin@example.com', password='admin123', is_admin=True)
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin user created (admin / admin123)")
        else:
            print("ℹ️ Admin already exists")
    except Exception as e:
        print("❌ DB INIT ERROR:", e)
