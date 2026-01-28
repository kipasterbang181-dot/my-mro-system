import os
import io
import base64
import qrcode
import pandas as pd
import traceback
import logging
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from sqlalchemy import or_, and_, extract

# ==========================================
# LIBRARY TAMBAHAN UNTUK PDF & EXCEL
# ==========================================
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

app = Flask(__name__)

# Konfigurasi Keselamatan & Sesi
app.secret_key = os.environ.get("SECRET_KEY", "g7_aerospace_secure_vault_2026")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)
app.config['SESSION_REFRESH_EACH_REQUEST'] = True

# ==========================================
# KONFIGURASI DATABASE (POSTGRESQL)
# ==========================================
DB_URL = "postgresql://postgres.yyvrjgdzhliodbgijlgb:KUCINGPUTIH10@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "pool_size": 20,
    "max_overflow": 30,
}
db = SQLAlchemy(app)

# ==========================================
# MODEL DATABASE YANG DIPERLUASKAN
# ==========================================
class RepairLog(db.Model):
    __tablename__ = 'repair_log'
    id = db.Column(db.Integer, primary_key=True)
    drn = db.Column(db.String(100), index=True) 
    peralatan = db.Column(db.String(255))
    pn = db.Column(db.String(255), index=True)
    sn = db.Column(db.String(255), index=True)
    date_in = db.Column(db.Date, nullable=False) 
    date_out = db.Column(db.Date) 
    defect = db.Column(db.Text)
    status_type = db.Column(db.String(100), default='ACTIVE') 
    pic = db.Column(db.String(255))
    is_warranty = db.Column(db.Boolean, default=False) 
    remarks = db.Column(db.Text) # Tambahan baru
    created_at = db.Column(db.DateTime, default=datetime.now)
    last_updated = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

class AuditLog(db.Model): # Model tambahan untuk rekod aktiviti
    __tablename__ = 'audit_log'
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(100))
    action = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.now)

with app.app_context():
    try:
        db.create_all()
        print("✅ Database Synchronized.")
    except Exception as e:
        print(f"❌ Connection Error: {e}")

# ==========================================
# FUNGSI UTILITI (HELPERS)
# ==========================================
def log_activity(user, action):
    try:
        new_audit = AuditLog(user=user, action=action)
        db.session.add(new_audit)
        db.session.commit()
    except:
        db.session.rollback()

# ==========================================
# LALUAN SISTEM (ROUTES)
# ==========================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('u')
        pw = request.form.get('p')
        if user == 'admin' and pw == 'password123':
            session.permanent = True
            session['admin'] = True
            session['user_id'] = user
            log_activity(user, "Logged into the system")
            flash("Selamat Datang ke G7 MRO System", "success")
            return redirect(url_for('admin'))
        flash("Kredensial Tidak Sah!", "danger")
    return render_template('login.html')

@app.route('/admin')
def admin():
    if not session.get('admin'): 
        return redirect(url_for('login', next=request.path))
    
    try:
        # Penapisan (Filtering) Carian
        search_query = request.args.get('search', '')
        if search_query:
            logs = RepairLog.query.filter(
                or_(
                    RepairLog.sn.ilike(f"%{search_query}%"),
                    RepairLog.pn.ilike(f"%{search_query}%"),
                    RepairLog.peralatan.ilike(f"%{search_query}%")
                )
            ).order_by(RepairLog.id.desc()).all()
        else:
            logs = RepairLog.query.order_by(RepairLog.id.desc()).all()

        # Logik Statistik (Matriks Tahun vs Status)
        status_list = [
            "SERVICEABLE", "RETURN SERVICEABLE", "RETURN UNSERVICEABLE",
            "WAITING LO", "OV REPAIR", "UNDER REPAIR", "AWAITING SPARE",
            "SPARE READY", "WARRANTY REPAIR", "QUOTE SUBMITTED", "READY TO QUOTE"
        ]
        
        # Tambah status dinamik dari DB
        current_db_statuses = db.session.query(RepairLog.status_type).distinct().all()
        for s in current_db_statuses:
            if s[0] and s[0].upper() not in status_list:
                status_list.append(s[0].upper())

        years = sorted(list(set([l.date_in.year for l in logs if l.date_in])), reverse=True) or [datetime.now().year]
        
        stats_matrix = {s: {y: 0 for y in years} for s in status_list}
        row_totals = {s: 0 for s in status_list}
        column_totals = {y: 0 for y in years}
        
        for l in logs:
            s_key = l.status_type.upper() if l.status_type else "ACTIVE"
            y_key = l.date_in.year
            if s_key in stats_matrix and y_key in years:
                stats_matrix[s_key][y_key] += 1
                row_totals[s_key] += 1
                column_totals[y_key] += 1

        return render_template('admin.html', 
                               logs=logs, 
                               years=years, 
                               status_list=status_list,
                               stats_matrix=stats_matrix,
                               row_totals=row_totals,
                               column_totals=column_totals,
                               grand_total=len(logs))
    except Exception as e:
        return f"Dashboard Error: {str(e)}", 500

