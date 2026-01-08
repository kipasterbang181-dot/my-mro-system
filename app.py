import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
# Rahsia untuk sesi login admin
app.secret_key = os.environ.get("SECRET_KEY", "avionic_mro_system_2026")

# --- KONFIGURASI DATABASE SUPABASE ---
# Menggunakan sambungan Direct ke PostgreSQL Supabase
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:KUCINGPUTIH10@db.yyvrjgdzhliodbgijlgb.supabase.co:5432/postgres'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True}

db = SQLAlchemy(app)

# --- MODEL JADUAL DATABASE ---
class RepairLog(db.Model):
    __tablename__ = 'repair_log'
    id = db.Column(db.Integer, primary_key=True)
    tarikh = db.Column(db.String(50))
    peralatan = db.Column(db.String(100))
    sn = db.Column(db.String(100))
    status = db.Column(db.String(50))
    tindakan = db.Column(db.String(500))
    jurutera = db.Column(db.String(100))

# --- ROUTES (LALUAN SISTEM) ---

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
        return jsonify({"status": "success", "message": "Data berjaya disimpan!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('u')
        p = request.form.get('p')
        # Login: admin | Password: password123
        if u == 'admin' and p == 'password123':
            session['admin'] = True
            return redirect(url_for('admin'))
    return render_template('login.html')

@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect(url_for('login'))
    
    # Ambil data dan susun dari yang terbaru di atas
    try:
        logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
        return render_template('admin.html', logs=logs)
    except Exception as e:
        return f"Ralat Database: {str(e)}"

@app.route('/view/<int:log_id>')
def view_report(log_id):
    # Halaman untuk orang scan QR nampak detail
    log = RepairLog.query.get_or_404(log_id)
    # Anda perlukan fail view_pdf.html nanti, buat masa ni kita guna template mudah
    return f"<h1>Detail Rekod MRO</h1><p>Alatan: {log.peralatan}</p><p>S/N: {log.sn}</p><p>Status: {log.status}</p>"

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- PENGESAHAN TABLE ---
if __name__ == '__main__':
    with app.app_context():
        # Baris ini sangat penting: Ia akan cipta table 'repair_log' di Supabase secara automatik
        db.create_all()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)