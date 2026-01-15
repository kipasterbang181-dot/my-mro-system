import os
import io
import base64
import qrcode
import pandas as pd
import numpy as np
from flask import Flask, render_template, request, redirect, url_for, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "g7_aerospace_key_2026")

# --- DATABASE CONFIG ---
DB_URL = "postgresql://postgres.yyvrjgdzhliodbgijlgb:KUCINGPUTIH10@aws-1-ap-southeast-1.pooler.southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True}
db = SQLAlchemy(app)

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

with app.app_context():
    db.create_all()

# --- FUNGSI PEMBANTU (HELPER) ---
def fix_date(val):
    """Menukar format tarikh pelik Excel atau string kepada YYYY-MM-DD"""
    if pd.isna(val) or str(val).strip().lower() in ['nan', '0', '', 'none', '-']:
        return None
    try:
        # Jika format nombor Excel (cth: 45281)
        if isinstance(val, (int, float)) or str(val).replace('.','').isdigit():
            return pd.to_datetime(float(val), unit='D', origin='1899-12-30').strftime('%Y-%m-%d')
        # Jika format string (cth: 21/08/2024)
        return pd.to_datetime(str(val)).strftime('%Y-%m-%d')
    except:
        return str(val)[:10]

def mapping_status(val):
    s = str(val).strip().upper()
    if any(x in s for x in ['SERVICEABLE', 'SIAP', 'COMPLETED']): return 'SERVICEABLE'
    if any(x in s for x in ['BER', 'BEYOND REPAIR', 'SCRAPPED', 'DAMAGE']): return 'UNSERVICEABLE'
    if any(x in s for x in ['INSPECTED', 'CHECKED']): return 'INSPECTED'
    return 'ACTIVE'

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



# --- FUNGSI IMPORT EXCEL (VERSI POWER & FLEXIBLE) ---
@app.route('/import_excel', methods=['POST'])
def import_excel():
    if not session.get('admin'): return redirect(url_for('login'))
    
    file = request.files.get('file_excel')
    if not file: return "Tiada fail dipilih"

    try:
        # 1. Cari Header secara automatik
        df_raw = pd.read_excel(file, header=None)
        header_row_index = 0
        for i, row in df_raw.iterrows():
            row_str = [str(x).upper() for x in row.values]
            if any(k in s for s in row_str for k in ['PART NO', 'SERIAL NO', 'P/N', 'PART NUMBER']):
                header_row_index = i
                break

        # 2. Baca semula dari baris header tersebut
        file.seek(0)
        df = pd.read_excel(file, skiprows=header_row_index)
        df.columns = [str(c).strip().upper() for c in df.columns]

        logs_to_add = []

        for _, row in df.iterrows():
            # Cari Serial Number (Wajib ada)
            sn_val = str(row.get('SERIAL NO', row.get('S/N', row.get('SERIAL NUMBER', '')))).strip()
            if sn_val == "" or sn_val.lower() == 'nan':
                continue

            # Mapping flexible untuk setiap column
            peralatan = str(row.get('DESCRIPTION', row.get('EQUIPMENT', row.get('PERALATAN', 'N/A')))).upper()
            pn = str(row.get('PART NO', row.get('P/N', row.get('PN', row.get('PART NUMBER', 'N/A'))))).upper()
            
            # Cari JTP dalam column JTP atau REMARKS atau PIC
            val_pic = str(row.get('JTP', row.get('PIC', row.get('REMARKS', 'N/A')))).upper()
            
            # Proses Tarikh
            d_in = fix_date(row.get('DATE IN', row.get('TARIKH MASUK', row.get('DATEIN'))))
            if not d_in: d_in = datetime.now().strftime("%Y-%m-%d")
            
            d_out = fix_date(row.get('DATE OUT', row.get('TARIKH KELUAR', row.get('DATEOUT'))))
            if not d_out: d_out = "-"

            new_log = RepairLog(
                peralatan=peralatan,
                pn=pn,
                sn=sn_val.upper(),
                date_in=d_in,
                date_out=d_out,
                status_type=mapping_status(row.get('STATUS', 'ACTIVE')),
                pic=val_pic,
                defect=str(row.get('DEFECT', row.get('REMARKS', 'IMPORT DARI EXCEL'))).upper()
            )
            logs_to_add.append(new_log)
        
        if logs_to_add:
            db.session.bulk_save_objects(logs_to_add)
            db.session.commit()
            
        return redirect(url_for('admin'))
    except Exception as e:
        db.session.rollback()
        return f"Ralat semasa proses Excel: {str(e)}"

@app.route('/view_tag/<int:id>')
def view_tag(id):
    l = RepairLog.query.get_or_404(id)
    return render_template('view_tag.html', l=l)

@app.route('/download_qr/<int:id>')
def download_qr(id):
    l = RepairLog.query.get_or_404(id)
    qr_link = f"{request.url_root}view_tag/{id}"
    qr = qrcode.make(qr_link)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype='image/png', as_attachment=True, download_name=f"QR_{l.sn}.png")

@app.route('/delete/<int:id>')
def delete(id):
    if not session.get('admin'): return redirect(url_for('login'))
    l = RepairLog.query.get_or_404(id)
    db.session.delete(l)
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/delete_bulk', methods=['POST'])
def delete_bulk():
    if not session.get('admin'): return redirect(url_for('login'))
    selected_ids = request.form.getlist('selected_ids')
    if selected_ids:
        try:
            ids_to_delete = [int(i) for i in selected_ids]
            RepairLog.query.filter(RepairLog.id.in_(ids_to_delete)).delete(synchronize_session=False)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return f"Ralat semasa bulk delete: {str(e)}"
    return redirect(url_for('admin'))

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if not session.get('admin'): return redirect(url_for('login'))
    l = RepairLog.query.get_or_404(id)
    if request.method == 'POST':
        l.peralatan = request.form.get('peralatan', '').upper()
        l.pn = request.form.get('pn', '').upper()
        l.sn = request.form.get('sn', '').upper()
        l.pic = request.form.get('pic', '').upper()
        l.date_in = request.form.get('date_in')
        l.date_out = request.form.get('date_out')
        new_status = request.form.get('status_type')
        if new_status: l.status_type = new_status.upper()
        db.session.commit()
        return redirect(url_for('admin'))
    return render_template('edit.html', item=l)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)