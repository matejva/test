from app import db, User, app
from werkzeug.security import generate_password_hash

with app.app_context():
    try:
        db.create_all()  # vytvorí všetky tabuľky
        admin = User.query.filter_by(name="admin").first()
        if not admin:
            hashed_pw = generate_password_hash("admin123")
            admin = User(
                name='admin',
                email='admin@example.com',
                password=hashed_pw,
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin user created (admin / admin123)")
        else:
            print("ℹ️ Admin already exists")
    except Exception as e:
        print("❌ DB INIT ERROR:", e)
