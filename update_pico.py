import json

# טעינת הקובץ המלא מהריפו
with open("global_history.json", "r", encoding="utf-8") as f:
    global_data = json.load(f)

light_profiles = []

# מעבר על כל הפרופילים וניקוי שדות ה-files הכבדים בלבד
if isinstance(global_data, list):
    for p in global_data:
        light_profile = {
            "id": p.get("id"),
            "email": p.get("email"),
            "exmail": p.get("exmail"),
            "password": p.get("password"),
            "firstName": p.get("firstName"),
            "lastName": p.get("lastName"),
            "events": p.get("events", [])
            # שדה ה-files מוסר לחלוטין מכל פרופיל כדי לחסוך ענק בזיכרון!
        }
        light_profiles.append(light_profile)

# שמירת הקובץ המצומצם שיועבר למכשיר
with open("local_history.json", "w", encoding="utf-8") as f:
    json.dump(light_profiles, f, ensure_ascii=False, indent=2)

print("Successfully stripped files and updated local_history.json!")
