"""Administrator dashboard, detection-rule management, and report review."""

import re

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func, select

from ..extensions import db
from ..models import (
    AnalysisCheck,
    CheckFlag,
    DetectionRule,
    ReportReview,
    ScamReport,
)
from ..utils.decorators import role_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.get("/")
@role_required("admin")
def dashboard():
    total = db.session.scalar(select(func.count(AnalysisCheck.id))) or 0
    counts = {
        level: (
            db.session.scalar(
                select(func.count(AnalysisCheck.id)).where(
                    AnalysisCheck.risk_level == level
                )
            )
            or 0
        )
        for level in ("low", "medium", "high")
    }
    pending = db.session.scalar(
        select(func.count(ScamReport.id)).where(ScamReport.status == "pending")
    ) or 0
    common_flags = db.session.execute(
        select(CheckFlag.rule_name, func.count(CheckFlag.id).label("total"))
        .group_by(CheckFlag.rule_name)
        .order_by(func.count(CheckFlag.id).desc())
        .limit(5)
    ).all()
    return render_template(
        "admin/dashboard.html",
        total=total,
        counts=counts,
        pending=pending,
        common_flags=common_flags,
    )


@admin_bp.get("/rules")
@role_required("admin")
def rules():
    all_rules = db.session.scalars(
        select(DetectionRule).order_by(DetectionRule.name.asc())
    ).all()
    return render_template("admin/rules.html", rules=all_rules)


@admin_bp.route("/rules/new", methods=["GET", "POST"])
@role_required("admin")
def create_rule():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        pattern = request.form.get("pattern", "").strip()
        try:
            points = int(request.form.get("points", ""))
        except ValueError:
            points = -1
        if not name or not description or not pattern:
            flash("All rule fields are required.", "danger")
        elif len(name) > 120 or len(description) > 500 or len(pattern) > 1000:
            flash("One or more fields exceed the allowed length.", "danger")
        elif not 0 <= points <= 100:
            flash("Points must be between 0 and 100.", "danger")
        elif db.session.scalar(
            select(DetectionRule.id).where(DetectionRule.name == name)
        ):
            flash("A rule with that name already exists.", "danger")
        else:
            # Admin-created rules deliberately use literal keywords only.
            # This avoids executing arbitrary administrator-supplied regexes.
            rule = DetectionRule(
                name=name,
                description=description,
                pattern=pattern,
                match_type="keyword",
                points=points,
                is_active=True,
            )
            db.session.add(rule)
            db.session.commit()
            flash("Detection rule created.", "success")
            return redirect(url_for("admin.rules"))
    return render_template("admin/rule_form.html", rule=None)


@admin_bp.route("/rules/<int:rule_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_rule(rule_id: int):
    rule = db.session.get(DetectionRule, rule_id)
    if rule is None:
        abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        pattern = request.form.get("pattern", "").strip()
        try:
            points = int(request.form.get("points", ""))
        except ValueError:
            points = -1
        duplicate = db.session.scalar(
            select(DetectionRule.id).where(
                DetectionRule.name == name, DetectionRule.id != rule.id
            )
        )
        invalid_regex = False
        if rule.match_type == "regex" and pattern:
            try:
                re.compile(pattern, flags=re.IGNORECASE)
            except re.error:
                invalid_regex = True

        if not name or not description or not pattern:
            flash("All rule fields are required.", "danger")
        elif len(name) > 120 or len(description) > 500 or len(pattern) > 1000:
            flash("One or more fields exceed the allowed length.", "danger")
        elif not 0 <= points <= 100 or duplicate:
            flash("Check the points value and ensure the rule name is unique.", "danger")
        elif invalid_regex:
            flash("Enter a valid regular expression for this rule.", "danger")
        else:
            rule.name = name
            rule.description = description
            rule.pattern = pattern
            rule.points = points
            # Preserve the existing match type. Regex rules are validated above;
            # new rules remain keyword-only to avoid exposing arbitrary regexes.
            db.session.commit()
            flash("Detection rule updated.", "success")
            return redirect(url_for("admin.rules"))
    return render_template("admin/rule_form.html", rule=rule)


@admin_bp.post("/rules/<int:rule_id>/toggle")
@role_required("admin")
def toggle_rule(rule_id: int):
    rule = db.session.get(DetectionRule, rule_id)
    if rule is None:
        abort(404)
    rule.is_active = not rule.is_active
    db.session.commit()
    flash(f"Rule {'enabled' if rule.is_active else 'disabled'}.", "success")
    return redirect(url_for("admin.rules"))


@admin_bp.post("/rules/<int:rule_id>/delete")
@role_required("admin")
def delete_rule(rule_id: int):
    rule = db.session.get(DetectionRule, rule_id)
    if rule is None:
        abort(404)
    # Historical flags retain their rule-name/explanation/points snapshot.
    db.session.delete(rule)
    db.session.commit()
    flash("Detection rule deleted.", "success")
    return redirect(url_for("admin.rules"))


@admin_bp.get("/reports")
@role_required("admin")
def reports():
    status = request.args.get("status", "pending")
    if status not in {"pending", "approved", "rejected", "all"}:
        status = "pending"
    query = select(ScamReport).order_by(ScamReport.created_at.desc())
    if status != "all":
        query = query.where(ScamReport.status == status)
    items = db.session.scalars(query).all()
    return render_template("admin/reports.html", reports=items, selected_status=status)


@admin_bp.post("/reports/<int:report_id>/review")
@role_required("admin")
def review_report(report_id: int):
    report = db.session.get(ScamReport, report_id)
    if report is None:
        abort(404)
    decision = request.form.get("decision", "")
    notes = request.form.get("notes", "").strip() or None
    if decision not in {"approved", "rejected"}:
        abort(400)
    if notes and len(notes) > 1000:
        flash("Review notes cannot exceed 1,000 characters.", "danger")
        return redirect(url_for("admin.reports"))
    report.status = decision
    db.session.add(
        ReportReview(
            report_id=report.id,
            admin_id=current_user.id,
            decision=decision,
            notes=notes,
        )
    )
    db.session.commit()
    flash(f"Report {decision}.", "success")
    return redirect(url_for("admin.reports"))
