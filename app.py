# ===========================================
# Flask Image Processor + SQLAlchemy (SQLite)
# FINAL VERSION – endpoint process sudah fix
# ===========================================

import os
import uuid
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for, flash, session
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import cv2

app = Flask(__name__)
app.secret_key = "dev-secret-key"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///history.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_DIR = os.path.join(STATIC_DIR, "uploads")
PROCESSED_DIR = os.path.join(STATIC_DIR, "processed")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

ALLOWED_EXTS = {"png", "jpg", "jpeg", "bmp", "tif", "tiff"}

DELETE_FILES_ON_REMOVE = False


class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(50), nullable=False, index=True)
    ori = db.Column(db.String(255), nullable=False)
    hasil = db.Column(db.String(255), nullable=False)
    metode = db.Column(db.String(20), nullable=False)
    waktu = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


with app.app_context():
    db.create_all()


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTS


def unique_name(stem: str, ext: str) -> str:
    return f"{stem}_{uuid.uuid4().hex[:8]}.{ext.lower()}"


def process_image(input_path: str, method: str):
    img = cv2.imread(input_path)
    if img is None:
        raise ValueError("Gagal membaca gambar")

    if method == "grayscale":
        out = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    elif method == "invert":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        out = cv2.bitwise_not(gray)
    elif method == "otsu":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, out = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    elif method == "edge":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        out = cv2.Canny(gray, 100, 200)
    else:
        out = img

    return out


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload")
def upload():
    nama_q = request.args.get("nama", "").strip()
    if nama_q:
        session["nama"] = nama_q

    nama = session.get("nama", "")
    if not nama:
        flash("Masukkan nama terlebih dahulu.")
        return redirect(url_for("index"))

    methods = [
        ("grayscale", "Grayscale"),
        ("invert", "Invert"),
        ("otsu", "OTSU Threshold"),
        ("edge", "Canny Edge"),
    ]
    return render_template("upload.html", nama=nama, methods=methods)


@app.route("/process", methods=["POST"])
def process():
    nama = request.form.get("nama", "").strip() or session.get("nama", "")
    method = request.form.get("method", "").strip()
    file = request.files.get("file")

    if not nama:
        flash("Nama tidak boleh kosong.")
        return redirect(url_for("index"))

    if not file or file.filename == "":
        flash("Pilih file gambar terlebih dahulu.")
        return redirect(url_for("upload"))

    if not allowed_file(file.filename):
        flash("Format file tidak didukung.")
        return redirect(url_for("upload"))

    filename_safe = secure_filename(file.filename)
    ext = filename_safe.rsplit(".", 1)[1].lower()
    stored_name = unique_name("img", ext)
    path_in = os.path.join(UPLOAD_DIR, stored_name)
    file.save(path_in)

    try:
        processed = process_image(path_in, method)
    except Exception as e:
        flash(f"Gagal memproses gambar: {e}")
        return redirect(url_for("upload"))

    out_name = unique_name(f"{os.path.splitext(stored_name)[0]}_{method}", "png")
    path_out = os.path.join(PROCESSED_DIR, out_name)
    cv2.imwrite(path_out, processed)

    rec = History(
        nama=nama,
        ori=f"uploads/{stored_name}",
        hasil=f"processed/{out_name}",
        metode=method,
    )
    db.session.add(rec)
    db.session.commit()

    return render_template(
        "result.html",
        nama=nama,
        metode=method,
        ori=url_for("static", filename=rec.ori),
        hasil=url_for("static", filename=rec.hasil),
    )


@app.route("/history")
def history():
    nama_q = request.args.get("nama", "").strip()
    if nama_q:
        session["nama"] = nama_q

    nama = session.get("nama", "")
    if not nama:
        flash("Masukkan nama terlebih dahulu.")
        return redirect(url_for("index"))

    records = History.query.filter_by(nama=nama).order_by(History.waktu.desc()).all()

    return render_template("history.html", nama=nama, data=records)


@app.route("/delete_history")
def delete_history():
    nama = session.get("nama", "")

    if DELETE_FILES_ON_REMOVE:
        to_delete = History.query.filter_by(nama=nama).all()
        for r in to_delete:
            try: os.remove(os.path.join(STATIC_DIR, r.ori))
            except: pass
            try: os.remove(os.path.join(STATIC_DIR, r.hasil))
            except: pass

    History.query.filter_by(nama=nama).delete()
    db.session.commit()

    flash("Riwayat berhasil dihapus.")
    return redirect(url_for("history"))


@app.route("/delete_item")
def delete_item():
    item_id = request.args.get("id", "").strip()
    nama = request.args.get("nama", "").strip() or session.get("nama", "")

    item = History.query.get(item_id)
    if item and item.nama == nama:

        if DELETE_FILES_ON_REMOVE:
            try: os.remove(os.path.join(STATIC_DIR, item.ori))
            except: pass
            try: os.remove(os.path.join(STATIC_DIR, item.hasil))
            except: pass

        db.session.delete(item)
        db.session.commit()
        flash("1 item berhasil dihapus")

    return redirect(url_for("history"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
