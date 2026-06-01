from pydoc import doc
from flask import Flask, render_template, request, jsonify
import os, secrets, json
import firebase_admin
from firebase_admin import credentials, firestore, auth
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from datetime import datetime
from PyPDF2 import PdfReader

from groq import Groq

# =========================
# LOAD ENV
# =========================
load_dotenv()

# =========================
# GROQ SETUP
# =========================
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
GROQ_MODEL = "llama-3.1-8b-instant"

# =========================
# FIREBASE INIT
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "submissions")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

firebase_credentials = os.getenv("FIREBASE_CREDENTIALS")

if firebase_credentials:

    cred = credentials.Certificate(
        json.loads(firebase_credentials)
    )

else:

    cred = credentials.Certificate(
        os.path.join(BASE_DIR, "firebase_key.json")
    )

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()

# =========================
# FLASK APP
# =========================
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

FIXED_DOMAIN = "schoolapp.com"

def matric_to_email(matric):
    return f"{matric}@{FIXED_DOMAIN}"


def extract_text_from_file(file_path):
    file_path_lower = file_path.lower()

    # TXT FILE
    if file_path_lower.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    # PDF FILE
    if file_path_lower.endswith(".pdf"):
        text = ""
        reader = PdfReader(file_path)

        for page in reader.pages:
            extracted_text = page.extract_text()

            if extracted_text:
                text += extracted_text + "\n"

        return text

    return ""

# =========================
# ROUTES
# =========================
@app.route('/')
def home():
    return render_template("login.html")

@app.route('/login')
def login_page():
    return render_template("login.html")

@app.route('/register')
def register_page():
    return render_template("register.html")

@app.route('/inter')
def inter_page():
    return render_template("inter.html")

# =========================
# REGISTER
# =========================
@app.route('/register-student', methods=['POST'])
def register_student():
    data = request.json

    matric = data.get("matric")
    password = data.get("password")
    name = data.get("name", "Student")
    university = "International Islamic University Malaysia"

    if not matric or not password:
        return jsonify({"status": "fail", "message": "Missing fields"})

    email = matric_to_email(matric)

    try:
        try:
            auth.get_user_by_email(email)
            return jsonify({"status": "exist", "message": "Account already exists"})
        except Exception:
            pass

        user = auth.create_user(email=email, password=password)

        db.collection("students").document(user.uid).set({
            "uid": user.uid,
            "matric": matric,
            "email": email,
            "name": name,
            "university": university,
            "aicasStatus": False
        })

        return jsonify({
            "status": "success",
            "uid": user.uid
        })

    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

# =========================
# LOGIN
# =========================
@app.route('/login-student', methods=['POST'])
def login_student():
    data = request.json

    matric = data.get("matric")
    password = data.get("password")
    university = data.get("university")

    if not matric or not password:
        return jsonify({"status": "fail", "message": "Missing fields"})

    email = matric_to_email(matric)

    try:
        import requests

        API_KEY = os.getenv("FIRE_BASE_KEY")

        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"

        res = requests.post(url, json={
            "email": email,
            "password": password,
            "returnSecureToken": True
        })

        result = res.json()

        if "idToken" not in result:
            return jsonify({"status": "fail","message": str(result)})

        user_record = auth.get_user_by_email(email)

        doc = db.collection("students").document(user_record.uid).get()

        if not doc.exists:
            return jsonify({"status": "fail", "message": "Student data not found"})

        student_data = doc.to_dict()
        name = student_data.get("name", "Student")
        aicas_status = student_data.get("aicasStatus", False)

        # Only AICAS login sends university
        if university:
            if student_data.get("university") != university:
                return jsonify({
                    "status": "fail",
                    "message": "University does not match this account"
                })
            if student_data.get("aicasStatus") == True:
                return jsonify({
                    "status": "exists",
                    "message": "AICAS account already linked to this student"
                })

            db.collection("students").document(user_record.uid).update({
                "aicasStatus": True
            })

            aicas_status = True

        redirect_url = "/login" if university else "/inter"

        return jsonify({
            "status": "success",
            "redirect": redirect_url,
            "uid": user_record.uid,
            "name": name,
            "university": student_data.get("university"),
            "aicasStatus": aicas_status
        })

    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

