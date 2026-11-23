# InternShield – Fake Internship & Job Offer Detection System

**Course:** CSC203B – Software Development Fundamentals  
**Programme:** B.Tech Computer Science and Engineering  
**Project:** InternShield  
**Student:** [Enter student name and USN]  
**Institution:** [Enter institution]  
**Submission date:** 23 November 2026

> **Submission note:** Replace the screenshot placeholders with genuine screenshots from the local demonstration, and enter the measured response time from the demonstration laptop. Do not submit this report with placeholders.

## 1. Problem statement

Students increasingly receive internship and job offers through email, messaging applications, and online platforms. Some suspicious offers request registration or training fees, ask for identity or banking information, use pressure tactics, or promise unrealistic employment benefits. Students may find it difficult to identify these warning signs before responding.

InternShield is a web application that screens offer text using configurable rules. It calculates an explainable preliminary score, identifies the warning signs that contributed to it, and provides student and administrator workflows for analysis history and suspicious-offer reports.

The system is an aid to decision-making, not a fraud-detection authority. It does not verify an employer's legal identity or guarantee that an offer is genuine.

## 2. Objectives

1. Allow students to submit offer text or supported TXT/PDF files.
2. Detect configurable warning signs using a deterministic rule engine.
3. Display a 0–100 score, Low/Medium/High risk band, and explanations.
4. Provide secure student accounts and private analysis history.
5. Allow students to report suspicious companies or offers.
6. Allow administrators to manage rules and review reports.
7. Evaluate correctness, usability, reliability, performance, and security.

## 3. Stakeholders

- **Students:** submit offers, review risk indicators, manage their own history, and report suspicious offers.
- **Administrator / placement cell:** maintain detection rules, review submitted reports, and monitor aggregate activity.
- **Genuine employers:** indirectly benefit when students are encouraged to verify offers instead of relying on unverified claims.

## 4. Requirements

### 4.1 Functional requirements

| ID | Requirement | Implementation |
|---|---|---|
| FR1 | Register, log in, log out, and enforce student/admin roles | Flask-Login, hashed passwords, role guards |
| FR2 | Accept pasted offer text and TXT/PDF uploads | Student analysis form and in-memory parser |
| FR3 | Calculate a deterministic score and risk band | Configurable rule engine; score capped at 100 |
| FR4 | Explain detected warning signs | Stored rule-name, explanation, and points snapshots |
| FR5 | View and delete personal analysis history | Queries scoped to the signed-in student |
| FR6 | Submit suspicious-offer reports | Student report form |
| FR7 | Approve or reject reports | Admin review route and audit records |
| FR8 | Add, edit, enable, disable, and delete rules | Admin rule-management pages |
| FR9 | Show aggregate analysis statistics | Admin dashboard |
| FR10 | Protect sessions and state-changing forms | Flask-Login, strong session protection, CSRF |

### 4.2 Non-functional requirements

- **Performance:** the rule engine should process a 50,000-character offer within the three-second target on the test environment.
- **Security:** password hashing, role-based access, CSRF protection, secure session settings, server-side validation, and ownership checks.
- **Reliability:** reject empty, unsupported, oversized, corrupt, encrypted, and textless uploads with a clear message.
- **Usability:** responsive Bootstrap interface, clear risk labels, explanations, and navigation.
- **Privacy:** analysis history is restricted to its owner; offer text is not sent to an AI provider unless the student explicitly opts in.
- **Maintainability:** routes, models, parsing, scoring, and configuration are separated into modules; detection rules are stored in SQLite.

## 5. Design and implementation

### 5.1 Technology stack

Python 3.12, Flask and Flask-SQLAlchemy [1, 4], Flask-Login [2], Flask-WTF [3], Werkzeug [6], PyMuPDF [5], Bootstrap 5, JavaScript, and pytest [7].

### 5.2 Main workflow

1. A student registers or logs in.
2. The student pastes offer text or uploads a TXT/PDF file.
3. The server validates and extracts the text.
4. Active detection rules are evaluated. Each rule contributes at most once.
5. Points are added and capped at 100.
6. The application maps the score to a risk band and stores the result and flag snapshots.
7. The student reviews the score and explanations and may delete the saved analysis later.

### 5.3 Scoring rules

| Indicator | Points |
|---|---:|
| Upfront fees or deposits | 30 |
| Sensitive identity or financial information | 20 |
| Consumer email sender | 15 |
| Urgency or pressure tactics | 15 |
| Unverifiable company presence | 15 |
| Unrealistic employment promises | 15 |
| Suspicious formatting / language | 5 |

Risk bands: **0–30 Low**, **31–60 Medium**, and **61–100 High**. A single 30-point fee indicator is therefore Low under this configured threshold; multiple warning signs can raise the result to Medium or High. A low score is not a guarantee of legitimacy.

