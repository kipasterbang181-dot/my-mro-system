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
    ✅ IMPROVED: Parse date from HTML form or Excel with better error handling
    """
    if not date_str or date_str.strip() == '' or str(date_str).strip() == '-':
        return None
    try:
        # Handle different date formats
        if isinstance(date_str, str):
            # Remove time component if exists
            date_part = date_str.split('T')[0].split(' ')[0]
            
            # Try different date formats
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y']:
                try:
                    return datetime.strptime(date_part, fmt).date()
                except ValueError:
                    continue
                    
            logger.warning(f"Could not parse date format: {date_str}")
            return None
            
        elif hasattr(date_str, 'year'):
            # Already a date object
            return date_str
        elif isinstance(date_str, (int, float)):
            # Excel serial date number
            try:
                # Excel epoch starts at 1899-12-30
                excel_date = datetime(1899, 12, 30) + pd.Timedelta(days=date_str)
                return excel_date.date()
            except:
                return None
        return None
    except Exception as e:
        logger.warning(f"Could not parse date: {date_str} - Error: {e}")
        return None

def smart_excel_mapper(row, header_row=None):
    """
    ✅ SMART EXCEL MAPPER - Automatically detects column positions
    This function makes the import flexible and adapts to different Excel formats
    """
    # If we have headers, find columns by name
    if header_row:
        header_lower = [str(h).lower().strip() for h in header_row]
        
        # Find column indices by searching for keywords
        def find_col(keywords):
            for keyword in keywords:
                for i, h in enumerate(header_lower):
                    if keyword in h:
                        return i
            return None
        
        pn_idx = find_col(['part no', 'p/n', 'pn', 'part'])
        sn_idx = find_col(['serial no', 's/n', 'sn', 'serial'])
        desc_idx = find_col(['description', 'peralatan', 'equipment', 'desc'])
        date_in_idx = find_col(['date in', 'in date', 'received'])
        date_out_idx = find_col(['date out', 'out date', 'delivered'])
        status_idx = find_col(['status', 'condition'])
        pic_idx = find_col(['pic', 'jtp', 'person', 'technician'])
        defect_idx = find_col(['defect', 'problem', 'issue', 'remarks'])
    else:
        # Default column positions (based on your original Excel)
        pn_idx = 1
        sn_idx = 3
        desc_idx = 2
        date_in_idx = 4
        date_out_idx = 5
        status_idx = 6
        pic_idx = 7
        defect_idx = 13
    
    # Extract data safely
    def get_val(idx, default='N/A'):
        if idx is not None and idx < len(row):
            val = row[idx]
            return str(val).strip().upper() if val else default
        return default
    
    return {
        'pn': get_val(pn_idx),
        'sn': get_val(sn_idx),
        'peralatan': get_val(desc_idx),
        'date_in': row[date_in_idx] if date_in_idx and date_in_idx < len(row) else None,
        'date_out': row[date_out_idx] if date_out_idx and date_out_idx < len(row) else None,
        'status': get_val(status_idx, 'UNDER REPAIR'),
        'pic': get_val(pic_idx),
        'defect': get_val(defect_idx)
    }

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
            status_type=status_val.upper().strip(),
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
    """
    ✅ ADMIN ONLY - Import with authentication required
    """
    if not session.get('admin'): 
        return jsonify({"error": "Unauthorized"}), 403
    
    data_list = request.json.get('data', [])
    if not data_list: 
        return jsonify({"error": "No data received"}), 400
    
    try:
        logs_to_add = []
        
        for item in data_list:
            # ✅ FIXED: Use improved parse_date_input function
            d_in = parse_date_input(item.get('DATE IN')) or datetime.now().date()
            d_out = parse_date_input(item.get('DATE OUT'))

            new_log = RepairLog(
                drn=str(item.get('DRN', 'N/A')).upper(),
                peralatan=str(item.get('PERALATAN', item.get('DESCRIPTION', 'N/A'))).upper(),
                pn=str(item.get('P/N', item.get('PART NO', 'N/A'))).upper(),
                sn=str(item.get('S/N', item.get('SERIAL NO', 'N/A'))).upper(),
                date_in=d_in,
                date_out=d_out,
                status_type=str(item.get('STATUS', 'UNDER REPAIR')).upper(),
                pic=str(item.get('PIC', 'N/A')).upper(),
                defect=str(item.get('DEFECT', 'N/A')).upper()
            )
            logs_to_add.append(new_log)
        
        if logs_to_add:
            db.session.bulk_save_objects(logs_to_add)
            db.session.commit()
            
        return jsonify({"status": "success", "count": len(logs_to_add)}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Bulk Import Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/import_bulk_public', methods=['POST'])
def import_bulk_public():
    """
    ✅ NEW PUBLIC ENDPOINT - No authentication required
    This allows the index.html page to import Excel without being logged in
    """
    logger.info("=" * 60)
    logger.info("🔓 PUBLIC IMPORT ENDPOINT CALLED")
    logger.info("=" * 60)
    
    try:
        # Check if request has JSON
        if not request.is_json:
            logger.error("❌ Request is not JSON")
            return jsonify({
                "status": "error", 
                "error": "Content-Type must be application/json"
            }), 400
        
        data_list = request.json.get('data', [])
        logger.info(f"📦 Received {len(data_list)} items for import")
        
        if not data_list: 
            logger.warning("⚠️ No data in request")
            return jsonify({
                "status": "error", 
                "error": "No data received"
            }), 400
        
        logs_to_add = []
        success_count = 0
        error_count = 0
        errors = []
        
        for idx, item in enumerate(data_list):
            try:
                # ✅ FIXED: Use improved parse_date_input function
                d_in = parse_date_input(item.get('DATE IN')) or datetime.now().date()
                d_out = parse_date_input(item.get('DATE OUT'))

                # Log first 2 records for debugging
                if idx < 2:
                    logger.info(f"\n📝 Processing Row {idx + 1}:")
                    logger.info(f"  DATE IN (raw): {item.get('DATE IN')}")
                    logger.info(f"  DATE IN (parsed): {d_in}")
                    logger.info(f"  DATE OUT (raw): {item.get('DATE OUT')}")
                    logger.info(f"  DATE OUT (parsed): {d_out}")

                # Create new log entry
                new_log = RepairLog(
                    drn=str(item.get('DRN', '-')).upper(),
                    peralatan=str(item.get('PERALATAN', item.get('DESCRIPTION', 'N/A'))).upper(),
                    pn=str(item.get('P/N', item.get('PART NO', 'N/A'))).upper(),
                    sn=str(item.get('S/N', item.get('SERIAL NO', 'N/A'))).upper(),
                    date_in=d_in,
                    date_out=d_out,
                    status_type=str(item.get('STATUS', 'UNDER REPAIR')).upper().strip(),
                    pic=str(item.get('PIC', 'N/A')).upper(),
                    defect=str(item.get('DEFECT', 'N/A')).upper()
                )
                
                logs_to_add.append(new_log)
                success_count += 1
                
            except Exception as row_error:
                error_count += 1
                error_msg = f"Row {idx + 1}: {str(row_error)}"
                errors.append(error_msg)
                logger.error(f"❌ {error_msg}")
        
        # Bulk save all valid records
        if logs_to_add:
            try:
                db.session.bulk_save_objects(logs_to_add)
                db.session.commit()
                logger.info(f"✅ Successfully imported {success_count} records from public endpoint")
            except Exception as db_error:
                db.session.rollback()
                logger.error(f"❌ Database error during commit: {db_error}")
                return jsonify({
                    "status": "error",
                    "error": f"Database error: {str(db_error)}"
                }), 500
        
        return jsonify({
            "status": "success", 
            "count": success_count,
            "errors": error_count,
            "error_details": errors if errors else None
        }), 200
        
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        logger.error(f"❌ Bulk Import Public Error: {error_msg}")
        logger.error(traceback.format_exc())
        return jsonify({
            "status": "error", 
            "error": error_msg
        }), 500

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
            
            new_status = request.form.get('status') or request.form.get('status_type')
            if new_status: 
                l.status_type = new_status.upper().strip()
            
            d_in_str = request.form.get('date_in')
            if d_in_str: 
                l.date_in = parse_date_input(d_in_str)
            
            d_out_str = request.form.get('date_out')
            if d_out_str and d_out_str.strip():
                l.date_out = parse_date_input(d_out_str)
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
    """
    ✅ FIXED: Bulk delete route with better logging
    """
    if not session.get('admin'): 
        logger.warning("Unauthorized bulk delete attempt")
        return redirect(url_for('login', next=request.path))
    
    selected_ids = request.form.getlist('ids')
    logger.info(f"Bulk delete request received with {len(selected_ids)} items")
    
    if selected_ids:
        try:
            ids_to_delete = [int(i) for i in selected_ids]
            logger.info(f"Deleting IDs: {ids_to_delete}")
            
            deleted_count = RepairLog.query.filter(RepairLog.id.in_(ids_to_delete)).delete(synchronize_session=False)
            db.session.commit()
            
            logger.info(f"Successfully deleted {deleted_count} records")
            flash(f"{deleted_count} rekod berjaya dipadam secara pukal.", "success")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Bulk Delete Error: {e}")
            logger.error(traceback.format_exc())
            flash("Ralat semasa memadam rekod.", "error")
    else:
        logger.warning("No records selected for deletion")
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
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        
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
# ENTRY POINT APLIKASI
# ==============================================================================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
