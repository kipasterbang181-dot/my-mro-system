# ==============================================================================
# IMPORT LIBRARY YANG DIPERLUKAN
# ==============================================================================
import os
import io
import base64
import qrcode
import pandas as pd
import traceback
import logging

from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ==============================================================================
# INISIALISASI APLIKASI FLASK
# ==============================================================================
app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = app.logger

# ==============================================================================
# KONFIGURASI KESELAMATAN & DATABASE
# ==============================================================================
app.secret_key = os.environ.get("SECRET_KEY", "g7_aerospace_key_2026")

DB_URL = "postgresql+psycopg2://postgres.yyvrjgdzhliodbgijlgb:KUCINGPUTIH10@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"

app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

db = SQLAlchemy(app)

# ==============================================================================
# MODEL DATABASE (SKEMA JADUAL)
# ==============================================================================
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

    def to_dict(self):
        return {
            'id': self.id,
            'sn': self.sn,
            'pn': self.pn,
            'peralatan': self.peralatan,
            'status': self.status_type
        }

# ==============================================================================
# PERSEDIAAN DATABASE AWAL
# ==============================================================================
with app.app_context():
    try:
        db.create_all()
        print(">>> Sambungan Database Berjaya: Jadual telah disemak/dicipta.")
    except Exception as e:
        print(f">>> Ralat Sambungan Awal Database: {e}")

# ==============================================================================
# FUNGSI BANTUAN (HELPER FUNCTIONS)
# ==============================================================================
def parse_date_input(date_str):
    """
    Fungsi untuk menukar string tarikh dari HTML form (YYYY-MM-DD)
    kepada objek Python date. Mengembalikan None jika string kosong.
    """
    if not date_str or date_str.strip() == '':
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return None


def normalize_status(status_str):
    """
    ✅ NORMALIZE STATUS FUNCTION
    Normalize status strings to match standard categories.
    This ensures "TDI on Progress", "TDI IN PROGRESS", "TDI On Progress"
    all map to the same status: "TDI IN PROGRESS"
    """
    if not status_str:
        return "UNDER REPAIR"
    
    # Clean the input - remove extra spaces, convert to uppercase
    status = str(status_str).strip().upper()
    
    # Remove multiple spaces
    status = ' '.join(status.split())
    
    # ========== EXACT MAPPING ==========
    
    # Serviceable variations
    if status in ['SERVICEABLE', 'RETURN SERVICEABLE', 'SER']:
        return 'SERVICEABLE'
    
    # Unserviceable
    if status in ['RETURN UNSERVICEABLE', 'UNSERVICEABLE', 'UNSER']:
        return 'RETURN UNSERVICEABLE'
    
    # Under Repair / OV Repair
    if status in ['UNDER REPAIR', 'REPAIR', 'OV REPAIR']:
        return 'UNDER REPAIR'
    
    # Warranty Repair (handle typo "waranty")
    if 'WARRANT' in status or 'WARANT' in status:
        return 'WARRANTY REPAIR'
    
    # TDI variations - THIS IS THE KEY FIX!
    if 'TDI' in status:
        # "TDI ON PROGRESS", "TDI In Progress", "TDI on progress" → TDI IN PROGRESS
        if 'PROGRESS' in status or 'ON PROGRESS' in status:
            return 'TDI IN PROGRESS'
        
        # "TDI to review", "TDI TO REVIEW" → TDI TO REVIEW
        if 'REVIEW' in status:
            return 'TDI TO REVIEW'
        
        # "TDI Ready to quote", "TDI READY TO QUOTE" → TDI READY TO QUOTE
        if 'READY' in status and 'QUOTE' in status:
            return 'TDI READY TO QUOTE'
        
        # Default TDI (if no specific sub-status)
        return 'TDI IN PROGRESS'
    
    # Quote/Delivery
    if 'READY TO QUOTE' in status or 'READY FOR QUOTE' in status:
        return 'READY TO QUOTE'
    
    if 'READY TO DELIVERED' in status or 'READY FOR DELIVER' in status:
        return 'READY TO DELIVERED'
    
    if 'QUOTE SUBMITTED' in status:
        return 'QUOTE SUBMITTED'
    
    # Waiting states
    if 'WAITING' in status:
        return 'WAITING LO'
    
    if 'AWAITING SPARE' in status or 'SPARE' in status:
        return 'AWAITING SPARE'
    
    if 'SPARE READY' in status:
        return 'SPARE READY'
    
    # Return
    if 'RETURN' in status and 'AEROTREE' in status:
        return 'RETURN TO AEROTREE'
    
    # If no match found, return uppercase version
    return status