@app.route('/check-aicas-status', methods=['POST'])
def check_aicas_status():

    data = request.json
    uid = data.get("uid")

    if not uid:
        return jsonify({
            "status": "fail"
        })

    try:

        doc = db.collection("students").document(uid).get()

        if not doc.exists:
            return jsonify({
                "status": "fail"
            })

        student_data = doc.to_dict()

        return jsonify({
            "status": "success",
            "aicasStatus": student_data.get("aicasStatus", False)
        })

    except Exception as e:
        return jsonify({
            "status": "fail",
            "message": str(e)
        })

@app.route('/aicas-login')
def aicas_login_page():
    return render_template("aicas_login.html")
# =========================
# CHATBOT
# =========================
@app.route('/chatbot', methods=['POST'])
def chatbot():
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        message = request.form.get("message", "").lower()
        uid = request.form.get("uid")
        file = request.files.get("file")
    else:
        data = request.json
        message = data.get("message", "").lower()
        uid = data.get("uid")
        file = None

    try:
        # =========================
        # COURSE DETAIL QUESTIONS
        # who is my lecturer, when is, where is, final exam
        # =========================
        if any(word in message for word in ["lecturer", "when", "where", "venue", "final exam", "exam"]):

            if not uid:
                return jsonify({"type": "text", "reply": "User not logged in"})

            courses_ref = db.collection("students").document(uid).collection("timetable").stream()
            courses = [doc.to_dict() for doc in courses_ref]

            matched_course = None

            for course in courses:
                course_code = course.get("code", "").lower()
                course_name = course.get("name", "").lower()

                if (
                    course_code in message
                    or course_name in message
                    or any(word in message for word in course_name.split())
                ):
                    matched_course = course
                    break

            if not matched_course:
                return jsonify({
                    "type": "text",
                    "reply": "I could not find that course in your timetable."
                })

            code = matched_course.get("code")

            if "lecturer" in message or "teach" in message:
                return jsonify({
                    "type": "text",
                    "reply": f"Your lecturer for {matched_course.get('name')} is {matched_course.get('lecturer')}."
                })

            if "where" in message or "venue" in message:
                return jsonify({
                    "type": "text",
                    "reply": f"{matched_course.get('name')} is held at {matched_course.get('venue')}."
                })

            if "exam" in message or "final" in message:
                exam_doc = db.collection("students") \
                    .document(uid) \
                    .collection("exam_timetable") \
                    .document(code) \
                    .get()

                if not exam_doc.exists:
                    return jsonify({
                        "type": "text",
                        "reply": f"{matched_course.get('name')} has no final exam record."
                    })

                exam = exam_doc.to_dict()

                if exam.get("status") == "No final":
                    return jsonify({
                        "type": "text",
                        "reply": f"{matched_course.get('name')} has no final exam."
                    })

                return jsonify({
                    "type": "text",
                    "reply": f"Your final exam for {matched_course.get('name')} is on {exam.get('date')} at {exam.get('time')}."
                })

            if "when" in message or "time" in message:
                return jsonify({
                    "type": "text",
                    "reply": f"{matched_course.get('name')} is on {matched_course.get('day')} at {matched_course.get('time')}."
                })
        # =========================
        # EXAM TIMETABLE
        # =========================
        if any(word in message for word in ["exam", "final", "final exam", "exam timetable"]):

            if not uid:
                return jsonify({"type": "text", "reply": "User not logged in"})

            exam_ref = db.collection("students") \
                .document(uid) \
                .collection("exam_timetable") \
                .stream()

            exams = [doc.to_dict() for doc in exam_ref]

            return jsonify({
                "type": "exam_timetable",
                "data": exams
            })
        # =========================
        # TIMETABLE
        # =========================
        if any(word in message for word in ["timetable", "schedule", "class", "classes"]):

            if not uid:
                return jsonify({"type": "text", "reply": "User not logged in"})

            timetable_ref = db.collection("students").document(uid).collection("timetable").stream()
            timetable = [doc.to_dict() for doc in timetable_ref]

            return jsonify({
                "type": "timetable",
                "data": timetable
            })

        # =========================
        # OPEN COURSE MATERIAL PAGE
        # =========================
        if "open" in message or "material" in message or "course" in message:

            if not uid:
                return jsonify({"type": "text", "reply": "User not logged in"})

            courses_ref = db.collection("students").document(uid).collection("timetable").stream()
            courses = [doc.to_dict() for doc in courses_ref]

            for course in courses:
                course_code = course.get("code", "").lower()
                course_name = course.get("name", "").lower()

                if course_code in message or any(word in course_name for word in message.split()):
                    return jsonify({
                        "type": "redirect",
                        "reply": f"Opening {course.get('name')}...",
                        "url": f"/course/{course.get('code')}"
                    })

            return jsonify({
                "type": "text",
                "reply": "I could not find that course in your timetable."
            })
        # =========================
        # RETURN HOME
        # =========================
        if "home" in message:

            if "open" in message or "return" in message:
                return jsonify({
                    "type": "redirect",
                    "reply": "Returning home...",
                    "url": "/inter"
                })
            
        if any(word in message for word in ["submit", "send", "upload"]) and not file:
            return jsonify({
                "type": "text",
                "reply": "Please attach a file before submitting."
            })
        
        if file and any(word in message for word in ["submit", "send", "upload"]):

            courses_ref = db.collection("students").document(uid).collection("timetable").stream()

            for course in courses_ref:
                course_data = course.to_dict()
                course_code = course.id
                course_name = course_data.get("name", "").lower()

                course_code_lower = course_code.lower()
                course_code_short = course_code_lower.split()[0]

                course_words = course_name.split()

                course_match = (
                course_code_lower in message
                or course_code_short in message
                or course_name in message
                or any(word in message for word in course_words)
                )

                if course_match:
                    materials_ref = (
                        db.collection("students")
                        .document(uid)
                        .collection("timetable")
                        .document(course_code)
                        .collection("materials")
                        .stream()
                    )

                    for material in materials_ref:
                        material_data = material.to_dict()

                        if material_data.get("type") == "Assignment":
                            title = material_data.get("title", "").lower()

                            if title in message:
                                filename = secure_filename(file.filename)
                                saved_filename = f"{uid}_{material.id}_{filename}"

                                file_path = os.path.join(UPLOAD_FOLDER, saved_filename)
                                file.save(file_path)

                                file_url = f"/static/submissions/{saved_filename}"

                                db.collection("students") \
                                    .document(uid) \
                                    .collection("timetable") \
                                    .document(course_code) \
                                    .collection("materials") \
                                    .document(material.id) \
                                    .collection("submissions") \
                                    .document(uid) \
                                    .set({
                                        "uid": uid,
                                        "courseCode": course_code,
                                        "materialId": material.id,
                                        "fileName": filename,
                                        "fileUrl": file_url,
                                        "status": "Submitted for grading",
                                        "gradingStatus": "Not graded",
                                        "submittedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    })

                                return jsonify({
                                    "type": "redirect",
                                    "reply": "File submitted successfully.",
                                    "url": f"/submission-status/{course_code}/{material.id}"
                                })

            return jsonify({
                "type": "text",
                "reply": "I could not find the course or assignment. Try: submit this to CCBN test1"
            })

        # =========================
        # FILE SUMMARY USING GROQ
        # =========================
        if file and not any(word in message for word in ["submit", "send", "upload"]):

            filename = secure_filename(file.filename)
            saved_filename = f"{uid}_summary_{filename}"
            file_path = os.path.join(UPLOAD_FOLDER, saved_filename)

            file.save(file_path)

            file_text = extract_text_from_file(file_path)

            if not file_text.strip():
                return jsonify({
                    "type": "text",
                    "reply": "I could not read this file. Please upload a text-based PDF or TXT file."
                })

            # Prevent sending too much text to Groq
            file_text = file_text[:12000]

            prompt = f"""
You are AICAS AI assistant.

The user uploaded a file and wants help understanding it.
Summarize the file in simple student-friendly words.
Use this format:

1. Short summary
2. Main points
3. Important keywords
4. Simple conclusion

File name: {filename}

File content:
{file_text}
"""

            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful academic assistant."},
                    {"role": "user", "content": prompt}
                ]
            )

            return jsonify({
                "type": "text",
                "reply": response.choices[0].message.content
            })

        # =========================
        # STUDENTS
        # =========================
        elif "student" in message:

            students_ref = db.collection("students").stream()
            result = [doc.to_dict().get("matric") for doc in students_ref]

            return jsonify({
                "type": "students",
                "data": result
            })

        # =========================
        # GROQ AI
        # =========================
        prompt = f"""
You are AICAS AI assistant.

Rules:
- Do NOT answer timetable or class questions
- Keep answers short

User: {message}
"""

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
        )

        return jsonify({
            "type": "text",
            "reply": response.choices[0].message.content
        })

    except Exception as e:
        return jsonify({"type": "text", "reply": str(e)})
    
