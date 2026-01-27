import os
import io
import base64
import qrcode
import pandas as pd
import traceback
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
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
# Menggunakan URL Supabase dengan mod SSL diaktifkan
DB_URL = "postgresql://postgres.yyvrjgdzhliodbgijlgb:KUCINGPUTIH10@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"
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
    peralatan = db.Column(db.String(255))
    pn = db.Column(db.String(255))
    sn = db.Column(db.String(255))
    date_in = db.Column(db.String(100))
    date_out = db.Column(db.String(100))
    defect = db.Column(db.Text)
    status_type = db.Column(db.String(100)) # REPAIR / WARRANTY / ACTIVE
    pic = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.now)

# Memastikan table wujud dalam Supabase setiap kali app dijalankan
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
    """ Halaman utama untuk akses awam/import """
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """ Sistem kawalan akses Admin """
    next_page = request.args.get('next')
    
    if request.method == 'POST':
        # Logik Login: Username (u) & Password (p) dari login.html
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
    """ Dashboard Pengurusan Data dengan Debugging Luas """
    if not session.get('admin'): 
        return redirect(url_for('login', next=request.path))
    
    try:
        logs = RepairLog.query.order_by(RepairLog.id.desc()).all()

        # Pengiraan Ringkasan Unit mengikut Tahun (Jadual di Dashboard)
        summary_dict = {}
        for l in logs:
            if l.date_in:
                try:
                    year = str(l.date_in)[:4]
                    if year.isdigit():
                        summary_dict[year] = summary_dict.get(year, 0) + 1
                except:
                    continue

        sorted_years = sorted(summary_dict.keys())
        total_units = sum(summary_dict.values())

        return render_template('admin.html', 
                               logs=logs, 
                               summary_dict=summary_dict, 
                               sorted_years=sorted_years, 
                               total_units=total_units)
    except Exception as e:
        # Jika ralat berlaku, paparkan punca ralat secara terperinci (Traceback)
        error_details = traceback.format_exc()
        return f"<h3>Admin Dashboard Error (500)</h3><p>{str(e)}</p><pre>{error_details}</pre>", 500

@app.route('/history/<sn>')
def history(sn):
    """ Paparan Sejarah Aset untuk kegunaan Scan QR """
    logs = RepairLog.query.filter_by(sn=sn).order_by(RepairLog.date_in.desc()).all()
    asset_info = logs[0] if logs else None
    return render_template('history.html', logs=logs, asset=asset_info, sn=sn)

@app.route('/view_report/<int:id>')
def view_report(id):
    """ Preview Maintenance Report sebelum print """
    if not session.get('admin'): return redirect(url_for('login', next=request.path))
    l = RepairLog.query.get_or_404(id)
    return render_template('view_report.html', l=l)

@app.route('/incoming', methods=['GET', 'POST'])
def incoming():
    """ Kemasukan Data Baru (Manual atau melalui AJAX) """
    if request.method == 'GET':
        return render_template('incoming.html')
        
    try:
        # Mengambil data dan menukar semua kepada HURUF BESAR
        peralatan = request.form.get('peralatan', '').upper()
        pn = request.form.get('pn', '').upper()
        sn = request.form.get('sn', '').upper()
        date_in = request.form.get('date_in') or datetime.now().strftime("%Y-%m-%d")
        date_out = request.form.get('date_out', '') 
        defect = request.form.get('defect', 'N/A').upper()
        status = request.form.get('status_type', request.form.get('status', 'ACTIVE')).upper()
        pic = request.form.get('pic', 'N/A').upper()

        new_log = RepairLog(
            peralatan=peralatan, pn=pn, sn=sn,
            date_in=date_in, date_out=date_out,
            defect=defect, status_type=status, pic=pic
        )
        db.session.add(new_log)
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return "OK", 200
            
        return redirect(url_for('admin'))
    except Exception as e:
        db.session.rollback()
        return f"Database Error: {str(e)}", 500

# ==========================================
# PENJANAAN DOKUMEN (PDF & EXCEL)
# ==========================================

@app.route('/download_single_report/<int:item_id>')
def download_single_report(item_id):
    """ Generate PDF Report untuk satu unit sahaja """
    if not session.get('admin'): return redirect(url_for('login', next=request.path))
    l = RepairLog.query.get_or_404(item_id)
    
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle(name='CellStyle', fontSize=10, leading=12)

    elements.append(Paragraph("G7 AEROSPACE - UNIT MAINTENANCE REPORT", styles['Title']))
    elements.append(Spacer(1, 20))
    
    report_data = [
        ["FIELD", "DETAILS"],
        ["EQUIPMENT", Paragraph(l.peralatan or "N/A", cell_style)],
        ["PART NUMBER (P/N)", l.pn],
        ["SERIAL NUMBER (S/N)", l.sn],
        ["DEFECT / REMARKS", Paragraph(l.defect or "N/A", cell_style)],
        ["DATE IN", l.date_in],
        ["DATE OUT", l.date_out or "-"],
        ["STATUS", l.status_type],
        ["JTP / PIC", l.pic],
        ["REPORT GENERATED", datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
    ]
    
    t = Table(report_data, colWidths=[150, 300])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
    ]))
    
    elements.append(t)
    doc.build(elements)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=f"Report_{l.sn}.pdf")

