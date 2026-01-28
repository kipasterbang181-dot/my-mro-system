import os
import io
import base64
import qrcode
import pandas as pd
import traceback
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

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
# KONFIGURASI DATABASE (SUPABASE POSTGRES)
# ==========================================
DB_URL = "postgresql+psycopg2://postgres.yyvrjgdzhliodbgijlgb:KUCINGPUTIH10@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"

app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
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
        status_list = [
            "SERVICEABLE", "RETURN SERVICEABLE", "RETURN UNSERVICEABLE",
            "WAITING LO", "OV REPAIR", "UNDER REPAIR", "AWAITING SPARE",
            "SPARE READY", "WARRANTY REPAIR", "QUOTE SUBMITTED",
            "TDI IN PROGRESS", "TDI TO REVIEW", "TDI READY TO QUOTE",
            "READY TO DELIVERED WARRANTY", "READY TO QUOTE", "READY TO DELIVERED"
        ]

        db_statuses = db.session.query(RepairLog.status_type).distinct().all()
        for s in db_statuses:
            if s[0]:
                up_s = s[0].upper().strip()
                if up_s not in status_list:
                    status_list.append(up_s)

        years = sorted(list(set([l.date_in.year for l in logs if l.date_in])))
        if not years: years = [datetime.now().year]

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

        return render_template('admin.html', 
                               logs=logs, 
                               sorted_years=years,
                               years=years,
                               status_list=status_list,
                               stats_matrix=stats_matrix,
                               row_totals=row_totals,
                               column_totals=column_totals,
                               grand_total=grand_total,
                               total_units=len(logs),
                               stats=column_totals) 
                                   
    except Exception as e:
        error_details = traceback.format_exc()
        return f"<h3>Admin Dashboard Error (500)</h3><p>{str(e)}</p><pre>{error_details}</pre>", 500

@app.route('/history/<sn>')
def history(sn):
    logs = RepairLog.query.filter_by(sn=sn).order_by(RepairLog.date_in.desc()).all()
    asset_info = logs[0] if logs else None
    return render_template('history.html', logs=logs, asset=asset_info, sn=sn)

@app.route('/view_report/<int:id>')
def view_report(id):
    if not session.get('admin'): return redirect(url_for('login', next=request.path))
    l = RepairLog.query.get_or_404(id)
    return render_template('view_report.html', l=l)

@app.route('/incoming', methods=['GET', 'POST'])
def incoming():
    if request.method == 'GET':
        return render_template('incoming.html')
    try:
        status_val = request.form.get('status') or request.form.get('status_type') or "UNDER REPAIR"
        d_in_val = request.form.get('date_in')
        d_in = datetime.strptime(d_in_val, '%Y-%m-%d').date() if d_in_val else datetime.now().date()
        
        new_log = RepairLog(
            drn=request.form.get('drn', '').upper(),
            peralatan=request.form.get('peralatan', '').upper(),
            pn=request.form.get('pn', '').upper(),
            sn=request.form.get('sn', '').upper(),
            date_in=d_in,
            defect=request.form.get('defect', 'N/A').upper(),
            status_type=status_val.upper().strip(),
            pic=request.form.get('pic', 'N/A').upper()
        )
        db.session.add(new_log)
        db.session.commit()
        
        # PEMBETULAN UNTUK JAVASCRIPT/AJAX:
        # Jika request hantar data secara latar belakang (macam index.html awak buat)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({"status": "success", "message": "Data Berjaya Disimpan!"}), 200

        # Jika guna form biasa, stay di halaman asal
        flash("Data Berjaya Disimpan!", "success")
        return redirect(url_for('index')) # Tukar ke 'incoming' jika awak nak stay di borang kemasukan
        
    except Exception as e:
        db.session.rollback()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"status": "error", "message": str(e)}), 500
        return f"Database Error: {str(e)}", 500

@app.route('/download_report')
def download_report():
    if not session.get('admin'): return redirect(url_for('login', next=request.path))
    logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter), leftMargin=15, rightMargin=15)
    elements = []
    styles = getSampleStyleSheet()
    table_cell_style = ParagraphStyle(name='TableCell', fontSize=7, leading=8, alignment=1)
    elements.append(Paragraph(f"G7 AEROSPACE - REPAIR LOG SUMMARY ({datetime.now().strftime('%d/%m/%Y')})", styles['Title']))
    elements.append(Spacer(1, 12))
    data = [["ID", "PERALATAN", "P/N", "S/N", "DEFECT", "DATE IN", "DATE OUT", "STATUS", "PIC"]]
    for l in logs:
        data.append([
            l.id, Paragraph(l.peralatan or "N/A", table_cell_style), 
            Paragraph(l.pn or "N/A", table_cell_style), l.sn, 
            Paragraph(l.defect or "N/A", table_cell_style), 
            str(l.date_in), str(l.date_out) if l.date_out else "-", l.status_type, 
            Paragraph(l.pic or "N/A", table_cell_style)
        ])
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f1f5f9')]),
    ]))
    elements.append(t)
    doc.build(elements)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name="Full_Summary.pdf")

