from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import io, logging
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# ---------- KONFIGURÁCIA ----------
app = Flask(__name__)
app.secret_key = "supersecretkey"
# PostgreSQL connection string
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://we_app_db_user:Ueezs3eWQnGzhcKoUTZtijAHJ46RWmDI@dpg-d3lorabipnbc73a6llq0-a/we_app_db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
logging.basicConfig(level=logging.DEBUG)

# ---------- MODELY ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # "admin" alebo "user"

    @property
    def is_admin(self):
        return self.role == "admin"

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    unit_type = db.Column(db.String(10), nullable=False)  # "hodiny" alebo "m2"

class Record(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    note = db.Column(db.String(200))

    user = db.relationship("User", backref="records")
    project = db.relationship("Project", backref="records")

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    filename = db.Column(db.String(100), nullable=False)

# ---------- DB INIT ----------
with app.app_context():
    db.create_all()
    try:
        if not User.query.filter_by(username="admin").first():
            db.session.add(User(username="admin", email="admin@example.com", password="admin123", role="admin"))
            db.session.commit()
            print("✅ Admin vytvorený (admin / admin123)")
    except Exception as e:
        print("❌ DB INIT ERROR:", e)

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

# ---------- DASHBOARD ----------
@app.route('/dashboard')
def dashboard():
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))

    records = Record.query.filter_by(user_id=user['id']).all()
    projects = Project.query.all()
    for r in records:
        r.project = Project.query.get(r.project_id)

    total = sum([r.amount for r in records])
    return render_template('dashboard.html', user=user, records=records, projects=projects, total=total)

@app.route('/add_record', methods=['POST'])
def add_record():
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))

    rec = Record(
        user_id=user['id'],
        project_id=request.form['project_id'],
        date=request.form['date'],
        amount=float(request.form['amount']),
        note=request.form['note']
    )
    db.session.add(rec)
    db.session.commit()
    flash("Záznam pridaný!")
    return redirect(url_for('dashboard'))

@app.route('/edit_record/<int:id>', methods=['POST'])
def edit_record(id):
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))

    rec = Record.query.get(id)
    if rec and rec.user_id == user['id']:
        rec.project_id = request.form['project_id']
        rec.amount = float(request.form['amount'])
        rec.note = request.form['note']
        db.session.commit()
        flash("Záznam upravený.")
    return redirect(url_for('dashboard'))

# ---------- PROJEKTY ----------
@app.route('/projects')
def projects():
    user = session.get('user')
    if not user or user['role'] != 'admin':
        return redirect(url_for('login'))
    all_projects = Project.query.all()
    return render_template('projekt.html', projects=all_projects)

@app.route('/add_project', methods=['POST'])
def add_project():
    user = session.get('user')
    if not user or user['role'] != 'admin':
        return redirect(url_for('login'))
    name = request.form['name']
    unit_type = request.form['unit_type']
    p = Project(name=name, unit_type=unit_type)
    db.session.add(p)
    db.session.commit()
    flash("Projekt pridaný.")
    return redirect(url_for('projects'))

@app.route('/project/<int:id>')
def project_detail(id):
    user = session.get('user')
    if not user or user['role'] != 'admin':
        return redirect(url_for('login'))
    proj = Project.query.get(id)
    records = Record.query.filter_by(project_id=id).all()
    details = []
    for r in records:
        u = User.query.get(r.user_id)
        details.append({
            'username': u.username if u else 'Neznámy',
            'date': r.date,
            'amount': r.amount,
            'note': r.note
        })
    return render_template('admin.html', project=proj, details=details)

# ---------- POUŽÍVATELIA ----------
@app.route('/users')
def users():
    user = session.get('user')
    if not user or user['role'] != 'admin':
        return redirect(url_for('login'))
    all_users = User.query.all()
    return render_template('users.html', users=all_users)

@app.route('/create_user', methods=['GET', 'POST'])
def create_user():
    user = session.get('user')
    if not user or user['role'] != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = "admin" if request.form.get('is_admin') else "user"
        u = User(username=username, email=email, password=password, role=role)
        db.session.add(u)
        db.session.commit()
        flash("Používateľ vytvorený.")
        return redirect(url_for('users'))
    return render_template('create_user.html')

# ---------- PDF EXPORT ----------
@app.route('/export/pdf')
def export_pdf():
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(100, 800, f"HRC & Navate - Týždenný report: {user['username']}")
    y = 770
    records = Record.query.filter_by(user_id=user['id']).all()
    for r in records:
        proj = Project.query.get(r.project_id)
        line = f"{r.date} | {proj.name if proj else 'N/A'} | {r.amount} {proj.unit_type if proj else ''} | {r.note or ''}"
        p.drawString(100, y, line)
        y -= 20
        if y < 50:
            p.showPage()
            y = 800
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name='report.pdf', mimetype='application/pdf')

# ---------- ŠTART ----------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