@app.route('/materials')
def materials_page():
    return render_template("materials.html")

@app.route("/delete-history", methods=["POST"])
def delete_history():

    data = request.get_json()

    uid = data.get("uid")
    history_id = data.get("historyId")

    db.collection("students") \
        .document(uid) \
        .collection("history") \
        .document(history_id) \
        .delete()

    return jsonify({
        "status": "success"
    })

@app.route("/delete-generated-tool", methods=["POST"])
def delete_generated_tool():

    data = request.get_json()

    uid = data.get("uid")
    tool_id = data.get("toolId")

    db.collection("students") \
        .document(uid) \
        .collection("generatedTools") \
        .document(tool_id) \
        .delete()

    return jsonify({
        "status": "success"
    })

@app.route('/get-courses', methods=['POST'])
def get_courses():
    data = request.json
    uid = data.get("uid")

    if not uid:
        return jsonify({"status": "fail", "message": "User not logged in"})

    try:
        courses_ref = db.collection("students").document(uid).collection("timetable").stream()
        courses = [doc.to_dict() for doc in courses_ref]

        return jsonify({
            "status": "success",
            "courses": courses
        })

    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

@app.route("/get-assignments-timeline", methods=["POST"])
def get_assignments_timeline():
    data = request.get_json()
    uid = data.get("uid")

    assignments = []

    timetable_ref = (
        db.collection("students")
        .document(uid)
        .collection("timetable")
        .stream()
    )

    for course in timetable_ref:
        course_data = course.to_dict()
        course_code = course.id
        course_name = course_data.get("name", "")

        materials_ref = (
            db.collection("students")
            .document(uid)
            .collection("timetable")
            .document(course_code)
            .collection("materials")
            .stream()
        )

        for material in materials_ref:

            material_data = material.to_dict()

            if material_data.get("type") == "Assignment":

                submission_doc = (
                    db.collection("students")
                    .document(uid)
                    .collection("timetable")
                    .document(course_code)
                    .collection("materials")
                    .document(material.id)
                    .collection("submissions")
                    .document(uid)
                    .get()
                )

                # Hide if already submitted
                if submission_doc.exists:
                    continue

                assignments.append({
                    "id": material.id,
                    "courseCode": course_code,
                    "courseName": course_name,
                    "title": material_data.get("title", "Untitled Assignment"),
                    "description": material_data.get("description", ""),
                    "createdAt": str(material_data.get("createdAt", ""))
                })

    return jsonify({
        "status": "success",
        "assignments": assignments
    })
     
