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

# --- DATABASE CONFIG (SUPABASE + RENDER STABILITY) ---
# Penambahan ?sslmode=require untuk mengelakkan sekatan sambungan oleh Render
DB_URL = "postgresql://postgres.yyvrjgdzhliodbgijlgb:KUCINGPUTIH10@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"

app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Engine options untuk memastikan database tidak "timeout" atau "crash"
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 1800,
}

db = SQLAlchemy(app)

# --- DATABASE MODEL (SYNC DENGAN SQL BARU TUAN) ---
class RepairLog(db.Model):
    __tablename__ = 'repair_log'
    id = db.Column(db.Integer, primary_key=True)
    peralatan = db.Column(db.String(100))
    pn = db.Column(db.String(100)) # Ditambah untuk simpan Part Number
    sn = db.Column(db.String(100))
    date_in = db.Column(db.String(50))
    date_out = db.Column(db.String(50))
    defect = db.Column(db.Text)      # Sama dengan 'tindakan' dalam SQL tuan
    status_type = db.Column(db.String(50)) # Sama dengan 'status' dalam SQL tuan
    pic = db.Column(db.String(100))  # Sama dengan 'jurutera' dalam SQL tuan
    created_at = db.Column(db.DateTime, default=datetime.now)

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
    # Ambil data terbaru dari Supabase
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
        db.session.rollback()
        return f"Internal Server Error 500: Database Connection Failed - {str(e)}", 500

@app.route('/view_tag/<int:id>')
def view_tag(id):
    l = RepairLog.query.get_or_404(id)
    return render_template('view_tag.html', l=l, print_mode=False)

@app.route('/download_pdf/<int:id>')
def download_pdf(id):
    l = RepairLog.query.get_or_404(id)
    return render_template('view_tag.html', l=l, print_mode=True)

@app.route('/export')
def export_excel():
    if not session.get('admin'): return redirect(url_for('login'))
    logs = RepairLog.query.all()
    data = [{"Equipment": l.peralatan, "P/N": l.pn, "S/N": l.sn, "PIC": l.pic} for l in logs]
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    return send_file(output, download_name="G7_Report.xlsx", as_attachment=True)

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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))