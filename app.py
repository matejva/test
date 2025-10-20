from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash, jsonify, send_from_directory, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import logging
import os

# ---------- CONFIG ----------
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    "DATABASE_URL",
    "postgresql://postgresdatabase_aeol_user:IUYLlFKRzHgCEzRwwxScNz1xMgfKdjTq@dpg-d3r0toodl3ps73ca6on0-a/postgresdatabase_aeol"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.INFO
)

# ---------- MODELS ----------
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(200))
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
    user = db.relationship("User", backref="records")
    project = db.relationship("Project", backref="records")

class Document(db.Model):
    __tablename__ = "documents"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    filename = db.Column(db.String(200))
    user = db.relationship("User", backref="documents")

# ---------- ROUTES ----------
@app.route('/')
def login():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def do_login():
    name = request.form['username']
    password = request.form['password']
    user = User.query.filter_by(name=name).first()
    if user and check_password_hash(user.password, password):
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
    records = Record.query.filter_by(user_id=user['id']).order_by(Record.date.desc()).all()
    projects = Project.query.order_by(Project.name).all()
    total = sum([r.amount for r in records]) if records else 0
    return render_template('dashboard.html', user=user, records=records, projects=projects, total=total)

@app.route('/add_record', methods=['POST'])
def add_record():
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))
    rec = Record(
        user_id=user['id'],
        project_id=int(request.form['project_id']),
        date=request.form['date'],
        amount=float(request.form['amount']) if request.form['amount'] else 0,
        note=request.form.get('note')
    )
    db.session.add(rec)
    db.session.commit()
    flash("Záznam pridaný!")
    return redirect(url_for('dashboard'))

@app.route('/entry/<int:id>/json')
def entry_json(id):
    user = session.get('user')
    if not user:
        return jsonify({'error': 'not logged'}), 401
    r = Record.query.get_or_404(id)
    if r.user_id != user['id'] and not user.get('is_admin'):
        return jsonify({'error': 'forbidden'}), 403
    return jsonify({
        'id': r.id,
        'user_id': r.user_id,
        'project_id': r.project_id,
        'date': r.date,
        'amount': r.amount,
        'note': r.note or ''
    })

@app.route('/entry/update', methods=['POST'])
def entry_update():
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))
    rid = int(request.form.get('id'))
    r = Record.query.get_or_404(rid)
    if r.user_id != user['id'] and not user.get('is_admin'):
        flash("Nemáte oprávnenie upraviť tento záznam.")
        return redirect(url_for('dashboard'))
    r.project_id = int(request.form.get('project_id'))
    r.date = request.form.get('date')
    r.amount = float(request.form.get('amount') or 0)
    r.note = request.form.get('note')
    db.session.commit()
    flash("Záznam upravený.")
    return redirect(url_for('dashboard'))

@app.route('/delete_record/<int:id>', methods=['POST'])
def delete_record(id):
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))
    r = Record.query.get_or_404(id)
    if r.user_id != user['id'] and not user.get('is_admin'):
        flash("Nemáte oprávnenie zmazať tento záznam.")
        return redirect(url_for('dashboard'))
    db.session.delete(r)
    db.session.commit()
    flash("Záznam zmazaný.")
    return redirect(url_for('dashboard'))

@app.route('/projects')
def projects():
    user = session.get('user')
    if not user or not user['is_admin']:
        return redirect(url_for('login'))
    all_projects = Project.query.order_by(Project.name).all()
    return render_template('project.html', projects=all_projects)

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
    proj = Project.query.get_or_404(id)
    records = Record.query.filter_by(project_id=id).order_by(Record.date.desc()).all()
    details = []
    agg = {}
    for r in records:
        uname = r.user.name if r.user else 'Neznámy'
        details.append({'username': uname, 'date': r.date, 'amount': r.amount, 'note': r.note})
        agg.setdefault(uname, {'h': 0.0, 'm2': 0.0})
        if proj.unit_type == 'hodiny':
            agg[uname]['h'] += (r.amount or 0)
        else:
            agg[uname]['m2'] += (r.amount or 0)
    per_user = [{'user': k, 'h': v['h'], 'm2': v['m2']} for k, v in agg.items()]
    total_h = sum(x['h'] for x in per_user)
    total_m2 = sum(x['m2'] for x in per_user)
    return render_template('project_detail.html', project=proj, details=details, per_user=per_user, total_h=total_h, total_m2=total_m2)

@app.route('/users')
def users_list():
    user = session.get('user')
    if not user or not user['is_admin']:
        return redirect(url_for('login'))
    all_users = User.query.order_by(User.name).all()
    return render_template('users.html', users=all_users)

@app.route('/documents', methods=['GET', 'POST'])
def documents():
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))
    if request.method == 'POST':
        file = request.files.get('file')
        if file and file.filename:
            safe = secure_filename(file.filename)
            fname = f"{user['id']}_{int(datetime.utcnow().timestamp())}_{safe}"
            path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
            file.save(path)
            doc = Document(user_id=user['id'], filename=fname)
            db.session.add(doc)
            db.session.commit()
            flash("Dokument nahraný!")
            return redirect(url_for('documents'))
        flash("Nebolo možné nahrať súbor.", "danger")
    user_docs = Document.query.filter_by(user_id=user['id']).all()
    return render_template('documents.html', documents=user_docs)

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))
    doc = Document.query.filter_by(filename=filename).first_or_404()
    if not (user.get('is_admin') or doc.user_id == user['id']):
        flash("Nemáte prístup k tomuto súboru.")
        return redirect(url_for('documents'))
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

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
    records = Record.query.filter_by(user_id=user['id']).order_by(Record.date.desc()).all()
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

@app.route('/fix_admin')
def fix_admin():
    from werkzeug.security import generate_password_hash
    admin = User.query.filter_by(name='admin').first()
    if admin:
        admin.password = generate_password_hash('admin123')
        db.session.commit()
        return "✅ Admin heslo resetnuté na admin123"
    else:
        return "❌ Admin neexistuje"

# ---------- DB INIT ----------
with app.app_context():
    db.create_all()
    if not User.query.filter_by(name="admin").first():
        admin = User(
            name='admin',
            email='admin@example.com',
            password=generate_password_hash('admin123'),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        app.logger.info("✅ Admin user created (admin / admin123)")

# ---------- RUN ----------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

