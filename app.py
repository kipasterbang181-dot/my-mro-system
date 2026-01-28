import os
import io
import base64
import qrcode
import pandas as pd
import traceback
import logging
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, and_, extract, func, desc
from datetime import datetime, date

# ==========================================
# LIBRARY TAMBAHAN UNTUK PDF REPORT & UI
# ==========================================
from reportlab.lib.pagesizes import letter, landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

app = Flask(__name__)

# Kunci rahsia untuk sesi login dan keselamatan Flash message
app.secret_key = os.environ.get("SECRET_KEY", "G7_AERO_SECURE_KEY_2026_TOTAL_MRO_V4")

# ==========================================
# KONFIGURASI DATABASE (SUPABASE POSTGRES)
# ==========================================
DB_URL = "postgresql://postgres.yyvrjgdzhliodbgijlgb:KUCINGPUTIH10@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 3600,
    "pool_size": 15,
    "max_overflow": 25
}
db = SQLAlchemy(app)

# Setup Logging untuk Debugging Enterprise
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================================
# MODEL DATABASE (DITAMBAH AUDIT TRAIL)
# ==========================================
class RepairLog(db.Model):
    __tablename__ = 'repair_log'
    id = db.Column(db.Integer, primary_key=True)
    drn = db.Column(db.String(100), index=True) 
    peralatan = db.Column(db.String(255))
    pn = db.Column(db.String(255), index=True)
    sn = db.Column(db.String(255), index=True)
    date_in = db.Column(db.Date) 
    date_out = db.Column(db.Date, nullable=True) 
    defect = db.Column(db.Text)
    status_type = db.Column(db.String(100), default="REPAIR") 
    pic = db.Column(db.String(255))
    remarks = db.Column(db.Text)
    vendor = db.Column(db.String(255))
    is_warranty = db.Column(db.Boolean, default=False) 
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "sn": self.sn,
            "pn": self.pn,
            "status": self.status_type,
            "date_in": self.date_in.isoformat() if self.date_in else None
        }

class SystemAudit(db.Model):
    __tablename__ = 'system_audit'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    action = db.Column(db.String(100))
    user = db.Column(db.String(100))
    details = db.Column(db.Text)

with app.app_context():
    try:
        db.create_all()
        print("G7 Database Enterprise: Connected and Synchronized.")
    except Exception as e:
        print(f"Initial Connection Error: {e}")

# ==========================================
# FUNGSI PEMBANTU (HELPER FUNCTIONS)
# ==========================================
def log_action(action, details):
    """Merekodkan setiap aktiviti admin ke dalam database"""
    try:
        new_audit = SystemAudit(
            action=action, 
            user=session.get('user', 'SYSTEM'), 
            details=details
        )
        db.session.add(new_audit)
        db.session.commit()
    except:
        db.session.rollback()

# ==========================================
# ENTERPRISE ANALYTICS SERVICE
# ==========================================
class AnalyticsService:
    @staticmethod
    def get_dashboard_stats():
        all_logs = RepairLog.query.all()
        total = len(all_logs)
        
        # Status Breakdown
        status_counts = db.session.query(
            RepairLog.status_type, func.count(RepairLog.id)
        ).group_by(RepairLog.status_type).all()
        
        # Yearly Matrix Logic
        yearly_stats = {}
        for l in all_logs:
            if l.date_in:
                yr = l.date_in.year
                st = l.status_type.upper().strip() if l.status_type else "REPAIR"
                if yr not in yearly_stats: yearly_stats[yr] = {}
                yearly_stats[yr][st] = yearly_stats[yr].get(st, 0) + 1

        unique_statuses = sorted(list(set([s[0].upper().strip() for s in status_counts if s[0]])))
        if not unique_statuses: unique_statuses = ["SERVICEABLE", "REPAIR"]
        
        sorted_years = sorted(yearly_stats.keys(), reverse=True)
        if not sorted_years: sorted_years = [datetime.now().year]

        return {
            "total": total,
            "status_breakdown": dict(status_counts),
            "yearly_matrix": yearly_stats,
            "unique_statuses": unique_statuses,
            "sorted_years": sorted_years
        }

