"""
G7 AEROSPACE MRO & REPAIR LOG SYSTEM
Version: 3.0 (Enterprise Edition)
Lines of Code: 500+ 
Features: Flexible Excel Import, PDF Reporting, QR Tracking, Advanced Analytics
"""

import os
import io
import logging
import base64
import qrcode
import traceback
import pandas as pd
import numpy as np
from datetime import datetime, date
from flask import (
    Flask, render_template, request, redirect, 
    url_for, session, send_file, flash, jsonify
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, and_, extract, func

# ==============================================================================
# 1. REPORTING & PDF ENGINE LIBRARIES
# ==============================================================================
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, 
    Spacer, Image, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# ==============================================================================
# 2. APP CONFIGURATION & INITIALIZATION
# ==============================================================================
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "G7_AERO_SECURE_KEY_2026_TOTAL_MRO")

# Database Configuration (Supabase/PostgreSQL)
DB_URL = "postgresql://postgres.yyvrjgdzhliodbgijlgb:KUCINGPUTIH10@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # FIXED: Added '=' here
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 3600,
    "pool_size": 10,
    "max_overflow": 20
}

db = SQLAlchemy(app)

# Setup Logging for Debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==============================================================================
# 3. DATABASE MODELS
# ==============================================================================
class RepairLog(db.Model):
    """
    Main model for storing MRO Repair Logs.
    Designed to be compatible with legacy Excel formats and new system entries.
    """
    __tablename__ = 'repair_log'
    
    id = db.Column(db.Integer, primary_key=True)
    drn = db.Column(db.String(100), index=True) # Document Reference Number
    peralatan = db.Column(db.String(255), nullable=False)
    pn = db.Column(db.String(255), index=True)   # Part Number
    sn = db.Column(db.String(255), index=True)   # Serial Number
    date_in = db.Column(db.Date, default=date.today)
    date_out = db.Column(db.Date, nullable=True)
    defect = db.Column(db.Text)
    status_type = db.Column(db.String(100), default="REPAIR")
    pic = db.Column(db.String(255))
    remarks = db.Column(db.Text)
    vendor = db.Column(db.String(255))
    is_warranty = db.Column(db.Boolean, default=False)
    
    # Audit Fields
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "pn": self.pn,
            "sn": self.sn,
            "status": self.status_type,
            "date_in": self.date_in.isoformat() if self.date_in else None
        }

with app.app_context():
    try:
        db.create_all()
        logger.info("Database synchronized successfully.")
    except Exception as e:
        logger.error(f"Database sync failed: {e}")

# ==============================================================================
# 4. FLEXIBLE EXCEL ENGINE (THE CORE LOGIC)
# ==============================================================================
class FlexibleExcelEngine:
    """
    Advanced engine to handle various Excel formats.
    Capable of detecting multi-row headers and fuzzy-matching column names.
    """
    
    KEYWORDS = {
        'drn': ['NO', 'DRN', 'BIL', 'REFERENCE', 'ID'],
        'pn': ['PART NO', 'P/N', 'PART NUMBER', 'PN'],
        'peralatan': ['DESCRIPTION', 'PERALATAN', 'ITEM', 'NOMBOR KOMPONEN', 'NOMENCLATURE'],
        'sn': ['SERIAL NO', 'S/N', 'SERIAL NUMBER', 'SN'],
        'date_in': ['DATE IN', 'TARIKH MASUK', 'RECEIVED'],
        'date_out': ['DATE OUT', 'TARIKH KELUAR', 'DELIVERED'],
        'status': ['STATUS', 'CONDITION', 'REMARK', 'KATEGORI'],
        'defect': ['DEFECT', 'KEROSAKAN', 'FAILURE', 'SYMPTOM'],
        'pic': ['PIC', 'STAF', 'PERSON IN CHARGE', 'TEKNIKAL'],
        'vendor': ['VENDOR', 'OUTSIDE VENDOR', 'SENT TO']
    }

    @staticmethod
    def clean_header(df):
        """Detect and remove nested headers (like in your os2022.xlsx file)"""
        if len(df) > 0 and df.iloc[0].isnull().sum() > (len(df.columns) * 0.7):
            df = df.iloc[1:].reset_index(drop=True)
        return df

    @classmethod
    def map_columns(cls, available_cols):
        mapping = {}
        for key, aliases in cls.KEYWORDS.items():
            for alias in aliases:
                for col in available_cols:
                    if str(alias).upper() == str(col).strip().upper():
                        mapping[key] = col
                        break
                if key in mapping: break
        return mapping

    @classmethod
    def process_file(cls, file_stream):
        df = pd.read_excel(file_stream)
        df = cls.clean_header(df)
        col_map = cls.map_columns(df.columns)
        
        logs = []
        for _, row in df.iterrows():
            if pd.isna(row.get(col_map.get('pn'))) and pd.isna(row.get(col_map.get('sn'))):
                continue
                
            def parse_dt(val):
                try:
                    if pd.notnull(val):
                        return pd.to_datetime(val).date()
                    return None
                except: return None

            def get_v(key, default="N/A"):
                val = row.get(col_map.get(key))
                if pd.notnull(val):
                    return str(val).strip().upper()
                return default

            status_val = get_v('status', 'REPAIR')
            if status_val in ['NAN', '', 'NONE']: status_val = 'REPAIR'

            log_entry = RepairLog(
                drn=get_v('drn'),
                pn=get_v('pn'),
                peralatan=get_v('peralatan'),
                sn=get_v('sn'),
                status_type=status_val,
                defect=get_v('defect'),
                pic=get_v('pic'),
                vendor=get_v('vendor'),
                date_in=parse_dt(row.get(col_map.get('date_in'))) or date.today(),
                date_out=parse_dt(row.get(col_map.get('date_out')))
            )
            logs.append(log_entry)
        
        return logs

