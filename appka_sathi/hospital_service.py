import math
from db import get_db_connection

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat/2)**2 +
        math.cos(math.radians(lat1)) *
        math.cos(math.radians(lat2)) *
        math.sin(dlon/2)**2
    )

    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))


def get_nearby_hospitals(patient_lat, patient_lon, limit=3):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM hospitals
        WHERE available_beds > 0
    """)
    hospitals = cursor.fetchall()

    cursor.close()
    conn.close()

    for h in hospitals:
        h["distance_km"] = round(
            haversine(patient_lat, patient_lon, h["latitude"], h["longitude"]), 2
        )

    hospitals.sort(key=lambda x: x["distance_km"])

    return hospitals[:limit]