@app.route('/course/<course_code>')
def course_page(course_code):
    return render_template("course.html", course_code=course_code)

# =========================
# GET USER
# =========================
@app.route('/get-user', methods=['POST'])
def get_user():
    data = request.json
    uid = data.get("uid")

    try:
        doc = db.collection("students").document(uid).get()

        if not doc.exists:
            return jsonify({"status": "fail", "message": "User not found"})

        return jsonify({
            "status": "success",
            "name": doc.to_dict().get("name", "Student")
        })

    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

@app.route("/get-course-materials", methods=["POST"])
def get_course_materials():

    data = request.get_json()

    uid = data.get("uid")
    course_code = data.get("courseCode")

    if not uid or not course_code:
        return jsonify({
            "status": "fail"
        })

    try:

        materials_ref = (
            db.collection("students")
            .document(uid)
            .collection("timetable")
            .document(course_code)
            .collection("materials")
            .stream()
        )

        materials = []

        for doc in materials_ref:

            material = doc.to_dict()

            materials.append({
                "id": doc.id,
                "title": material.get("title", "Untitled"),
                "description": material.get("description", ""),
                "type": material.get("type", "Material"),
                "fileUrl": material.get("fileUrl", ""),
                "fileName": material.get("fileName", "")
            })

        return jsonify({
            "status": "success",
            "materials": materials
        })

    except Exception as e:
        return jsonify({
            "status": "fail",
            "message": str(e)
        })
