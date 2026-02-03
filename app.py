# ==============================================================================
# IMPORT LIBRARY YANG DIPERLUKAN
# ==============================================================================
# os: Untuk berinteraksi dengan sistem operasi (contoh: baca environment variables).
import os

# io: Untuk mengendalikan aliran input/output data (digunakan untuk file generation).
import io

# base64: Untuk encoding data binary jika perlu (jarang guna tapi ada library support).
import base64

# qrcode: Library untuk menjana QR Code secara dinamik.
import qrcode

# pandas: Library berkuasa untuk analisis data dan manipulasi Excel.
import pandas as pd

# traceback: Untuk mencetak ralat penuh (stack trace) jika program crash.
import traceback

# logging: Untuk mencatat aktiviti sistem (debugging dan audit trail).
import logging

# Flask Framework: Komponen utama untuk membina aplikasi web.
# render_template: Untuk paparkan file HTML.
# request: Untuk terima data dari form atau URL.
# redirect/url_for: Untuk pindah page.
# session: Untuk simpan data login pengguna sementara.
# send_file: Untuk membenarkan pengguna download file (PDF/Excel/PNG).
# flash: Untuk paparkan mesej notifikasi (Success/Error).
# jsonify: Untuk hantar data dalam format JSON (untuk API/AJAX).
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash, jsonify

# SQLAlchemy: ORM (Object Relational Mapper) untuk berinteraksi dengan Database.
from flask_sqlalchemy import SQLAlchemy

# datetime: Untuk pengurusan tarikh dan masa.
from datetime import datetime

# ==============================================================================
# LIBRARY UNTUK MENJANA LAPORAN PDF (REPORTLAB)
# ==============================================================================
# reportlab: Library standard industri untuk buat PDF guna Python.
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ==============================================================================
# INISIALISASI APLIKASI FLASK
# ==============================================================================
app = Flask(__name__)

# Tetapan Logger untuk memudahkan debugging jika ada error
logging.basicConfig(level=logging.INFO)
logger = app.logger

# ==============================================================================
# KONFIGURASI KESELAMATAN & DATABASE
# ==============================================================================

# SECRET_KEY: Digunakan untuk encrypt session cookies dan flash messages.
# Tanpa ini, login takkan berfungsi.
app.secret_key = os.environ.get("SECRET_KEY", "g7_aerospace_key_2026")

# DB_URL: Sambungan ke Supabase PostgreSQL.
# PERINGATAN: Pastikan URL ini betul dan password tidak mengandungi karakter pelik yang perlu di-encode.
DB_URL = "postgresql+psycopg2://postgres.yyvrjgdzhliodbgijlgb:KUCINGPUTIH10@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"

# Menetapkan URI database ke konfigurasi Flask
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL

# Mematikan notifikasi perubahan track (menjimatkan memori)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Konfigurasi enjin SQL untuk memastikan sambungan tidak putus (pool recycle)
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,  # Check connection sebelum guna
    "pool_recycle": 300,    # Refresh connection setiap 300 saat
}

# Inisialisasi objek Database
db = SQLAlchemy(app)

