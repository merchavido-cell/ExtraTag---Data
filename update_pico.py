import json

# טעינת הקובץ המלא מהריפו
with open("global_history.json", "r", encoding="utf-8") as f:
    global_data = json.load(f)

# חיפוש הפרופיל שלך (לדוגמה לפי האימייל שלך או לפי מזהה)
target_profile = None

# אם הנתונים הם רשימה של פרופילים:
if isinstance(global_data, list):
    for p in global_data:
        # שנה כאן את האימייל למייל האמיתי שלך במסד הנתונים
        if p.get("email") == "merchavido@gmail.com":
            target_profile = {
                "id": p.get("id"),
                "email": p.get("email"),
                "exmail": p.get("exmail"),
                "password": p.get("password"),
                "firstName": p.get("firstName"),
                "lastName": p.get("lastName"),
                "events": p.get("events", [])
                # שדה ה-files מושמט לחלוטין!
            }
            break

# אם לא נמצא ספציפי, ניקח ברירת מחדל את הפרופיל הראשון לצורך בדיקה
if not target_profile and isinstance(global_data, list) and len(global_data) > 0:
    p = global_data[0]
    target_profile = {
        "id": p.get("id"),
        "email": p.get("email"),
        "exmail": p.get("exmail"),
        "password": p.get("password"),
        "firstName": p.get("firstName"),
        "lastName": p.get("lastName"),
        "events": p.get("events", [])
    }

# שמירת הקובץ המצומצם local_history.json
if target_profile:
    with open("local_history.json", "w", encoding="utf-8") as f:
        json.dump(target_profile, f, ensure_ascii=False, indent=2)
    print("Successfully generated local_history.json without files!")
else:
    print("Error: Target profile not found.")
