import os
from flask import Flask, render_template, request, redirect, url_for
from supabase import create_client, Client
import qrcode
import io
import base64

app = Flask(__name__)

# 1. KONFIGURASI SUPABASE
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Inisialisasi awal sebagai None untuk elak ralat 'not defined'
supabase = None

if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Gagal sambung ke Supabase: {e}")
else:
    print("AMARAN: Maklumat SUPABASE_URL/KEY tidak dijumpai di Render Environment!")

# 2. HALAMAN UTAMA
@app.route('/')
def index():
    return render_template('index.html')

# 3. SIMPAN DATA (DENGAN CHECK SUPABASE)
@app.route('/incoming', methods=['POST'])
def incoming():
    # Semak jika supabase sudah didefinisikan
    if supabase is None:
        return "Ralat: Sambungan Database tidak dijumpai. Sila masukkan SUPABASE_URL di Render!"
        
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

# 4. ADMIN LOGIN
@app.route('/login', methods=['POST'])
def login():
    user = request.form.get('u')
    pwd = request.form.get('p')
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

# 6. VIEW TAG & QR
@app.route('/view_tag/<int:id>')
def view_tag(id):
    if supabase is None:
        return "Database tidak bersambung."
    try:
        res = supabase.table("tag_mro").select("*").eq("id", id).single().execute()
        record = res.data
        
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

# 7. DELETE RECORD
@app.route('/delete/<int:id>')
def delete(id):
    if supabase is None:
        return "Database tidak bersambung."
    try:
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