from app import db, User
import getpass

def main():
    name = input("Admin meno: ").strip()
    email = input("Email (voliteľný): ").strip() or None
    pw = getpass.getpass("Heslo: ")
    if User.query.filter_by(name=name).first():
        print("Používateľ s týmto menom už existuje.")
        return
    u = User(name=name, email=email, is_admin=True)
    u.set_password(pw)
    db.session.add(u)
    db.session.commit()
    print("Admin vytvorený.")

if __name__ == '__main__':
    from app import app
    with app.app_context():
        db.create_all()
        main()
