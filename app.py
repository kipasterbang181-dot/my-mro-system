import os
import io
import base64
import qrcode
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.secret_key = "g7_aerospace_key_2026"

# DATABASE CONFIG - Guna port 6543 untuk elak 'Network Unreachable'
DB_URL = "postgresql://postgres.yyvrjgdzhliodbgijlgb:KUCINGPUTIH10@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"

app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True}
db = SQLAlchemy(app)

# Model Data - Saya kekalkan nama 'RepairLog' tapi set table name ke 'repair_log'
class RepairLog(db.Model):
    __tablename__ = 'repair_log'
    id = db.Column(db.Integer, primary_key=True)
    peralatan = db.Column(db.String(100))
    pn = db.Column(db.String(100))
    sn = db.Column(db.String(100))
    date_in = db.Column(db.String(50))
    date_out = db.Column(db.String(50))
    defect = db.Column(db.Text)
    status_type = db.Column(db.String(50))
    pic = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.now)

# INI PENTING: Buat table automatik masa start
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

# DAH BETULKAN: Boleh buka muka surat login (GET) dan hantar data (POST)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('u') == 'admin' and request.form.get('p') == 'password123':
            session['admin'] = True
            return redirect(url_for('admin'))
        return "ID atau Password Salah!"
    return render_template('login.html')

@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect(url_for('login'))
    logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
    return render_template('admin.html', logs=logs)

@app.route('/incoming', methods=['POST'])
def incoming():
    try:
        new_log = RepairLog(
            date_in=datetime.now().strftime("%Y-%m-%d"),
            peralatan=request.form.get('peralatan', '').upper(),
            pn=request.form.get('pn', '').upper(),
            sn=request.form.get('sn', '').upper(),
            pic=request.form.get('pic', '').upper(),
            status_type="ACTIVE",
            defect="INITIAL ENTRY"
        )
        db.session.add(new_log)
        db.session.commit()
        return redirect(url_for('index'))
    except Exception as e:
        return f"Ralat Simpan Data: {str(e)}"

@app.route('/view_tag/<int:id>')
def view_tag(id):
    l = RepairLog.query.get_or_404(id)
    qr_data = f"{request.url_root}view_tag/{id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    qr_b64 = base64.b64encode(buffered.getvalue()).decode()
    return render_template('view_tag.html', l=l, qr_code=qr_b64)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)