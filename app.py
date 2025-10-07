import os
from datetime import datetime
from io import BytesIO

from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd

from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'change-this-secret')
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///timelog.db')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login = LoginManager(app)
login.login_view = 'login'

# MODELS
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    email = db.Column(db.String(200), nullable=True, unique=True)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

class TimeEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    hours = db.Column(db.Float, nullable=False)
    project = db.Column(db.String(200), nullable=True)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='entries')

# login loader
@login.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Helpers
def admin_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*a, **k):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Prístup pre admina len.", "danger")
            return redirect(url_for('dashboard'))
        return fn(*a, **k)
    return wrapper

# ROUTES
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name = request.form['name']
        pw = request.form['password']
        user = User.query.filter_by(name=name).first()
        if user and user.check_password(pw):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Nesprávne meno alebo heslo', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # user's own monthly summary (current month)
    month = request.args.get('month')
    year = request.args.get('year')
    if not month or not year:
        now = datetime.utcnow()
        month = now.month
        year = now.year
    else:
        month = int(month); year = int(year)

    entries = TimeEntry.query.filter(
        TimeEntry.user_id == current_user.id,
        db.extract('month', TimeEntry.date) == month,
        db.extract('year', TimeEntry.date) == year
    ).order_by(TimeEntry.date.desc()).all()

    total = sum(e.hours for e in entries)
    return render_template('dashboard.html', entries=entries, total=total, month=month, year=year)

@app.route('/entries')
@login_required
def entries():
    # filterable list (own entries)
    q = TimeEntry.query.filter_by(user_id=current_user.id).order_by(TimeEntry.date.desc())
    return render_template('entries.html', entries=q.all())

@app.route('/add', methods=['GET','POST'])
@login_required
def add_entry():
    if request.method == 'POST':
        date_s = request.form['date']
        project = request.form.get('project')
        hours = float(request.form['hours'])
        note = request.form.get('note')
        date_obj = datetime.strptime(date_s, '%Y-%m-%d').date()
        ent = TimeEntry(user_id=current_user.id, date=date_obj, hours=hours, project=project, note=note)
        db.session.add(ent)
        db.session.commit()
        flash('Záznam uložený', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_entry.html')

@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    users = User.query.order_by(User.name).all()
    return render_template('admin_panel.html', users=users)

@app.route('/admin/create_user', methods=['GET','POST'])
@login_required
@admin_required
def create_user():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form.get('email')
        pw = request.form['password']
        is_admin = True if request.form.get('is_admin') == 'on' else False
        if User.query.filter((User.name==name)|(User.email==email)).first():
            flash("Používateľ s daným menom/emailom už existuje", "danger")
            return redirect(url_for('create_user'))
        u = User(name=name, email=email, is_admin=is_admin)
        u.set_password(pw)
        db.session.add(u)
        db.session.commit()
        flash('Používateľ vytvorený', 'success')
        return redirect(url_for('admin_panel'))
    return render_template('create_user.html')

@app.route('/admin/users')
@login_required
@admin_required
def users():
    users = User.query.order_by(User.name).all()
    return render_template('users.html', users=users)

@app.route('/admin/delete_entry/<int:entry_id>', methods=['POST'])
@login_required
@admin_required
def delete_entry(entry_id):
    ent = TimeEntry.query.get_or_404(entry_id)
    db.session.delete(ent)
    db.session.commit()
    flash('Záznam zmazaný', 'success')
    return redirect(request.referrer or url_for('admin_panel'))

# Export (current user or all if admin)
@app.route('/export', methods=['GET'])
@login_required
def export():
    # params: user_id (optional, only admin can export others)
    user_id = request.args.get('user_id')
    year = request.args.get('year')
    month = request.args.get('month')
    if user_id:
        if not current_user.is_admin and int(user_id) != current_user.id:
            flash("Nemáte oprávnenie exportovať cudzie dáta", "danger")
            return redirect(url_for('dashboard'))
        uid = int(user_id)
    else:
        uid = current_user.id

    q = TimeEntry.query.filter(TimeEntry.user_id==uid)
    if year:
        q = q.filter(db.extract('year', TimeEntry.date)==int(year))
    if month:
        q = q.filter(db.extract('month', TimeEntry.date)==int(month))
    q = q.order_by(TimeEntry.date.asc()).all()

    rows = []
    for e in q:
        rows.append({
            'user': e.user.name,
            'date': e.date.isoformat(),
            'hours': e.hours,
            'project': e.project,
            'note': e.note
        })

    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=['user','date','hours','project','note'])

    # prepare excel in-memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='hours')
    output.seek(0)

    filename = f"timelog_user_{uid}_{year or 'all'}_{month or 'all'}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# Admin: list all entries with filters
@app.route('/admin/entries')
@login_required
@admin_required
def admin_entries():
    user_id = request.args.get('user_id', type=int)
    q = TimeEntry.query
    if user_id:
        q = q.filter(TimeEntry.user_id==user_id)
    entries = q.order_by(TimeEntry.date.desc()).all()
    users = User.query.order_by(User.name).all()
    return render_template('entries.html', entries=entries, users=users, admin_view=True)

if __name__ == '__main__':
    # create DB if not exists
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=os.getenv('FLASK_DEBUG', '0')=='1')