# ==============================================================================
# MODEL DATABASE (SKEMA JADUAL)
# ==============================================================================
class RepairLog(db.Model):
    """
    Model ini mewakili jadual 'repair_log' dalam database.
    Setiap variable mewakili satu kolum dalam jadual.
    """
    __tablename__ = 'repair_log'

    # ID unik untuk setiap rekod (Primary Key)
    id = db.Column(db.Integer, primary_key=True)

    # DRN: Document Reference Number (Rujukan dokumen)
    drn = db.Column(db.String(100)) 

    # Peralatan: Nama aset atau equipment
    peralatan = db.Column(db.String(255))

    # PN: Part Number
    pn = db.Column(db.String(255))

    # SN: Serial Number (Penting untuk tracking sejarah)
    sn = db.Column(db.String(255))

    # Tarikh Masuk
    date_in = db.Column(db.Date) 

    # Tarikh Keluar (Boleh jadi kosong/NULL jika belum siap)
    date_out = db.Column(db.Date) 

    # Defect: Kerosakan yang dilaporkan
    defect = db.Column(db.Text)

    # Status: Status semasa (Serviceable, Under Repair, dll)
    status_type = db.Column(db.String(100)) 

    # PIC: Person In Charge (Orang yang bertanggungjawab)
    pic = db.Column(db.String(255))

    # Warranty: Status waranti (True/False)
    is_warranty = db.Column(db.Boolean, default=False) 

    # Created At: Bila rekod ini dicipta
    created_at = db.Column(db.DateTime, default=datetime.now)

    # Last Updated: Bila kali terakhir rekod dikemaskini
    last_updated = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        """
        Fungsi bantuan untuk menukar objek database kepada Dictionary.
        Berguna untuk API JSON response.
        """
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
        # Cuba cipta jadual jika belum wujud
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

# ==============================================================================
# LALUAN (ROUTES) - HALAMAN UTAMA & LOGIN
# ==============================================================================

