import os
from flask import Flask, render_template, request, redirect, url_for
from supabase import create_client, Client
import qrcode
import io
import base64

app = Flask(__name__)

# 1. KONFIGURASI SUPABASE (Ambil dari Render Environment)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Kita sediakan variable ini supaya tidak keluar ralat 'not defined'
supabase = None

if SUPABASE_URL and SUPABASE_KEY:
    try:
        # Gunakan kunci yang tuan beri tadi
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Gagal sambung database: {e}")

# 2. HALAMAN UTAMA (BORANG)
@app.route('/')
def index():
    return render_template('index.html')

# 3. SIMPAN DATA KE SUPABASE
@app.route('/incoming', methods=['POST'])
def incoming():
    if supabase is None:
        return "Database link tak jumpa! Sila masukkan URL & KEY di Render Environment."
    try:
        data = {
            "peralatan": request.form.get("peralatan"),
            "pn": request.form.get("pn"),
            "sn": request.form.get("sn"),
            "pic": request.form.get("pic"),
            "defect": request.form.get("defect"),
            "status_type": request.form.get("status_type"),
            "date_in": request.form.get("date_in")
        }
        supabase.table("tag_mro").insert(data).execute()
        return redirect(url_for('index'))
    except Exception as e:
        return f"Ralat Simpan Data: {str(e)}"

# 4. ADMIN LOGIN (FIX ERROR 405)
@app.route('/login', methods=['POST'])
def login():
    user = request.form.get('u')
    pwd = request.form.get('p')
    # Password tuan: g7aero
    if user == "admin" and pwd == "g7aero":
        return redirect(url_for('admin'))
    return "ID atau Password Salah!"

# 5. DASHBOARD ADMIN
@app.route('/admin')
def admin():
    if supabase is None:
        return "Database tidak bersambung."
    try:
        res = supabase.table("tag_mro").select("*").order("id", desc=True).execute()
        return render_template('admin.html', l=res.data)
    except Exception as e:
        return f"Database Error: {str(e)}"

# 6. VIEW TAG & QR GENERATOR
@app.route('/view_tag/<int:id>')
def view_tag(id):
    if supabase is None:
        return "Database tidak bersambung."
    try:
        res = supabase.table("tag_mro").select("*").eq("id", id).single().execute()
        record = res.data
        
        # Link QR (Gunakan domain Render tuan)
        qr_link = f"https://my-mro-system.onrender.com/view_tag/{id}"
        
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(qr_link)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf)
        qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        
        return render_template('view_tag.html', l=record, qr_code=qr_b64)
    except Exception as e:
        return f"Ralat View Tag: {str(e)}"

# 7. DELETE RECORD (FIX ERROR 405)
@app.route('/delete/<int:id>')
def delete(id):
    if supabase is None:
        return "Database tidak bersambung."
    try:
        # Padam mengikut ID
        supabase.table("tag_mro").delete().eq("id", id).execute()
        return redirect(url_for('admin'))
    except Exception as e:
        return f"Gagal Padam Data: {str(e)}"

# 8. UPDATE RECORD
@app.route('/update/<int:id>', methods=['POST'])
def update(id):
    if supabase is None:
        return "Database tidak bersambung."
    try:
        data = {
            "peralatan": request.form.get("peralatan"),
            "pn": request.form.get("pn"),
            "sn": request.form.get("sn"),
            "pic": request.form.get("pic")
        }
        supabase.table("tag_mro").update(data).eq("id", id).execute()
        return redirect(url_for('admin'))
    except Exception as e:
        return f"Gagal Kemaskini: {str(e)}"

if __name__ == '__main__':
    app.run(debug=True)