[app]
# שם האפליקציה שיופיע בטלפון
title = ExtraTag

# שם הטאג/פילטר הפנימי של החבילה
package.name = extratag

# ה-Domain ההפוך המזהה את האפליקציה
package.domain = com.extratag

# תיקיית קובצי המקור (שורש הפרויקט)
source.dir = .

# סיומות הקבצים שייכללו באפליקציה
source.include_exts = py,png,jpg,kv,atlas,html,js,css,json

# גרסת האפליקציה
version = 1.0.6

# תלויות Python הנדרשות להרצה
requirements = python3,kivy,requests,certifi,urllib3

# כיוון המסך (portrait, landscape או all)
orientation = portrait

# הגדרת הרשאות (כגון גישה לאינטרנט)
android.permissions = INTERNET

# ארכיטקטורת המעבד (הגדרה יחידה למניעת שגיאות בצינור הבנייה)
android.archs = arm64-v8a

[buildozer]
# רמת הדיווחיות של התהליך (2 = מפורט)
log_level = 2