# ==============================================================================
# LALUAN (ROUTES) - HALAMAN UTAMA & LOGIN
# ==============================================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    next_page = request.args.get('next')

    if request.method == 'POST':
        username = request.form.get('u')
        password = request.form.get('p')

        if username == 'admin' and password == 'password123':
            session['admin'] = True
            flash("Log masuk berjaya!", "success")

            target = request.form.get('next_target')
            if target and target != 'None' and target != '':
                return redirect(target)
            return redirect(url_for('admin'))
        else:
            flash("Username atau Password salah!", "error")

    return render_template('login.html', next_page=next_page)

@app.route('/logout')
def logout():
    session.clear()
    flash("Anda telah log keluar.", "info")
    return redirect(url_for('index'))

# ==============================================================================
# LALUAN (ROUTES) - DASHBOARD ADMIN
# ==============================================================================

@app.route('/admin')
def admin():
    if not session.get('admin'): 
        return redirect(url_for('login', next=request.path))
    
    try:
        logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
        
        # ✅ UPDATED STATUS LIST - Cleaned up, no duplicates
        status_list = [
            "SERVICEABLE",
            "RETURN UNSERVICEABLE",
            "UNDER REPAIR",          # Includes "OV REPAIR"
            "WARRANTY REPAIR",
            "TDI IN PROGRESS",       # ✅ Includes "TDI on Progress", "TDI On Progress"
            "TDI TO REVIEW",
            "TDI READY TO QUOTE",    # ✅ Now will show correct count
            "READY TO QUOTE",
            "QUOTE SUBMITTED",
            "READY TO DELIVERED",
            "READY TO DELIVERED WARRANTY",
            "WAITING LO",
            "AWAITING SPARE",
            "SPARE READY",
            "RETURN TO AEROTREE"
        ]

        # Add any new statuses from DB that aren't in the list
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
        logger.error(f"Admin Dashboard Error: {e}")
        return f"<h3>Admin Dashboard Error (500)</h3><p>{str(e)}</p><pre>{error_details}</pre>", 500

# ==============================================================================
# LALUAN (ROUTES) - DATA MASUK & IMPORT
# ==============================================================================

