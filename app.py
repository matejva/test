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
    email = request.form['email']
    password = request.form['password']
    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password, password):
        session['user'] = {'id': user.id, 'name': user.name, 'is_admin': user.is_admin}
        return redirect(url_for('dashboard'))
    return render_template('login.html', error="Zlý e-mail alebo heslo")


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))
    
# ---------- Change Password ----------
@app.route('/change_password/<int:user_id>', methods=['POST'])
def change_password(user_id):
    user = session.get('user')
    if not user:
        flash("Musíš byť prihlásený.", "danger")
        return redirect(url_for('login'))

    # iba admin alebo majiteľ účtu
    if not (user.get('is_admin') or user['id'] == user_id):
        flash("Nemáš oprávnenie meniť toto heslo.", "danger")
        return redirect(url_for('users_list'))

    new_password = request.form.get('new_password')
    confirm = request.form.get('confirm_password')

    if not new_password or not confirm:
        flash("Zadaj heslo a potvrdenie.", "warning")
        return redirect(url_for('users_list'))

    if new_password != confirm:
        flash("Heslá sa nezhodujú.", "danger")
        return redirect(url_for('users_list'))

    target = User.query.get_or_404(user_id)
    target.password = generate_password_hash(new_password)
    db.session.commit()

    flash("Heslo bolo úspešne zmenené.", "success")
    return redirect(url_for('users_list'))


# ---------- DASHBOARD ----------
@app.route('/dashboard', methods=['GET'])
def dashboard():
    session_user = session.get('user')
    if not session_user:
        return redirect(url_for('login'))

    # --- 🔹 Filtrovanie ---
    selected_user = request.args.get('user_id', type=int)
    selected_project = request.args.get('project_id', type=int)
    unit_type_filter = request.args.get('unit_type')

    # --- 🔹 Query builder ---
    query = Record.query

    # Ak nie je admin → ukáž len jeho záznamy
    if session_user.get('is_admin'):
        if selected_user:
            query = query.filter_by(user_id=selected_user)
    else:
        query = query.filter_by(user_id=session_user['id'])

    if selected_project:
        query = query.filter_by(project_id=selected_project)

    if unit_type_filter:
        query = query.filter_by(unit_type=unit_type_filter)

    # --- 🔹 Načítanie dát ---
    records = query.order_by(Record.date.desc()).all()
    projects = Project.query.order_by(Project.name).all()
    users = User.query.order_by(User.name).all() if session_user.get('is_admin') else []

    # --- 🔹 Základné metriky ---
    total = sum(r.amount for r in records) if records else 0
    project_count = len(set(r.project_id for r in records)) if records else 0

    # --- 🔹 Výkon podľa dátumu ---
    date_map = {}
    for r in records:
        if not r.date:
            app.logger.warning(f"Záznam bez dátumu: id={r.id}, projekt={r.project_id}")
            continue
        key = r.date if isinstance(r.date, str) else r.date.strftime("%Y-%m-%d")
        date_map[key] = date_map.get(key, 0) + r.amount

    chart_labels = list(date_map.keys())
    chart_values = list(date_map.values())

    # --- 🔹 Hodiny podľa projektu ---
    hours_map = {}
    m2_map = {}
    for r in records:
        pname = r.project.name if r.project else "Neznámy projekt"
        if r.unit_type == "hodiny":
            hours_map[pname] = hours_map.get(pname, 0) + r.amount
        elif r.unit_type == "m2":
            m2_map[pname] = m2_map.get(pname, 0) + r.amount

    hours_labels = list(hours_map.keys())
    hours_values = list(hours_map.values())
    m2_labels = list(m2_map.keys())
    m2_values = list(m2_map.values())

   # --- 🔹 Súhrn podľa typu jednotky (pre koláčový graf) ---
    unit_map = {}
    for r in records:
        utype = r.unit_type or "Neznáme"
        unit_map[utype] = unit_map.get(utype, 0) + r.amount

    unit_labels = list(unit_map.keys())
    unit_values = list(unit_map.values())

    # --- 🔹 Výpočet výkonu podľa dátumu - rozdelené na hodiny a m² ---
    if session_user.get('is_admin'):
        records_all = Record.query.all()
    else:
        records_all = Record.query.filter_by(user_id=session_user['id']).all()

    date_data_hours = {}
    date_data_m2 = {}

    for r in records_all:
        if not r.date:
            continue
        key = r.date if isinstance(r.date, str) else r.date.strftime("%Y-%m-%d")

        if r.unit_type == "hodiny":
            date_data_hours[key] = date_data_hours.get(key, 0) + r.amount
        elif r.unit_type == "m2":
            date_data_m2[key] = date_data_m2.get(key, 0) + r.amount

    chart_labels_hours = sorted(date_data_hours.keys())
    chart_values_hours = [date_data_hours[k] for k in chart_labels_hours]

    chart_labels_m2 = sorted(date_data_m2.keys())
    chart_values_m2 = [date_data_m2[k] for k in chart_labels_m2]





    # --- 🔹 Render ---
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
    hours_labels=hours_labels,
    hours_values=hours_values,
    m2_labels=m2_labels,
    m2_values=m2_values,
    unit_labels=unit_labels,
    unit_values=unit_values,
    chart_labels_hours=chart_labels_hours,
    chart_values_hours=chart_values_hours,
    chart_labels_m2=chart_labels_m2,
    chart_values_m2=chart_values_m2,
    selected_user=selected_user,
    selected_project=selected_project,
    unit_type_filter=unit_type_filter
)

