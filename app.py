from flask import Flask, render_template, request, redirect, url_for, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hrc_navate.db'
db = SQLAlchemy(app)

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

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username="admin").first():
        db.session.add(User(username="admin", password="admin123", role="admin"))
        db.session.commit()

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
    if 'user' not in session:
        return redirect('/')
    user = session['user']
    records = Record.query.filter_by(user_id=user['id']).all()
    projects = Project.query.all()
    return render_template('dashboard.html', user=user, records=records, projects=projects)

@app.route('/add_record', methods=['POST'])
def add_record():
    user = session['user']
    rec = Record(
        user_id=user['id'],
        project_id=request.form['project_id'],
        date=request.form['date'],
        amount=request.form['amount'],
        note=request.form['note']
    )
    db.session.add(rec)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/edit_record/<int:id>', methods=['POST'])
def edit_record(id):
    rec = Record.query.get(id)
    rec.project_id = request.form['project_id']
    rec.amount = request.form['amount']
    rec.note = request.form['note']
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/projects')
def projects():
    user = session['user']
    if user['role'] != 'admin':
        return redirect('/')
    all_projects = Project.query.all()
    return render_template('projects.html', projects=all_projects)

@app.route('/add_project', methods=['POST'])
def add_project():
    p = Project(name=request.form['name'], unit_type=request.form['unit_type'])
    db.session.add(p)
    db.session.commit()
    return redirect(url_for('projects'))

@app.route('/project/<int:id>')
def project_detail(id):
    proj = Project.query.get(id)
    records = Record.query.filter_by(project_id=id).all()
    return render_template('admin.html', project=proj, records=records)

@app.route('/export/pdf')
def export_pdf():
    user = session['user']
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(100, 800, f"HRC & Navate - Týždenný report: {user['username']}")
    y = 770
    records = Record.query.filter_by(user_id=user['id']).all()
    for r in records:
        proj = Project.query.get(r.project_id)
        p.drawString(100, y, f"{r.date} | {proj.name} | {r.amount} {proj.unit_type} | {r.note}")
        y -= 20
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name='report.pdf', mimetype='application/pdf')

if __name__ == '__main__':
    app.run(debug=True)

