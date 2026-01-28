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
# LIBRARY TAMBAHAN UNTUK PDF REPORT
# ==========================================
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

app = Flask(__name__)

# Kunci rahsia untuk sesi login dan keselamatan Flash message
app.secret_key = os.environ.get("SECRET_KEY", "g7_aerospace_key_2026")

# ==========================================
# KONFIGURASI SESI (PELINDUNG LOGOUT)
# ==========================================
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
app.config['SESSION_REFRESH_EACH_REQUEST'] = True

# ==========================================
# KONFIGURASI DATABASE (SUPABASE POSTGRES)
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

# ==========================================
# MODEL DATABASE (REPAIR_LOG)
# ==========================================
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

with app.app_context():
    try:
        db.create_all()
        print("Database connected and tables checked.")
    except Exception as e:
        print(f"Initial Connection Error: {e}")

# ==========================================
# LALUAN (ROUTES) SISTEM
# ==========================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    next_page = request.args.get('next')
    if request.method == 'POST':
        if request.form.get('u') == 'admin' and request.form.get('p') == 'password123':
            session.permanent = True 
            session['admin'] = True
            target = request.form.get('next_target')
            if target and target != 'None' and target != '':
                return redirect(target)
            return redirect(url_for('admin'))
        else:
            flash("Username atau Password salah!", "error")
    return render_template('login.html', next_page=next_page)

@app.route('/admin')
def admin():
    if not session.get('admin'): 
        return redirect(url_for('login', next=request.path))
    
    try:
        logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
        status_list = ["SERVICEABLE", "RETURN SERVICEABLE", "RETURN UNSERVICEABLE", "WAITING LO", "OV REPAIR", "UNDER REPAIR", "AWAITING SPARE", "SPARE READY", "WARRANTY REPAIR", "QUOTE SUBMITTED", "TDI IN PROGRESS", "TDI TO REVIEW", "TDI READY TO QUOTE", "READY TO DELIVERED WARRANTY", "READY TO QUOTE", "READY TO DELIVERED"]

        db_statuses = db.session.query(RepairLog.status_type).distinct().all()
        for s in db_statuses:
            if s[0]:
                up_s = s[0].upper().strip()
                if up_s not in status_list:
                    status_list.append(up_s)

        years = sorted(list(set([l.date_in.year for l in logs if l.date_in]))) or [datetime.now().year]
        stats_matrix = {status: {year: 0 for year in years} for status in status_list}
        row_totals = {status: 0 for status in status_list}
        column_totals = {year: 0 for year in years}
        grand_total = 0

        for l in logs:
            if l.date_in and l.status_type:
                stat_key = l.status_type.upper().strip()
                year_key = l.date_in.year
                if stat_key in stats_matrix and year_key in years:
                    stats_matrix[stat_key][year_key] += 1
                    row_totals[stat_key] += 1
                    column_totals[year_key] += 1
                    grand_total += 1

        return render_template('admin.html', logs=logs, sorted_years=years, years=years, status_list=status_list, stats_matrix=stats_matrix, row_totals=row_totals, column_totals=column_totals, grand_total=grand_total, total_units=len(logs), stats=column_totals) 
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/incoming', methods=['GET', 'POST'])
def incoming():
    if not session.get('admin'): return redirect(url_for('login', next=request.path))
    if request.method == 'GET': return render_template('incoming.html')
    
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
        
        # [BETULKAN DI SINI] Guna request.referrer supaya dia tak paksa pergi ke /incoming
        return redirect(request.referrer or url_for('admin'))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Database Error: {str(e)}", "error")
        return redirect(request.referrer or url_for('incoming'))

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if not session.get('admin'): return redirect(url_for('login', next=request.full_path))
    l = RepairLog.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            l.peralatan = request.form.get('peralatan', '').upper()
            l.pn = request.form.get('pn', '').upper()
            l.sn = request.form.get('sn', '').upper()
            l.drn = request.form.get('drn', '').upper()
            l.pic = request.form.get('pic', '').upper()
            l.defect = request.form.get('defect', '').upper()
            l.status_type = request.form.get('status_type', '').upper().strip()
            
            d_in = request.form.get('date_in')
            if d_in: l.date_in = datetime.strptime(d_in, '%Y-%m-%d').date()
            d_out = request.form.get('date_out')
            l.date_out = datetime.strptime(d_out, '%Y-%m-%d').date() if d_out else None
            
            l.last_updated = datetime.now()
            db.session.commit()
            
            flash("Kemaskini berjaya!", "success")
            
            # [BETULKAN DI SINI] Kekal di page edit atau dashboard asal
            return redirect(request.referrer or url_for('admin'))
        except Exception as e:
            db.session.rollback()
            flash(f"Update Error: {str(e)}", "error")
            return redirect(request.referrer)
            
    return render_template('edit.html', item=l)

# --- FUNGSI LAIN KEKAL SAMA ---
@app.route('/history/<sn>')
def history(sn):
    logs = RepairLog.query.filter_by(sn=sn).order_by(RepairLog.date_in.desc()).all()
    return render_template('history.html', logs=logs, asset=logs[0] if logs else None, sn=sn)

@app.route('/delete/<int:id>')
def delete(id):
    if not session.get('admin'): return redirect(url_for('login', next=request.path))
    l = RepairLog.query.get_or_404(id)
    db.session.delete(l)
    db.session.commit()
    flash("Rekod berjaya dipadam.", "info")
    return redirect(request.referrer or url_for('admin'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)