@app.route('/add_record', methods=['POST'])
def add_record():
    session_user = session.get('user')
    if not session_user:
        return redirect(url_for('login'))

    try:
        project_id = int(request.form['project_id'])
        date_val = request.form['date']           # 'YYYY-MM-DD' string – u nás je date = String(20), OK
        unit_type = request.form.get('unit_type') # 'hodiny' alebo 'm2'
        amount_raw = request.form.get('amount', '0').strip()
        note = request.form.get('note')

        # základná validácia
        if unit_type not in ('hodiny', 'm2'):
            flash("Zvoľ typ jednotky (hodiny alebo m²).", "danger")
            return redirect(url_for('dashboard'))

        try:
            amount = float(amount_raw)
        except ValueError:
            flash("Množstvo musí byť číslo.", "danger")
            return redirect(url_for('dashboard'))

        rec = Record(
            user_id=session_user['id'],
            project_id=project_id,
            date=date_val,
            amount=amount,
            unit_type=unit_type,
            note=note
        )
        db.session.add(rec)
        db.session.commit()
        flash("✅ Záznam bol pridaný!", "success")

    except Exception as e:
        app.logger.exception("Chyba pri pridávaní záznamu")
        db.session.rollback()
        flash(f"❌ Nepodarilo sa pridať záznam: {e}", "danger")

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
    if not user:
        return redirect(url_for('login'))

    all_projects = Project.query.all()
    # Admin môže upravovať, bežný používateľ len vidí
    return render_template('project.html', projects=all_projects, is_admin=user['is_admin'], user=user)


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

# ---------- PROJECT DETAIL ----------
@app.route('/project/<int:id>')
def project_detail(id):
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))

    project = Project.query.get_or_404(id)

    # Záznamy k projektu
    records = (
        Record.query.filter_by(project_id=id)
        .join(User, Record.user_id == User.id)
        .add_columns(User.name.label('username'),
                     Record.date,
                     Record.amount,
                     Record.unit_type,
                     Record.note)
        .order_by(Record.date.desc())
        .all()
    )

    # Sumár podľa používateľov a jednotiek
    per_user = []
    total_h, total_m2 = 0, 0
    user_sums = {}
    for r in records:
        uname = r.username
        if uname not in user_sums:
            user_sums[uname] = {'h': 0, 'm2': 0}
        if r.unit_type == 'hodiny':
            user_sums[uname]['h'] += r.amount
            total_h += r.amount
        elif r.unit_type == 'm2':
            user_sums[uname]['m2'] += r.amount
            total_m2 += r.amount

    for uname, vals in user_sums.items():
        per_user.append({'user': uname, 'h': vals['h'], 'm2': vals['m2']})

    # Render detailu projektu
    return render_template(
        'project_detail.html',
        project=project,
        details=records,
        per_user=per_user,
        total_h=total_h,
        total_m2=total_m2,
        user=user
    )


