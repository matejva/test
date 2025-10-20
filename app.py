from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import logging
import os

# ---------- CONFIG ----------
app = Flask(__name__)

# Secret key from environment, fallback for dev
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# Database URI from environment variable (Render)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgresdatabase_aeol_user:IUYLlFKRzHgCEzRwwxScNz1xMgfKdjTq@dpg-d3r0toodl3ps73ca6on0-a/postgresdatabase_aeol"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
logging.basicConfig(level=logging.DEBUG)

# ---------- MODELS ----------
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(50))
    is_admin = db.Column(db.Boolean, default=False)

class Project(db.Model):
    __tablename__ = "projects"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    unit_type = db.Column(db.String(10))  # "hodiny" alebo "m2"

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
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    filename = db.Column(db.String(100))

# ---------- ROUTES ----------
@app.route('/')
def login():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def do_login():
    name = request.form['username']
    password = request.form['password']
    user = User.query.filter_by(name=name, password=password).first()
    if user:
        session['user'] = {'id': user.id, 'name': user.name, 'is_admin': user.is_admin}
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
        return redirect(url_for('login'))
    records = Record.query.filter_by(user_id=user['id']).all()
    projects = Project.query.all()
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
        amount=request.form['amount'],
        note=request.form['note']
    )
    db.session.add(rec)
    db.session.commit()
    flash("Záznam pridaný!")
    return redirect(url_for('dashboard'))

@app.route('/projects')
def projects():
    user = session.get('user')
    if not user or not user['is_admin']:
        return redirect(url_for('login'))
    all_projects = Project.query.all()
    return render_template('projekt.html', projects=all_projects)

@app.route('/add_project', methods=['POST'])
def add_project():
    user = session.get('user')
    if not user or not user['is_admin']:
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
    if not user or not user['is_admin']:
        return redirect(url_for('login'))
    proj = Project.query.get(id)
    records = Record.query.filter_by(project_id=id).all()
    details = []
    for r in records:
        u = User.query.get(r.user_id)
        details.append({
            'user_name': u.name if u else 'Neznámy',
            'date': r.date,
            'amount': r.amount,
            'note': r.note
        })
    return render_template('admin.html', project=proj, details=details)

@app.route('/export/pdf')
def export_pdf():
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(100, 800, f"HRC & Navate - Týždenný report: {user['name']}")
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

# ---------- RUN ----------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