@app.route('/incoming', methods=['GET', 'POST'])
def incoming():
    if not session.get('admin'): return redirect(url_for('login'))
    
    if request.method == 'GET':
        return render_template('incoming.html')
    
    try:
        # Ambil data dan bersihkan (sanitize)
        sn = request.form.get('sn', '').strip().upper()
        if not sn:
            flash("Serial Number wajib diisi!", "warning")
            return redirect(request.referrer)

        new_entry = RepairLog(
            drn=request.form.get('drn', '').upper(),
            peralatan=request.form.get('peralatan', '').upper(),
            pn=request.form.get('pn', '').upper(),
            sn=sn,
            date_in=datetime.strptime(request.form.get('date_in'), '%Y-%m-%d').date() if request.form.get('date_in') else datetime.now().date(),
            defect=request.form.get('defect', '').upper(),
            status_type=request.form.get('status_type', 'ACTIVE').upper(),
            pic=request.form.get('pic', 'N/A').upper(),
            is_warranty=True if request.form.get('is_warranty') == 'on' else False
        )
        
        db.session.add(new_entry)
        db.session.commit()
        
        log_activity(session.get('user_id'), f"Created new log for SN: {sn}")
        flash(f"Data {sn} berjaya didaftarkan!", "success")
        
        # KEKAL DI PAGE SAMA (REFERRER)
        return redirect(request.referrer or url_for('incoming'))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Gagal Simpan: {str(e)}", "danger")
        return redirect(request.referrer)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if not session.get('admin'): return redirect(url_for('login'))
    
    item = RepairLog.query.get_or_404(id)
    if request.method == 'POST':
        try:
            item.peralatan = request.form.get('peralatan', '').upper()
            item.pn = request.form.get('pn', '').upper()
            item.sn = request.form.get('sn', '').upper()
            item.status_type = request.form.get('status_type', '').upper()
            
            d_out = request.form.get('date_out')
            item.date_out = datetime.strptime(d_out, '%Y-%m-%d').date() if d_out else None
            
            item.last_updated = datetime.now()
            db.session.commit()
            
            log_activity(session.get('user_id'), f"Updated ID: {id}")
            flash("Rekod telah dikemaskini!", "info")
            
            # Kembali ke halaman asal (sama ada dashboard atau page lain)
            return redirect(request.referrer or url_for('admin'))
        except Exception as e:
            db.session.rollback()
            flash(f"Update Error: {str(e)}", "danger")
            return redirect(request.referrer)
            
    return render_template('edit.html', item=item)

@app.route('/import_excel', methods=['POST'])
def import_excel():
    if not session.get('admin'): return redirect(url_for('login'))
    
    file = request.files.get('file_excel')
    if not file or file.filename == '':
        flash("Sila pilih fail Excel!", "warning")
        return redirect(url_for('admin'))

    try:
        df = pd.read_excel(file)
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        success_count = 0
        # Gunakan chunking untuk data besar
        chunk_size = 100
        for i in range(0, len(df), chunk_size):
            chunk = df.iloc[i:i+chunk_size]
            batch = []
            for _, row in chunk.iterrows():
                # Logik pembersihan tarikh
                try:
                    d_in = pd.to_datetime(row.get('DATE IN')).date() if pd.notnull(row.get('DATE IN')) else datetime.now().date()
                except: d_in = datetime.now().date()

                batch.append(RepairLog(
                    drn=str(row.get('DRN', '')).upper(),
                    peralatan=str(row.get('PERALATAN', '')).upper(),
                    pn=str(row.get('P/N', '')).upper(),
                    sn=str(row.get('S/N', '')).upper(),
                    date_in=d_in,
                    status_type=str(row.get('STATUS', 'ACTIVE')).upper(),
                    pic=str(row.get('PIC', 'N/A')).upper()
                ))
            db.session.bulk_save_objects(batch)
            db.session.commit()
            success_count += len(batch)

        log_activity(session.get('user_id'), f"Bulk Imported {success_count} records")
        flash(f"Selesai! {success_count} data berjaya diimport.", "success")
        return redirect(url_for('admin'))
        
    except Exception as e:
        db.session.rollback()
        return f"Import Failure: {str(e)}", 500

@app.route('/download_report')
def download_report():
    if not session.get('admin'): return redirect(url_for('login'))
    
    logs = RepairLog.query.order_by(RepairLog.date_in.desc()).all()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter))
    elements = []
    
    # Styling PDF
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleCustom', parent=styles['Title'], fontSize=16, spaceAfter=20)
    
    elements.append(Paragraph("G7 AEROSPACE MRO SUMMARY REPORT", title_style))
    
    # Table Data
    data = [["NO", "DRN", "EQUIPMENT", "P/N", "S/N", "DATE IN", "STATUS", "PIC"]]
    for i, l in enumerate(logs, 1):
        data.append([
            i, l.drn, l.peralatan[:20], l.pn, l.sn, 
            l.date_in.strftime('%d/%m/%Y') if l.date_in else "-",
            l.status_type, l.pic
        ])
    
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white])
    ]))
    
    elements.append(table)
    doc.build(elements)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="MRO_Full_Report.pdf")

@app.route('/delete/<int:id>')
def delete(id):
    if not session.get('admin'): return redirect(url_for('login'))
    
    l = RepairLog.query.get_or_404(id)
    sn_deleted = l.sn
    db.session.delete(l)
    db.session.commit()
    
    log_activity(session.get('user_id'), f"Deleted SN: {sn_deleted}")
    flash(f"Rekod {sn_deleted} telah dipadam.", "warning")
    return redirect(request.referrer or url_for('admin'))

@app.route('/logout')
def logout():
    log_activity(session.get('user_id'), "Logged out")
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Pastikan host 0.0.0.0 untuk deployment (Render/Heroku)
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)