# ---------- PDF EXPORT ----------
@app.route('/export/pdf')
def export_pdf():
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))

    def normalize_text(text):
        """Nahradí diakritiku, aby PDF s Helvetica vedel text vykresliť."""
        import unicodedata
        if not text:
            return ""
        return ''.join(
            c for c in unicodedata.normalize('NFD', text)
            if unicodedata.category(c) != 'Mn'
        )

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 80

    # Hlavička
    p.setFont("Helvetica-Bold", 16)
    p.drawString(60, y, normalize_text("HRC & Navate – Výkonnostný report"))
    y -= 20
    p.setFont("Helvetica", 10)
    p.drawString(60, y, normalize_text(f"Generované: {datetime.now().strftime('%d.%m.%Y %H:%M')}"))
    y -= 25
    p.line(50, y, width - 50, y)
    y -= 25

    # Hlavička tabuľky
    p.setFont("Helvetica-Bold", 11)
    headers = ["Dátum", "Používateľ", "Projekt", "Hodiny", "m²", "Poznámka"]
    x_positions = [60, 130, 220, 350, 420, 490]
    for x, text in zip(x_positions, headers):
        p.drawString(x, y, normalize_text(text))
    y -= 10
    p.line(50, y, width - 50, y)
    y -= 15

    # Dáta
    records = Record.query.all() if user['is_admin'] else Record.query.filter_by(user_id=user['id']).all()
    total_hours, total_m2 = 0.0, 0.0
    p.setFont("Helvetica", 10)

    for r in records:
        proj = Project.query.get(r.project_id)
        usr = User.query.get(r.user_id)

        p.drawString(60, y, str(r.date))
        p.drawString(130, y, normalize_text(usr.name if usr else "—"))
        p.drawString(220, y, normalize_text(proj.name if proj else "—"))

        if r.unit_type == "hodiny":
            p.drawRightString(400, y, f"{r.amount:.2f}")
            total_hours += r.amount
        elif r.unit_type == "m2":
            p.drawRightString(470, y, f"{r.amount:.2f}")
            total_m2 += r.amount

        p.drawString(490, y, normalize_text(r.note or ""))
        y -= 18

        if y < 80:
            p.showPage()
            p.setFont("Helvetica", 10)
            y = height - 80

    # Súhrn
    y -= 10
    p.line(50, y, width - 50, y)
    y -= 20
    p.setFont("Helvetica-Bold", 12)
    p.drawString(60, y, normalize_text(f"Sucet hodin: {total_hours:.2f}"))
    y -= 18
    p.drawString(60, y, normalize_text(f"Sucet m2: {total_m2:.2f}"))

    p.save()
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name='vykonnostny_report.pdf',
        mimetype='application/pdf'
    )
# ---------- USERS ----------
@app.route('/users')
def users_list():
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))

    # Ak je admin → vidí všetkých
    if user.get('is_admin'):
        all_users = User.query.order_by(User.name).all()
    # Ak nie je admin → vidí len seba
    else:
        all_users = [User.query.get(user['id'])]

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

        new_user = User(
            name=name,
            email=email,
            password=generate_password_hash(password),
            is_admin=is_admin
        )
        db.session.add(new_user)
        db.session.commit()
        flash("✅ Používateľ bol vytvorený!", "success")
        return redirect(url_for('users_list'))

    return render_template('create_user.html', user=user)

# ---------- DOCUMENTS ----------
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
