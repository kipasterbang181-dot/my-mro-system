import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
import socket

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "avionic_mro_secret_2024")

# AMARAN: Gantikan link di bawah dengan Connection String dari Supabase anda
# Format: postgresql://postgres:[PASSWORD]@db.[ID-PROJEK].supabase.co:5432/postgres
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:PASSWORD_ANDA@db.XXXXXXXX.supabase.co:5432/postgres'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Struktur Database
class RepairLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tarikh = db.Column(db.String(50))
    peralatan = db.Column(db.String(100))
    sn = db.Column(db.String(100))
    status = db.Column(db.String(50))
    tindakan = db.Column(db.String(500))
    jurutera = db.Column(db.String(100))

# Fungsi untuk dapatkan IP (Hanya untuk kegunaan local/testing)
def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
    except: ip = '127.0.0.1'
    finally: s.close()
    return ip

@app.route('/')
def index():
    return render_template('index.html', ip=get_ip())

@app.route('/save', methods=['POST'])
def save():
    data = request.json
    new_entry = RepairLog(**data)
    db.session.add(new_entry)
    db.session.commit()
    return jsonify({"status": "success", "id": new_entry.id})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('u')
        p = request.form.get('p')
        if u == 'admin' and p == 'password123':
            session['admin'] = True
            return redirect(url_for('admin'))
    return render_template('login.html')

@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect(url_for('login'))
    logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
    return render_template('admin.html', logs=logs)

@app.route('/view/<int:log_id>')
def view_report(log_id):
    log = RepairLog.query.get_or_404(log_id)
    return render_template('view_pdf.html', l=log)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    # Kod ini membolehkan Render menetapkan port secara dinamik
    port = int(os.environ.get("PORT", 5000))
    # db.create_all() akan dijalankan secara automatik jika table belum wujud
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=port)