@app.route('/')
def index():
    """
    Halaman Utama (Landing Page).
    Memaparkan borang untuk memasukkan data baru atau butang login.
    """
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Laluan untuk Log Masuk Admin.
    Menyemak username dan password.
    """
    # Ambil parameter 'next' jika pengguna cuba akses page admin tanpa login
    next_page = request.args.get('next')

    if request.method == 'POST':
        username = request.form.get('u')
        password = request.form.get('p')

        # Logik Login Mudah (Hardcoded untuk contoh ini)
        if username == 'admin' and password == 'password123':
            # Set session admin kepada True
            session['admin'] = True
            
            flash("Log masuk berjaya!", "success")

            # Redirect ke page asal atau ke Admin Dashboard
            target = request.form.get('next_target')
            if target and target != 'None' and target != '':
                return redirect(target)
            return redirect(url_for('admin'))
        else:
            # Jika password salah
            flash("Username atau Password salah!", "error")

    return render_template('login.html', next_page=next_page)

@app.route('/logout')
def logout():
    """
    Log Keluar.
    Membuang session dan menghantar pengguna ke halaman utama.
    """
    session.clear()
    flash("Anda telah log keluar.", "info")
    return redirect(url_for('index'))

# ==============================================================================
# LALUAN (ROUTES) - DASHBOARD ADMIN
# ==============================================================================

@app.route('/admin')
def admin():
    """
    Dashboard utama Admin.
    Memaparkan statistik, senarai aset, dan carta ringkasan.
    """
    # Semak sekuriti: Adakah pengguna sudah login?
    if not session.get('admin'): 
        return redirect(url_for('login', next=request.path))
    
    try:
        # Ambil semua rekod dari database, susun dari yang terbaru (ID Descending)
        logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
        
        # Senarai status standard untuk statistik
        status_list = [
            "SERVICEABLE", "RETURN SERVICEABLE", "RETURN UNSERVICEABLE",
            "WAITING LO", "OV REPAIR", "UNDER REPAIR", "AWAITING SPARE",
            "SPARE READY", "WARRANTY REPAIR", "QUOTE SUBMITTED",
            "TDI IN PROGRESS", "TDI TO REVIEW", "TDI READY TO QUOTE",
            "READY TO DELIVERED WARRANTY", "READY TO QUOTE", "READY TO DELIVERED"
        ]

        # Tambah status dinamik dari database jika ada status baru yang tak tersenarai
        # ─── BLACKLIST: status yang tidak patut paparkan dalam stats ───
        status_blacklist = {"OV TDI"}

        db_statuses = db.session.query(RepairLog.status_type).distinct().all()
        for s in db_statuses:
            if s[0]:
                up_s = s[0].upper().strip()
                if up_s not in status_list and up_s not in status_blacklist:
                    status_list.append(up_s)

        # Logik Statistik (Tahun)
        # Ambil tahun-tahun unik dari data date_in
        years = sorted(list(set([l.date_in.year for l in logs if l.date_in])))
        if not years: years = [datetime.now().year] # Default tahun semasa jika tiada data

        # Inisialisasi Matriks Statistik
        stats_matrix = {status: {year: 0 for year in years} for status in status_list}
        row_totals = {status: 0 for status in status_list}
        column_totals = {year: 0 for year in years}
        grand_total = 0

        # Pengiraan Statistik
        for l in logs:
            if l.date_in and l.status_type:
                stat_key = l.status_type.upper().strip()
                year_key = l.date_in.year
                
                if stat_key in stats_matrix and year_key in years:
                    stats_matrix[stat_key][year_key] += 1
                    row_totals[stat_key] += 1
                    column_totals[year_key] += 1
                    grand_total += 1

        # Render template admin dengan data yang diproses
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
        # Jika berlaku error kritikal pada dashboard
        error_details = traceback.format_exc()
        logger.error(f"Admin Dashboard Error: {e}")
        return f"<h3>Admin Dashboard Error (500)</h3><p>{str(e)}</p><pre>{error_details}</pre>", 500

# ==============================================================================
# LALUAN (ROUTES) - DATA MASUK & IMPORT
# ==============================================================================

@app.route('/incoming', methods=['GET', 'POST'])
def incoming():
    """
    Laluan untuk borang data masuk (manual entry) dari index.html.
    """
    # Jika GET request, paparkan borang sahaja (biasanya dikendalikan index.html)
    if request.method == 'GET':
        return render_template('incoming.html')
    
    try:
        # Ambil data dari Form Request
        status_val = request.form.get('status') or request.form.get('status_type') or "UNDER REPAIR"
        d_in_val = request.form.get('date_in')
        
        # Parse tarikh masuk
        d_in = parse_date_input(d_in_val)
        if not d_in:
            d_in = datetime.now().date() # Default hari ini jika kosong
        
        # Cipta objek RepairLog baru
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
        
        # Simpan ke Database
        db.session.add(new_log)
        db.session.commit()
        
        # Handle response untuk AJAX atau Form Submit biasa
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({"status": "success", "message": "Data Berjaya Disimpan!"}), 200

        flash("Data Berjaya Disimpan!", "success")
        return redirect(url_for('index'))
        
    except Exception as e:
        # Rollback jika ada error DB
        db.session.rollback()
        logger.error(f"Incoming Data Error: {e}")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"status": "error", "message": str(e)}), 500
        return f"Database Error: {str(e)}", 500


@app.route('/import_bulk', methods=['POST'])
def import_bulk():
    """
    API untuk memproses Import Data pukal dari Excel (JSON payload).
    ✅ With duplicate detection — skip records that already exist in DB.
    """
    if not session.get('admin'): 
        return jsonify({"error": "Unauthorized"}), 403
    
    data_list = request.json.get('data', [])
    if not data_list: 
        return jsonify({"error": "No data received"}), 400
    
    try:
        # ─── Load existing records as a SET for fast lookup ───
        # Key = (pn, sn, date_in) — if all 3 match, it's a duplicate
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
        seen_in_batch = set()  # dedupe WITHIN the incoming payload too

        for item in data_list:
            d_in = parse_date(item.get('DATE IN')) or datetime.now().date()
            d_out = parse_date(item.get('DATE OUT'))

            pn_val  = str(item.get('P/N', item.get('PART NO', 'N/A'))).upper().strip()
            sn_val  = str(item.get('S/N', item.get('SERIAL NO', 'N/A'))).upper().strip()
            d_in_str = str(d_in)

            # ─── DUPLICATE CHECK ───
            key = (pn_val, sn_val, d_in_str)

            # Skip if already in DB
            if key in existing_set:
                skipped += 1
                continue

            # Skip if duplicate within this same batch
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
                status_type=str(item.get('STATUS', 'UNDER REPAIR')).upper(),
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
    """
    Laluan untuk mengedit rekod sedia ada.
    """
    # Semak sekuriti
    if not session.get('admin'): 
        return redirect(url_for('login', next=request.full_path))
    
    # Dapatkan rekod dari DB atau 404 jika tiada
    l = RepairLog.query.get_or_404(id)
    
    # Dapatkan parameter asal (untuk butang 'Back')
    source = request.args.get('from', request.form.get('origin_source', 'admin'))

    if request.method == 'POST':
        try:
            # Kemaskini maklumat asas (Pastikan UPPERCASE)
            l.peralatan = request.form.get('peralatan', '').upper()
            l.pn = request.form.get('pn', '').upper()
            l.sn = request.form.get('sn', '').upper()
            l.drn = request.form.get('drn', '').upper()
            l.pic = request.form.get('pic', '').upper()
            
            # Update Defect
            l.defect = request.form.get('defect', '').upper()
            
            # Update Status
            new_status = request.form.get('status') or request.form.get('status_type')
            if new_status: 
                l.status_type = new_status.upper().strip()
            
            # Date Handling Logic - Memastikan tarikh tidak hilang
            d_in_str = request.form.get('date_in')
            if d_in_str: 
                l.date_in = datetime.strptime(d_in_str, '%Y-%m-%d').date()
            
            # Date Out Handling
            d_out_str = request.form.get('date_out')
            if d_out_str and d_out_str.strip():
                l.date_out = datetime.strptime(d_out_str, '%Y-%m-%d').date()
            else:
                # Jika kosong, set kepada None dalam database
                l.date_out = None 
                
            # Kemaskini timestamp
            l.last_updated = datetime.now()
            
            # Simpan perubahan
            db.session.commit()
            flash("Rekod Berjaya Dikemaskini!", "success")
            
            # Redirect ke halaman yang betul (History/View Tag atau Admin)
            if source == 'view_tag':
                return redirect(url_for('view_tag', id=id))
            return redirect(url_for('admin'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Edit Error ID {id}: {e}")
            flash(f"Ralat Simpan: {str(e)}", "error")

    # Paparkan template edit dengan data sedia ada
    return render_template('edit.html', item=l, source=source)


@app.route('/isolate/<int:id>')
def isolate_log(id):
    """
    Isolate a component — sets status to ISOLATED, clears date_out.
    Admin only.
    """
    if not session.get('admin'):
        return redirect(url_for('login', next=request.path))

    try:
        l = RepairLog.query.get_or_404(id)
        l.status_type = "ISOLATED"
        l.date_out = None
        l.last_updated = datetime.now()
        db.session.commit()
        flash("Rekod telah di-isolate.", "success")
    except Exception as e:
        db.session.rollback()
        flash("Gagal isolate rekod.", "error")

    return redirect(url_for('admin'))


@app.route('/clear_all', methods=['POST'])
def clear_all():
    """
    Padam SEMUA rekod dari database.
    Admin only. Guna untuk fresh reimport.
    """
    if not session.get('admin'):
        return jsonify({"error": "Unauthorized"}), 403

    try:
        RepairLog.query.delete()
        db.session.commit()
        logger.info("All records cleared by admin")
        return jsonify({"status": "success", "message": "All records deleted"}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Clear All Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/delete/<int:id>')
def delete_log(id):
    """
    Padam satu rekod sahaja.
    """
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
    Bulk Delete - Padam multiple records serentak
    """
    if not session.get('admin'): 
        return redirect(url_for('login', next=request.path))
    
    # Ambil senarai ID dari form checkbox (name="ids" dalam HTML)
    selected_ids = request.form.getlist('ids') 
    
    if selected_ids:
        try:
            # Tukar ID kepada integer
            ids_to_delete = [int(i) for i in selected_ids]
            
            # Padam rekod yang ID-nya ada dalam senarai
            RepairLog.query.filter(RepairLog.id.in_(ids_to_delete)).delete(synchronize_session=False)
            
            # Commit transaksi
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
    """
    History Route - Shows all records for a specific serial number
    """
    # Cari semua rekod berkaitan SN ini
    logs = RepairLog.query.filter_by(sn=sn).order_by(RepairLog.date_in.desc()).all()
    
    # Jika tiada log, buat dummy data untuk elak error template
    if not logs:
        asset_info = {"peralatan": "UNKNOWN", "sn": sn}
    else:
        asset_info = logs[0] # Ambil info aset terkini
        
    return render_template('history.html', logs=logs, asset=asset_info, sn=sn)