### 5.4 Security and privacy controls

Public registration always creates a student account. Administrator accounts are created by a seed script using local environment variables; no default admin password or API key is committed. Passwords are stored as hashes using Werkzeug security helpers [6]. CSRF protection applies to state-changing forms [3]. Student history reads and deletes are owner-scoped. Uploads are parsed in memory and are not stored in the public static directory.

The optional AI review is disabled by default, requires explicit consent for each submission, uses a bounded text excerpt, and requires HTTPS for remote providers. Its output is supplementary and cannot change the deterministic score.

### 5.5 Implementation screenshots

Insert actual screenshots captured from the running application:

- **Figure 1 – Login and student registration:** [Insert screenshot]
- **Figure 2 – Student analysis form:** [Insert screenshot]
- **Figure 3 – Analysis result showing score and explanations:** [Insert screenshot]
- **Figure 4 – Student history and scam report:** [Insert screenshot]
- **Figure 5 – Admin dashboard and detection-rule management:** [Insert screenshot]
- **Figure 6 – Admin report review:** [Insert screenshot]

## 6. Testing and results

Automated tests are run by GitHub Actions on Python 3.12 using pytest [7]. The suite includes rule scoring and thresholds, large-input performance, TXT/PDF parsing, invalid uploads, authentication, role restrictions, student data isolation, rule administration, report review, seeding, and optional AI safeguards.

**Verified final code CI:** 45 automated tests passed in 4.80 seconds on the GitHub Actions runner using Python 3.12. Python module compilation also passed. The run is recorded at https://github.com/Chirantan112/InternShield/actions/runs/45144802303. This is the CI suite duration, not the measured end-to-end response time on the demonstration laptop.

| Test ID | Test scenario | Expected result | Result |
|---|---|---|---|
| TC1 | Genuine offer with no configured warning signs | Score 0, Low | Automated test |
| TC2 | Offer asks for a registration fee | Fee flag and 30 points (Low under the defined band) | Automated test |
| TC3 | Offer asks for Aadhaar and OTP | Sensitive-information flag | Automated test |
| TC4 | Empty offer submission | Clear validation message; no crash | Automated test |
| TC5 | Unsupported file extension | Upload rejected | Automated test |
| TC6 | Incorrect password | Login rejected with generic message | Automated test |
| TC7 | Student opens admin page | HTTP 403 | Automated test |
| TC8 | Student attempts to view/delete another student's analysis | Not disclosed; deletion returns 404 | Automated test |
| TC9 | Scores of 30 and 31 | Low and Medium respectively | Automated test |
| TC10 | Administrator changes a rule's points | Updated points affect subsequent scoring | Automated test |
| TC11 | 50,000-character offer | Rule engine completes within three seconds on CI runner | Automated test |
| TC12 | Disabled detection rule | Rule is not applied | Automated test |

**Local demonstration measurements:**  
- Device / Python version: [Enter details]  
- Offer length: [Enter character count]  
- Measured end-to-end response time: [Enter measured time]  
- Screenshots captured: [List figures]

CI timings and local end-to-end response times are different measurements. Record the local result from the actual demonstration machine rather than copying the CI duration.

## 7. Limitations and future enhancements

- Rule matching is based on configured text indicators; it cannot establish whether an employer is legally registered or authenticate an email sender.
- Missing company information is detected only when the message contains configured phrases; absence of a website is not independently verified.
- PDF support extracts selectable text and does not perform OCR on scanned images.
- The optional AI review depends on the provider configured by the administrator and may return inaccurate suggestions.
- Future improvements could include verified company-data integrations, OCR, configurable audit exports, stronger abuse-rate controls, and deployment behind a production WSGI server with HTTPS.

## 8. Conclusion

InternShield implements a modular student-facing offer-screening workflow with explainable deterministic scoring, role-based access, private history, scam reporting, administrator rule management, and report moderation. Automated tests exercise the main service and workflow paths. The application is intended to help students recognize warning signs and independently verify offers; it does not label an organization as fraudulent solely from a score.

## References

1. Flask documentation – Application setup and configuration: https://flask.palletsprojects.com/
2. Flask-Login documentation – User session management: https://flask-login.readthedocs.io/
3. Flask-WTF documentation – CSRF protection: https://flask-wtf.readthedocs.io/
4. SQLAlchemy documentation – ORM and database operations: https://docs.sqlalchemy.org/
5. PyMuPDF documentation – PDF text extraction: https://pymupdf.readthedocs.io/
6. Werkzeug documentation – Security helpers and password hashing: https://werkzeug.palletsprojects.com/
7. pytest documentation – Automated testing: https://docs.pytest.org/
