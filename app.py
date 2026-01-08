import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

app = Flask(__name__)
# Rahsia untuk sesi login admin
app.secret_key = os.environ.get("SECRET_KEY", "avionic_mro_system_2026")

# --- KONFIGURASI DATABASE SUPABASE (MODE POOLER) ---
# Menggunakan format username postgres.[ID_PROJEK] untuk melepasi ralat 'Tenant not found'
DB_URL = "postgresql://postgres.yyvrjgdzhliodbgijlgb:KUCINGPUTIH10@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"

app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

db = SQLAlchemy(app)

# --- MODEL JADUAL DATABASE ---
class RepairLog(db.Model):
    __tablename__ = 'repair_log'
    id = db.Column(db.Integer, primary_key=True)
    tarikh = db.Column(db.String(50))
    peralatan = db.Column(db.String(100))
    sn = db.Column(db.String(100))
    status = db.Column(db.String(50))
    tindakan = db.Column(db.Text)
    jurutera = db.Column(db.String(100))

# --- LALUAN SISTEM (ROUTES) ---

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
    try:
        logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
        return render_template('admin.html', logs=logs)
    except Exception as e:
        return f"Ralat Database: {str(e)}"

@app.route('/view/<int:log_id>')
def view_report(log_id):
    log = RepairLog.query.get_or_404(log_id)
    return f"""
    <html>
    <head><title>MRO Report - {log.sn}</title><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-gray-100 p-10 font-sans">
        <div class="max-w-2xl mx-auto bg-white p-8 rounded-xl shadow-md border-t-8 border-blue-900">
            <h1 class="text-2xl font-bold text-blue-900 border-b pb-4 mb-6 uppercase">Laporan Penyelenggaraan Avionik</h1>
            <div class="grid grid-cols-2 gap-4">
                <p class="font-bold">Peralatan:</p><p>{log.peralatan}</p>
                <p class="font-bold">Serial Number:</p><p class="font-mono">{log.sn}</p>
                <p class="font-bold">Tarikh:</p><p>{log.tarikh}</p>
                <p class="font-bold">Status:</p><p class="font-bold uppercase text-blue-600">{log.status}</p>
                <p class="font-bold">Tindakan:</p><p class="italic">{log.tindakan}</p>
                <p class="font-bold">Jurutera:</p><p>{log.jurutera}</p>
            </div>
            <div class="mt-10 text-center text-gray-400 text-xs">Sistem Janaan Automatik Avionic QR Code</div>
        </div>
    </body>
    </html>
    """

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- BAHAGIAN PENTING: BINA TABLE AUTOMATIK ---
if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()
            print("Database & Jadual sedia digunakan.")
        except Exception as e:
            print(f"Gagal membina jadual: {e}")
            
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)