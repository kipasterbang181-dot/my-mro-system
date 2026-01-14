import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import qrcode
import io
import base64

app = Flask(__name__)

# AMBIL LINK DARI RENDER ENVIRONMENT
uri = os.environ.get("DATABASE_URL")
# Fix untuk Render/Heroku (tukar postgres:// kepada postgresql:// jika perlu)
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Model Data
class TagMRO(db.Model):
    __tablename__ = 'tag_mro'
    id = db.Column(db.Integer, primary_key=True)
    peralatan = db.Column(db.String(100))
    pn = db.Column(db.String(100))
    sn = db.Column(db.String(100))
    pic = db.Column(db.String(100))
    defect = db.Column(db.Text)
    status_type = db.Column(db.String(50))
    date_in = db.Column(db.String(50))

# AUTO CREATE TABLE (Penting!)
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/incoming', methods=['POST'])
def incoming():
    try:
        new_tag = TagMRO(
            peralatan=request.form.get("peralatan"),
            pn=request.form.get("pn"),
            sn=request.form.get("sn"),
            pic=request.form.get("pic"),
            defect=request.form.get("defect"),
            status_type=request.form.get("status_type"),
            date_in=request.form.get("date_in")
        )
        db.session.add(new_tag)
        db.session.commit()
        return redirect(url_for('index'))
    except Exception as e:
        return f"Ralat Simpan: {str(e)}"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('u')
        pwd = request.form.get('p')
        if user == "admin" and pwd == "g7aero":
            return redirect(url_for('admin'))
        return "ID atau Password Salah!"
    return render_template('login.html')

@app.route('/admin')
def admin():
    try:
        data_list = TagMRO.query.order_by(TagMRO.id.desc()).all()
        return render_template('admin.html', l=data_list)
    except Exception as e:
        return f"Database Error: {str(e)}"

@app.route('/view_tag/<int:id>')
def view_tag(id):
    record = TagMRO.query.get_or_404(id)
    # Gunakan domain tuan
    qr_link = f"https://my-mro-system.onrender.com/view_tag/{id}"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(qr_link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf)
    qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    
    return render_template('view_tag.html', l=record, qr_code=qr_b64)

@app.route('/delete/<int:id>')
def delete(id):
    record = TagMRO.query.get_or_404(id)
    db.session.delete(record)
    db.session.commit()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True)