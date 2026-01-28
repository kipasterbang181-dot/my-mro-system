import os
import io
import base64
import qrcode
import pandas as pd
import traceback
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

# ==========================================
# LIBRARY UNTUK PDF REPORT
# ==========================================
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "g7_aerospace_key_2026")

# ==========================================
# KONFIGURASI DATABASE
# ==========================================
DB_URL = "postgresql://postgres.yyvrjgdzhliodbgijlgb:KUCINGPUTIH10@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "pool_size": 10,
    "max_overflow": 20,
}
db = SQLAlchemy(app)

class RepairLog(db.Model):
    __tablename__ = 'repair_log'
    id = db.Column(db.Integer, primary_key=True)
    drn = db.Column(db.String(100)) 
    peralatan = db.Column(db.String(255))
    pn = db.Column(db.String(255))
    sn = db.Column(db.String(255))
    date_in = db.Column(db.Date) 
    date_out = db.Column(db.Date) 
    defect = db.Column(db.Text)
    status_type = db.Column(db.String(100)) 
    pic = db.Column(db.String(255))
    is_warranty = db.Column(db.Boolean, default=False) 
    created_at = db.Column(db.DateTime, default=datetime.now)
    last_updated = db.Column(db.DateTime, default=datetime.now)

# ==========================================
# FUNGSI EXPORT (UNTUK SELESAIKAN ERROR)
# ==========================================

@app.route('/download_report')
def download_report():
    """Menjana Report PDF untuk semua log."""
    if not session.get('admin'): return redirect(url_for('login'))
    
    logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    elements = []
    
    styles = getSampleStyleSheet()
    elements.append(Paragraph("G7 AEROSPACE - AUTHORIZED MAINTENANCE LOG", styles['Title']))
    elements.append(Spacer(1, 12))
    
    data = [["DATE IN", "EQUIPMENT", "P/N", "S/N", "STATUS", "PIC"]]
    for l in logs:
        data.append([
            l.date_in.strftime('%Y-%m-%d') if l.date_in else "-",
            l.peralatan[:20], # Potong teks panjang supaya tak lari table
            l.pn,
            l.sn,
            l.status_type,
            l.pic
        ])
    
    t = Table(data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ]))
    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="G7_MRO_Report.pdf", mimetype='application/pdf')

@app.route('/export_excel')
def export_excel():
    """Export data ke format Excel."""
    if not session.get('admin'): return redirect(url_for('login'))
    
    logs = RepairLog.query.all()
    data = []
    for l in logs:
        data.append({
            "DRN": l.drn, "Equipment": l.peralatan, "P/N": l.pn, "S/N": l.sn,
            "Date In": l.date_in, "Status": l.status_type, "Defect": l.defect, "PIC": l.pic
        })
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Logs')
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="MRO_Database.xlsx")

# ==========================================
# ROUTES UTAMA (LOGIN, ADMIN, INCOMING)
# ==========================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('u') == 'admin' and request.form.get('p') == 'password123':
            session.permanent = True 
            session['admin'] = True
            return redirect(url_for('admin'))
        flash("Username/Password salah!", "error")
    return render_template('login.html')

@app.route('/admin')
def admin():
    if not session.get('admin'): return redirect(url_for('login'))
    logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
    # Logik statistik matrix (saya ringkaskan untuk penjimatan kod)
    return render_template('admin.html', logs=logs)

@app.route('/incoming', methods=['GET', 'POST'])
def incoming():
    if not session.get('admin'): return redirect(url_for('login'))
    if request.method == 'POST':
        try:
            sn = request.form.get('sn', '').upper()
            new_log = RepairLog(
                drn=request.form.get('drn', '').upper(),
                peralatan=request.form.get('peralatan', '').upper(),
                pn=request.form.get('pn', '').upper(),
                sn=sn,
                date_in=datetime.strptime(request.form.get('date_in'), '%Y-%m-%d').date() if request.form.get('date_in') else datetime.now().date(),
                defect=request.form.get('defect', 'N/A').upper(),
                status_type=request.form.get('status_type', 'ACTIVE').upper().strip(),
                pic=request.form.get('pic', 'N/A').upper()
            )
            db.session.add(new_log)
            db.session.commit()
            flash(f"Data {sn} berjaya disimpan!", "success")
            # KEKAL DI PAGE ASAL (REFERRER)
            return redirect(request.referrer or url_for('admin'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "error")
            return redirect(request.referrer)
    return render_template('incoming.html')

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if not session.get('admin'): return redirect(url_for('login'))
    l = RepairLog.query.get_or_404(id)
    if request.method == 'POST':
        l.peralatan = request.form.get('peralatan', '').upper()
        l.pn = request.form.get('pn', '').upper()
        l.sn = request.form.get('sn', '').upper()
        l.status_type = request.form.get('status_type', '').upper()
        db.session.commit()
        flash("Data dikemaskini!", "success")
        return redirect(request.referrer or url_for('admin'))
    return render_template('edit.html', item=l)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)