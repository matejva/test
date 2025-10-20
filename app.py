from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import io, os, logging
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

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

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# ---------- MODELS ----------
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    email = db.Column(db.String(120))
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


@app.route('/dashboard', methods=['GET'])
def dashboard():
    session_user = session.get('user')
    if not session_user:
        return redirect(url_for('login'))

    selected_user = request.args.get('user_id', type=int)
    selected_project = request.args.get('project_id', type=int)

    query = Record.query

    # 🔹 ak je admin, môže filtrovať
    if session_user.get('is_admin'):
        if selected_user:
            query = query.filter_by(user_id=selected_user)
    else:
        query = query.filter_by(user_id=session_user['id'])

    if selected_project:
        query = query.filter_by(project_id=selected_project)

    records = query.order_by(Record.date.desc()).all()
    projects = Project.query.order_by(Project.name).all()
    users = User.query.order_by(User.name).all() if session_user.get('is_admin') else []

    total = sum([r.amount for r in records]) if records else 0
    project_count = len(set(r.project_id for r in records)) if records else 0

    # 📊 Výkon podľa dní
    date_map = {}
    for r in records:
        date_map[r.date] = date_map.get(r.date, 0) + r.amount
    chart_labels = list(date_map.keys())
    chart_values = list(date_map.values())

    # 🥧 Výkon podľa projektu
    project_map = {}
    for r in records:
        pname = r.project.name if r.project else "Neznámy projekt"
        project_map[pname] = project_map.get(pname, 0) + r.amount
    project_labels = list(project_map.keys())
    project_values = list(project_map.values())

    return render_template(
        'dashboard.html',
        user=session_user,
        users=users,
        projects=projects,
        records=records,
        total=total,
        project_count=project_count,
        chart_labels=chart_labels,
        chart_values=chart_values,
        project_labels=project_labels,
        project_values=project_values,
        selected_user=selected_user,
        selected_project=selected_project
    )


@app.route('/add_record', methods=['POST'])
def add_record():
    session_user = session.get('user')
    if not session_user:
        return redirect(url_for('login'))

    rec = Record(
        user_id=session_user['id'],
        project_id=int(request.form['project_id']),
        date=request.form['date'],
        amount=float(request.form['amount']) if request.form['amount'] else 0,
        note=request.form.get('note')
    )
    db.session.add(rec)
    db.session.commit()
    flash("Záznam bol pridaný!", "success")
    return redirect(url_for('dashboard'))


# -------- Projekty --------
@app.route('/projects')
def projects():
    user = session.get('user')
    if not user or not user.get('is_admin'):
        return redirect(url_for('login'))
    all_projects = Project.query.order_by(Project.name).all()
    return render_template('project.html', projects=all_projects, user=user)


@app.route('/add_project', methods=['POST'])
def add_project():
    user = session.get('user')
    if not user or not user.get('is_admin'):
        return redirect(url_for('login'))
    name = request.form['name']
    unit_type = request.form['unit_type']
    p = Project(name=name, unit_type=unit_type)
    db.session.add(p)
    db.session.commit()
    flash("✅ Projekt pridaný!", "success")
    return redirect(url_for('projects'))


@app.route('/project/<int:id>')
def project_detail(id):
    user = session.get('user')
    if not user or not user.get('is_admin'):
        return redirect(url_for('login'))
    proj = Project.query.get_or_404(id)
    records = Record.query.filter_by(project_id=id).order_by(Record.date.desc()).all()
    details, agg = [], {}
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
    return render_template('project_detail.html', project=proj, details=details, per_user=per_user,
                           total_h=total_h, total_m2=total_m2)


# ---------- USERS ----------
@app.route('/users')
def users_list():
    user = session.get('user')
    if not user or not user.get('is_admin'):
        return redirect(url_for('login'))

    all_users = User.query.order_by(User.name).all()
    return render_template('users.html', users=all_users, user=user)

@app.route('/create_user', methods=['GET', 'POST'])
def create_user():
    user = session.get('user')
    if not user or not user.get('is_admin'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        email = request.form.get('email')
        password = request.form['password']
        is_admin = bool(request.form.get('is_admin'))

        if User.query.filter_by(name=name).first():
            flash("Používateľ s týmto menom už existuje.", "danger")
            return redirect(url_for('create_user'))

        new_user = User(name=name, email=email, password=generate_password_hash(password), is_admin=is_admin)
        db.session.add(new_user)
        db.session.commit()
        flash("✅ Používateľ bol vytvorený!", "success")
        return redirect(url_for('users_list'))

    return render_template('create_user.html', user=user)


@app.route('/documents', methods=['GET', 'POST'])
def documents():
    session_user = session.get('user')
    if not session_user:
        return redirect(url_for('login'))

    if request.method == 'POST':
        file = request.files.get('file')
        if file and file.filename:
            safe = secure_filename(file.filename)
            fname = f"{session_user['id']}_{int(datetime.utcnow().timestamp())}_{safe}"
            path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
            file.save(path)
            doc = Document(user_id=session_user['id'], filename=fname)
            db.session.add(doc)
            db.session.commit()
            flash("Dokument nahraný!", "success")
            return redirect(url_for('documents'))
        flash("Nebolo možné nahrať súbor.", "danger")

    user_docs = Document.query.filter_by(user_id=session_user['id']).all()
    return render_template('documents.html', documents=user_docs)


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    session_user = session.get('user')
    if not session_user:
        return redirect(url_for('login'))
    doc = Document.query.filter_by(filename=filename).first_or_404()
    if not (session_user.get('is_admin') or doc.user_id == session_user['id']):
        flash("Nemáte prístup k tomuto súboru.")
        return redirect(url_for('documents'))
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


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
