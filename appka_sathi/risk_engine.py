def assess_risk(age, bp, symptoms):
    """
    Rule-based AI Risk Engine
    Designed for explainability & auditability
    """

    score = 0
    reasons = []


    if age >= 60:
        score += 2
        reasons.append("Patient age above 60")

    elif age >= 45:
        score += 1
        reasons.append("Patient age between 45 and 59")


    if bp is not None:
        if bp >= 180:
            score += 3
            reasons.append("Severely high blood pressure (≥180)")

        elif bp >= 160:
            score += 2
            reasons.append("High blood pressure (160–179)")

        elif bp >= 140:
            score += 1
            reasons.append("Elevated blood pressure (140–159)")

    critical_symptoms = {

        "chest_pain": 3,
        "breathlessness": 3,
        "palpitations": 2,
        "cold_sweat": 2,
        "cyanosis": 4,


        "unconscious": 4,
        "seizure": 4,
        "slurred_speech": 3,
        "vision_loss": 3,


        "bleeding": 3,
        "head_injury": 3,
        "burns": 3
    }


    moderate_symptoms = {
    
        "high_fever": 2,
        "persistent_fever": 2,
        "vomiting": 1,
        "diarrhea": 1,
        "dehydration": 1,

        "dizziness": 1,
        "headache": 1,


        "fracture": 1,
        "abdominal_pain": 1
    }

    for symptom in symptoms:
        if symptom in critical_symptoms:
            score += critical_symptoms[symptom]
            reasons.append(
                f"Critical symptom detected: {symptom.replace('_', ' ')}"
            )

        elif symptom in moderate_symptoms:
            score += moderate_symptoms[symptom]
            reasons.append(
                f"Moderate symptom detected: {symptom.replace('_', ' ')}"
            )

    if score <= 2:
        risk = "Low"
    elif score <= 5:
        risk = "Moderate"
    elif score <= 8:
        risk = "High"
    else:
        risk = "Critical"

   
    confidence = round(min(score / 12, 1.0), 2)

    return risk, score, confidence, reasons
