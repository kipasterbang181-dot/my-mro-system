import os
from flask import Flask, render_template, request, redirect, url_for
from supabase import create_client, Client
import qrcode
import io
import base64

app = Flask(__name__)

# 1. AMBIL MAKLUMAT DARI RENDER ENVIRONMENT
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Semakan keselamatan supaya tidak crash jika URL tertinggal
if not SUPABASE_URL or not SUPABASE_KEY:
    print("RALAT: Sila masukkan SUPABASE_URL dan SUPABASE_KEY di Render Environment!")
else:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/incoming', methods=['POST'])
def incoming():
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

@app.route('/login', methods=['POST'])
def login():
    user = request.form.get('u')
    pwd = request.form.get('p')
    if user == "admin" and pwd == "g7aero":
        return redirect(url_for('admin'))
    return "Login Gagal!"

@app.route('/admin')
def admin():
    res = supabase.table("tag_mro").select("*").order("id", desc=True).execute()
    return render_template('admin.html', l=res.data)

@app.route('/view_tag/<int:id>')
def view_tag(id):
    res = supabase.table("tag_mro").select("*").eq("id", id).single().execute()
    record = res.data
    
    # Bina QR (Pastikan link ini ikut domain Render tuan)
    qr_link = f"https://my-mro-system.onrender.com/view_tag/{id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(qr_link)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf)
    qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    
    return render_template('view_tag.html', l=record, qr_code=qr_b64)

# FIX ERROR 405: Tukar ke fungsi link biasa
@app.route('/delete/<int:id>')
def delete(id):
    supabase.table("tag_mro").delete().eq("id", id).execute()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True)