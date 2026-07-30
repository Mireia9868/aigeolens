"""
GEO MVP - Flask API Server
Serves the Japanese landing page and handles GEO diagnosis API requests.
Supports Stripe payment for premium reports.

Flow:
  /api/scan               - Free lightweight scan (Stage 1 only)
  /api/create-checkout    - Create Stripe Checkout Session for paid plans
  /api/verify-payment     - Verify Stripe payment and generate full report
  /api/analyze            - Full analysis (legacy: lead-capture based, kept for backward compat)
  /api/pricing            - Get pricing plans
  /api/webhook/stripe     - Stripe webhook handler
"""
import os
import sys
import json
import re
import hashlib
import time
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS

# Add backend dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    FLASK_PORT, DEBUG_MODE, DEMO_MODE, APP_URL,
    STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_CURRENCY,
    PRICING_PLANS,
)
from engine.analyzer import GEOAnalyzer

# === Stripe initialization ===
STRIPE_AVAILABLE = False
if STRIPE_SECRET_KEY:
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        STRIPE_AVAILABLE = True
    except ImportError:
        pass

app = Flask(__name__, static_folder=None)
CORS(app)

# Frontend directory (parent of backend/)
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

# Lead storage (file-based for MVP)
LEADS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads.json")

# Payment verification store (file-based for MVP)
PAYMENTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "payments.json")


def _save_lead(email: str, company: str, url: str, brand: str, plan: str = "free"):
    """Append lead to JSON file."""
    lead = {
        "email": email,
        "company": company,
        "url": url,
        "brand": brand,
        "plan": plan,
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


def _save_payment(session_id: str, email: str, company: str, url: str, brand: str, plan: str, amount: int):
    """Save verified payment record."""
    record = {
        "session_id": session_id,
        "email": email,
        "company": company,
        "url": url,
        "brand": brand,
        "plan": plan,
        "amount": amount,
        "verified": False,
        "timestamp": datetime.now().isoformat(),
    }
    payments = []
    if os.path.exists(PAYMENTS_FILE):
        try:
            with open(PAYMENTS_FILE, "r", encoding="utf-8") as f:
                payments = json.load(f)
        except (json.JSONDecodeError, IOError):
            payments = []
    payments.append(record)
    with open(PAYMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(payments, f, ensure_ascii=False, indent=2)


def _get_payment(session_id: str) -> dict:
    """Get payment record by session_id."""
    if not os.path.exists(PAYMENTS_FILE):
        return None
    try:
        with open(PAYMENTS_FILE, "r", encoding="utf-8") as f:
            payments = json.load(f)
        for p in payments:
            if p.get("session_id") == session_id:
                return p
    except (json.JSONDecodeError, IOError):
        pass
    return None


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
    """Serve static assets (css, js, images, robots.txt, sitemap.xml, llms.txt)."""
    return send_from_directory(FRONTEND_DIR, filename)


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "mode": "demo" if DEMO_MODE else "live",
        "ai_provider": "deepseek" if not DEMO_MODE else "none",
        "stripe_enabled": STRIPE_AVAILABLE,
    })


