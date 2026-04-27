import qrcode
import os
from flask import request, current_app

def generate_qr(referral_id):
    qr_dir = os.path.join(current_app.root_path, "static", "qr")
    os.makedirs(qr_dir, exist_ok=True)

    file_path = os.path.join(qr_dir, f"{referral_id}.png")

    host = request.host
    url = f"http://{host}/referral/{referral_id}"

    qr = qrcode.make(url)
    qr.save(file_path)

    return f"/static/qr/{referral_id}.png"

