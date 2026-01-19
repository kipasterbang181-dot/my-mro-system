import os
import io
import base64
import qrcode
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Library Tambahan untuk PDF Report
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "g7_aerospace_key_2026")

# --- DATABASE CONFIG ---
DB_URL = "postgresql://postgres.yyvrjgdzhliodbgijlgb:KUCINGPUTIH10@aws-1-ap-southeast-1.pooler.southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}
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
        else:
            flash("Username atau Password salah!", "error")
    return render_template('login.html')

@app.route('/admin')
def admin():
    if not session.get('admin'): 
        return redirect(url_for('login'))
    logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
    return render_template('admin.html', logs=logs)

@app.route('/history/<sn>')
def history(sn):
    if not session.get('admin'): return redirect(url_for('login'))
    logs = RepairLog.query.filter_by(sn=sn).order_by(RepairLog.date_in.asc()).all()
    asset_info = logs[0] if logs else None
    return render_template('history.html', logs=logs, asset=asset_info, sn=sn)

@app.route('/view_report/<int:id>')
def view_report(id):
    if not session.get('admin'): return redirect(url_for('login'))
    l = RepairLog.query.get_or_404(id)
    return render_template('view_report.html', l=l)

@app.route('/incoming', methods=['POST'])
def incoming():
    try:
        peralatan = request.form.get('peralatan', '').upper()
        pn = request.form.get('pn', '').upper()
        sn = request.form.get('sn', '').upper()
        date_in = request.form.get('date_in') or datetime.now().strftime("%Y-%m-%d")
        date_out = request.form.get('date_out', '') 
        defect = request.form.get('defect', 'N/A').upper()
        status = request.form.get('status', request.form.get('status_type', 'ACTIVE')).upper()
        pic = request.form.get('pic', 'N/A').upper()

        new_log = RepairLog(
            peralatan=peralatan,
            pn=pn,
            sn=sn,
            date_in=date_in,
            date_out=date_out,
            defect=defect,
            status_type=status,
            pic=pic
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
    if not session.get('admin'): return redirect(url_for('login'))
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
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
    ]))
    
    elements.append(t)
    doc.build(elements)
    buf.seek(0)
    
    # KEMASKINI: as_attachment=True akan terus download fail
    return send_file(
        buf, 
        mimetype='application/pdf', 
        as_attachment=True, 
        download_name=f"Report_{l.sn}_{l.id}.pdf"
    )

@app.route('/download_report')
def download_report():
    if not session.get('admin'): return redirect(url_for('login'))
    logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
    
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter))
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph(f"G7 AEROSPACE - REPAIR LOG SUMMARY REPORT ({datetime.now().strftime('%d/%m/%Y')})", styles['Title']))
    elements.append(Spacer(1, 12))
    
    data = [["ID", "PERALATAN", "P/N", "S/N", "DATE IN", "DATE OUT", "STATUS", "PIC"]]
    table_cell_style = ParagraphStyle(name='TableCell', fontSize=7, leading=8)

    for l in logs:
        data.append([
            l.id, 
            Paragraph(l.peralatan[:50] if l.peralatan else "N/A", table_cell_style), 
            l.pn, 
            l.sn, 
            l.date_in, 
            l.date_out or "-", 
            l.status_type, 
            l.pic
        ])
    
    t = Table(data, repeatRows=1, hAlign='CENTER')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f1f5f9')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    
    elements.append(t)
    doc.build(elements)
    buf.seek(0)
    
    # KEMASKINI: as_attachment=True untuk full summary report
    return send_file(
        buf, 
        mimetype='application/pdf', 
        as_attachment=True, 
        download_name=f"Full_Summary_Report_{datetime.now().strftime('%Y%m%d')}.pdf"
    )

@app.route('/import_excel', methods=['POST'])
def import_excel():
    if not session.get('admin'): return redirect(url_for('login'))
    file = request.files.get('file_excel')
    if not file: return "Tiada fail dipilih"
    try:
        df_scan = pd.read_excel(file, header=None)
        header_idx = 0
        for i, row in df_scan.iterrows():
            row_str = [str(x).upper() for x in row.values if pd.notna(x)]
            if any(k in s for s in row_str for k in ['PART NO', 'SERIAL NO', 'P/N', 'DESCRIPTION']):
                header_idx = i
                break
        file.seek(0)
        df = pd.read_excel(file, skiprows=header_idx)
        df.columns = [str(c).strip().upper() for c in df.columns]

        def clean_val(val, is_date=False):
            if pd.isna(val) or str(val).strip().lower() in ['nan', '0', '0.0', '', '-']: 
                return None if is_date else "N/A"
            if is_date:
                try:
                    if isinstance(val, (int, float)):
                        return pd.to_datetime(val, unit='D', origin='1899-12-30').strftime('%Y-%m-%d')
                    return pd.to_datetime(str(val)).strftime('%Y-%m-%d')
                except: return str(val)[:10]
            return str(val).strip().upper()

        logs_to_add = []
        for _, row in df.iterrows():
            sn = clean_val(row.get('SERIAL NO', row.get('S/N', row.get('SERIAL NUMBER', ''))))
            if sn == "N/A": continue
            d_in = clean_val(row.get('DATE IN'), True)
            d_out = clean_val(row.get('DATE OUT', row.get('DATE OUT2', '')), True) or "-"
            new_log = RepairLog(
                peralatan=clean_val(row.get('DESCRIPTION', row.get('PERALATAN', ''))),
                pn=clean_val(row.get('PART NO', row.get('P/N', ''))),
                sn=sn,
                date_in=d_in or datetime.now().strftime("%Y-%m-%d"),
                date_out=d_out,
                status_type=str(row.get('STATUS', 'ACTIVE')).upper(),
                pic=clean_val(row.get('JTP', 'N/A')),
                defect=clean_val(row.get('DEFECT', 'N/A'))
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
            return f"Ralat Padam Pukal: {str(e)}"
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
        l.defect = request.form.get('defect', '').upper()
        l.status_type = request.form.get('status_type', '').upper()
        db.session.commit()
        return redirect(url_for('admin'))
    return render_template('edit.html', item=l)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)