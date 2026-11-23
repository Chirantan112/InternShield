# InternShield

**Internship and Job Offer Risk Screening for Students**

InternShield is a student-focused Flask web application that checks internship and job-offer messages for common warning signs. Students can paste offer text or upload TXT/PDF documents, review an explainable risk score, keep a private analysis history, and report suspicious offers. Administrators can manage detection rules, review reports, and monitor aggregate activity.

> **Important:** A risk score is a preliminary indicator, not proof of fraud. A low score does not guarantee legitimacy, and a free email address alone is not proof of a scam. Always verify the employer independently.

## Features

### Student
- Student registration, login, and logout; passwords are hashed.
- Analyze pasted offer text or upload text-based TXT/PDF files (5 MB maximum; 50,000 characters maximum by default).
- See Low / Medium / High risk, a capped 0–100 score, and explanations for each matched rule.
- View and delete only your own analysis history.
- Submit suspicious company/offer reports and see their review status.
- Optional external AI context review only after explicit consent. It is supplementary and never changes the deterministic score.

### Administrator
- Dashboard with total analyses, Low/Medium/High counts, common flags, and pending reports.
- Add, edit, enable, disable, and delete keyword detection rules and change their point values.
- Review student reports, approve/reject them, and keep an audit history of decisions.

### Detection rules and risk bands
Default rules are seeded by `scripts/seed_data.py`. The initial weights are:

| Warning sign | Points |
|---|---:|
| Upfront fees or deposits | 30 |
| Sensitive identity / financial information | 20 |
| Consumer email sender | 15 |
| Urgency or pressure tactics | 15 |
| Unverifiable company presence | 15 |
| Unrealistic employment promises | 15 |
| Suspicious formatting / language | 5 |

Each rule contributes at most once per analysis; the total is capped at 100.

| Score | Risk band |
|---:|---|
| 0–30 | Low |
| 31–60 | Medium |
| 61–100 | High |

The score is intentionally explainable and configurable. The current implementation uses literal keyword/phrase matching for administrator-managed rules. A separate contextual review layer highlights generic combinations (such as training alongside an internship, discounts/referrals, forms, payment wording, placement-assistance claims, and affiliation claims) and suggests verification questions. These prompts do not add score points and do not establish fraud. The system does not verify company registrations, sender authenticity, or live website reputation. Mentions of well-known companies, universities, or certifications are not proof that an affiliation is genuine; applicants must verify those claims independently.

## Technology

- Python 3.12+
- Flask, Flask-SQLAlchemy, SQLite
- Flask-Login, Flask-WTF / CSRF, Werkzeug password hashing
- PyMuPDF for PDF text extraction
- Bootstrap 5, HTML, CSS, JavaScript
- pytest and GitHub Actions

The required analysis workflow works locally without an API key. The optional AI review uses an OpenAI-compatible chat-completions endpoint and is disabled by default.

## Local setup (Windows PowerShell)

Use Python 3.12 or 3.13 for dependency compatibility.

1. Clone the repository and enter its folder:

   ```powershell
   git clone https://github.com/Chirantan112/InternShield.git
   cd InternShield
   ```

2. Create and activate a virtual environment:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies:

   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. Create your local environment file and set a secret:

   ```powershell
   Copy-Item .env.example .env
   ```

   Edit `.env` and set a long, random `SECRET_KEY`. Set the bootstrap administrator values:
   - `ADMIN_EMAIL`
   - `ADMIN_PASSWORD` (at least 10 characters)
   - `ADMIN_NAME` (optional)

   These credentials are read from your local environment and are never stored in the source code. Do not commit `.env`.

5. Create the database and default admin/rules:

   ```powershell
   python -m scripts.seed_data
   ```

   The seeding script is idempotent: it creates missing default rules and the configured admin, and does not silently elevate an existing student account. When a later release adds default keyword phrases, rerunning this command appends missing defaults to existing keyword rules while preserving administrator-added phrases and existing account records. It does not reset the database or overwrite the admin password.

6. Start the development server:

   ```powershell
   python run.py
   ```

   Open `http://127.0.0.1:5000`. Create a student account from the registration page; administrator accounts are created only by the secure seed process.

## Updating an existing installation

After pulling an update that changes the default detection phrases, run:

```powershell
python -m scripts.seed_data
```

Use the same local `.env` configuration. The seed process updates missing default keyword phrases in existing default rules, preserves other phrases already configured in those rules, and leaves user records and analysis history intact. Review administrator-managed rules in the dashboard after updating.

## Optional AI review configuration

AI review is disabled by default. To enable it, configure these values in your local `.env` file:

- `AI_ENABLED=true`
- `AI_PROVIDER=openai-compatible`
- `AI_API_KEY` — your provider key
- `AI_BASE_URL` — provider API base URL (for example, an OpenAI-compatible `/v1` base)
- `AI_MODEL` — model identifier supported by that provider

Restart the server after changing environment values. Students must separately tick the consent checkbox for each analysis before offer text is sent to the configured external provider. The request is bounded to 10,000 characters. Never commit API keys. AI output is untrusted supplementary advice and cannot override the score or risk band.

## Tests

Run the automated test suite from the repository root:

```powershell
python -m pytest -q
```

The GitHub Actions workflow also compiles Python modules and runs pytest on pushes and pull requests to `main`.

The suite covers rule scoring and thresholds, default seeded phrase regressions, TXT/PDF extraction and invalid files, authentication/password hashing, role restrictions, student data isolation, analysis history, rule management, and report moderation. Performance should be measured on the demonstration machine and recorded in the assignment report; do not treat a single CI run as a universal performance guarantee.

## Project structure

```text
InternShield/
├── config.py
├── run.py
├── requirements.txt
├── scripts/
│   └── seed_data.py
├── internshield/
│   ├── __init__.py
│   ├── extensions.py
│   ├── models.py
│   ├── routes/
│   │   ├── auth.py
│   │   ├── student.py
│   │   └── admin.py
│   ├── services/
│   │   ├── rule_engine.py
│   │   ├── file_parser.py
│   │   └── ai_review.py
│   ├── templates/
│   ├── static/
│   └── utils/
├── tests/
└── .github/workflows/tests.yml
```

## Security and limitations

- Public registration always creates a student; admin creation is environment-seeded.
- Passwords are stored as Werkzeug password hashes, not plaintext.
- CSRF protection is enabled for state-changing forms.
- Student history queries and deletion are scoped to the authenticated user.
- Upload parsing is in-memory, extension-checked, size-limited, and rejects unsupported/corrupt documents.
- Uploaded files are not saved to the public static folder.
- The optional AI provider receives offer text only after explicit per-analysis consent.
- Configure HTTPS and secure cookies for production. The built-in Flask server is for local development only.
- This academic prototype is not a substitute for legal, financial, or employment verification.

## Assignment documentation

The final submission report should include the title, problem statement, objectives, stakeholders, functional and non-functional requirements, implementation screenshots, source-code discussion, test cases with actual results, and conclusion. Keep the report within the 10-page limit and cite external sources in the text. Capture screenshots and record measured timings from the actual local run; do not invent demonstration evidence or test results.