@app.route('/download_report')
def download_report():
    """ Generate PDF untuk keseluruhan log (Landscape) """
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
            l.date_in, l.date_out or "-", l.status_type, 
            Paragraph(l.pic or "N/A", table_cell_style)
        ])
    
    col_widths = [30, 120, 90, 70, 180, 60, 60, 80, 80]
    t = Table(data, repeatRows=1, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f1f5f9')]),
    ]))
    elements.append(t)
    doc.build(elements)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name="Full_Summary.pdf")

@app.route('/export_excel')
def export_excel_data():
    """ Eksport data ke fail .xlsx """
    if not session.get('admin'): return redirect(url_for('login', next=request.path))
    logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
    data = [{
        "ID": l.id, "PERALATAN": l.peralatan, "P/N": l.pn, "S/N": l.sn,
        "DEFECT": l.defect or "N/A", "DATE IN": l.date_in, "DATE OUT": l.date_out or "-",
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
    """ Import data dari fail Excel ke Database """
    if not session.get('admin'): return redirect(url_for('login', next=request.path))
    file = request.files.get('file_excel')
    if not file: return "Tiada fail dipilih"
    try:
        df = pd.read_excel(file)
        df.columns = [str(c).strip().upper() for c in df.columns]

        logs_to_add = []
        for _, row in df.iterrows():
            new_log = RepairLog(
                peralatan=str(row.get('PERALATAN', 'N/A')).upper(),
                pn=str(row.get('P/N', row.get('PART NUMBER', 'N/A'))).upper(),
                sn=str(row.get('S/N', row.get('SERIAL NUMBER', 'N/A'))).upper(),
                date_in=str(row.get('DATE IN', datetime.now().strftime("%Y-%m-%d"))),
                date_out=str(row.get('DATE OUT', '-')),
                status_type=str(row.get('STATUS', 'ACTIVE')).upper(),
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

# ==========================================
# PENGURUSAN QR & TAG
# ==========================================

@app.route('/view_tag/<int:id>')
def view_tag(id):
    """ Paparan Service Tag (Label Biru) """
    l = RepairLog.query.get_or_404(id)
    count = RepairLog.query.filter_by(sn=l.sn).count()
    return render_template('view_tag.html', l=l, logs_count=count)

@app.route('/download_qr/<int:id>')
def download_qr(id):
    """ Muat turun imej QR Code yang point ke halaman History """
    l = RepairLog.query.get_or_404(id)
    # QR akan membawa user ke sejarah pergerakan S/N tersebut
    qr_link = f"{request.url_root}history/{l.sn}"
    qr = qrcode.make(qr_link)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype='image/png', as_attachment=True, download_name=f"QR_{l.sn}.png")

# ==========================================
# EDIT, DELETE & LOGOUT
# ==========================================

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    """ Edit rekod sedia ada """
    if not session.get('admin'): return redirect(url_for('login', next=request.full_path))
    l = RepairLog.query.get_or_404(id)
    source = request.args.get('from', 'admin')

    if request.method == 'POST':
        l.peralatan = request.form.get('peralatan', '').upper()
        l.pn = request.form.get('pn', '').upper()
        l.sn = request.form.get('sn', '').upper()
        l.pic = request.form.get('pic', '').upper()
        l.date_in = request.form.get('date_in')
        l.date_out = request.form.get('date_out')
        l.defect = request.form.get('defect', '').upper()
        l.status_type = request.form.get('status_type', '').upper()
        db.session.commit()
        
        origin = request.form.get('origin_source')
        if origin == 'view_tag':
            return redirect(url_for('view_tag', id=l.id))
        return redirect(url_for('admin'))
        
    return render_template('edit.html', item=l, source=source)

@app.route('/delete/<int:id>')
def delete(id):
    """ Padam satu rekod """
    if not session.get('admin'): return redirect(url_for('login', next=request.path))
    l = RepairLog.query.get_or_404(id)
    db.session.delete(l)
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/delete_bulk', methods=['POST'])
def delete_bulk():
    """ Padam rekod yang dipilih secara banyak (bulk) """
    if not session.get('admin'): return redirect(url_for('login', next=request.path))
    selected_ids = request.form.getlist('selected_ids')
    if selected_ids:
        ids_to_delete = [int(i) for i in selected_ids]
        RepairLog.query.filter(RepairLog.id.in_(ids_to_delete)).delete(synchronize_session=False)
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    """ Keluar dari sesi Admin """
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Berjalan pada port 5000 (Local) atau dinamik (Server)
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)