@app.route("/submission/<course_code>/<material_id>")
def submission_page(course_code, material_id):
    return render_template(
        "submission.html",
        course_code=course_code,
        material_id=material_id
    ) 

@app.route("/get-submission-detail", methods=["POST"])
def get_submission_detail():
    data = request.get_json()

    uid = data.get("uid")
    course_code = data.get("courseCode")
    material_id = data.get("materialId")

    if not uid or not course_code or not material_id:
        return jsonify({
            "status": "fail",
            "message": "Missing data"
        })

    submission_doc = (
        db.collection("students")
        .document(uid)
        .collection("timetable")
        .document(course_code)
        .collection("materials")
        .document(material_id)
        .collection("submissions")
        .document(uid)
        .get()
    )

    if not submission_doc.exists:
        return jsonify({
            "status": "success",
            "submitted": False
        })

    submission = submission_doc.to_dict()

    return jsonify({
        "status": "success",
        "submitted": True,
        "fileName": submission.get("fileName", ""),
        "fileUrl": submission.get("fileUrl", ""),
        "submittedAt": submission.get("submittedAt", "")
    })

@app.route("/upload-submission", methods=["POST"])
def upload_submission():
    uid = request.form.get("uid")
    course_code = request.form.get("courseCode")
    material_id = request.form.get("materialId")
    file = request.files.get("file")

    if not uid or not course_code or not material_id or not file:
        return jsonify({
            "status": "fail",
            "message": "Missing data"
        })

    filename = secure_filename(file.filename)

    saved_filename = f"{uid}_{material_id}_{filename}"
    file_path = os.path.join(UPLOAD_FOLDER, saved_filename)

    file.save(file_path)

    file_url = f"/static/submissions/{saved_filename}"

    db.collection("students") \
        .document(uid) \
        .collection("timetable") \
        .document(course_code) \
        .collection("materials") \
        .document(material_id) \
        .collection("submissions") \
        .document(uid) \
        .set({
            "uid": uid,
            "courseCode": course_code,
            "materialId": material_id,
            "fileName": filename,
            "fileUrl": file_url,
            "status": "Submitted for grading",
            "gradingStatus": "Not graded",
            "submittedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    return jsonify({
        "status": "success",
        "fileUrl": file_url
    })
@app.route("/check-submission", methods=["POST"])
def check_submission():
    data = request.get_json()

    uid = data.get("uid")
    course_code = data.get("courseCode")
    material_id = data.get("materialId")

    submission_doc = (
        db.collection("students")
        .document(uid)
        .collection("timetable")
        .document(course_code)
        .collection("materials")
        .document(material_id)
        .collection("submissions")
        .document(uid)
        .get()
    )

    return jsonify({
        "status": "success",
        "submitted": submission_doc.exists
    })
    
@app.route("/submission-status/<course_code>/<material_id>")
def submission_status_page(course_code, material_id):
    return render_template(
        "submission_status.html",
        course_code=course_code,
        material_id=material_id
    )
    
