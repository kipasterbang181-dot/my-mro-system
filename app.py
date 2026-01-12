import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.secret_key = "mro_system_2026"

# --- CONFIG DATABASE (AWS-1 & PORT 6543) ---
DB_URL = "postgresql://postgres.yyvrjgdzhliodbgijlgb:KUCINGPUTIH10@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres"

app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True}

db = SQLAlchemy(app)

# --- MODEL DATABASE ---
class RepairLog(db.Model):
    __tablename__ = 'repair_log'
    id = db.Column(db.Integer, primary_key=True)
    tarikh = db.Column(db.String(50))
    peralatan = db.Column(db.String(100))
    sn = db.Column(db.String(100))
    status = db.Column(db.String(50))
    tindakan = db.Column(db.Text)
    jurutera = db.Column(db.String(100))
    # Kolum untuk simpan history masa masuk data
    created_at = db.Column(db.DateTime, default=datetime.now)

# --- ROUTE UTAMA (BORANG PEKERJA) ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/save', methods=['POST'])
def save():
    try:
        data = request.json
        new_entry = RepairLog(
            tarikh=data.get('tarikh'), 
            peralatan=data.get('peralatan'),
            sn=data.get('sn'), 
            status=data.get('status'),
            tindakan=data.get('tindakan'), 
            jurutera=data.get('jurutera')
        )
        db.session.add(new_entry)
        db.session.commit()
        return jsonify({"status": "success", "id": new_entry.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

# --- ROUTE LOGIN (MENGIKUT BORANG BOOTSTRAP AWAK) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Mengambil data daripada input name="u" dan name="p"
        username = request.form.get('u')
        password = request.form.get('p')
        
        if username == 'admin' and password == 'password123':
            session['admin'] = True
            return redirect(url_for('admin'))
        else:
            # Jika salah, hantar mesej ralat ringkas
            return "Username atau Password salah! <a href='/login'>Cuba lagi</a>"
            
    return render_template('login.html')

# --- ROUTE ADMIN DASHBOARD ---
@app.route('/admin')
def admin():
    if not session.get('admin'): 
        return redirect(url_for('login'))
    logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
    return render_template('admin.html', logs=logs)

# --- ROUTE EDIT & UPDATE DATA ---
@app.route('/edit/<int:log_id>')
def edit_log(log_id):
    if not session.get('admin'): 
        return redirect(url_for('login'))
    log_data = RepairLog.query.get_or_404(log_id)
    return render_template('edit.html', l=log_data)

@app.route('/update/<int:log_id>', methods=['POST'])
def update_log(log_id):
    if not session.get('admin'): 
        return redirect(url_for('login'))
    log = RepairLog.query.get_or_404(log_id)
    log.tarikh = request.form.get('tarikh')
    log.status = request.form.get('status')
    log.tindakan = request.form.get('tindakan')
    db.session.commit()
    return redirect(url_for('admin'))

# --- ROUTE PADAM (TONG SAMPAH) ---
@app.route('/delete/<int:log_id>', methods=['POST'])
def delete_log(log_id):
    if not session.get('admin'): 
        return redirect(url_for('login'))
    log = RepairLog.query.get_or_404(log_id)
    db.session.delete(log)
    db.session.commit()
    return redirect(url_for('admin'))

# --- ROUTE LOGOUT ---
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- ROUTE VIEW PDF/REPORT ---
@app.route('/view/<int:log_id>')
def view_report(log_id):
    log_data = RepairLog.query.get_or_404(log_id)
    return render_template('view_pdf.html', l=log_data)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)