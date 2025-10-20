from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import io, logging
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# ---------- ZÁKLADNÁ KONFIGURÁCIA ----------
app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hrc_navate.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
logging.basicConfig(level=logging.DEBUG)

# ---------- MODELY ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(50))
    role = db.Column(db.String(10))  # "admin" alebo "user"

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    unit_type = db.Column(db.String(10))  # "hodiny" alebo "m2"

class Record(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    date = db.Column(db.String(20))
    amount = db.Column(db.Float)
    note = db.Column(db.String(200))

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    filename = db.Column(db.String(100))

# ---------- DB INIT ----------
with app.app_context():
    db.create_all()
    try:
        if not User.query.filter_by(username="admin").first():
            db.session.add(User(username="admin", password="admin123", role="admin"))
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

@app.route('/dashboard')
def dashboard():
    user = session.get('user')
    if not user:
        return redirect('/')
    records = Record.query.filter_by(user_id=user['id']).all()
    projects = Project.query.all()

    # Automatický súčet za týždeň
    total = sum([r.amount for r in records])
    return render_template('dashboard.html', user=user, records=records, projects=projects, total=total)

@app.route('/add_record', methods=['POST'])
def add_record():
    user = session.get('user')
    if not user:
        return redirect('/')
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

@app.route('/edit_record/<int:id>', methods=['POST'])
def edit_record(id):
    user = session.get('user')
    if not user:
        return redirect('/')
    rec = Record.query.get(id)
    if rec and rec.user_id == user['id']:
        rec.project_id = request.form['project_id']
        rec.amount = request.form['amount']
        rec.note = request.form['note']
        db.session.commit()
        flash("Záznam upravený.")
    return redirect(url_for('dashboard'))

@app.route('/projects')
def projects():
    user = session.get('user')
    if not user or user['role'] != 'admin':
        return redirect('/')
    all_projects = Project.query.all()
    return render_template('projects.html', projects=all_projects)

@app.route('/add_project', methods=['POST'])
def add_project():
    user = session.get('user')
    if not user or user['role'] != 'admin':
        return redirect('/')
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
        return redirect('/')
    proj = Project.query.get(id)
    records = Record.query.filter_by(project_id=id).all()
    # Získaj mená pracovníkov
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

@app.route('/export/pdf')
def export_pdf():
    user = session.get('user')
    if not user:
        return redirect('/')
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
    app.run(host='0.0.0.0', port=5000, debug=False)
