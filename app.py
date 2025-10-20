from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from flask_sqlalchemy import SQLAlchemy
import os, io, logging, traceback
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# ---------- ZÁKLADNÁ KONFIGURÁCIA ----------
app = Flask(__name__)
app.secret_key = "supersecretkey"

# PostgreSQL connection
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    "DATABASE_URL",
    "postgresql://we_app_db_user:Ueezs3eWQnGzhcKoUTZtijAHJ46RWmDI@dpg-d3lorabipnbc73a6llq0-a/we_app_db"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
logging.basicConfig(level=logging.DEBUG)

# ---------- MODELY ----------
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(50))
    role = db.Column(db.String(10))

    @property
    def name(self):
        return self.username

    @property
    def is_admin(self):
        return self.role == "admin"

class Project(db.Model):
    __tablename__ = "projects"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    unit_type = db.Column(db.String(10))

class Record(db.Model):
    __tablename__ = "records"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    date = db.Column(db.String(20))
    amount = db.Column(db.Float)
    note = db.Column(db.String(200))

class Document(db.Model):
    __tablename__ = "documents"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    filename = db.Column(db.String(100))

# ---------- DB INIT ----------
with app.app_context():
    try:
        db.create_all()
        print("✅ DB connected and tables created")

        # Admin user
        if not User.query.filter_by(username="admin").first():
            db.session.add(User(
                username="admin",
                email="admin@example.com",
                password="admin123",
                role="admin"
            ))
            db.session.commit()
            print("✅ Admin user created")
    except Exception as e:
        print("❌ DB INIT ERROR:", e)
        print(traceback.format_exc())

# ---------- ERROR HANDLER ----------
@app.errorhandler(Exception)
def handle_exception(e):
    logging.error("Exception: %s", traceback.format_exc())
    return "Internal Server Error - check logs", 500

# ---------- ROUTY ----------
@app.route('/')
def login():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def do_login():
    user = User.query.filter_by(username=request.form['username'], password=request.form['password']).first()
    if user:
        session['user'] = {'id': user.id, 'username': user.username, 'role': user.role}
        return redirect(url_for('dashboard'))
    return render_template('login.html', error="Zlé meno alebo heslo")

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    user = session.get('user')
    if not user:
        return redirect('/')
    records = Record.query.filter_by(user_id=user['id']).all()
    projects = Project.query.all()
    total = sum([r.amount for r in records])
    return render_template('dashboard.html', user=user, records=records, projects=projects, total=total)

@app.route('/users')
def users():
    user = session.get('user')
    if not user or user['role'] != 'admin':
        return redirect('/')
    all_users = User.query.all()
    return render_template('user.html', users=all_users)

# (ostatné routes ako add_record, edit_record, projects, add_project, project_detail, export_pdf zostávajú rovnaké)

# ---------- ŠTART ----------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)  # debug=True len pre test
