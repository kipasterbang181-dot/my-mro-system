import os
import io
import base64
import qrcode
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "g7_aerospace_key_2026")

# --- DATABASE CONFIG ---
DB_URL = "postgresql://postgres.yyvrjgdzhliodbgijlgb:KUCINGPUTIH10@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"
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

@app.route('/import_excel', methods=['POST'])
def import_excel():
    if not session.get('admin'): return redirect(url_for('login'))
    
    file = request.files.get('file_excel')
    if not file: return "Tiada fail dipilih"

    try:
        df = pd.read_excel(file)

        def mapping_status(val):
            s = str(val).upper()
            if any(x in s for x in ['SERVICEABLE', 'SIAP', 'COMPLETED']): return 'SERVICEABLE'
            if any(x in s for x in ['BER', 'BEYOND REPAIR', 'SCRAPPED', 'DAMAGE']): return 'UNSERVICEABLE'
            if any(x in s for x in ['INSPECTED', 'CHECKED']): return 'INSPECTED'
            return 'ACTIVE'

        for _, row in df.iterrows():
            # --- TAMBAHAN UNTUK DATE & JTP ---
            d_in = str(row.get('DATE IN', datetime.now().strftime("%Y-%m-%d")))
            d_out = str(row.get('DATE OUT', '-'))
            # Cari JTP atau PIC dari Excel
            val_pic = str(row.get('JTP', row.get('PIC', 'BULK IMPORT'))).upper()
            
            new_log = RepairLog(
                peralatan=str(row.get('DESCRIPTION', 'N/A')).upper(),
                pn=str(row.get('PART NO', 'N/A')).upper(),
                sn=str(row.get('SERIAL NO', 'N/A')).upper(),
                date_in=d_in,
                date_out=d_out,
                status_type=mapping_status(row.get('STATUS', 'ACTIVE')),
                pic=val_pic,
                defect=str(row.get('DEFECT', row.get('REMARKS', 'INITIAL ENTRY'))).upper()
            )
            db.session.add(new_log)
        
        db.session.commit()
        return redirect(url_for('admin'))
    except Exception as e:
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
    return send_file(
        buf, 
        mimetype='image/png', 
        as_attachment=True, 
        download_name=f"QR_{l.sn}.png"
    )

@app.route('/delete/<int:id>')
def delete(id):
    if not session.get('admin'): return redirect(url_for('login'))
    l = RepairLog.query.get_or_404(id)
    db.session.delete(l)
    db.session.commit()
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
        if new_status:
            l.status_type = new_status.upper()
            
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