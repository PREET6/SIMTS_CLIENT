from flask import (
    Blueprint,
    abort,
    current_app,
    make_response,
    render_template,
    request,
    send_from_directory,
    send_file,
)
from sqlalchemy import or_
from werkzeug.exceptions import BadRequest

from extensions import db, limiter
from models import Certificate, ContactMessage, Course, Marksheet, Student
from services.blob_storage import blob_enabled, download_to_temp, BlobStorageError

public_bp = Blueprint("public", __name__)


# ============================================================
# SECURITY / CACHE CONTROL
# ============================================================

def no_store(response):
    """
    Prevent sensitive verification results from being cached
    by the browser or intermediary proxies.
    """
    response = make_response(response)

    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, max-age=0"
    )
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return response


# ============================================================
# STUDENT SEARCH HELPER
# ============================================================

def find_student(query):
    """
    Find a student using either student ID or email.

    The query is intentionally limited in length to prevent
    unnecessarily large database queries.
    """
    query = (query or "").strip()

    if not query or len(query) > 200:
        return None

    return Student.query.filter(
        or_(
            Student.student_id.ilike(query),
            Student.email.ilike(query),
        )
    ).first()


# ============================================================
# HOME
# ============================================================

@public_bp.route("/")
def home():
    courses = (
        Course.query
        .filter_by(status="active")
        .order_by(Course.id.desc())
        .limit(6)
        .all()
    )

    return render_template(
        "index.html",
        courses=courses,
    )


# ============================================================
# COURSES
# ============================================================

@public_bp.route("/courses")
def courses():
    courses = (
        Course.query
        .filter_by(status="active")
        .order_by(Course.course_name)
        .all()
    )

    return render_template(
        "courses.html",
        courses=courses,
    )


# ============================================================
# ADMISSION VERIFICATION
# ============================================================

@public_bp.route(
    "/admission-verification",
    methods=["GET", "POST"],
)
@limiter.limit(
    "30 per minute",
    methods=["POST"],
)
def admission_verification():

    student = None
    searched = False

    if request.method == "POST":

        searched = True

        query = request.form.get("query", "").strip()

        # Reject excessively large input.
        if len(query) > 200:
            raise BadRequest(
                "Verification input is too long."
            )

        student = find_student(query)

    response = render_template(
        "admission_verification.html",
        student=student,
        searched=searched,
    )

    return no_store(response)


# ============================================================
# CERTIFICATE VERIFICATION
# ============================================================

@public_bp.route(
    "/certificate-verification",
    methods=["GET", "POST"],
)
@limiter.limit(
    "30 per minute",
    methods=["POST"],
)
def certificate_verification():

    certificate = None
    student = None
    searched = False

    if request.method == "POST":

        searched = True

        query = (
            request.form.get("query", "")
            .strip()
        )

        # Reject excessively large input.
        if len(query) > 200:
            raise BadRequest(
                "Verification input is too long."
            )

        # 1. Search directly by certificate number
        if query:
            certificate = (
                Certificate.query
                .filter_by(
                    certificate_number=query,
                    status="valid",
                )
                .first()
            )

        # 2. If certificate number wasn't found, search by student ID/email.
        if certificate:
            student = db.session.get(
                Student,
                certificate.student_id,
            )
        else:
            student = find_student(query)
            if student and student.certificate_number:
                certificate = (
                    Certificate.query
                    .filter_by(
                        certificate_number=(
                            student.certificate_number
                        ),
                        status="valid",
                    )
                    .first()
                )

    response = render_template(
        "certificate_verification.html",
        certificate=certificate,
        student=student,
        searched=searched,
    )

    return no_store(response)


# ============================================================
# MARKSHEET VERIFICATION
# ============================================================

