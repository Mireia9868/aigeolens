"""
GEO MVP - Flask API Server
Serves the Japanese landing page and handles GEO diagnosis API requests.

Two-step funnel:
  /api/scan   - Free lightweight scan (Stage 1 only, no DeepSeek API call)
  /api/analyze - Full 4-stage analysis (requires email + company_name for lead capture)
"""
import os
import sys
import json
import re
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# Add backend dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import FLASK_PORT, DEBUG_MODE, DEMO_MODE
from engine.analyzer import GEOAnalyzer

app = Flask(__name__, static_folder=None)
CORS(app)

# Frontend directory (parent of backend/)
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

# Lead storage (file-based for MVP)
LEADS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads.json")


def _save_lead(email: str, company: str, url: str, brand: str):
    """Append lead to JSON file."""
    lead = {
        "email": email,
        "company": company,
        "url": url,
        "brand": brand,
        "timestamp": datetime.now().isoformat(),
    }
    leads = []
    if os.path.exists(LEADS_FILE):
        try:
            with open(LEADS_FILE, "r", encoding="utf-8") as f:
                leads = json.load(f)
        except (json.JSONDecodeError, IOError):
            leads = []
    leads.append(lead)
    with open(LEADS_FILE, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=2)


def _is_valid_email(email: str) -> bool:
    """Basic email validation."""
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


# ==================== Routes ====================

@app.route("/")
def index():
    """Serve the Japanese landing page."""
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    """Serve static assets (css, js, images)."""
    return send_from_directory(FRONTEND_DIR, filename)


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "mode": "demo" if DEMO_MODE else "live",
        "ai_provider": "deepseek" if not DEMO_MODE else "none",
    })


@app.route("/api/scan", methods=["POST"])
def scan():
    """
    Free lightweight scan - Stage 1 only (no DeepSeek API call).
    Returns: GEO score, 3 key issues, crawl summary.
    Cost: ~$0.02 (crawler only, no AI)
    """
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    brand_name = data.get("brand_name", "").strip()

    if not url:
        return jsonify({"error": "URL is required"}), 400

    if "." not in url:
        return jsonify({"error": "Invalid URL format"}), 400

    try:
        analyzer = GEOAnalyzer(url, brand_name)
        scan_result = analyzer.run_scan_only()

        # Store scan data in a temp token for the analyze step
        scan_token = analyzer.analysis_id

        return jsonify({
            "scan_token": scan_token,
            "url": url,
            "brand": analyzer.brand_name,
            **scan_result,
        })
    except Exception as e:
        return jsonify({
            "error": "scan_failed",
            "message": str(e),
            "url": url,
        }), 500


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """
    Full 4-stage GEO analysis (requires lead capture: email + company_name).
    Accepts: {"url": "...", "brand_name": "...", "email": "...", "company_name": "..."}
    Returns: Full GEO diagnostic report JSON.
    Cost: ~$0.17-0.50 (DeepSeek API calls)
    """
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    brand_name = data.get("brand_name", "").strip()
    email = data.get("email", "").strip()
    company_name = data.get("company_name", "").strip()

    if not url:
        return jsonify({"error": "URL is required"}), 400

    if not email or not _is_valid_email(email):
        return jsonify({"error": "valid_email_required", "message": "A valid email is required to unlock the full report"}), 400

    if not company_name:
        return jsonify({"error": "company_name_required", "message": "Company name is required"}), 400

    # Basic URL validation
    if "." not in url:
        return jsonify({"error": "Invalid URL format"}), 400

    # Save lead
    try:
        _save_lead(email, company_name, url, brand_name)
    except Exception:
        pass  # Don't block analysis if lead save fails

    try:
        analyzer = GEOAnalyzer(url, brand_name)
        result = analyzer.run_full_analysis()
        result["lead"] = {"email": email, "company": company_name}
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "error": "analysis_failed",
            "message": str(e),
            "url": url,
        }), 500


@app.route("/api/demo", methods=["GET"])
def demo_report():
    """Return a sample report for preview without crawling."""
    sample_url = "https://example.com"
    analyzer = GEOAnalyzer(sample_url, "DemoBrand")
    # Use demo data without actually crawling
    result = {
        "analysis_id": "demo-" + analyzer.analysis_id,
        "url": sample_url,
        "brand": "DemoBrand",
        "timestamp": "2026-01-01T00:00:00",
        "demo": True,
        "stages": {
            "stage1_infrastructure": analyzer._demo_stage1() if hasattr(analyzer, '_demo_stage1') else {"score": 55},
            "stage2_ai_visibility": analyzer._demo_stage2(),
            "stage3_competitive": analyzer._demo_stage3(),
        }
    }
    # Fix stage1 demo
    result["stages"]["stage1_infrastructure"] = {
        "score": 55,
        "passed_checks": 8,
        "total_checks": 15,
        "checks": [
            {"code": "title_tag", "name": "Title Tag", "passed": True, "message": "Page has a descriptive title tag", "detail": "DemoBrand - AI Solutions"},
            {"code": "meta_description", "name": "Meta Description", "passed": False, "message": "Missing meta description", "detail": ""},
            {"code": "structured_data", "name": "Structured Data (Schema.org)", "passed": False, "message": "No structured data found - critical for AI understanding", "detail": "[]"},
            {"code": "open_graph", "name": "Open Graph Tags", "passed": True, "message": "3 OG tags found", "detail": "{}"},
            {"code": "heading_structure", "name": "Heading Structure (H1-H6)", "passed": True, "message": "1 H1 tag found", "detail": "[\"DemoBrand\"]"},
            {"code": "image_alt", "name": "Image Alt Text", "passed": False, "message": "5/12 images have alt text (42%)", "detail": "5/12"},
            {"code": "ssl_https", "name": "SSL/HTTPS", "passed": True, "message": "Site uses HTTPS", "detail": "True"},
            {"code": "language_decl", "name": "Language Declaration", "passed": True, "message": "Language declared: en", "detail": "en"},
        ],
        "crawl_summary": {
            "title": "DemoBrand - AI Solutions",
            "description": "",
            "word_count": 850,
            "language": "en",
            "page_size_kb": 156.3,
            "has_ssl": True,
            "has_schema": False,
            "domain": "example.com",
        }
    }
    result["stages"]["stage4_scoring"] = analyzer._run_stage4(result["stages"])
    result["overall_score"] = result["stages"]["stage4_scoring"]["aivo_score"]["total_score"]
    result["score_level"] = result["stages"]["stage4_scoring"]["aivo_score"]["level"]
    return jsonify(result)


# ==================== Main ====================

if __name__ == "__main__":
    mode_str = "DEMO MODE (no API key)" if DEMO_MODE else f"LIVE MODE (DeepSeek)"
    print(f"\n{'='*50}")
    print(f"  GEO MVP Diagnostic Engine")
    print(f"  Mode: {mode_str}")
    print(f"  Port: {FLASK_PORT}")
    print(f"  Frontend: {FRONTEND_DIR}")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=DEBUG_MODE)