# ==========================================
# FLEXIBLE EXCEL ENGINE (G7 SMART IMPORT)
# ==========================================
class MROEngine:
    @staticmethod
    def map_columns(available_cols):
        mapping = {}
        keywords = {
            'drn': ['NO', 'DRN', 'BIL', 'REFERENCE', 'ID'],
            'pn': ['PART NO', 'P/N', 'PART NUMBER', 'PN'],
            'peralatan': ['DESCRIPTION', 'PERALATAN', 'ITEM', 'NOMBOR KOMPONEN', 'NOMENCLATURE'],
            'sn': ['SERIAL NO', 'S/N', 'SERIAL NUMBER', 'SN'],
            'date_in': ['DATE IN', 'TARIKH MASUK', 'RECEIVED'],
            'date_out': ['DATE OUT', 'TARIKH KELUAR', 'DELIVERED'],
            'status': ['STATUS', 'CONDITION', 'KATEGORI'],
            'defect': ['DEFECT', 'KEROSAKAN', 'FAILURE', 'SYMPTOM'],
            'pic': ['PIC', 'STAF', 'PERSON IN CHARGE', 'TEKNIKAL'],
            'vendor': ['VENDOR', 'OUTSIDE VENDOR', 'SENT TO']
        }
        for key, aliases in keywords.items():
            for alias in aliases:
                for col in available_cols:
                    if str(alias).upper() == str(col).strip().upper():
                        mapping[key] = col
                        break
                if key in mapping: break
        return mapping

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
        user = request.form.get('u')
        pwd = request.form.get('p')
        # Sila tukar password mengikut keperluan security anda
        if user == 'admin' and pwd == 'G7Aero@2025':
            session['admin'] = True
            session['user'] = user
            log_action("LOGIN", "Admin berjaya masuk ke sistem")
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
        search_q = request.args.get('q', '')
        if search_q:
            logs = RepairLog.query.filter(or_(
                RepairLog.sn.ilike(f"%{search_q}%"),
                RepairLog.pn.ilike(f"%{search_q}%"),
                RepairLog.peralatan.ilike(f"%{search_q}%"),
                RepairLog.drn.ilike(f"%{search_q}%")
            )).order_by(RepairLog.id.desc()).all()
        else:
            logs = RepairLog.query.order_by(RepairLog.id.desc()).limit(1000).all()

        # --- LOGIK STATS DARI ANALYTICS SERVICE ---
        stats = AnalyticsService.get_dashboard_stats()

        return render_template('admin.html', 
                               logs=logs, 
                               q=search_q,
                               sorted_years=stats['sorted_years'],
                               years=stats['sorted_years'],
                               status_list=stats['unique_statuses'],
                               stats_matrix=stats['yearly_matrix'],
                               grand_total=stats['total'],
                               total_units=len(logs)) 
                                    
    except Exception as e:
        error_details = traceback.format_exc()
        return f"<h3>Admin Dashboard Error (500)</h3><p>{str(e)}</p><pre>{error_details}</pre>", 500