@app.route('/export_excel')
def export_excel_data():
    if not session.get('admin'): return redirect(url_for('login', next=request.path))
    logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
    data = [{
        "ID": l.id, "DRN": l.drn, "PERALATAN": l.peralatan, "P/N": l.pn, "S/N": l.sn,
        "DEFECT": l.defect or "N/A", "DATE IN": str(l.date_in), "DATE OUT": str(l.date_out) if l.date_out else "-",
        "STATUS": l.status_type, "PIC": l.pic
    } for l in logs]
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Repair Logs')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name="Repair_Log.xlsx")

@app.route('/import_excel', methods=['POST'])
def import_excel():
    if not session.get('admin'): return redirect(url_for('login', next=request.path))
    file = request.files.get('file_excel')
    if not file: return "Tiada fail dipilih"
    try:
        df = pd.read_excel(file)
        df.columns = [str(c).strip().upper() for c in df.columns]
        logs_to_add = []
        for _, row in df.iterrows():
            d_in = pd.to_datetime(row.get('DATE IN')).date() if pd.notnull(row.get('DATE IN')) else datetime.now().date()
            d_out = pd.to_datetime(row.get('DATE OUT')).date() if pd.notnull(row.get('DATE OUT')) else None
            
            new_log = RepairLog(
                drn=str(row.get('DRN', 'N/A')).upper(),
                peralatan=str(row.get('PERALATAN', 'N/A')).upper(),
                pn=str(row.get('P/N', row.get('PART NUMBER', 'N/A'))).upper(),
                sn=str(row.get('S/N', row.get('SERIAL NUMBER', 'N/A'))).upper(),
                date_in=d_in,
                date_out=d_out,
                status_type=str(row.get('STATUS', 'UNDER REPAIR')).upper(),
                pic=str(row.get('PIC', 'N/A')).upper(),
                defect=str(row.get('DEFECT', 'N/A')).upper()
            )
            logs_to_add.append(new_log)
        if logs_to_add:
            db.session.bulk_save_objects(logs_to_add)
            db.session.commit()
        return redirect(url_for('admin'))
    except Exception as e:
        return f"Excel Import Error: {str(e)}"

@app.route('/view_tag/<int:id>')
def view_tag(id):
    l = RepairLog.query.get_or_404(id)
    count = RepairLog.query.filter_by(sn=l.sn).count()
    return render_template('view_tag.html', l=l, logs_count=count)

@app.route('/download_qr/<int:id>')
def download_qr(id):
    l = RepairLog.query.get_or_404(id)
    qr = qrcode.make(f"{request.url_root}history/{l.sn}")
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype='image/png', as_attachment=True, download_name=f"QR_{l.sn}.png")

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if not session.get('admin'): return redirect(url_for('login', next=request.full_path))
    l = RepairLog.query.get_or_404(id)
    source = request.args.get('from', 'admin')
    if request.method == 'POST':
        new_status = request.form.get('status') or request.form.get('status_type')
        l.peralatan = request.form.get('peralatan', '').upper()
        l.pn = request.form.get('pn', '').upper()
        l.sn = request.form.get('sn', '').upper()
        l.drn = request.form.get('drn', '').upper()
        l.pic = request.form.get('pic', '').upper()
        
        d_in_str = request.form.get('date_in')
        if d_in_str: l.date_in = datetime.strptime(d_in_str, '%Y-%m-%d').date()
        d_out_str = request.form.get('date_out')
        l.date_out = datetime.strptime(d_out_str, '%Y-%m-%d').date() if d_out_str else None
            
        l.defect = request.form.get('defect', '').upper()
        if new_status: l.status_type = new_status.upper().strip()
            
        l.last_updated = datetime.now()
        db.session.commit()
        
        # PEMBETULAN: Kekal di halaman edit selepas simpan kemas kini
        flash("Rekod Berjaya Dikemaskini!", "success")
        return redirect(url_for('edit', id=id, source=source))

    return render_template('edit.html', item=l, source=source)

@app.route('/delete/<int:id>')
def delete(id):
    if not session.get('admin'): return redirect(url_for('login', next=request.path))
    l = RepairLog.query.get_or_404(id)
    db.session.delete(l)
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/delete_bulk', methods=['POST'])
def delete_bulk():
    if not session.get('admin'): return redirect(url_for('login', next=request.path))
    selected_ids = request.form.getlist('selected_ids')
    if selected_ids:
        ids_to_delete = [int(i) for i in selected_ids]
        RepairLog.query.filter(RepairLog.id.in_(ids_to_delete)).delete(synchronize_session=False)
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)