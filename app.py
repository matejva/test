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


class Record(db.Model):
    __tablename__ = "records"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    date = db.Column(db.String(20))
    amount = db.Column(db.Float)
    unit_type = db.Column(db.String(10))  # hodiny alebo m2
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


# ---------- DASHBOARD ----------
@app.route('/dashboard', methods=['GET'])
def dashboard():
    session_user = session.get('user')
    if not session_user:
        return redirect(url_for('login'))

    selected_user = request.args.get('user_id', type=int)
    selected_project = request.args.get('project_id', type=int)

    query = Record.query
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

    # Výkon podľa dní
    date_map = {}
    for r in records:
        date_map[r.date] = date_map.get(r.date, 0) + r.amount
    chart_labels = list(date_map.keys())
    chart_values = list(date_map.values())

    # Výkon podľa projektu
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
        unit_type=request.form['unit_type'],
        note=request.form.get('note')
    )
    db.session.add(rec)
    db.session.commit()
    flash("Záznam bol pridaný!", "success")
    return redirect(url_for('dashboard'))


@app.route('/delete_record/<int:id>', methods=['POST'])
def delete_record(id):
    user = session.get('user')
    if not user or not user.get('is_admin'):
        return redirect(url_for('login'))
    rec = Record.query.get_or_404(id)
    db.session.delete(rec)
    db.session.commit()
    flash("Záznam bol odstránený.", "success")
    return redirect(url_for('dashboard'))


# ---------- PROJECTS ----------
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
    p = Project(name=name)
    db.session.add(p)
    db.session.commit()
    flash("✅ Projekt pridaný!", "success")
    return redirect(url_for('projects'))


@app.route('/delete_project/<int:id>', methods=['POST'])
def delete_project(id):
    user = session.get('user')
    if not user or not user.get('is_admin'):
        return redirect(url_for('login'))
    proj = Project.query.get_or_404(id)
    Record.query.filter_by(project_id=id).delete()
    db.session.delete(proj)
    db.session.commit()
    flash("Projekt bol odstránený.", "success")
    return redirect(url_for('projects'))


# ---------- PDF EXPORT ----------
@app.route('/export/pdf')
def export_pdf():
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))

    selected_user = request.args.get('user_id', type=int)
    selected_project = request.args.get('project_id', type=int)

    query = Record.query
    if user.get('is_admin') and selected_user:
        query = query.filter_by(user_id=selected_user)
    else:
        query = query.filter_by(user_id=user['id'])

    if selected_project:
        query = query.filter_by(project_id=selected_project)

    records = query.order_by(Record.date.desc()).all()

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    p.setFont("Helvetica-Bold", 18)
    p.drawString(50, height - 50, "HRC & Navate – Výkonnostný report")
    p.setFont("Helvetica", 10)
    p.drawString(50, height - 70, f"Generované: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    p.line(50, height - 75, width - 50, height - 75)

    y = height - 100
    p.setFont("Helvetica-Bold", 11)
    p.drawString(60, y, "Dátum")
    p.drawString(120, y, "Používateľ")
    p.drawString(230, y, "Projekt")
    p.drawString(370, y, "Množstvo")
    p.drawString(440, y, "Jedn.")
    p.drawString(480, y, "Poznámka")
    y -= 10
    p.line(50, y, width - 50, y)
    y -= 15

    total = 0
    for r in records:
        if y < 50:
            p.showPage()
            y = height - 50
        p.setFont("Helvetica", 10)
        p.drawString(60, y, r.date)
        p.drawString(120, y, r.user.name if r.user else "-")
        p.drawString(230, y, r.project.name if r.project else "-")
        p.drawString(370, y, str(r.amount))
        p.drawString(440, y, r.unit_type or "")
        p.drawString(480, y, (r.note or "")[:30])
        total += r.amount
        y -= 18

    y -= 10
    p.line(50, y, width - 50, y)
    p.setFont("Helvetica-Bold", 11)
    p.drawString(60, y - 20, f"Celkový súčet: {total:.2f}")

    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="vykon_report.pdf", mimetype="application/pdf")


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