@app.route('/view_report/<int:id>')
def view_report(id):
    """
    View Report - Shows printable report for a specific record
    """
    if not session.get('admin'): 
        return redirect(url_for('login', next=request.path))
    
    # Dapatkan data atau return 404 jika ID salah
    l = RepairLog.query.get_or_404(id)
    return render_template('view_report.html', l=l)


@app.route('/view_tag/<int:id>')
def view_tag(id):
    """
    View Tag - Shows digital asset tag with QR code
    """
    # Dapatkan log spesifik berdasarkan ID
    l = RepairLog.query.get_or_404(id)
    
    # Kira berapa kali item dengan SN ini telah diselenggara
    count = RepairLog.query.filter_by(sn=l.sn).count()
    
    return render_template('view_tag.html', l=l, logs_count=count)

# ==============================================================================
# LALUAN (ROUTES) - JANA FILE (PDF/EXCEL/QR)
# ==============================================================================

@app.route('/download_qr/<int:id>')
def download_qr(id):
    """
    Menjana QR Code dalam format PNG untuk dimuat turun.
    QR Code links to view_tag page
    """
    # Dapatkan info aset
    l = RepairLog.query.get_or_404(id)
    
    # URL yang akan ditanam dalam QR Code (Link to view_tag)
    qr_url = f"{request.url_root}view_tag/{l.id}"
    
    # Jana QR
    qr = qrcode.make(qr_url)
    
    # Simpan ke dalam memori (BytesIO) tanpa perlu simpan fail fizikal
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    buf.seek(0)
    
    # Hantar fail kepada pengguna
    return send_file(buf, mimetype='image/png', as_attachment=True, download_name=f"QR_{l.sn}.png")


