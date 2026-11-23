# InternShield

**Internship and Job Offer Risk Screening for Students**

InternShield is a student-focused web application that examines internship and job offer messages for common scam indicators. Students can paste offer text or upload a supported text/PDF document, review an explainable risk score, keep a private history of checks, and report suspicious offers. Administrators can manage detection rules, review reports, and monitor system activity.

> **Important:** InternShield provides a preliminary, rule-based risk assessment. It does not prove that an employer or offer is fraudulent. A low score is not a guarantee of legitimacy, and a single indicator (such as a free email address) is not proof of a scam.

## Project goals

- Identify common warning signs such as requests for fees, sensitive information, suspicious urgency, and unrealistic promises.
- Explain every triggered indicator rather than returning an unexplained score.
- Keep student accounts, analysis history, and report workflows separated by role.
- Allow administrators to maintain detection rules without editing application code.
- Evaluate functionality, performance, usability, reliability, security, and correctness through documented tests.

## Planned technology

- Python 3 and Flask
- Flask-SQLAlchemy and SQLite
- Flask-Login and Werkzeug password hashing
- Flask-WTF for form and CSRF protection
- PyMuPDF for PDF text extraction
- HTML, CSS, JavaScript, and Bootstrap
- pytest for automated tests

The core detection workflow is designed to run locally without a paid AI/API dependency. Optional API integrations, if considered later, will remain separate from the required rule-based functionality.

## Main capabilities

### Student
- Register, log in, and log out.
- Analyze pasted offer text or supported TXT/PDF files.
- View a Low, Medium, or High risk band, a score, and explanations for detected indicators.
- View and delete only their own analysis history.
- Submit suspicious-offer/company reports.

### Administrator
- View aggregate analysis statistics and common warning indicators.
- Add, edit, enable, disable, and delete detection rules.
- Review submitted reports and approve or reject them.

## Assignment alignment

The implementation and final report will cover the required sections:

1. Title
2. Problem statement
3. Objectives
4. Stakeholders
5. Functional requirements
6. Non-functional requirements
7. Implementation screenshots
8. Source code
9. Test cases with actual test results
10. Conclusion

The project will be evaluated against functionality, performance, usability, reliability, security, and correctness. The report is intended to remain within the assignment's 10-page limit. Sources used in the report will be cited in the text.

## Development status

The repository is being built incrementally. Features and test results will be marked complete only after implementation and verification.

## Local setup

Setup instructions will be added as the application files are introduced. Do not commit local databases, secret keys, virtual environments, uploaded private offers, or other user data.
