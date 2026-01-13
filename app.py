import os
import pandas as pd
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.secret_key = "mro_system_2026"

# --- CONFIG DATABASE ---
DB_URL = "postgresql://postgres.yyvrjgdzhliodbgijlgb:KUCINGPUTIH10@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres"
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODEL DATABASE ---
class RepairLog(db.Model):
    __tablename__ = 'repair_log'
    id = db.Column(db.Integer, primary_key=True)
    date_in = db.Column(db.String(50))
    date_out = db.Column(db.String(50))
    peralatan = db.Column(db.String(100))
    sn = db.Column(db.String(100))
    status = db.Column(db.String(50))
    tindakan = db.Column(db.Text)
    jurutera = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.now)

# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/save', methods=['POST'])
def save():
    try:
        data = request.json
        new_entry = RepairLog(
            date_in=data.get('date_in'),
            date_out=data.get('date_out'),
            peralatan=data.get('peralatan'),
            sn=data.get('sn'),
            status=data.get('status'),
            tindakan=data.get('tindakan'),
            jurutera=data.get('jurutera')
        )
        db.session.add(new_entry)
        db.session.commit()
        return jsonify({"status": "success", "id": new_entry.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/export_excel')
def export_excel():
    # Tiada login check supaya pekerja boleh download
    logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
    data = []
    for l in logs:
        data.append({
            "Date In": l.date_in,
            "Date Out": l.date_out,
            "Peralatan": l.peralatan,
            "S/N": l.sn,
            "Status": l.status,
            "Tindakan": l.tindakan,
            "Jurutera": l.jurutera
        })
    df = pd.DataFrame(data)
    file_path = "Master_Repair_Log.xlsx"
    df.to_excel(file_path, index=False)
    return send_file(file_path, as_attachment=True)

@app.route('/import_excel', methods=['POST'])
def import_excel():
    if not session.get('admin'): return redirect(url_for('login'))
    file = request.files.get('file')
    if not file: return "Tiada fail", 400
    try:
        df = pd.read_excel(file)
        for _, row in df.iterrows():
            new_log = RepairLog(
                date_in=str(row.get('date_in', '')),
                date_out=str(row.get('date_out', '')),
                peralatan=row.get('peralatan'),
                sn=row.get('sn'),
                status=row.get('status'),
                tindakan=row.get('tindakan'),
                jurutera=row.get('jurutera')
            )
            db.session.add(new_log)
        db.session.commit()
        return redirect(url_for('admin'))
    except Exception as e:
        return f"Ralat: {str(e)}"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('u') == 'admin' and request.form.get('p') == 'password123':
            session['admin'] = True
            return redirect(url_for('admin'))
    return render_template('login.html')

@app.route('/admin')
def admin():
    if not session.get('admin'): return redirect(url_for('login'))
    logs = RepairLog.query.order_by(RepairLog.id.desc()).all()
    return render_template('admin.html', logs=logs)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/view/<int:log_id>')
def view_report(log_id):
    log = RepairLog.query.get_or_404(log_id)
    return render_template('view_pdf.html', l=log)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))