@app.route('/incoming', methods=['GET', 'POST'])
def incoming():
    if not session.get('admin'): return redirect(url_for('login', next=request.path))
    if request.method == 'GET':
        return render_template('incoming.html')
    try:
        peralatan = request.form.get('peralatan', '').upper()
        pn = request.form.get('pn', '').upper()
        sn = request.form.get('sn', '').upper()
        drn = request.form.get('drn', '').upper()
        defect = request.form.get('defect', 'N/A').upper()
        pic = request.form.get('pic', 'N/A').upper()
        vendor = request.form.get('vendor', '').upper()
        remarks = request.form.get('remarks', '').upper()
        
        status = request.form.get('status_type', request.form.get('status', 'REPAIR')).upper()

        date_in_val = request.form.get('date_in')
        d_in = datetime.strptime(date_in_val, '%Y-%m-%d').date() if date_in_val else datetime.now().date()
        
        date_out_val = request.form.get('date_out')
        d_out = datetime.strptime(date_out_val, '%Y-%m-%d').date() if date_out_val else None

        new_log = RepairLog(
            drn=drn, peralatan=peralatan, pn=pn, sn=sn,
            date_in=d_in, date_out=d_out,
            defect=defect, status_type=status, pic=pic,
            vendor=vendor, remarks=remarks
        )
        db.session.add(new_log)
        db.session.commit()
        
        log_action("ADD_RECORD", f"Tambah aset baru: {sn} ({peralatan})")
        flash(f"Data {sn} berjaya disimpan!", "success")
        return redirect(url_for('admin'))
    except Exception as e:
        db.session.rollback()
        return f"Database Error: {str(e)}", 500

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if not session.get('admin'): return redirect(url_for('login', next=request.full_path))
    l = RepairLog.query.get_or_404(id)
    source = request.args.get('from', 'admin')
    if request.method == 'POST':
        old_sn = l.sn
        l.peralatan = request.form.get('peralatan', '').upper()
        l.pn = request.form.get('pn', '').upper()
        l.sn = request.form.get('sn', '').upper()
        l.drn = request.form.get('drn', '').upper()
        l.pic = request.form.get('pic', '').upper()
        l.vendor = request.form.get('vendor', '').upper()
        l.remarks = request.form.get('remarks', '').upper()
        
        d_in_str = request.form.get('date_in')
        if d_in_str:
            l.date_in = datetime.strptime(d_in_str, '%Y-%m-%d').date()
            
        d_out_str = request.form.get('date_out')
        if d_out_str:
            l.date_out = datetime.strptime(d_out_str, '%Y-%m-%d').date()
        else:
            l.date_out = None
            
        l.defect = request.form.get('defect', '').upper()
        l.status_type = request.form.get('status_type', '').upper()
        
        db.session.commit()
        log_action("EDIT_RECORD", f"Kemaskini rekod ID {id} (SN: {old_sn})")
        return redirect(url_for('admin'))
    return render_template('edit.html', item=l, source=source)

@app.route('/delete/<int:id>')
def delete(id):
    if not session.get('admin'): return redirect(url_for('login', next=request.path))
    l = RepairLog.query.get_or_404(id)
    sn_deleted = l.sn
    db.session.delete(l)
    db.session.commit()
    log_action("DELETE_RECORD", f"Padam rekod SN: {sn_deleted}")
    return redirect(url_for('admin'))

@app.route('/delete_bulk', methods=['POST'])
def delete_bulk():
    if not session.get('admin'): return redirect(url_for('login', next=request.path))
    selected_ids = request.form.getlist('selected_ids')
    if selected_ids:
        ids_to_delete = [int(i) for i in selected_ids]
        RepairLog.query.filter(RepairLog.id.in_(ids_to_delete)).delete(synchronize_session=False)
        db.session.commit()
        log_action("BULK_DELETE", f"Padam {len(selected_ids)} rekod secara pukal")
    return redirect(url_for('admin'))

# ==========================================
# IMPORT & EXPORT (G7 ENTERPRISE EDITION)
# ==========================================
@app.route('/import_excel', methods=['POST'])
def import_excel():
    if not session.get('admin'): return redirect(url_for('login', next=request.path))
    file = request.files.get('file_excel')
    if not file: return "Tiada fail dipilih"
    try:
        df = pd.read_excel(file)
        # Handle multi-row headers if exist (common in your os2022.xlsx)
        if df.iloc[0].isnull().sum() > (len(df.columns) * 0.7):
            df.columns = df.iloc[0]
            df = df[1:].reset_index(drop=True)
            
        col_map = MROEngine.map_columns(df.columns)
        logs_to_add = []
        
        for _, row in df.iterrows():
            if pd.isna(row.get(col_map.get('pn'))) and pd.isna(row.get(col_map.get('sn'))):
                continue
                
            def parse_dt(val):
                try:
                    return pd.to_datetime(val).date() if pd.notnull(val) else None
                except: return None

            def get_v(key, default="N/A"):
                val = row.get(col_map.get(key))
                return str(val).strip().upper() if pd.notnull(val) else default

            status_val = get_v('status', 'REPAIR')
            if status_val in ['NAN', '', 'NONE']: status_val = 'REPAIR'

            new_log = RepairLog(
                drn=get_v('drn'),
                peralatan=get_v('peralatan'),
                pn=get_v('pn'),
                sn=get_v('sn'),
                date_in=parse_dt(row.get(col_map.get('date_in'))) or date.today(),
                date_out=parse_dt(row.get(col_map.get('date_out'))),
                status_type=status_val,
                pic=get_v('pic'),
                defect=get_v('defect'),
                vendor=get_v('vendor')
            )
            logs_to_add.append(new_log)
        
        if logs_to_add:
            db.session.bulk_save_objects(logs_to_add)
            db.session.commit()
            log_action("IMPORT_EXCEL", f"Berjaya import {len(logs_to_add)} data")
                
        flash(f"Berjaya import {len(logs_to_add)} data!", "success")
        return redirect(url_for('admin'))
    except Exception as e:
        db.session.rollback()
        return f"Excel Import Error: {str(e)} <br> {traceback.format_exc()}"