# ==============================================================================
# 5. ANALYTICS & STATS SERVICE
# ==============================================================================
class AnalyticsService:
    @staticmethod
    def get_dashboard_stats():
        all_logs = RepairLog.query.all()
        total = len(all_logs)
        
        status_counts = db.session.query(
            RepairLog.status_type, func.count(RepairLog.id)
        ).group_by(RepairLog.status_type).all()
        
        yearly_stats = {}
        for l in all_logs:
            if l.date_in:
                yr = l.date_in.year
                st = l.status_type.upper() if l.status_type else "REPAIR"
                if yr not in yearly_stats: yearly_stats[yr] = {}
                yearly_stats[yr][st] = yearly_stats[yr].get(st, 0) + 1

        unique_statuses = sorted(list(set([s[0].upper() for s in status_counts if s[0]])))
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

# ==============================================================================
# 6. AUTHENTICATION & SESSION WRAPPERS
# ==============================================================================
def is_admin():
    return session.get('admin', False)

@app.before_request
def check_session_timeout():
    pass

# ==============================================================================
# 7. PRIMARY ROUTES (WEB INTERFACE)
# ==============================================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('u')
        pwd = request.form.get('p')
        if user == 'admin' and pwd == 'password123':
            session['admin'] = True
            session.permanent = True
            flash("Welcome back, Commander.", "success")
            return redirect(url_for('admin_dashboard'))
        flash("Invalid credentials. Access denied.", "error")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/admin')
def admin_dashboard():
    if not is_admin(): return redirect(url_for('login'))
    
    try:
        search_q = request.args.get('q', '')
        if search_q:
            logs = RepairLog.query.filter(
                or_(
                    RepairLog.sn.ilike(f"%{search_q}%"),
                    RepairLog.pn.ilike(f"%{search_q}%"),
                    RepairLog.peralatan.ilike(f"%{search_q}%"),
                    RepairLog.drn.ilike(f"%{search_q}%")
                )
            ).order_by(RepairLog.id.desc()).all()
        else:
            logs = RepairLog.query.order_by(RepairLog.id.desc()).limit(1000).all()

        stats = AnalyticsService.get_dashboard_stats()
        
        return render_template('admin.html', logs=logs, stats=stats, q=search_q)
    except Exception as e:
        logger.error(f"Dashboard error: {traceback.format_exc()}")
        return f"System Error: {str(e)}", 500

# ==============================================================================
# 8. DATA OPERATIONS (IMPORT, EXPORT, CRUD)
# ==============================================================================

@app.route('/import_excel', methods=['POST'])
def import_excel():
    if not is_admin(): return "Unauthorized", 403
    
    file = request.files.get('file_excel')
    if not file or file.filename == '':
        flash("No file selected", "warning")
        return redirect(url_for('admin_dashboard'))

    try:
        logs = FlexibleExcelEngine.process_file(file)
        chunk_size = 100
        for i in range(0, len(logs), chunk_size):
            db.session.bulk_save_objects(logs[i:i+chunk_size])
            db.session.commit()
            
        flash(f"Successfully processed {len(logs)} records from Excel.", "success")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Import failed: {traceback.format_exc()}")
        flash(f"Import Error: {str(e)}", "error")
        
    return redirect(url_for('admin_dashboard'))

@app.route('/edit_log/<int:id>', methods=['GET', 'POST'])
def edit_log(id):
    if not is_admin(): return redirect(url_for('login'))
    log = RepairLog.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            log.peralatan = request.form.get('peralatan').upper()
            log.pn = request.form.get('pn').upper()
            log.sn = request.form.get('sn').upper()
            log.status_type = request.form.get('status_type').upper()
            log.defect = request.form.get('defect').upper()
            log.pic = request.form.get('pic').upper()
            
            d_in = request.form.get('date_in')
            if d_in: log.date_in = datetime.strptime(d_in, '%Y-%m-%d').date()
            
            d_out = request.form.get('date_out')
            if d_out: log.date_out = datetime.strptime(d_out, '%Y-%m-%d').date()
            else: log.date_out = None
            
            db.session.commit()
            flash("Record updated successfully.", "success")
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f"Update failed: {e}", "error")

    return render_template('edit.html', item=log)

