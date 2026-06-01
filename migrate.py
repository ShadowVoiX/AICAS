import json
import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

student_uid = "WjguGhmq7HNwHBz0IW5XfJfbQoN2"

with open("exam_timetable.json", "r") as f:
    exam_data = json.load(f)

# Get student's current timetable course codes
timetable_docs = db.collection("students") \
    .document(student_uid) \
    .collection("timetable") \
    .stream()

current_courses = [doc.id for doc in timetable_docs]

for course_code in current_courses:
    matched_exam = None

    for exam in exam_data:
        if exam["code"].upper() == course_code.upper():
            matched_exam = exam
            break

    if matched_exam:
        db.collection("students") \
            .document(student_uid) \
            .collection("exam_timetable") \
            .document(course_code) \
            .set({
                "code": matched_exam["code"],
                "date": matched_exam["date"],
                "day": matched_exam["day"],
                "time": matched_exam["time"],
                "status": "Final Exam"
            })

        print(f"Uploaded exam for {course_code}")

    else:
        db.collection("students") \
            .document(student_uid) \
            .collection("exam_timetable") \
            .document(course_code) \
            .set({
                "code": course_code,
                "date": None,
                "day": None,
                "time": None,
                "status": "No final"
            })

        print(f"No final for {course_code}")

print("Exam timetable upload completed.")