import os, io, qrcode, pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "g7_aerospace_key_2026")

# --- DATABASE CONFIG (SUPABASE CONNECTION) ---
DB_URL = "postgresql://postgres.yyvrjgdzhliodbgijlgb:KUCINGPUTIH10@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"
app.config.update(
    SQLALCHEMY_DATABASE_URI=DB_URL,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True, "pool_recycle": 300}
)
db = SQLAlchemy(app)

# --- DATABASE MODEL ---
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

# --- HELPER: LOGIN CHECK ---
def login_required():
    return session.get('admin')

# --- MAIN ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('u') == 'admin' and request.form.get('p') == 'password123':
            session['admin'] = True
            return redirect(url_for('admin'))
        flash("Username atau Password salah!", "error")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/admin')
def admin():
    if not login_required(): return redirect(url_for('login'))
    count = RepairLog.query.count()
    return render_template('admin.html', count=count)

# --- EXECUTIVE DASHBOARD & MASTER TABLE ---
@app.route('/admin/table')
@app.route('/summary')
def admin_table():
    if not login_required(): return redirect(url_for('login'))
    
    # Ambil data terbaru dari database
    logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
    summary_data = {}
    years_found = set()
    
    status_list = [
        'SERVICEABLE', 'RETURN SERVICEABLE', 'RETURN UNSERVICEABLE', 'WAITING LO', 
        'OV REPAIR', 'UNDER REPAIR', 'AWAITING SPARE', 'SPARE READY',
        'WARRANTY REPAIR', 'QUOTE SUBMITTED', 'TDI IN PROGRESS', 
        'TDI TO REVIEW', 'TDI READY TO QUOTE', 'READY TO DELIVERED WARRANTY'
    ]

    for l in logs:
        try:
            # Gunakan date_in, jika kosong gunakan created_at
            raw_date = str(l.date_in) if l.date_in else str(l.created_at)
            year = raw_date[:4] # Ambil YYYY
            
            if year.isdigit():
                years_found.add(year)
                st = str(l.status_type).upper().strip() if l.status_type else "UNKNOWN"
                if st not in summary_data: 
                    summary_data[st] = {}
                summary_data[st][year] = summary_data[st].get(year, 0) + 1
        except: 
            continue

    return render_template('admin_table.html', 
                            logs=logs, 
                            summary_data=summary_data, 
                            sorted_years=sorted(list(years_found)) or [str(datetime.now().year)],
                            status_list=status_list)

# --- DATA OPERATIONS (ADD, EDIT, DELETE) ---
@app.route('/incoming', methods=['POST'])
def incoming():
    try:
        new_log = RepairLog(
            peralatan=request.form.get('peralatan', '').upper(),
            pn=request.form.get('pn', '').upper(),
            sn=request.form.get('sn', '').upper(),
            date_in=request.form.get('date_in') or datetime.now().strftime("%Y-%m-%d"),
            defect=request.form.get('defect', 'N/A').upper(),
            status_type=request.form.get('status', 'ACTIVE').upper(),
            pic=request.form.get('pic', 'N/A').upper()
        )
        db.session.add(new_log)
        db.session.commit()
        return redirect(url_for('index'))
    except Exception as e:
        db.session.rollback()
        return f"Database Error: {str(e)}"

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if not login_required(): return redirect(url_for('login'))
    l = RepairLog.query.get_or_404(id)
    if request.method == 'POST':
        l.peralatan = request.form.get('peralatan').upper()
        l.pn = request.form.get('pn').upper()
        l.sn = request.form.get('sn').upper()
        l.date_in = request.form.get('date_in')
        l.date_out = request.form.get('date_out')
        l.defect = request.form.get('defect').upper()
        l.status_type = request.form.get('status_type').upper()
        l.pic = request.form.get('pic').upper()
        db.session.commit()
        return redirect(url_for('admin_table'))
    return render_template('edit.html', item=l)

@app.route('/delete/<int:id>')
def delete(id):
    if not login_required(): return redirect(url_for('login'))
    db.session.delete(RepairLog.query.get(id))
    db.session.commit()
    return redirect(url_for('admin_table'))

@app.route('/delete_bulk', methods=['POST'])
def delete_bulk():
    if not login_required(): return redirect(url_for('login'))
    ids = request.form.getlist('selected_ids')
    if ids:
        RepairLog.query.filter(RepairLog.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()
    return redirect(url_for('admin_table'))

# --- EXPORTS (EXCEL, PDF, QR) ---
@app.route('/export_excel')
def export_excel():
    if not login_required(): return redirect(url_for('login'))
    logs = RepairLog.query.all()
    df = pd.DataFrame([{
        "ID": l.id, "ALAT": l.peralatan, "P/N": l.pn, "S/N": l.sn, 
        "STATUS": l.status_type, "DATE IN": l.date_in, "PIC": l.pic
    } for l in logs])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Logs')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name="G7_Data_Export.xlsx")

@app.route('/download_report')
def download_report():
    if not login_required(): return redirect(url_for('login'))
    logs = RepairLog.query.all()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter))
    elements = []
    data = [["ID", "EQUIPMENT", "P/N", "S/N", "STATUS", "DATE IN"]]
    for l in logs:
        data.append([l.id, l.peralatan, l.pn, l.sn, l.status_type, l.date_in])
    
    table = Table(data)
    table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.gray),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke)
    ]))
    elements.append(Paragraph("G7 AEROSPACE EXECUTIVE SUMMARY", getSampleStyleSheet()['Title']))
    elements.append(Spacer(1, 12))
    elements.append(table)
    doc.build(elements)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name="G7_Executive_Report.pdf")

@app.route('/download_qr/<int:id>')
def download_qr(id):
    l = RepairLog.query.get_or_404(id)
    qr = qrcode.make(f"{request.url_root}view_tag/{id}")
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype='image/png', as_attachment=True, download_name=f"QR_{l.sn}.png")

@app.route('/view_tag/<int:id>')
def view_tag(id):
    l = RepairLog.query.get_or_404(id)
    return render_template('view_tag.html', l=l)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)