@app.route("/api/pricing", methods=["GET"])
def pricing():
    """Return pricing plans."""
    return jsonify({
        "plans": PRICING_PLANS,
        "currency": "JPY",
        "stripe_enabled": STRIPE_AVAILABLE,
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


@app.route("/api/create-checkout", methods=["POST"])
def create_checkout():
    """
    Create a Stripe Checkout Session for paid plans.
    Expects: {"plan": "audit|pro|business", "url": "...", "brand_name": "...", "email": "...", "company_name": "..."}
    Returns: {"checkout_url": "https://checkout.stripe.com/..."}
    """
    if not STRIPE_AVAILABLE:
        return jsonify({
            "error": "payment_not_configured",
            "message": "Stripe payment is not configured. Please contact support."
        }), 503

    data = request.get_json() or {}
    plan_key = data.get("plan", "").strip()
    url = data.get("url", "").strip()
    brand_name = data.get("brand_name", "").strip()
    email = data.get("email", "").strip()
    company_name = data.get("company_name", "").strip()

    if plan_key not in ("audit", "pro", "business"):
        return jsonify({"error": "invalid_plan", "message": "Plan must be audit, pro, or business"}), 400

    if not url or "." not in url:
        return jsonify({"error": "valid_url_required"}), 400

    if not email or not _is_valid_email(email):
        return jsonify({"error": "valid_email_required"}), 400

    if not company_name:
        return jsonify({"error": "company_name_required"}), 400

    plan = PRICING_PLANS[plan_key]

    try:
        # Create Stripe Checkout Session
        # For JPY (zero-decimal currency), amount is in whole yen
        session_params = {
            "payment_method_types": ["card"],
            "line_items": [{
                "price_data": {
                    "currency": STRIPE_CURRENCY,
                    "product_data": {
                        "name": f"AI GeoLens - {plan['name']}",
                        "description": plan["description"],
                    },
                    "unit_amount": plan["price"],  # JPY is zero-decimal
                },
                "quantity": 1,
            }],
            "mode": "payment" if plan_key == "audit" else "subscription",
            "success_url": f"{APP_URL}/payment-success.html?session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{APP_URL}/payment-cancel.html",
            "customer_email": email,
            "metadata": {
                "url": url[:500],
                "brand_name": brand_name[:200],
                "email": email,
                "company_name": company_name[:200],
                "plan": plan_key,
            },
            "allow_promotion_codes": True,
        }

        session = stripe.checkout.Session.create(**session_params)

        # Save lead
        _save_lead(email, company_name, url, brand_name, plan_key)

        return jsonify({
            "checkout_url": session.url,
            "session_id": session.id,
        })

    except stripe.error.StripeError as e:
        return jsonify({
            "error": "stripe_error",
            "message": str(e),
        }), 500
    except Exception as e:
        return jsonify({
            "error": "checkout_failed",
            "message": str(e),
        }), 500


@app.route("/api/verify-payment", methods=["POST"])
def verify_payment():
    """
    Verify Stripe payment and generate full GEO report.
    Expects: {"session_id": "cs_test_..."}
    Returns: Full GEO diagnostic report JSON.
    """
    if not STRIPE_AVAILABLE:
        return jsonify({"error": "payment_not_configured"}), 503

    data = request.get_json() or {}
    session_id = data.get("session_id", "").strip()

    if not session_id:
        return jsonify({"error": "session_id_required"}), 400

    try:
        # Retrieve the session from Stripe
        session = stripe.checkout.Session.retrieve(session_id)

        if session.payment_status != "paid":
            return jsonify({
                "error": "payment_not_completed",
                "message": "Payment has not been completed yet."
            }), 402

        # Extract metadata
        metadata = session.metadata or {}
        url = metadata.get("url", "")
        brand_name = metadata.get("brand_name", "")
        email = metadata.get("email", "")
        company_name = metadata.get("company_name", "")
        plan = metadata.get("plan", "audit")

        # Save payment record
        _save_payment(session_id, email, company_name, url, brand_name, plan, session.amount_total)

        # Generate full report
        analyzer = GEOAnalyzer(url, brand_name)
        result = analyzer.run_full_analysis()
        result["lead"] = {"email": email, "company": company_name}
        result["payment"] = {
            "session_id": session_id,
            "plan": plan,
            "amount": session.amount_total,
            "currency": session.currency,
        }

        return jsonify(result)

    except stripe.error.StripeError as e:
        return jsonify({"error": "stripe_error", "message": str(e)}), 500
    except Exception as e:
        return jsonify({
            "error": "analysis_failed",
            "message": str(e),
        }), 500


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """
    Full 4-stage GEO analysis (legacy: lead-capture based, kept for backward compat).
    Accepts: {"url": "...", "brand_name": "...", "email": "...", "company_name": "..."}
    """
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    brand_name = data.get("brand_name", "").strip()
    email = data.get("email", "").strip()
    company_name = data.get("company_name", "").strip()

    if not url:
        return jsonify({"error": "URL is required"}), 400

    if not email or not _is_valid_email(email):
        return jsonify({"error": "valid_email_required", "message": "A valid email is required"}), 400

    if not company_name:
        return jsonify({"error": "company_name_required", "message": "Company name is required"}), 400

    if "." not in url:
        return jsonify({"error": "Invalid URL format"}), 400

    try:
        _save_lead(email, company_name, url, brand_name, "free_lead")
    except Exception:
        pass

    try:
        analyzer = GEOAnalyzer(url, brand_name)
        result = analyzer.run_full_analysis()
        result["lead"] = {"email": email, "company": company_name}
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": "analysis_failed", "message": str(e)}), 500


@app.route("/api/webhook/stripe", methods=["POST"])
def stripe_webhook():
    """Handle Stripe webhook events."""
    if not STRIPE_AVAILABLE or not STRIPE_WEBHOOK_SECRET:
        return jsonify({"error": "webhook_not_configured"}), 503

    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return jsonify({"error": "invalid_payload"}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({"error": "invalid_signature"}), 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = session.get("metadata", {})
        _save_payment(
            session["id"],
            metadata.get("email", ""),
            metadata.get("company_name", ""),
            metadata.get("url", ""),
            metadata.get("brand_name", ""),
            metadata.get("plan", "audit"),
            session.get("amount_total", 0),
        )

    return jsonify({"received": True})


@app.route("/api/demo", methods=["GET"])
def demo_report():
    """Return a sample report for preview without crawling."""
    sample_url = "https://example.com"
    analyzer = GEOAnalyzer(sample_url, "DemoBrand")
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
    stripe_str = "Stripe: ENABLED" if STRIPE_AVAILABLE else "Stripe: NOT CONFIGURED"
    print(f"\n{'='*50}")
    print(f"  GEO MVP Diagnostic Engine")
    print(f"  Mode: {mode_str}")
    print(f"  Payment: {stripe_str}")
    print(f"  Port: {FLASK_PORT}")
    print(f"  Frontend: {FRONTEND_DIR}")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=DEBUG_MODE)
