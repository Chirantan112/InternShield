"""Student-facing offer analysis, history, and reporting workflows."""

from time import perf_counter

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func, select

from ..extensions import db
from ..models import AnalysisCheck, CheckFlag, DetectionRule, ScamReport
from ..services.ai_review import AIReviewError, request_ai_review
from ..services.file_parser import FileParseError, extract_offer_text
from ..services.rule_engine import InvalidRulePattern, analyze_offer
from ..utils.decorators import role_required

student_bp = Blueprint("student", __name__, url_prefix="/student")


@student_bp.get("/")
@role_required("student")
def dashboard():
    recent_checks = db.session.scalars(
        select(AnalysisCheck)
        .where(AnalysisCheck.user_id == current_user.id)
        .order_by(AnalysisCheck.created_at.desc())
        .limit(5)
    ).all()
    total_checks = db.session.scalar(
        select(func.count(AnalysisCheck.id)).where(
            AnalysisCheck.user_id == current_user.id
        )
    ) or 0
    return render_template(
        "student/dashboard.html",
        recent_checks=recent_checks,
        total_checks=total_checks,
    )


@student_bp.route("/analyze", methods=["GET", "POST"])
@role_required("student")
def analyze():
    if request.method == "GET":
        return render_template("student/analyze.html")

    uploaded = request.files.get("offer_file")
    pasted_text = request.form.get("offer_text", "").strip()
    source_type = "pasted_text"

    try:
        if uploaded and uploaded.filename:
            text = extract_offer_text(
                uploaded,
                uploaded.filename,
                max_bytes=current_app.config["MAX_CONTENT_LENGTH"],
                max_characters=current_app.config["MAX_ANALYSIS_CHARACTERS"],
            )
            source_type = "uploaded_file"
        else:
            text = pasted_text

        if not text:
            raise ValueError("Paste an offer or choose a TXT/PDF file to analyze.")
        if len(text) > current_app.config["MAX_ANALYSIS_CHARACTERS"]:
            raise ValueError("Offer text exceeds the configured character limit.")

        rules = db.session.scalars(
            select(DetectionRule).where(DetectionRule.is_active.is_(True))
        ).all()
        started = perf_counter()
        result = analyze_offer(text, rules)
        duration_ms = round((perf_counter() - started) * 1000, 2)

        check = AnalysisCheck(
            user_id=current_user.id,
            input_text=text,
            source_type=source_type,
            score=result["score"],
            risk_level=result["risk_level"],
        )
        for flag in result["flags"]:
            check.flags.append(
                CheckFlag(
                    rule_id=flag["rule_id"],
                    rule_name=flag["rule_name"],
                    explanation=flag["explanation"],
                    points=flag["points"],
                )
            )
        db.session.add(check)
        db.session.commit()

        # External processing is strictly opt-in. A provider failure never
        # discards the saved deterministic result or changes its score.
        ai_review = None
        if request.form.get("ai_opt_in") == "yes":
            try:
                ai_review = request_ai_review(text, current_app.config)
            except AIReviewError as exc:
                flash(str(exc), "warning")

        return render_template(
            "student/result.html",
            check=check,
            result=result,
            duration_ms=duration_ms,
            ai_review=ai_review,
        )
    except (FileParseError, InvalidRulePattern, ValueError) as exc:
        db.session.rollback()
        flash(str(exc), "danger")
        return redirect(url_for("student.analyze"))


@student_bp.get("/history")
@role_required("student")
def history():
    checks = db.session.scalars(
        select(AnalysisCheck)
        .where(AnalysisCheck.user_id == current_user.id)
        .order_by(AnalysisCheck.created_at.desc())
    ).all()
    return render_template("student/history.html", checks=checks)


@student_bp.post("/history/<int:check_id>/delete")
@role_required("student")
def delete_history(check_id: int):
    check = db.session.scalar(
        select(AnalysisCheck).where(
            AnalysisCheck.id == check_id,
            AnalysisCheck.user_id == current_user.id,
        )
    )
    if check is None:
        abort(404)
    db.session.delete(check)
    db.session.commit()
    flash("Analysis deleted from your history.", "success")
    return redirect(url_for("student.history"))


@student_bp.route("/report", methods=["GET", "POST"])
@role_required("student")
def report_scam():
    if request.method == "POST":
        company_name = request.form.get("company_name", "").strip()
        offer_details = request.form.get("offer_details", "").strip()
        contact = request.form.get("contact_or_website", "").strip() or None
        if not company_name or not offer_details:
            flash("Company name and offer details are required.", "danger")
        elif len(company_name) > 160 or len(offer_details) > 20_000 or (
            contact and len(contact) > 500
        ):
            flash("One or more report fields exceed the allowed length.", "danger")
        else:
            report = ScamReport(
                user_id=current_user.id,
                company_name=company_name,
                offer_details=offer_details,
                contact_or_website=contact,
            )
            db.session.add(report)
            db.session.commit()
            flash("Your report was submitted for administrator review.", "success")
            return redirect(url_for("student.my_reports"))

    return render_template("student/report.html")


@student_bp.get("/reports")
@role_required("student")
def my_reports():
    reports = db.session.scalars(
        select(ScamReport)
        .where(ScamReport.user_id == current_user.id)
        .order_by(ScamReport.created_at.desc())
    ).all()
    return render_template("student/reports.html", reports=reports)
