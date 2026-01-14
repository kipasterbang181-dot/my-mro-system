import os
import pandas as pd
import threading
import time
import requests
import io
import qrcode
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.secret_key = "g7_aerospace_key_2026"

# --- DATABASE CONFIG (SUPABASE) ---
# Menggunakan PostgreSQL Direct Connection dari Supabase
DB_URL = "postgresql://postgres.yyvrjgdzhliodbgijlgb:KUCINGPUTIH10@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres"
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True}
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
    status_type = db.Column(db.String(50))
    pic = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.now)

# --- ANTI-TIDUR (KEEP ALIVE) ---
def keep_alive():
    time.sleep(20)
    while True:
        try:
            print("G7 Aerospace System: Monitoring Heartbeat...")
        except: pass
        time.sleep(600)

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Admin Credentials
        if request.form.get('u') == 'admin' and request.form.get('p') == 'password123':
            session['admin'] = True
            return redirect(url_for('admin'))
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
            peralatan=request.form.get('peralatan').upper(),
            pn=request.form.get('pn').upper(),
            sn=request.form.get('sn').upper(),
            pic=request.form.get('pic').upper(), # JTP disimpan di sini
            status_type="REPAIR",
            defect="N/A"
        )
        db.session.add(new_log)
        db.session.commit()
        return redirect(url_for('index'))
    except Exception as e:
        print(f"Error: {e}")
        return "Internal Server Error 500: Database Connection Failed", 500

@app.route('/view_tag/<int:id>')
def view_tag(id):
    l = RepairLog.query.get_or_404(id)
    
    # Ensure static folder exists for QR
    if not os.path.exists('static'):
        os.makedirs('static')
    
    # Generate QR Code Link
    qr_url = f"{request.url_root}view_tag/{id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(qr_url)
    qr.make(fit=True)
    
    qr_filename = f"qr_{id}.png"
    qr_path = os.path.join('static', qr_filename)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(qr_path)
    
    return render_template('view_tag.html', l=l, qr_code=qr_filename, print_mode=False)

@app.route('/download_pdf/<int:id>')
def download_pdf(id):
    l = RepairLog.query.get_or_404(id)
    # Generate QR also for PDF view
    if not os.path.exists('static'): os.makedirs('static')
    qr_url = f"{request.url_root}view_tag/{id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr_filename = f"qr_{id}.png"
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(os.path.join('static', qr_filename))

    return render_template('view_tag.html', l=l, qr_code=qr_filename, print_mode=True)

@app.route('/export')
def export_excel():
    if not session.get('admin'): 
        return redirect(url_for('login'))
    
    logs = RepairLog.query.all()
    data = []
    for l in logs:
        data.append({
            "Date In": l.date_in,
            "Equipment": l.peralatan,
            "Part Number": l.pn,
            "Serial Number": l.sn,
            "JTP (PIC)": l.pic,
            "Status": l.status_type
        })
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='G7_Logs')
    output.seek(0)
    
    return send_file(
        output, 
        download_name=f"G7_Report_{datetime.now().strftime('%Y%m%d')}.xlsx", 
        as_attachment=True
    )

@app.route('/edit/<int:id>')
def edit(id):
    if not session.get('admin'): return redirect(url_for('login'))
    l = RepairLog.query.get_or_404(id)
    return render_template('edit.html', l=l)

@app.route('/update/<int:id>', methods=['POST'])
def update(id):
    if not session.get('admin'): return redirect(url_for('login'))
    l = RepairLog.query.get_or_404(id)
    l.peralatan = request.form.get('peralatan').upper()
    l.pn = request.form.get('pn').upper()
    l.sn = request.form.get('sn').upper()
    l.pic = request.form.get('pic').upper()
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/delete/<int:id>', methods=['POST', 'GET'])
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

# Keep alive thread
threading.Thread(target=keep_alive, daemon=True).start()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))