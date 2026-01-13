import os
import pandas as pd
import threading
import time
import requests
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import io

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
            # Ganti dengan URL Render anda selepas deploy nanti
            # Contoh: requests.get("https://g7-system.onrender.com")
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
        # Mengikut nama input 'u' dan 'p' dalam login.html
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
    if not session.get('admin'): return redirect(url_for('login'))
    new_log = RepairLog(
        date_in=request.form.get('date_in'),
        peralatan=request.form.get('peralatan'),
        pn=request.form.get('pn'),
        sn=request.form.get('sn'),
        defect=request.form.get('defect'),
        status_type=request.form.get('status_type'),
        pic=request.form.get('pic')
    )
    db.session.add(new_log)
    db.session.commit()
    return redirect(url_for('admin'))

# --- TAMBAHAN: ROUTE UNTUK VIEW PDF / CERTIFICATE ---
@app.route('/view/<int:log_id>')
def view_log(log_id):
    # Sesiapa sahaja (termasuk scan QR) boleh tengok tanpa login admin
    log = RepairLog.query.get_or_404(log_id)
    return render_template('view_tag.html', l=log)

# --- TAMBAHAN: EXPORT TO EXCEL (BACKEND OPTION) ---
@app.route('/export')
def export_excel():
    if not session.get('admin'): return redirect(url_for('login'))
    logs = RepairLog.query.all()
    
    data = []
    for l in logs:
        data.append({
            "Date In": l.date_in,
            "Equipment": l.peralatan,
            "P/N": l.pn,
            "S/N": l.sn,
            "Status": l.status_type,
            "PIC": l.pic,
            "Defect": l.defect
        })
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='G7Logs')
    output.seek(0)
    
    return send_file(output, attachment_filename="G7_Aerospace_Report.xlsx", as_attachment=True)

@app.route('/edit/<int:log_id>')
def edit_page(log_id):
    if not session.get('admin'): return redirect(url_for('login'))
    log = RepairLog.query.get_or_404(log_id)
    return render_template('edit.html', l=log)

@app.route('/update/<int:log_id>', methods=['POST'])
def update_log(log_id):
    if not session.get('admin'): return redirect(url_for('login'))
    log = RepairLog.query.get_or_404(log_id)
    log.date_in = request.form.get('date_in')
    log.peralatan = request.form.get('peralatan')
    log.pn = request.form.get('pn')
    log.sn = request.form.get('sn')
    log.defect = request.form.get('defect')
    log.status_type = request.form.get('status_type')
    log.pic = request.form.get('pic')
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/delete/<int:log_id>', methods=['POST'])
def delete_log(log_id):
    if not session.get('admin'): return redirect(url_for('login'))
    log = RepairLog.query.get_or_404(log_id)
    db.session.delete(log)
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Mulakan Thread Anti-Tidur
threading.Thread(target=keep_alive, daemon=True).start()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))