@app.route("/remove-submission", methods=["POST"])
def remove_submission():
    data = request.get_json()

    uid = data.get("uid")
    course_code = data.get("courseCode")
    material_id = data.get("materialId")

    if not uid or not course_code or not material_id:
        return jsonify({
            "status": "fail",
            "message": "Missing data"
        })

    submission_ref = (
        db.collection("students")
        .document(uid)
        .collection("timetable")
        .document(course_code)
        .collection("materials")
        .document(material_id)
        .collection("submissions")
        .document(uid)
    )

    submission_ref.delete()

    return jsonify({
        "status": "success"
    })

@app.route("/generate-flashcards", methods=["POST"])
def generate_flashcards():
    try:
        if request.content_type and request.content_type.startswith("multipart/form-data"):
            uid = request.form.get("uid")
            file = request.files.get("file")
        else:
            return jsonify({
                "status": "fail",
                "message": "No file received"
            })

        if not uid or not file:
            return jsonify({
                "status": "fail",
                "message": "Missing user or file"
            })

        filename = secure_filename(file.filename)
        saved_filename = f"{uid}_flashcards_{filename}"
        file_path = os.path.join(UPLOAD_FOLDER, saved_filename)

        file.save(file_path)

        file_text = extract_text_from_file(file_path)

        if not file_text.strip():
            return jsonify({
                "status": "fail",
                "message": "I could not read this file. Please upload a text-based PDF or TXT file."
            })

        file_text = file_text[:12000]

        prompt = f"""
Create 8 flashcards from this study material.

Return ONLY valid JSON.
Do not include markdown.
Do not include explanation outside JSON.

JSON format:
[
  {{
    "question": "Question text",
    "answer": "Answer text"
  }}
]

Study material:
{file_text}
"""

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are an academic flashcard generator. Always return valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        flashcard_text = response.choices[0].message.content

        return jsonify({
            "status": "success",
            "flashcards": flashcard_text
        })

    except Exception as e:
        return jsonify({
            "status": "fail",
            "message": str(e)
        })

@app.route("/generate-summary", methods=["POST"])
def generate_summary():
    try:
        if request.content_type and request.content_type.startswith("multipart/form-data"):
            uid = request.form.get("uid")
            file = request.files.get("file")
        else:
            return jsonify({
                "status": "fail",
                "message": "No file received"
            })

        if not uid or not file:
            return jsonify({
                "status": "fail",
                "message": "Missing user or file"
            })

        filename = secure_filename(file.filename)
        saved_filename = f"{uid}_summary_tool_{filename}"
        file_path = os.path.join(UPLOAD_FOLDER, saved_filename)

        file.save(file_path)

        file_text = extract_text_from_file(file_path)

        if not file_text.strip():
            return jsonify({
                "status": "fail",
                "message": "I could not read this file. Please upload a text-based PDF or TXT file."
            })

        file_text = file_text[:12000]

        prompt = f"""
Summarize this study material for a student.

Use this format:

1. Short Overview
2. Main Points
3. Important Terms
4. Exam Focus
5. Simple Conclusion

Keep it clear and easy to revise.

Study material:
{file_text}
"""

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are an academic notes summarizer for students."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        summary_text = response.choices[0].message.content

        return jsonify({
            "status": "success",
            "summary": summary_text
        })

    except Exception as e:
        return jsonify({
            "status": "fail",
            "message": str(e)
        })

@app.route("/generate-study-plan", methods=["POST"])
def generate_study_plan():
    try:
        data = request.get_json()

        subject = data.get("subject")
        exam_date = data.get("examDate")
        chapter_count = data.get("chapterCount")
        study_hours = data.get("studyHours")
        topics = data.get("topics", "")

        if not subject or not exam_date or not chapter_count or not study_hours:
            return jsonify({
                "status": "fail",
                "message": "Missing study plan details"
            })

        prompt = f"""
Create a practical student study plan.

Subject: {subject}
Exam date: {exam_date}
Number of chapters: {chapter_count}
Study hours per day: {study_hours}
Topics/chapters: {topics}

Use this format:

1. Study Overview
2. Daily Study Schedule
3. Revision Strategy
4. Practice Questions Plan
5. Final Day Review

Make it realistic and easy for a student to follow.
"""

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are an academic study planner for students."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return jsonify({
            "status": "success",
            "studyPlan": response.choices[0].message.content
        })

    except Exception as e:
        return jsonify({
            "status": "fail",
            "message": str(e)
        })