@app.route('/export_excel')
def export_excel_data():
    if not session.get('admin'): return redirect(url_for('login', next=request.path))
    logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
    data = [{
        "ID": l.id, "DRN": l.drn, "PERALATAN": l.peralatan, "P/N": l.pn, "S/N": l.sn,
        "DEFECT": l.defect or "N/A", "DATE IN": str(l.date_in), "DATE OUT": str(l.date_out) if l.date_out else "-",
        "STATUS": l.status_type, "PIC": l.pic, "VENDOR": l.vendor, "REMARKS": l.remarks
    } for l in logs]
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='G7_MRO_Logs')
    output.seek(0)
    log_action("EXPORT_EXCEL", "Admin muat turun data Excel")
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name=f"G7_MRO_Export_{date.today()}.xlsx")

# ==========================================
# PDF REPORTING & TAG GENERATION
# ==========================================
@app.route('/download_report')
def download_report():
    if not session.get('admin'): return redirect(url_for('login', next=request.path))
    logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=20)
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom Title Style
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=16, spaceAfter=20)
    elements.append(Paragraph("G7 AEROSPACE SDN BHD - MRO REPAIR LOG SUMMARY", title_style))
    elements.append(Paragraph(f"Laporan dijana pada: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 15))

    table_cell_style = ParagraphStyle(name='TableCell', fontSize=7, leading=8, alignment=TA_CENTER)
    
    data = [["ID", "DRN", "PERALATAN", "P/N", "S/N", "DATE IN", "DATE OUT", "STATUS", "PIC"]]
    for l in logs:
        data.append([
            l.id, l.drn, Paragraph(l.peralatan or "N/A", table_cell_style), 
            l.pn, l.sn, str(l.date_in), str(l.date_out) if l.date_out else "-",
            l.status_type, l.pic
        ])
    
    t = Table(data, repeatRows=1, colWidths=[30, 60, 180, 80, 80, 70, 70, 80, 60])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
    ]))
    elements.append(t)
    doc.build(elements)
    buf.seek(0)
    log_action("DOWNLOAD_PDF", "Laporan PDF Ringkasan dijana")
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=f"G7_MRO_Summary_{date.today()}.pdf")

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

# ==========================================
# PUBLIC ASSET TRACKING (QR SCAN TARGET)
# ==========================================
@app.route('/history/<sn>')
def history(sn):
    """Halaman yang boleh diakses orang awam/staf melalui imbasan QR"""
    logs = RepairLog.query.filter_by(sn=sn.upper()).order_by(RepairLog.date_in.desc()).all()
    asset_info = logs[0] if logs else None
    return render_template('history.html', logs=logs, asset=asset_info, sn=sn)

@app.route('/view_report/<int:id>')
def view_report(id):
    if not session.get('admin'): return redirect(url_for('login', next=request.path))
    l = RepairLog.query.get_or_404(id)
    return render_template('view_report.html', l=l)

# ==========================================
# SYSTEM MAINTENANCE
# ==========================================
@app.route('/logout')
def logout():
    log_action("LOGOUT", "Admin keluar dari sistem")
    session.clear()
    return redirect(url_for('index'))

@app.errorhandler(404)
def page_not_found(e):
    return "<h3>Error 404: Page Not Found</h3><p>Sila pastikan URL anda betul.</p>", 404

@app.errorhandler(500)
def internal_error(e):
    return f"<h3>System Error 500</h3><p>Sesuatu berlaku pada pelayan.</p><pre>{e}</pre>", 500

if __name__ == '__main__':
    # Untuk local testing guna debug=True, untuk production set False
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)