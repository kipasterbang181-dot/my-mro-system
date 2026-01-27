import os
import io
import base64
import qrcode
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import text

# Library Tambahan untuk PDF Report
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

app = Flask(__name__)
# Secret key dikekalkan
app.secret_key = os.environ.get("SECRET_KEY", "g7_aerospace_key_2026")

# --- DATABASE CONFIG (SUPABASE) ---
DB_URL = "postgresql://postgres.yyvrjgdzhliodbgijlgb:KUCINGPUTIH10@aws-1-ap-southeast-1.pooler.southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}
db = SQLAlchemy(app)

# --- MODEL DATABASE (Diselaraskan dengan kolum baru) ---
class RepairLog(db.Model):
    __tablename__ = 'repair_log'
    id = db.Column(db.Integer, primary_key=True)
    drn = db.Column(db.String(100))
    peralatan = db.Column(db.String(255))
    pn = db.Column(db.String(100))
    sn = db.Column(db.String(100))
    date_in = db.Column(db.Text) 
    date_out = db.Column(db.Text)
    defect = db.Column(db.Text)
    status_type = db.Column(db.String(100))
    pic = db.Column(db.String(255))
    # Kolum Tambahan
    is_warranty = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    last_updated = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

# Inisialisasi Database & Trigger
with app.app_context():
    db.create_all()
    try:
        # SQL Trigger untuk update last_updated secara automatik di peringkat database
        db.session.execute(text("""
            CREATE OR REPLACE FUNCTION update_modified_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.last_updated = now();
                RETURN NEW;
            END;
            $$ language 'plpgsql';
        """))
        db.session.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_repair_log_modtime') THEN
                    CREATE TRIGGER update_repair_log_modtime
                    BEFORE UPDATE ON repair_log
                    FOR EACH ROW
                    EXECUTE PROCEDURE update_modified_column();
                END IF;
            END $$;
        """))
        db.session.commit()
    except Exception as e:
        print(f"Trigger Setup Info: {e}")

# --- ROUTES ---

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
    
    logs_raw = RepairLog.query.order_by(RepairLog.id.desc()).all()
    
    # PROSES PEMBERSIHAN DATA (Guna logik asal anda)
    cleaned_logs = []
    for log in logs_raw:
        cleaned_logs.append({
            'id': log.id,
            'drn': log.drn or "N/A",
            'peralatan': log.peralatan or "N/A",
            'pn': log.pn or "N/A",
            'sn': log.sn or "N/A",
            'date_in': str(log.date_in) if log.date_in else "",
            'date_out': str(log.date_out) if log.date_out else "-",
            'defect': log.defect or "N/A",
            'status_type': str(log.status_type or "ACTIVE").strip().upper(),
            'pic': log.pic or "N/A",
            'is_warranty': log.is_warranty # Data tambahan untuk frontend
        })
    return render_template('admin.html', logs=cleaned_logs)

@app.route('/history/<sn>')
def history(sn):
    logs = RepairLog.query.filter_by(sn=sn).order_by(RepairLog.id.asc()).all()
    asset_info = logs[0] if logs else None
    return render_template('history.html', logs=logs, asset=asset_info, sn=sn)

@app.route('/view_report/<int:id>')
def view_report(id):
    if not session.get('admin'): return redirect(url_for('login', next=request.path))
    l = RepairLog.query.get_or_404(id)
    return render_template('view_report.html', l=l)

@app.route('/incoming', methods=['POST'])
def incoming():
    try:
        drn = request.form.get('drn', '').upper()
        peralatan = request.form.get('peralatan', '').upper()
        pn = request.form.get('pn', '').upper()
        sn = request.form.get('sn', '').upper()
        date_in = request.form.get('date_in') or datetime.now().strftime("%Y-%m-%d")
        date_out = request.form.get('date_out', '') 
        defect = request.form.get('defect', 'N/A').upper()
        status = request.form.get('status', request.form.get('status_type', 'ACTIVE')).upper()
        pic = request.form.get('pic', 'N/A').upper()
        # Warranty check
        warranty = True if request.form.get('is_warranty') == 'on' else False

        new_log = RepairLog(
            drn=drn, peralatan=peralatan, pn=pn, sn=sn,
            date_in=date_in, date_out=date_out, defect=defect,
            status_type=status, pic=pic, is_warranty=warranty
        )
        db.session.add(new_log)
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return "OK", 200
        return redirect(url_for('index'))
    except Exception as e:
        db.session.rollback()
        return f"Database Error: {str(e)}", 500

@app.route('/download_single_report/<int:item_id>')
def download_single_report(item_id):
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
        ["DRN", l.drn or "N/A"],
        ["EQUIPMENT", Paragraph(l.peralatan or "N/A", cell_style)],
        ["PART NUMBER (P/N)", l.pn or "N/A"],
        ["SERIAL NUMBER (S/N)", l.sn or "N/A"],
        ["DEFECT / REMARKS", Paragraph(l.defect or "N/A", cell_style)],
        ["DATE IN", l.date_in or "N/A"],
        ["DATE OUT", l.date_out or "-"],
        ["STATUS", l.status_type or "N/A"],
        ["JTP / PIC", l.pic or "N/A"],
        ["WARRANTY", "YES" if l.is_warranty else "NO"], # Kolum baru dalam report
        ["REPORT GENERATED", datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
    ]
    
    t = Table(report_data, colWidths=[150, 300])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
    ]))
    
    elements.append(t)
    doc.build(elements)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=f"Report_{l.sn}.pdf")

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
    
    data = [["ID", "DRN", "PERALATAN", "P/N", "S/N", "DEFECT", "DATE IN", "DATE OUT", "STATUS", "PIC"]]
    for l in logs:
        data.append([
            l.id, l.drn or "N/A",
            Paragraph(l.peralatan or "N/A", table_cell_style), 
            Paragraph(l.pn or "N/A", table_cell_style), 
            l.sn or "N/A", 
            Paragraph(l.defect or "N/A", table_cell_style), 
            l.date_in or "N/A", l.date_out or "-", 
            l.status_type or "N/A", 
            Paragraph(l.pic or "N/A", table_cell_style)
        ])
    
    t = Table(data, repeatRows=1, colWidths=[30, 60, 100, 80, 70, 150, 60, 60, 80, 80])
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
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name="Full_Report.pdf")

@app.route('/export_excel')
def export_excel_data():
    if not session.get('admin'): return redirect(url_for('login', next=request.path))
    logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
    data = []
    for l in logs:
        data.append({
            "ID": l.id, "DRN": l.drn or "N/A", "PERALATAN": l.peralatan or "N/A",
            "P/N": l.pn or "N/A", "S/N": l.sn or "N/A", "DEFECT": l.defect or "N/A",
            "DATE IN": l.date_in or "N/A", "DATE OUT": l.date_out or "-",
            "STATUS": l.status_type or "N/A", "PIC": l.pic or "N/A",
            "WARRANTY": "YES" if l.is_warranty else "NO"
        })
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
        df_scan = pd.read_excel(file, header=None)
        header_idx = 0
        for i, row in df_scan.iterrows():
            row_str = [str(x).upper() for x in row.values if pd.notna(x)]
            if any(k in row_str for k in ['PART NO', 'SERIAL NO', 'P/N', 'S/N']):
                header_idx = i
                break
        
        file.seek(0)
        df = pd.read_excel(file, skiprows=header_idx)
        df.columns = [str(c).strip().upper() for c in df.columns]

        def find_col(keywords):
            for col in df.columns:
                if any(k in col for k in keywords): return col
            return None

        c_drn = find_col(['DRN', 'DEFECT REPORT']) 
        c_sn = find_col(['SERIAL NO', 'S/N', 'SERIAL NUMBER'])
        c_pn = find_col(['PART NO', 'P/N', 'PART NUMBER'])
        c_desc = find_col(['DESCRIPTION', 'PERALATAN', 'EQUIPMENT'])
        c_in = find_col(['DATE IN'])
        c_out = find_col(['DATE OUT'])
        c_status = find_col(['STATUS'])
        c_defect = find_col(['DEFECT'])
        c_jtp = find_col(['JTP', 'PIC'])

        def clean_val(val, is_date=False):
            if pd.isna(val) or str(val).strip().lower() in ['nan', '0', '0.0', '', '-']: 
                return None if is_date else "N/A"
            if is_date:
                try: return pd.to_datetime(str(val)).strftime('%Y-%m-%d')
                except: return str(val)[:10]
            return str(val).strip().upper()

        logs_to_add = []
        for _, row in df.iterrows():
            sn = clean_val(row.get(c_sn)) if c_sn else "N/A"
            if sn == "N/A": continue
            
            new_log = RepairLog(
                drn=clean_val(row.get(c_drn)) if c_drn else "N/A",
                peralatan=clean_val(row.get(c_desc)) if c_desc else "N/A",
                pn=clean_val(row.get(c_pn)) if c_pn else "N/A",
                sn=sn,
                date_in=clean_val(row.get(c_in), True) or datetime.now().strftime("%Y-%m-%d"),
                date_out=clean_val(row.get(c_out), True) or "-",
                status_type=clean_val(row.get(c_status)) or "ACTIVE",
                pic=clean_val(row.get(c_jtp)) if c_jtp else "N/A",
                defect=clean_val(row.get(c_defect)) if c_defect else "N/A"
            )
            logs_to_add.append(new_log)
        
        if logs_to_add:
            db.session.bulk_save_objects(logs_to_add)
            db.session.commit()
        return redirect(url_for('admin'))
    except Exception as e:
        db.session.rollback()
        return f"Excel Import Error: {str(e)}"

@app.route('/view_tag/<int:id>')
def view_tag(id):
    l = RepairLog.query.get_or_404(id)
    count = RepairLog.query.filter_by(sn=l.sn).count()
    return render_template('view_tag.html', l=l, logs_count=count)

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
        try:
            ids_to_delete = [int(i) for i in selected_ids]
            RepairLog.query.filter(RepairLog.id.in_(ids_to_delete)).delete(synchronize_session=False)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return f"Error: {str(e)}"
    return redirect(url_for('admin'))

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if not session.get('admin'): return redirect(url_for('login', next=request.full_path))
    l = RepairLog.query.get_or_404(id)
    source = request.args.get('from', 'admin')

    if request.method == 'POST':
        l.drn = request.form.get('drn', '').upper()
        l.peralatan = request.form.get('peralatan', '').upper()
        l.pn = request.form.get('pn', '').upper()
        l.sn = request.form.get('sn', '').upper()
        l.pic = request.form.get('pic', '').upper()
        l.date_in = request.form.get('date_in')
        l.date_out = request.form.get('date_out')
        l.defect = request.form.get('defect', '').upper()
        l.status_type = request.form.get('status_type', '').upper()
        l.is_warranty = True if request.form.get('is_warranty') == 'on' else False
        db.session.commit()
        
        if request.form.get('origin_source') == 'view_tag':
            return redirect(url_for('view_tag', id=l.id))
        return redirect(url_for('admin'))
        
    return render_template('edit.html', item=l, source=source)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)