@app.route("/generate-keyterms", methods=["POST"])
def generate_keyterms():
    try:
        if request.content_type and request.content_type.startswith("multipart/form-data"):
            uid = request.form.get("uid")
            file = request.files.get("file")
        else:
            return jsonify({
                "status": "fail",
                "message": "No file received"
            })

        if not uid or not file:
            return jsonify({
                "status": "fail",
                "message": "Missing user or file"
            })

        filename = secure_filename(file.filename)
        saved_filename = f"{uid}_keyterms_{filename}"
        file_path = os.path.join(UPLOAD_FOLDER, saved_filename)

        file.save(file_path)

        file_text = extract_text_from_file(file_path)

        if not file_text.strip():
            return jsonify({
                "status": "fail",
                "message": "I could not read this file. Please upload a text-based PDF or TXT file."
            })

        file_text = file_text[:12000]

        prompt = f"""
Extract 10 important key terms from this study material.

Return ONLY valid JSON.
Do not include markdown.
Do not include explanation outside JSON.

JSON format:
[
  {{
    "term": "Key term",
    "definition": "Simple student-friendly definition"
  }}
]

Study material:
{file_text}
"""

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are an academic key term extractor. Always return valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        keyterm_text = response.choices[0].message.content

        return jsonify({
            "status": "success",
            "keyTerms": keyterm_text
        })

    except Exception as e:
        return jsonify({
            "status": "fail",
            "message": str(e)
        })

@app.route("/explain-beginner", methods=["POST"])
def explain_beginner():

    try:

        uid = request.form.get("uid")
        file = request.files.get("file")

        if not uid or not file:
            return jsonify({
                "status": "fail",
                "message": "Missing data"
            })

        filename = secure_filename(file.filename)

        saved_filename = f"{uid}_beginner_{filename}"

        file_path = os.path.join(
            UPLOAD_FOLDER,
            saved_filename
        )

        file.save(file_path)

        file_text = extract_text_from_file(file_path)

        if not file_text.strip():
            return jsonify({
                "status": "fail",
                "message": "Could not read file"
            })

        file_text = file_text[:12000]

        prompt = f"""
Explain this study material as if teaching a complete beginner.

Rules:
- Use simple language
- Avoid jargon where possible
- Use analogies
- Use examples
- Make it easy for first year students

Material:

{file_text}
"""

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a friendly tutor."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return jsonify({
            "status": "success",
            "explanation":
                response.choices[0].message.content
        })

    except Exception as e:

        return jsonify({
            "status": "fail",
            "message": str(e)
        })
@app.route("/get-generated-tools", methods=["POST"])
def get_generated_tools():
    try:
        data = request.get_json()
        uid = data.get("uid")

        tools_ref = db.collection("students") \
            .document(uid) \
            .collection("generatedTools") \
            .order_by("createdAt", direction=firestore.Query.DESCENDING) \
            .limit(10) \
            .stream()

        tools = []

        for doc in tools_ref:
            item = doc.to_dict()
            item["id"] = doc.id
            tools.append(item)

        return jsonify({
            "status": "success",
            "tools": tools
        })

    except Exception as e:
        return jsonify({
            "status": "fail",
            "message": str(e)
        })

