"""Integration tests for student and administrator workflows."""

from werkzeug.security import generate_password_hash

from internshield.extensions import db
from internshield.models import AnalysisCheck, ScamReport, User


def test_student_analysis_saves_explainable_result(client, student, app):
    response = client.post(
        "/student/analyze",
        data={"offer_text": "Pay a registration fee before joining."},
    )
    assert response.status_code == 200
    assert b"30" in response.data
    assert b"Fee request" in response.data
    with app.app_context():
        check = db.session.query(AnalysisCheck).one()
        assert check.score == 30
        assert check.risk_level == "low"
        assert check.flags[0].rule_name == "Fee request"


def test_empty_analysis_is_handled_without_server_error(client, student):
    response = client.post("/student/analyze", data={"offer_text": "  "})
    assert response.status_code == 302


def test_student_history_is_private_and_delete_is_owner_scoped(client, student, app):
    with app.app_context():
        other = User(
            name="Other Student",
            email="other@example.test",
            password_hash=generate_password_hash("OtherPassword123"),
            role="student",
        )
        db.session.add(other)
        db.session.flush()
        private_check = AnalysisCheck(
            user_id=other.id,
            input_text="Private offer",
            source_type="pasted_text",
            score=0,
            risk_level="low",
        )
        db.session.add(private_check)
        db.session.commit()
        check_id = private_check.id

    history_response = client.get("/student/history")
    assert history_response.status_code == 200
    assert b"Private offer" not in history_response.data
    response = client.post(f"/student/history/{check_id}/delete")
    assert response.status_code == 404
    with app.app_context():
        assert db.session.get(AnalysisCheck, check_id) is not None


def test_student_cannot_access_admin_pages(client, student):
    response = client.get("/admin/")
    assert response.status_code == 403


def test_student_can_submit_and_view_own_report(client, student):
    response = client.post(
        "/student/report",
        data={
            "company_name": "Suspicious Recruiter",
            "contact_or_website": "recruiter@example.test",
            "offer_details": "They asked me to pay a registration fee.",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Suspicious Recruiter" in response.data


def test_admin_can_create_edit_and_disable_keyword_rule(admin_client, app):
    response = admin_client.post(
        "/admin/rules/new",
        data={
            "name": "Urgent payment",
            "description": "Requests urgent payment.",
            "pattern": "pay immediately",
            "points": "25",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        from internshield.models import DetectionRule

        rule = db.session.query(DetectionRule).filter_by(name="Urgent payment").one()
        rule_id = rule.id

    response = admin_client.post(
        f"/admin/rules/{rule_id}/edit",
        data={
            "name": "Urgent payment",
            "description": "Requests urgent payment.",
            "pattern": "pay immediately",
            "points": "35",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        from internshield.models import DetectionRule
        from internshield.services.rule_engine import analyze_offer

        rule = db.session.get(DetectionRule, rule_id)
        assert rule.points == 35
        updated_result = analyze_offer("Please pay immediately.", [rule])
        assert updated_result["score"] == 35

    response = admin_client.post(
        f"/admin/rules/{rule_id}/toggle",
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        from internshield.models import DetectionRule
        from internshield.services.rule_engine import analyze_offer

        rule = db.session.get(DetectionRule, rule_id)
        assert rule.is_active is False
        disabled_result = analyze_offer("Please pay immediately.", [rule])
        assert disabled_result["score"] == 0

    response = admin_client.post(
        f"/admin/rules/{rule_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        from internshield.models import DetectionRule

        assert db.session.get(DetectionRule, rule_id) is None

def test_admin_can_review_scam_report(admin_client, app):
    with app.app_context():
        student_user = User(
            name="Reporter",
            email="reporter@example.test",
            password_hash=generate_password_hash("ReporterPassword123"),
            role="student",
        )
        db.session.add(student_user)
        db.session.flush()
        report = ScamReport(
            user_id=student_user.id,
            company_name="Fake Jobs Ltd",
            offer_details="Asked for a fee.",
        )
        db.session.add(report)
        db.session.commit()
        report_id = report.id

    response = admin_client.post(
        f"/admin/reports/{report_id}/review",
        data={"decision": "approved", "notes": "Evidence reviewed."},
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        report = db.session.get(ScamReport, report_id)
        assert report.status == "approved"
        assert report.reviews[0].decision == "approved"
        assert report.reviews[0].notes == "Evidence reviewed."


def test_unauthenticated_user_is_redirected_to_login(client):
    response = client.get("/student/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_student_can_analyze_txt_upload(client, student):
    from io import BytesIO

    response = client.post(
        "/student/analyze",
        data={"offer_file": (BytesIO(b"Please pay a registration fee."), "offer.txt")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert b"Fee request" in response.data


def test_student_upload_rejects_unsupported_file(client, student):
    from io import BytesIO

    response = client.post(
        "/student/analyze",
        data={"offer_file": (BytesIO(b"not supported"), "offer.exe")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Unsupported file type" in response.data


def test_ai_opt_in_does_not_block_rule_based_result_when_disabled(client, student, app):
    response = client.post(
        "/student/analyze",
        data={
            "offer_text": "Please pay a registration fee.",
            "ai_opt_in": "yes",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"30" in response.data
    assert b"not configured" in response.data
    with app.app_context():
        saved = db.session.query(AnalysisCheck).one()
        assert saved.score == 30
        assert saved.risk_level == "low"
