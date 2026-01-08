import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
# Key untuk sesi login
app.secret_key = os.environ.get("SECRET_KEY", "avionic_mro_2026_key")

# --- DATABASE SUPABASE (DIRECT CONNECTION) ---
# Saya telah tukar ke port 5432 dan alamat db direct untuk elakkan ralat 'Tenant Not Found'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:KUCINGPUTIH10@db.yyvrjgdzhliodbgijlgb.supabase.co:5432/postgres'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Struktur Database MRO
class RepairLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tarikh = db.Column(db.String(50))
    peralatan = db.Column(db.String(100))
    sn = db.Column(db.String(100))
    status = db.Column(db.String(50))
    tindakan = db.Column(db.String(500))
    jurutera = db.Column(db.String(100))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/save', methods=['POST'])
def save():
    try:
        data = request.json
        new_entry = RepairLog(**data)
        db.session.add(new_entry)
        db.session.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        # Jika ralat, ia akan beritahu punca di skrin telefon anda
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('u')
        p = request.form.get('p')
        # Username: admin | Password: password123
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

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    with app.app_context():
        db.create_all() # Membuat table automatik di Supabase
    app.run(host='0.0.0.0', port=port)