@app.route("/save-chat-history", methods=["POST"])
def save_chat_history():
    try:
        data = request.get_json()

        uid = data.get("uid")
        history_id = data.get("historyId")
        title = data.get("title", "New Chat")
        messages = data.get("messages", [])

        if not uid or not messages:
            return jsonify({
                "status": "fail",
                "message": "Missing chat history data"
            })

        history_data = {
            "title": title,
            "messages": messages,
            "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        if history_id:
            db.collection("students").document(uid) \
                .collection("history").document(history_id) \
                .set(history_data, merge=True)

            return jsonify({
                "status": "success",
                "historyId": history_id
            })

        doc_ref = db.collection("students").document(uid) \
            .collection("history").add(history_data)

        return jsonify({
            "status": "success",
            "historyId": doc_ref[1].id
        })

    except Exception as e:
        return jsonify({
            "status": "fail",
            "message": str(e)
        })


@app.route("/get-chat-histories", methods=["POST"])
def get_chat_histories():
    try:
        data = request.get_json()
        uid = data.get("uid")

        histories_ref = db.collection("students").document(uid) \
            .collection("history") \
            .order_by("updatedAt", direction=firestore.Query.DESCENDING) \
            .limit(20) \
            .stream()

        histories = []

        for doc in histories_ref:
            item = doc.to_dict()
            item["id"] = doc.id
            histories.append(item)

        return jsonify({
            "status": "success",
            "histories": histories
        })

    except Exception as e:
        return jsonify({
            "status": "fail",
            "message": str(e)
        })


@app.route("/get-chat-history", methods=["POST"])
def get_chat_history():
    try:
        data = request.get_json()
        uid = data.get("uid")
        history_id = data.get("historyId")

        doc = db.collection("students").document(uid) \
            .collection("history").document(history_id).get()

        if not doc.exists:
            return jsonify({
                "status": "fail",
                "message": "Chat history not found"
            })

        item = doc.to_dict()
        item["id"] = doc.id

        return jsonify({
            "status": "success",
            "history": item
        })

    except Exception as e:
        return jsonify({
            "status": "fail",
            "message": str(e)
        })

@app.route("/save-generated-tool", methods=["POST"])
def save_generated_tool():
    try:
        data = request.get_json()

        uid = data.get("uid")
        tool_type = data.get("type")
        title = data.get("title")
        content = data.get("content")

        if not uid or not tool_type or not title or not content:
            return jsonify({
                "status": "fail",
                "message": "Missing data"
            })

        db.collection("students") \
            .document(uid) \
            .collection("generatedTools") \
            .add({
                "type": tool_type,
                "title": title,
                "content": content,
                "createdAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

        return jsonify({"status": "success"})

    except Exception as e:
        return jsonify({
            "status": "fail",
            "message": str(e)
        })

@app.route("/generate-quiz", methods=["POST"])
def generate_quiz():
    try:
        if request.content_type and request.content_type.startswith("multipart/form-data"):
            uid = request.form.get("uid")
            file = request.files.get("file")
        else:
            return jsonify({
                "status": "fail",
                "message": "No file received"
            })

        if not uid or not file:
            return jsonify({
                "status": "fail",
                "message": "Missing user or file"
            })

        filename = secure_filename(file.filename)
        saved_filename = f"{uid}_quiz_{filename}"
        file_path = os.path.join(UPLOAD_FOLDER, saved_filename)

        file.save(file_path)

        file_text = extract_text_from_file(file_path)

        if not file_text.strip():
            return jsonify({
                "status": "fail",
                "message": "I could not read this file. Please upload a text-based PDF or TXT file."
            })

        file_text = file_text[:12000]

        prompt = f"""
Create 5 multiple choice quiz questions from this study material.

Return ONLY valid JSON.
Do not include markdown.
Do not include explanation outside JSON.

JSON format:
[
  {{
    "question": "Question text",
    "options": [
      "Option A",
      "Option B",
      "Option C",
      "Option D"
    ],
    "correctIndex": 0,
    "explanation": "Short explanation why this answer is correct."
  }}
]

Study material:
{file_text}
"""

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are an academic quiz generator. Always return valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        quiz_text = response.choices[0].message.content

        return jsonify({
            "status": "success",
            "quiz": quiz_text
        })

    except Exception as e:
        return jsonify({
            "status": "fail",
            "message": str(e)
        })

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(debug=True)