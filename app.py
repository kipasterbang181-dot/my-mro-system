import os
import pandas as pd
import threading
import time
import requests
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import io
import qrcode  # Tambahan untuk QR

app = Flask(__name__)
app.secret_key = "g7_aerospace_key_2026"

# --- DATABASE CONFIG (SUPABASE) ---
DB_URL = "postgresql://postgres.yyvrjgdzhliodbgijlgb:KUCINGPUTIH10@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres"
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- DATABASE MODEL ---
class RepairLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    peralatan = db.Column(db.String(255))
    pn = db.Column(db.String(100))
    sn = db.Column(db.String(100))
    date_in = db.Column(db.String(50))
    date_out = db.Column(db.String(50))
    defect = db.Column(db.Text)
    status_type = db.Column(db.String(50)) # Repair / Warranty
    pic = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.now)

# --- SELF-PING FUNCTION (ANTI-TIDUR) ---
def keep_alive():
    time.sleep(20)
    while True:
        try:
            # Ganti dengan URL Render anda selepas deploy
            requests.get("http://127.0.0.1:5000")
            print("Ping Berkala: Server G7 Terjaga")
        except: pass
        time.sleep(600)

# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('u') == 'admin' and request.form.get('p') == 'password123':
            session['admin'] = True
            return redirect(url_for('admin'))
    return render_template('login.html')

@app.route('/admin')
def admin():
    if not session.get('admin'): return redirect(url_for('login'))
    logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
    return render_template('admin.html', logs=logs)

@app.route('/incoming', methods=['POST'])
def incoming():
    # Sesiapa boleh submit dari index.html, tapi kita kekalkan logik asal tuan
    new_log = RepairLog(
        date_in=datetime.now().strftime("%Y-%m-%d"),
        peralatan=request.form.get('peralatan'),
        pn=request.form.get('pn'),
        sn=request.form.get('sn'),
        pic=request.form.get('pic'),
        status_type="Active"
    )
    db.session.add(new_log)
    db.session.commit()
    return redirect(url_for('index'))

# --- ROUTE UNTUK VIEW PDF / QR TAG ---
@app.route('/view_tag/<int:id>')
def view_tag(id):
    l = RepairLog.query.get_or_404(id)
    
    # Generate QR Code
    if not os.path.exists('static'):
        os.makedirs('static')
    
    qr_data = f"{request.url_root}view_tag/{id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    qr_filename = f"qr_{id}.png"
    qr_path = os.path.join('static', qr_filename)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(qr_path)
    
    return render_template('view_tag.html', l=l, qr_code=qr_filename)

@app.route('/export')
def export_excel():
    if not session.get('admin'): return redirect(url_for('login'))
    logs = RepairLog.query.all()
    data = []
    for l in logs:
        data.append({
            "Equipment": l.peralatan,
            "P/N": l.pn,
            "S/N": l.sn,
            "PIC": l.pic
        })
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    return send_file(output, download_name="G7_Report.xlsx", as_attachment=True)

@app.route('/edit/<int:id>')
def edit(id):
    if not session.get('admin'): return redirect(url_for('login'))
    l = RepairLog.query.get_or_404(id)
    return render_template('edit.html', l=l)

@app.route('/update/<int:id>', methods=['POST'])
def update(id):
    if not session.get('admin'): return redirect(url_for('login'))
    l = RepairLog.query.get_or_404(id)
    l.peralatan = request.form.get('peralatan')
    l.pn = request.form.get('pn')
    l.sn = request.form.get('sn')
    l.pic = request.form.get('pic')
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/delete/<int:id>')
def delete(id):
    if not session.get('admin'): return redirect(url_for('login'))
    l = RepairLog.query.get_or_404(id)
    db.session.delete(l)
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

threading.Thread(target=keep_alive, daemon=True).start()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))