@app.route('/download_report')
def download_report():
    """
    Menjana laporan PDF penuh menggunakan ReportLab.
    Memaparkan semua rekod dalam format jadual yang kemas.
    """
    # Sekuriti check
    if not session.get('admin'): 
        return redirect(url_for('login', next=request.path))
    
    try:
        # Ambil semua data
        logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
        
        # Buffer untuk simpan PDF dalam memori
        buf = io.BytesIO()
        
        # Setup dokumen PDF (Landscape A4)
        doc = SimpleDocTemplate(buf, pagesize=landscape(letter), leftMargin=15, rightMargin=15)
        elements = []
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = styles['Title']
        
        # Tajuk Laporan
        elements.append(Paragraph(f"G7 AEROSPACE - REPAIR LOG SUMMARY ({datetime.now().strftime('%d/%m/%Y')})", title_style))
        elements.append(Spacer(1, 12))
        
        # Style untuk sel jadual (Font kecil supaya muat)
        table_cell_style = ParagraphStyle(name='TableCell', fontSize=7, leading=8, alignment=1)
        
        # Header Jadual
        data = [["ID", "PERALATAN", "P/N", "S/N", "DEFECT", "DATE IN", "DATE OUT", "STATUS", "PIC"]]
        
        # Isi Data
        for l in logs:
            # Gunakan Paragraph untuk text wrapping jika terlalu panjang
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
        
        # Konfigurasi Table
        t = Table(data, repeatRows=1) # Ulang header setiap page
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')), # Header gelap
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), # Tulisan putih
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black), # Grid line
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f1f5f9')]), # Zebra striping
            ('FONTSIZE', (0, 0), (-1, -1), 7), # Saiz font
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(t)
        
        # Bina PDF
        doc.build(elements)
        buf.seek(0)
        
        return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name="Full_Summary.pdf")
        
    except Exception as e:
        logger.error(f"PDF Generation Error: {e}")
        return f"Error Generating PDF: {e}"