@public_bp.route(
    "/marksheet-verification",
    methods=["GET", "POST"],
)
@limiter.limit(
    "30 per minute",
    methods=["POST"],
)
def marksheet_verification():

    marksheet = None
    student = None
    searched = False

    if request.method == "POST":

        searched = True

        query = (
            request.form.get("query", "")
            .strip()
        )

        # Reject excessively large input.
        if len(query) > 200:
            raise BadRequest(
                "Verification input is too long."
            )

        # 1. Search directly by marksheet number
        if query:
            marksheet = (
                Marksheet.query
                .filter_by(
                    marksheet_number=query,
                    status="valid",
                )
                .first()
            )

        # 2. If marksheet number wasn't found, search by student ID/email.
        if marksheet:
            student = db.session.get(
                Student,
                marksheet.student_id,
            )
        else:
            student = find_student(query)
            if student and student.marksheet_number:
                marksheet = (
                    Marksheet.query
                    .filter_by(
                        marksheet_number=(
                            student.marksheet_number
                        ),
                        status="valid",
                    )
                    .first()
                )

    response = render_template(
        "marksheet_verification.html",
        marksheet=marksheet,
        student=student,
        searched=searched,
    )

    return no_store(response)


# ============================================================
# VIEW CERTIFICATE PDF
# ============================================================

@public_bp.route(
    "/certificate/<int:certificate_id>/view"
)
@limiter.limit("60 per minute")
def view_certificate(certificate_id):

    certificate = db.session.get(
        Certificate,
        certificate_id,
    )

    # Never expose invalid/non-existing certificates.
    if (
        not certificate
        or certificate.status != "valid"
    ):
        abort(404)

    if blob_enabled():
        try:
            temp_path = download_to_temp(certificate.file_name)
        except BlobStorageError:
            abort(404)

        response = send_file(
            temp_path,
            mimetype="application/pdf",
            as_attachment=False,
            download_name="certificate.pdf",
        )
        response.call_on_close(
            lambda path=temp_path: path.unlink(missing_ok=True)
        )
    else:
        response = send_from_directory(
            current_app.config["UPLOAD_FOLDER"],
            certificate.file_name,
            as_attachment=False,
            mimetype="application/pdf",
        )

    # Sensitive certificate files should not be cached.
    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, max-age=0"
    )
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    # Security headers.
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Display PDF in browser instead of forcing download.
    response.headers["Content-Disposition"] = "inline"

    return response


# ============================================================
# VIEW MARKSHEET PDF
# ============================================================

@public_bp.route(
    "/marksheet/<int:marksheet_id>/view"
)
@limiter.limit("60 per minute")
def view_marksheet(marksheet_id):

    marksheet = db.session.get(
        Marksheet,
        marksheet_id,
    )

    # Never expose invalid/non-existing marksheets.
    if (
        not marksheet
        or marksheet.status != "valid"
    ):
        abort(404)

    if blob_enabled():
        try:
            temp_path = download_to_temp(marksheet.file_name)
        except BlobStorageError:
            abort(404)

        response = send_file(
            temp_path,
            mimetype="application/pdf",
            as_attachment=False,
            download_name="marksheet.pdf",
        )
        response.call_on_close(
            lambda path=temp_path: path.unlink(missing_ok=True)
        )
    else:
        response = send_from_directory(
            current_app.config["UPLOAD_FOLDER"],
            marksheet.file_name,
            as_attachment=False,
            mimetype="application/pdf",
        )

    # Sensitive marksheet files should not be cached.
    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, max-age=0"
    )
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    # Security headers.
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Display PDF in browser instead of forcing download.
    response.headers["Content-Disposition"] = "inline"

    return response


# ============================================================
# CONTACT US
# ============================================================

@public_bp.route(
    "/contact",
    methods=["GET", "POST"],
)
@limiter.limit(
    "5 per minute",
    methods=["POST"],
)
def contact():

    if request.method == "POST":

        name = (
            request.form.get("name", "")
            .strip()
        )

        email = (
            request.form.get("email", "")
            .strip()
        )

        subject = (
            request.form.get("subject", "")
            .strip()
        )

        message = (
            request.form.get("message", "")
            .strip()
        )

        # Required fields
        if not name or not email or not message:

            return render_template(
                "contact.html",
                error=(
                    "Please complete all required fields."
                ),
            )

        # Length validation
        if (
            len(name) > 200
            or len(email) > 200
            or len(subject) > 300
            or len(message) > 5000
        ):

            return render_template(
                "contact.html",
                error=(
                    "One or more fields are too long."
                ),
            )

        # Save contact message
        db.session.add(
            ContactMessage(
                name=name,
                email=email,
                subject=subject,
                message=message,
            )
        )

        db.session.commit()

        return render_template(
            "contact.html",
            success=(
                "Your message has been sent successfully."
            ),
        )

    return render_template(
        "contact.html"
    )