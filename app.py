import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "mro_key_2026"

# --- DATABASE CONFIG (AWS-1 & PORT 6543) ---
DB_URL = "postgresql://postgres.yyvrjgdzhliodbgijlgb:KUCINGPUTIH10@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres"

app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True}

db = SQLAlchemy(app)

class RepairLog(db.Model):
    __tablename__ = 'repair_log'
    id = db.Column(db.Integer, primary_key=True)
    tarikh = db.Column(db.String(50))
    peralatan = db.Column(db.String(100))
    sn = db.Column(db.String(100))
    status = db.Column(db.String(50))
    tindakan = db.Column(db.Text)
    jurutera = db.Column(db.String(100))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/save', methods=['POST'])
def save():
    try:
        data = request.json
        new_entry = RepairLog(
            tarikh=data.get('tarikh'), peralatan=data.get('peralatan'),
            sn=data.get('sn'), status=data.get('status'),
            tindakan=data.get('tindakan'), jurutera=data.get('jurutera')
        )
        db.session.add(new_entry)
        db.session.commit()
        return jsonify({"status": "success", "id": new_entry.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('u') == 'admin' and request.form.get('p') == 'password123':
            session['admin'] = True
            return redirect(url_for('admin'))
    return render_template('login.html')

@app.route('/admin')
def admin():
    if not session.get('admin'): 
        return redirect(url_for('login'))
    logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
    return render_template('admin.html', logs=logs)

# --- FUNGSI LOGOUT (Selesaikan 404 Logout) ---
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- FUNGSI VIEW (Gunakan 'l' supaya sepadan dengan HTML anda) ---
@app.route('/view/<int:log_id>')
def view_report(log_id):
    log_data = RepairLog.query.get_or_404(log_id)
    return render_template('view_pdf.html', l=log_data)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)