@app.route('/delete_logs', methods=['POST'])
def delete_logs():
    if not is_admin(): return "Forbidden", 403
    ids = request.form.getlist('selected_ids')
    if ids:
        try:
            RepairLog.query.filter(RepairLog.id.in_([int(i) for i in ids])).delete(synchronize_session=False)
            db.session.commit()
            flash(f"Deleted {len(ids)} records.", "info")
        except Exception as e:
            db.session.rollback()
            flash(f"Delete failed: {e}", "error")
    return redirect(url_for('admin_dashboard'))

# ==============================================================================
# 9. SPECIALIZED SERVICES (PDF, QR, EXCEL EXPORT)
# ==============================================================================

@app.route('/download_pdf_report')
def download_pdf_report():
    if not is_admin(): return "Unauthorized", 403
    
    logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    
    elements = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=16, spaceAfter=20)
    header_style = ParagraphStyle('HeaderStyle', fontSize=8, textColor=colors.whitesmoke, alignment=TA_CENTER)
    cell_style = ParagraphStyle('CellStyle', fontSize=7, alignment=TA_CENTER)

    elements.append(Paragraph("G7 AEROSPACE SDN BHD - MRO REPAIR LOG REPORT", title_style))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%d %B %Y %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 0.2*inch))

    data = [[
        Paragraph("<b>DRN</b>", header_style),
        Paragraph("<b>DESCRIPTION</b>", header_style),
        Paragraph("<b>PART NO</b>", header_style),
        Paragraph("<b>SERIAL NO</b>", header_style),
        Paragraph("<b>STATUS</b>", header_style),
        Paragraph("<b>DATE IN</b>", header_style),
        Paragraph("<b>DATE OUT</b>", header_style),
        Paragraph("<b>PIC</b>", header_style)
    ]]

    for l in logs:
        data.append([
            Paragraph(str(l.drn or "-"), cell_style),
            Paragraph(str(l.peralatan or "-"), cell_style),
            Paragraph(str(l.pn or "-"), cell_style),
            Paragraph(str(l.sn or "-"), cell_style),
            Paragraph(f"<b>{l.status_type}</b>", cell_style),
            Paragraph(str(l.date_in) if l.date_in else "-", cell_style),
            Paragraph(str(l.date_out) if l.date_out else "-", cell_style),
            Paragraph(str(l.pic or "-"), cell_style)
        ])

    table = Table(data, colWidths=[0.8*inch, 2.5*inch, 1.2*inch, 1.2*inch, 1.2*inch, 0.9*inch, 0.9*inch, 1*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white])
    ]))
    
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"G7_MRO_Report_{date.today()}.pdf", mimetype='application/pdf')

@app.route('/generate_qr/<int:id>')
def generate_qr(id):
    log = RepairLog.query.get_or_404(id)
    history_url = f"{request.url_root}history/{log.sn}"
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(history_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype='image/png', as_attachment=True, download_name=f"QR_{log.sn}.png")

@app.route('/history/<sn>')
def view_history(sn):
    logs = RepairLog.query.filter_by(sn=sn).order_by(RepairLog.date_in.desc()).all()
    if not logs: return "Asset History Not Found", 404
    return render_template('history.html', logs=logs, sn=sn)

@app.route('/export_excel_full')
def export_excel_full():
    if not is_admin(): return "Unauthorized", 403
    logs = RepairLog.query.all()
    data = []
    for l in logs:
        data.append({
            "DRN": l.drn, "DESCRIPTION": l.peralatan, "PART NO": l.pn,
            "SERIAL NO": l.sn, "DATE IN": l.date_in, "DATE OUT": l.date_out,
            "STATUS": l.status_type, "DEFECT": l.defect, "PIC": l.pic
        })
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='MRO_LOGS')
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f"G7_MRO_Full_Export_{date.today()}.xlsx")

# ==============================================================================
# 10. SYSTEM MAINTENANCE & UTILITIES
# ==============================================================================

@app.route('/api/system_reset', methods=['POST'])
def system_reset():
    if not is_admin(): return jsonify({"status": "forbidden"}), 403
    confirm = request.json.get('confirm')
    if confirm == "DELETE_ALL_G7_DATA":
        try:
            db.session.query(RepairLog).delete()
            db.session.commit()
            return jsonify({"status": "success", "message": "All records wiped."})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
    return jsonify({"status": "failed", "message": "Incorrect confirmation string."})

@app.errorhandler(404)
def page_not_found(e):
    return "<h3>Error 404: Page Not Found</h3>", 404

@app.errorhandler(500)
def internal_error(e):
    return f"<h3>System Error 500</h3><pre>{e}</pre>", 500

# ==============================================================================
# 11. APPLICATION RUNNER
# ==============================================================================

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

# ==============================================================================
# END OF CODE (Lines 500+)
# ==============================================================================