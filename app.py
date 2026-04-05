import os
import json
import base64
from pathlib import Path

import anthropic
from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from dotenv import load_dotenv

_root = Path(__file__).resolve().parent
load_dotenv(_root / ".env")

app = Flask(__name__)
CORS(app)


def _comma_join_field(body, key):
    """Build a comma-separated line from str, list, or missing profile field."""
    val = body.get(key)
    if val is None or val == "":
        return None
    if isinstance(val, str):
        s = val.strip()
        return s or None
    if isinstance(val, (list, tuple)):
        parts = [str(x).strip() for x in val if str(x).strip()]
        return ", ".join(parts) if parts else None
    return str(val)

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-20250514"


def _parse_json_array(raw: str):
    """Parse a JSON array from model output; tolerate preamble or markdown fences."""
    s = raw.strip()
    for fence in ("```json", "```"):
        if s.startswith(fence):
            s = s[len(fence) :].strip()
    if s.endswith("```"):
        s = s[:-3].strip()
    try:
        out = json.loads(s)
        if isinstance(out, list):
            return out
    except json.JSONDecodeError:
        pass
    start = s.find("[")
    if start == -1:
        raise ValueError("No JSON array found in model response")
    decoder = json.JSONDecoder()
    value, _ = decoder.raw_decode(s[start:])
    if not isinstance(value, list):
        raise ValueError("Model response was not a JSON array")
    return value


def _json_error(message: str, status: int = 500):
    """Always valid JSON + correct Content-Type (avoids HTML fallback confusing the client)."""
    return Response(
        json.dumps({"error": message}),
        status=status,
        mimetype="application/json",
    )


def _api_path() -> str:
    """PATH_INFO is reliable inside error handlers; request.path can be wrong in edge cases."""
    return request.environ.get("PATH_INFO") or getattr(request, "path", "") or ""


@app.errorhandler(Exception)
def _api_json_errors(e):
    """Never return Flask's HTML error page for /api/* — the front end expects JSON."""
    path = _api_path()
    if not path.startswith("/api/"):
        raise e
    if isinstance(e, HTTPException):
        code = e.code if e.code is not None else 500
        return _json_error(e.description or str(e), code)
    app.logger.exception("API error: %s", path)
    return _json_error(str(e) or type(e).__name__, 500)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/parse-resume", methods=["POST"])
def parse_resume():
    """Accept a resume file, extract structured candidate data using Claude."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    filename = file.filename.lower()
    file_bytes = file.read()

    extraction_prompt = """You are a resume parser for a sales recruiting platform.
Extract structured data from this resume and return ONLY valid JSON with no preamble or markdown.
Use this exact schema:
{
  "name": "",
  "title": "",
  "yearsExperience": "",
  "location": "",
  "education": "",
  "industries": [],
  "skills": [],
  "achievements": ""
}
- "title": most recent job title
- "yearsExperience": estimate total years in sales/professional work as a number string
- "location": city/state or "Remote" if applicable
- "industries": array of industry verticals the candidate has worked in (e.g. ["SaaS", "FinTech"])
- "skills": array of sales skills, methodologies, tools (e.g. ["Enterprise sales", "MEDDIC", "Salesforce"])
- "achievements": 2-3 sentence summary of standout accomplishments, quota performance, deal sizes"""

    try:
        if filename.endswith(".pdf"):
            b64 = base64.standard_b64encode(file_bytes).decode("utf-8")
            message = client.messages.create(
                model=MODEL,
                max_tokens=1000,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": extraction_prompt},
                    ],
                }],
            )
        else:
            # DOCX / TXT — extract text and send as plain text
            try:
                text = file_bytes.decode("utf-8", errors="ignore")
            except Exception:
                text = file_bytes.decode("latin-1", errors="ignore")

            message = client.messages.create(
                model=MODEL,
                max_tokens=1000,
                messages=[{
                    "role": "user",
                    "content": f"{extraction_prompt}\n\nRESUME TEXT:\n{text}",
                }],
            )

        raw = "".join(b.text for b in message.content if hasattr(b, "text"))
        clean = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(clean)
        return jsonify({"success": True, "data": parsed})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/match-jobs", methods=["POST"])
def match_jobs():
    """Given a candidate profile JSON, return all strong-fit sales job matches."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "No profile data provided"}), 400

    industries_s = _comma_join_field(body, "industries")
    skills_s = _comma_join_field(body, "skills")

    profile_lines = [
        body.get("name") and f"Candidate: {body['name']}",
        body.get("title") and f"Current title: {body['title']}",
        body.get("yearsExperience") and f"Years of experience: {body['yearsExperience']}",
        body.get("location") and f"Target location: {body['location']}",
        body.get("targetComp") and f"Target OTE: {body['targetComp']}",
        body.get("education") and f"Education: {body['education']}",
        industries_s and f"Industry expertise: {industries_s}",
        skills_s and f"Key skills: {skills_s}",
        body.get("achievements") and f"Achievements: {body['achievements']}",
        body.get("preferredRole") and f"Preferred role type: {body['preferredRole']}",
        body.get("companyStage") and f"Company stage preference: {body['companyStage']}",
        body.get("workModel") and f"Work model preference: {body['workModel']}",
    ]
    profile_text = "\n".join(line for line in profile_lines if line)

    prompt = f"""You are an expert sales recruiter AI. Based on this candidate profile, list up to 12 distinct, realistic sales job opportunities that are strong matches (include every strong match you find, but cap at 12 roles). Use real company names where possible.

Each role MUST include "url": a full https link (job posting, company careers page, or a scoped LinkedIn/Indeed search URL). Use real, reachable URLs only.

Keep each "reason" to 1–2 sentences. Keep "tags" to 3–4 short items.

CANDIDATE PROFILE:
{profile_text}

Respond ONLY with a valid JSON array. No preamble, no markdown. Schema:
[{{"title":"","company":"","location":"","url":"","matchScore":0,"reason":"","tags":[]}}]"""

    message = client.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", MODEL),
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(b.text for b in message.content if hasattr(b, "text"))
    results = _parse_json_array(raw)
    if not isinstance(results, list):
        return jsonify({"error": "Model returned an unexpected format"}), 500
    payload = {"success": True, "results": results}
    json.dumps(payload)
    return jsonify(payload)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