@app.route('/incoming', methods=['GET', 'POST'])
def incoming():
    if request.method == 'GET':
        return render_template('incoming.html')
    
    try:
        status_val = request.form.get('status') or request.form.get('status_type') or "UNDER REPAIR"
        # ✅ USE NORMALIZE_STATUS
        normalized_status = normalize_status(status_val)
        
        d_in_val = request.form.get('date_in')
        d_in = parse_date_input(d_in_val)
        if not d_in:
            d_in = datetime.now().date()
        
        new_log = RepairLog(
            drn=request.form.get('drn', '').upper(),
            peralatan=request.form.get('peralatan', '').upper(),
            pn=request.form.get('pn', '').upper(),
            sn=request.form.get('sn', '').upper(),
            date_in=d_in,
            defect=request.form.get('defect', 'N/A').upper(), 
            status_type=normalized_status,  # ✅ NORMALIZED
            pic=request.form.get('pic', 'N/A').upper()
        )
        
        db.session.add(new_log)
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({"status": "success", "message": "Data Berjaya Disimpan!"}), 200

        flash("Data Berjaya Disimpan!", "success")
        return redirect(url_for('index'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Incoming Data Error: {e}")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"status": "error", "message": str(e)}), 500
        return f"Database Error: {str(e)}", 500


@app.route('/import_bulk', methods=['POST'])
def import_bulk():
    if not session.get('admin'): 
        return jsonify({"error": "Unauthorized"}), 403
    
    data_list = request.json.get('data', [])
    if not data_list: 
        return jsonify({"error": "No data received"}), 400
    
    try:
        existing = db.session.query(
            RepairLog.pn, RepairLog.sn, RepairLog.date_in
        ).all()
        existing_set = set()
        for row in existing:
            existing_set.add((
                str(row[0] or '').upper().strip(),
                str(row[1] or '').upper().strip(),
                str(row[2]) if row[2] else ''
            ))

        def parse_date(d_str):
            if not d_str or str(d_str).strip() in ('', '-', 'None'):
                return None
            try:
                if isinstance(d_str, str):
                    date_part = d_str.split('T')[0].split(' ')[0]
                    return datetime.strptime(date_part, '%Y-%m-%d').date()
                elif hasattr(d_str, 'year'):
                    return d_str
                return None
            except Exception as e:
                logger.warning(f"Date parse error for '{d_str}': {e}")
                return None

        logs_to_add = []
        skipped = 0
        seen_in_batch = set()

        for item in data_list:
            d_in = parse_date(item.get('DATE IN')) or datetime.now().date()
            d_out = parse_date(item.get('DATE OUT'))

            pn_val  = str(item.get('P/N', item.get('PART NO', 'N/A'))).upper().strip()
            sn_val  = str(item.get('S/N', item.get('SERIAL NO', 'N/A'))).upper().strip()
            d_in_str = str(d_in)

            key = (pn_val, sn_val, d_in_str)

            if key in existing_set:
                skipped += 1
                continue

            if key in seen_in_batch:
                skipped += 1
                continue

            seen_in_batch.add(key)

            new_log = RepairLog(
                drn=str(item.get('DRN', 'N/A')).upper(),
                peralatan=str(item.get('PERALATAN', item.get('DESCRIPTION', 'N/A'))).upper(),
                pn=pn_val,
                sn=sn_val,
                date_in=d_in,
                date_out=d_out,
                status_type=normalize_status(item.get('STATUS', 'UNDER REPAIR')),  # ✅ NORMALIZED
                pic=str(item.get('PIC', 'N/A')).upper(),
                defect=str(item.get('DEFECT', 'N/A')).upper()
            )
            logs_to_add.append(new_log)
        
        if logs_to_add:
            db.session.bulk_save_objects(logs_to_add)
            db.session.commit()
            
        return jsonify({"status": "success", "count": len(logs_to_add), "skipped": skipped}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Bulk Import Error: {e}")
        return jsonify({"error": str(e)}), 500

# ==============================================================================
# LALUAN (ROUTES) - KEMASKINI, EDIT & DELETE
# ==============================================================================

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if not session.get('admin'): 
        return redirect(url_for('login', next=request.full_path))
    
    l = RepairLog.query.get_or_404(id)
    source = request.args.get('from', request.form.get('origin_source', 'admin'))

    if request.method == 'POST':
        try:
            l.peralatan = request.form.get('peralatan', '').upper()
            l.pn = request.form.get('pn', '').upper()
            l.sn = request.form.get('sn', '').upper()
            l.drn = request.form.get('drn', '').upper()
            l.pic = request.form.get('pic', '').upper()
            l.defect = request.form.get('defect', '').upper()
            
            # ✅ USE NORMALIZE_STATUS
            new_status = request.form.get('status') or request.form.get('status_type')
            if new_status: 
                l.status_type = normalize_status(new_status)
            
            d_in_str = request.form.get('date_in')
            if d_in_str: 
                l.date_in = datetime.strptime(d_in_str, '%Y-%m-%d').date()
            
            d_out_str = request.form.get('date_out')
            if d_out_str and d_out_str.strip():
                l.date_out = datetime.strptime(d_out_str, '%Y-%m-%d').date()
            else:
                l.date_out = None 
                
            l.last_updated = datetime.now()
            db.session.commit()
            flash("Rekod Berjaya Dikemaskini!", "success")
            
            if source == 'view_tag':
                return redirect(url_for('view_tag', id=id))
            return redirect(url_for('admin'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Edit Error ID {id}: {e}")
            flash(f"Ralat Simpan: {str(e)}", "error")

    return render_template('edit.html', item=l, source=source)


@app.route('/delete/<int:id>')
def delete_log(id):
    if not session.get('admin'): 
        return redirect(url_for('login', next=request.path))
    
    try:
        l = RepairLog.query.get_or_404(id)
        db.session.delete(l)
        db.session.commit()
        flash("Rekod dipadam.", "success")
    except Exception as e:
        db.session.rollback()
        flash("Gagal memadam rekod.", "error")
        
    return redirect(url_for('admin'))


@app.route('/delete_bulk', methods=['POST'])
def bulk_delete():
    if not session.get('admin'): 
        return redirect(url_for('login', next=request.path))
    
    selected_ids = request.form.getlist('ids') 
    
    if selected_ids:
        try:
            ids_to_delete = [int(i) for i in selected_ids]
            RepairLog.query.filter(RepairLog.id.in_(ids_to_delete)).delete(synchronize_session=False)
            db.session.commit()
            flash(f"{len(ids_to_delete)} rekod berjaya dipadam secara pukal.", "success")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Bulk Delete Error: {e}")
            flash("Ralat semasa memadam rekod.", "error")
    else:
        flash("Tiada rekod dipilih untuk dipadam.", "warning")
            
    return redirect(url_for('admin'))

# ==============================================================================
# LALUAN (ROUTES) - VIEW, HISTORY & REPORT
# ==============================================================================

@app.route('/history/<path:sn>')
def history(sn):
    logs = RepairLog.query.filter_by(sn=sn).order_by(RepairLog.date_in.desc()).all()
    
    if not logs:
        asset_info = {"peralatan": "UNKNOWN", "sn": sn}
    else:
        asset_info = logs[0]
        
    return render_template('history.html', logs=logs, asset=asset_info, sn=sn)


@app.route('/view_report/<int:id>')
def view_report(id):
    if not session.get('admin'): 
        return redirect(url_for('login', next=request.path))
    
    l = RepairLog.query.get_or_404(id)
    return render_template('view_report.html', l=l)


@app.route('/view_tag/<int:id>')
def view_tag(id):
    l = RepairLog.query.get_or_404(id)
    count = RepairLog.query.filter_by(sn=l.sn).count()
    return render_template('view_tag.html', l=l, logs_count=count)

# ==============================================================================
# LALUAN (ROUTES) - JANA FILE (PDF/EXCEL/QR)
# ==============================================================================

@app.route('/download_qr/<int:id>')
def download_qr(id):
    l = RepairLog.query.get_or_404(id)
    qr_url = f"{request.url_root}view_tag/{l.id}"
    qr = qrcode.make(qr_url)
    
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    buf.seek(0)
    
    return send_file(buf, mimetype='image/png', as_attachment=True, download_name=f"QR_{l.sn}.png")


@app.route('/download_report')
def download_report():
    if not session.get('admin'): 
        return redirect(url_for('login', next=request.path))
    
    try:
        logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=landscape(letter), leftMargin=15, rightMargin=15)
        elements = []
        
        styles = getSampleStyleSheet()
        title_style = styles['Title']
        
        elements.append(Paragraph(f"G7 AEROSPACE - REPAIR LOG SUMMARY ({datetime.now().strftime('%d/%m/%Y')})", title_style))
        elements.append(Spacer(1, 12))
        
        table_cell_style = ParagraphStyle(name='TableCell', fontSize=7, leading=8, alignment=1)
        
        data = [["ID", "PERALATAN", "P/N", "S/N", "DEFECT", "DATE IN", "DATE OUT", "STATUS", "PIC"]]
        
        for l in logs:
            data.append([
                l.id, 
                Paragraph(l.peralatan or "N/A", table_cell_style), 
                Paragraph(l.pn or "N/A", table_cell_style), 
                l.sn, 
                Paragraph(l.defect or "N/A", table_cell_style), 
                str(l.date_in), 
                str(l.date_out) if l.date_out else "-", 
                l.status_type, 
                Paragraph(l.pic or "N/A", table_cell_style)
            ])
        
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f1f5f9')]),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(t)
        doc.build(elements)
        buf.seek(0)
        
        return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name="Full_Summary.pdf")
        
    except Exception as e:
        logger.error(f"PDF Generation Error: {e}")
        return f"Error Generating PDF: {e}"


@app.route('/export_excel')
def export_excel_data():
    if not session.get('admin'): 
        return redirect(url_for('login', next=request.path))
    
    try:
        logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
        
        data = [{
            "ID": l.id, 
            "DRN": l.drn, 
            "PERALATAN": l.peralatan, 
            "P/N": l.pn, 
            "S/N": l.sn,
            "DEFECT": l.defect or "N/A", 
            "DATE IN": str(l.date_in), 
            "DATE OUT": str(l.date_out) if l.date_out else "-",
            "STATUS": l.status_type, 
            "PIC": l.pic
        } for l in logs]
        
        df = pd.DataFrame(data)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Repair Logs')
            
            worksheet = writer.sheets['Repair Logs']
            for i, col in enumerate(df.columns):
                width = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.set_column(i, i, width)
                
        output.seek(0)
        
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name="Repair_Log.xlsx")
        
    except Exception as e:
        logger.error(f"Excel Export Error: {e}")
        return f"Error Exporting Excel: {e}"


# ==============================================================================
# ✅ ONE-TIME CLEANUP ROUTE - Normalize existing database records
# ==============================================================================

@app.route('/normalize_existing_statuses')
def normalize_existing_statuses():
    """
    ONE-TIME: Normalize all existing status values in database
    Visit this URL once after deploying the new code to fix existing data
    """
    if not session.get('admin'): 
        return redirect(url_for('login'))
    
    try:
        all_logs = RepairLog.query.all()
        updated_count = 0
        changes = {}
        
        for log in all_logs:
            old_status = log.status_type
            new_status = normalize_status(old_status)
            
            if old_status != new_status:
                change_key = f"{old_status} → {new_status}"
                if change_key not in changes:
                    changes[change_key] = 0
                changes[change_key] += 1
                
                log.status_type = new_status
                log.last_updated = datetime.now()
                updated_count += 1
        
        db.session.commit()
        
        report = f"✅ NORMALIZATION COMPLETE!\n\n"
        report += f"Total records updated: {updated_count}\n\n"
        report += "Changes made:\n"
        for change, count in sorted(changes.items(), key=lambda x: x[1], reverse=True):
            report += f"  • {change} ({count} records)\n"
        
        flash(report, "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error: {str(e)}", "error")
    
    return redirect(url_for('admin'))


# ==============================================================================
# LALUAN PUBLIC IMPORT (tanpa login) — digunakan oleh index.html
# ==============================================================================

@app.route('/import_bulk_public', methods=['POST'])
def import_bulk_public():
    data_list = request.json.get('data', [])
    if not data_list:
        return jsonify({"error": "No data received"}), 400

    try:
        existing = db.session.query(
            RepairLog.pn, RepairLog.sn, RepairLog.date_in
        ).all()
        existing_set = set()
        for row in existing:
            existing_set.add((
                str(row[0] or '').upper().strip(),
                str(row[1] or '').upper().strip(),
                str(row[2]) if row[2] else ''
            ))

        def parse_date(d_str):
            if not d_str or str(d_str).strip() in ('', '-', 'None'):
                return None
            try:
                if isinstance(d_str, str):
                    date_part = d_str.split('T')[0].split(' ')[0]
                    return datetime.strptime(date_part, '%Y-%m-%d').date()
                elif hasattr(d_str, 'year'):
                    return d_str
                return None
            except Exception as e:
                logger.warning(f"Date parse error for '{d_str}': {e}")
                return None

        logs_to_add = []
        skipped = 0
        seen_in_batch = set()

        for item in data_list:
            d_in = parse_date(item.get('DATE IN')) or datetime.now().date()
            d_out = parse_date(item.get('DATE OUT'))

            pn_val  = str(item.get('P/N', item.get('PART NO', 'N/A'))).upper().strip()
            sn_val  = str(item.get('S/N', item.get('SERIAL NO', 'N/A'))).upper().strip()
            d_in_str = str(d_in)

            key = (pn_val, sn_val, d_in_str)

            if key in existing_set:
                skipped += 1
                continue
            if key in seen_in_batch:
                skipped += 1
                continue

            seen_in_batch.add(key)

            new_log = RepairLog(
                drn=str(item.get('DRN', 'N/A')).upper(),
                peralatan=str(item.get('PERALATAN', item.get('DESCRIPTION', 'N/A'))).upper(),
                pn=pn_val,
                sn=sn_val,
                date_in=d_in,
                date_out=d_out,
                status_type=normalize_status(item.get('STATUS', 'UNDER REPAIR')),  # ✅ NORMALIZED
                pic=str(item.get('PIC', 'N/A')).upper(),
                defect=str(item.get('DEFECT', 'N/A')).upper()
            )
            logs_to_add.append(new_log)

        if logs_to_add:
            db.session.bulk_save_objects(logs_to_add)
            db.session.commit()

        return jsonify({"status": "success", "count": len(logs_to_add), "skipped": skipped}), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Public Bulk Import Error: {e}")
        return jsonify({"error": str(e)}), 500

# ==============================================================================
# ENTRY POINT APLIKASI
# ==============================================================================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
