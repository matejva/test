from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import io, os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# ---------- ZÁKLADNÁ KONFIGURÁCIA ----------
app = Flask(__name__)
app.secret_key = "supersecretkey"

# PostgreSQL databáza na Render
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://we_app_db_user:Ueezs3eWQnGzhcKoUTZtijAHJ46RWmDI@dpg-d3lorabipnbc73a6llq0-a/we_app_db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)

# ---------- MODELY ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(50), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

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

    user = db.relationship('User', backref='records')
    project = db.relationship('Project', backref='records')

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    filename = db.Column(db.String(100), nullable=False)

# ---------- DB INIT ----------
with app.app_context():
    db.create_all()
    # Vytvorenie admin účtu, ak neexistuje
    try:
        if not User.query.filter_by(name="admin").first():
            db.session.add(User(name="admin", email="admin@test.com", password="admin123", is_admin=True))
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
    user = User.query.filter_by(name=request.form['username'], password=request.form['password']).first()
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
    if not user or not user.get('is_admin'):
        return redirect(url_for('dashboard'))
    all_projects = Project.query.all()
    return render_template('project.html', projects=all_projects)

@app.route('/add_project', methods=['POST'])
def add_project():
    user = session.get('user')
    if not user or not user.get('is_admin'):
        return redirect(url_for('dashboard'))
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
    if not user or not user.get('is_admin'):
        return redirect(url_for('dashboard'))
    proj = Project.query.get(id)
    records = Record.query.filter_by(project_id=id).all()
    return render_template('admin.html', project=proj, records=records)

@app.route('/documents', methods=['GET', 'POST'])
def documents():
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))

    if request.method == 'POST':
        if 'file' not in request.files:
            flash("Nebolo vybrané žiadne súbor!")
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash("Nebolo vybrané žiadne súbor!")
            return redirect(request.url)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        doc = Document(user_id=user['id'], filename=file.filename)
        db.session.add(doc)
        db.session.commit()
        flash("Súbor úspešne nahraný!")
        return redirect(url_for('documents'))

    docs = Document.query.filter_by(user_id=user['id']).all()
    return render_template('documents.html', documents=docs)

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
        line = f"{r.date} | {r.project.name if r.project else 'N/A'} | {r.amount} {r.project.unit_type if r.project else ''} | {r.note or ''}"
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
