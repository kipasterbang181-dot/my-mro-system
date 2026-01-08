import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
# Rahsia untuk sesi login admin
app.secret_key = os.environ.get("SECRET_KEY", "avionic_mro_system_2026")

# --- KONFIGURASI DATABASE SUPABASE (POOLER MODE) ---
# Menggunakan username berformat postgres.[ID_PROJEK] dan port 6543
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres.yyvrjgdzhliodbgijlgb:KUCINGPUTIH10@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres'
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
    tindakan = db.Column(db.String(500))
    jurutera = db.Column(db.String(100))

# --- ROUTES ---

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
    # Gunakan template ringkas sementara sebelum anda buat view_pdf.html
    return f"""
    <html>
    <body style="font-family:sans-serif; padding:40px;">
        <h2>REKOD PENYELENGGARAAN AVIONIK</h2>
        <hr>
        <p><b>Peralatan:</b> {log.peralatan}</p>
        <p><b>S/N:</b> {log.sn}</p>
        <p><b>Status:</b> {log.status}</p>
        <p><b>Tindakan:</b> {log.tindakan}</p>
        <p><b>Jurutera:</b> {log.jurutera}</p>
        <p><b>Tarikh:</b> {log.tarikh}</p>
    </body>
    </html>
    """

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)