@app.route('/export_excel')
def export_excel_data():
    """
    Menjana fail Excel (.xlsx) mengandungi semua data database.
    Menggunakan Pandas untuk prestasi tinggi.
    """
    if not session.get('admin'): 
        return redirect(url_for('login', next=request.path))
    
    try:
        logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
        
        # Format data untuk DataFrame
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
        
        # Buat DataFrame
        df = pd.DataFrame(data)
        
        # Tulis ke buffer BytesIO
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Repair Logs')
            
            # Auto-adjust column width (Optional visual improvement)
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
# CLEANUP — Padam duplikat dari DB (admin only)
# ==============================================================================

@app.route('/cleanup_duplicates', methods=['POST'])
def cleanup_duplicates():
    """
    Removes exact duplicate records from DB.
    Keeps the FIRST (lowest ID) for each (pn, sn, date_in) group.
    Admin only.
    """
    if not session.get('admin'):
        return jsonify({"error": "Unauthorized"}), 403

    try:
        # Get all records grouped by (pn, sn, date_in)
        from sqlalchemy import func
        
        # Find duplicate groups: (pn, sn, date_in) that appear more than once
        duplicates_query = (
            db.session.query(
                RepairLog.pn,
                RepairLog.sn,
                RepairLog.date_in,
                func.count(RepairLog.id).label('cnt'),
                func.min(RepairLog.id).label('keep_id')  # keep the lowest ID
            )
            .group_by(RepairLog.pn, RepairLog.sn, RepairLog.date_in)
            .having(func.count(RepairLog.id) > 1)
            .all()
        )

        deleted_count = 0
        for dup in duplicates_query:
            # Delete all records in this group EXCEPT the one with lowest ID
            count = (
                RepairLog.query
                .filter(
                    RepairLog.pn == dup.pn,
                    RepairLog.sn == dup.sn,
                    RepairLog.date_in == dup.date_in,
                    RepairLog.id != dup.keep_id
                )
                .delete()
            )
            deleted_count += count

        db.session.commit()
        logger.info(f"Cleanup: deleted {deleted_count} duplicate records")
        return jsonify({"status": "success", "deleted": deleted_count}), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Cleanup Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/delete_all', methods=['POST'])
def delete_all():
    """
    Delete ALL records from repair_log table.
    Admin only. Used before fresh reimport.
    """
    if not session.get('admin'):
        return jsonify({"error": "Unauthorized"}), 403

    try:
        count = RepairLog.query.delete()
        db.session.commit()
        logger.info(f"Delete All: removed {count} records")
        return jsonify({"status": "success", "deleted": count}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Delete All Error: {e}")
        return jsonify({"error": str(e)}), 500

# ==============================================================================
# LALUAN PUBLIC IMPORT (tanpa login) — digunakan oleh index.html
# ==============================================================================

@app.route('/import_bulk_public', methods=['POST'])
def import_bulk_public():
    """
    Public bulk import endpoint — no admin login required.
    Used by the main index.html page.
    ✅ Same duplicate detection as /import_bulk.
    """
    data_list = request.json.get('data', [])
    if not data_list:
        return jsonify({"error": "No data received"}), 400

    try:
        # ─── Load existing (pn, sn, date_in) for duplicate check ───
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
                status_type=str(item.get('STATUS', 'UNDER REPAIR')).upper(),
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
    # Dapatkan PORT dari environment variable (penting untuk Cloud deployment)
    # Jika tiada, guna port 5000 sebagai default
    port = int(os.environ.get("PORT", 5000))
    
    # Jalankan aplikasi
    # debug=True membolehkan auto-reload bila kod diubah (Untuk Development)
    # Untuk Production, debug patut False
    app.run(host='0.0.0.0', port=port, debug=True)

# ==============================================================================
# TAMAT KOD APP.PY - FULLY CORRECTED VERSION
# ==============================================================================
