from flask import (
    Flask, request, jsonify, render_template,
    redirect, url_for, session
)
from risk_engine import assess_risk
from qr_service import generate_qr
from hospital_service import get_nearby_hospitals
from db import get_db_connection
import uuid

app = Flask(__name__)
app.secret_key = "sahayak_ai_secret"


REFERRAL_STORE = {}


def login_required():
    return session.get("admin_logged_in")


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM admins WHERE username=%s AND password=%s",
            (username, password)
        )
        admin = cursor.fetchone()

        cursor.close()
        conn.close()

        if admin:
            session["admin_logged_in"] = True
            session["admin_role"] = admin["role"]
            return redirect(url_for("dashboard"))

        return render_template(
            "login.html",
            error="Invalid username or password"
        )

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect(url_for("login"))
    return render_template("dashboard.html")


@app.route("/triage", methods=["POST"])
def triage():
    data = request.json

    if not data.get("consent"):
        return jsonify({
            "error": "Patient consent is required for automated risk assessment."
        }), 403

    age = int(data.get("age"))
    if age < 0 or age > 120:
        return jsonify({
            "error": "Age must be between 0 and 120"
        }),400
    bp_raw = data.get("bp")
    bp = int(bp_raw) if bp_raw and bp_raw.strip() != "" else None

    symptoms = data.get("symptoms", [])
    photo = data.get("photo")
    patient_name = data.get("patient_name", "Unknown")

    risk, score, ai_prob, reasons = assess_risk(age, bp, symptoms)

    referral_id = f"REF-{uuid.uuid4().hex[:6].upper()}"

 
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO triage_records
        (referral_id, patient_name, age, bp, symptoms,
         risk_level, ai_risk_level)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        referral_id,
        patient_name,
        age,
        bp,
        ",".join(symptoms),
        risk,
        risk
    ))

    conn.commit()
    cursor.close()
    conn.close()


    REFERRAL_STORE[referral_id] = {
        "patient_name": patient_name,
        "risk": risk,
        "photo": photo,
        "symptoms": symptoms,
        "used": False
    }


    qr_path = None
    hospitals = []

    if risk == "Critical":
        qr_path = generate_qr(referral_id)

        patient_lat = 11.9416
        patient_lon = 79.8083
        hospitals = get_nearby_hospitals(patient_lat, patient_lon)

    return jsonify({
        "message": f"{risk} risk – referral generated",
        "risk": risk,
        "risk_score": score,
        "ai_probability": ai_prob,
        "reasons": reasons,
        "qr_code": qr_path,
        "referral_id": referral_id,
        "nearby_hospitals": hospitals
    })


@app.route("/select-hospital", methods=["POST"])
def select_hospital():
    data = request.json
    referral_id = data.get("referral_id")
    hospital_name = data.get("hospital_name")

    if not referral_id or not hospital_name:
        return jsonify({"error": "Invalid data"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT available_beds
            FROM hospitals
            WHERE name = %s
            FOR UPDATE
        """, (hospital_name,))
        hospital = cursor.fetchone()

        if not hospital or hospital["available_beds"] <= 0:
            return jsonify({
                "status": "warning",
                "message": "No beds available in this hospital"
            }), 409

        cursor.execute("""
            UPDATE triage_records
            SET hospital_assigned = %s
            WHERE referral_id = %s
        """, (hospital_name, referral_id))

        cursor.execute("""
            UPDATE hospitals
            SET available_beds = available_beds - 1
            WHERE name = %s
        """, (hospital_name,))

        conn.commit()

        return jsonify({
            "status": "success",
            "message": f"Hospital assigned: {hospital_name}"
        })

    except Exception:
        conn.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

    finally:
        cursor.close()
        conn.close()


@app.route("/referral/<referral_id>")
def referral_page(referral_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM triage_records WHERE referral_id = %s",
        (referral_id,)
    )
    record = cursor.fetchone()

    if not record:
        cursor.close()
        conn.close()
        return "❌ Invalid QR Code", 404

    if record["qr_used"] == 1:
        cursor.close()
        conn.close()
        return "⚡ SECURITY ALERT: This QR code has already been used.", 410

    cursor.execute(
        "UPDATE triage_records SET qr_used = 1 WHERE referral_id = %s",
        (referral_id,)
    )
    conn.commit()

    cursor.close()
    conn.close()

    referral_data = REFERRAL_STORE.get(referral_id)
    photo = referral_data["photo"] if referral_data else None

    return render_template(
        "referral.html",
        referral_id=record["referral_id"],
        patient_name=record["patient_name"],
        risk=record["risk_level"],
        photo=photo,
        symptoms=record["symptoms"].split(","),
        hospital=record["hospital_assigned"] or "Not assigned"
    )

@app.route("/finalize-risk", methods=["POST"])
def finalize_risk():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json

    referral_id = data.get("referral_id")
    final_risk = data.get("final_risk")
    corrected_symptoms = data.get("corrected_symptoms", [])
    override_reason = data.get("override_reason", "").strip()

    if not referral_id or not final_risk:
        return jsonify({"error": "Invalid data"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE triage_records
    SET
        final_risk_level = %s,
        corrected_symptoms = %s,
        decision_time = NOW(),
        hospital_assigned = IFNULL(hospital_assigned, 'To be assigned')
    WHERE referral_id = %s
""", (
    final_risk,
    ",".join(corrected_symptoms),
    referral_id
))

    conn.commit()  
    cursor.close()
    conn.close()

    return jsonify({"status": "success"})



@app.route("/recalculate-risk", methods=["POST"])
def recalculate_risk():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json

    referral_id = data.get("referral_id")
    symptoms = data.get("symptoms", [])

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT age, bp FROM triage_records WHERE referral_id=%s",
        (referral_id,)
    )
    record = cursor.fetchone()

    cursor.close()
    conn.close()

    if not record:
        return jsonify({"error": "Case not found"}), 404

    risk, score, prob, reasons = assess_risk(
        record["age"],
        record["bp"],
        symptoms
    )

    return jsonify({
        "risk": risk,
        "reasons": reasons
    })


@app.route("/risk-history")
def risk_history():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT risk_level, COUNT(*) AS total_cases
        FROM triage_records
        GROUP BY risk_level
    """)

    data = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("risk_history.html", data=data)



@app.route("/triage-history")
def triage_history():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
    SELECT
        referral_id,
        patient_name,
        age,
        bp,
        risk_level,
        final_risk_level,
        hospital_assigned,
        created_at,
CASE
    WHEN final_risk_level IS NULL THEN 'Pending'
    WHEN hospital_assigned IS NULL THEN 'Awaiting Hospital'
    ELSE 'Completed'
END AS status
    FROM triage_records
    ORDER BY created_at DESC
""")

    records = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("triage_history.html", records=records)


@app.route("/validate/<referral_id>")
def validate_case(referral_id):
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM triage_records WHERE referral_id=%s",
        (referral_id,)
    )
    record = cursor.fetchone()

    cursor.close()
    conn.close()

    if not record:
        return "Case not found", 404

    return render_template(
        "validate_case.html",
        record=record,
        symptoms=record["symptoms"].split(",")
    )


@app.route("/hospital-load")
def hospital_load():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT name, available_beds
        FROM hospitals
        ORDER BY available_beds DESC
    """)

    hospitals = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("hospital_load.html", hospitals=hospitals)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)