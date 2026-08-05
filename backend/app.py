"""
GEO MVP - Flask API Server
Serves the Japanese landing page and handles GEO diagnosis API requests.
Supports PayPal payment + bank transfer for premium reports.

Flow:
  /api/scan               - Free lightweight scan (Stage 1 only, rate-limited)
  /api/create-paypal-order - Create PayPal order for paid plans
  /api/verify-payment     - Verify PayPal payment and generate full report
  /api/analyze            - Lead capture only (Stage 1 summary, NO full report)
  /api/bank-transfer      - Create bank transfer order (manual verification)
  /api/pricing            - Get pricing plans
"""
import os
import sys
import json
import re
import uuid
import base64
import threading
import requests as http_requests
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Add backend dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    FLASK_PORT, DEBUG_MODE, DEMO_MODE, APP_URL, DATA_DIR,
    PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, PAYPAL_MODE,
    PAYPAL_BASE_URL, PAYPAL_CURRENCY,
    BANK_TRANSFER_ENABLED, BANK_NAME, BANK_BRANCH,
    BANK_ACCOUNT_TYPE, BANK_ACCOUNT_NUMBER, BANK_ACCOUNT_HOLDER,
    PRICING_PLANS,
)
from engine.analyzer import GEOAnalyzer

# === PayPal availability check ===
PAYPAL_AVAILABLE = bool(PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET)

app = Flask(__name__, static_folder=None)
CORS(app)

# === Rate Limiter ===
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# Frontend directory (parent of backend/)
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

# Lead storage (file-based, in DATA_DIR for Railway Volume persistence)
LEADS_FILE = os.path.join(DATA_DIR, "leads.json")

# Order storage (file-based for MVP) — maps PayPal order_id to our metadata
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")

# Payment records
PAYMENTS_FILE = os.path.join(DATA_DIR, "payments.json")

# File write lock (prevent race conditions)
_file_lock = threading.Lock()


# ==================== PayPal API Helpers ====================

def _paypal_get_access_token() -> str:
    """Get PayPal API access token using client credentials."""
    url = f"{PAYPAL_BASE_URL}/v1/oauth2/token"
    auth_str = f"{PAYPAL_CLIENT_ID}:{PAYPAL_CLIENT_SECRET}"
    auth_b64 = base64.b64encode(auth_str.encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = "grant_type=client_credentials"
    resp = http_requests.post(url, headers=headers, data=data, timeout=30)
    if not resp.ok:
        error_detail = resp.text[:500]
        raise http_requests.HTTPError(
            f"{resp.status_code} PayPal Token Error: {error_detail}",
            response=resp
        )
    return resp.json()["access_token"]


def _paypal_create_order(amount: int, description: str, return_url: str,
                         cancel_url: str, custom_ref: str) -> dict:
    """Create a PayPal order. Returns the full order JSON including approval links."""
    token = _paypal_get_access_token()
    url = f"{PAYPAL_BASE_URL}/v2/checkout/orders"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {
                "currency_code": PAYPAL_CURRENCY,
                "value": str(amount),
            },
            "description": description[:127],
            "custom_id": custom_ref,
        }],
        "application_context": {
            "return_url": return_url,
            "cancel_url": cancel_url,
            "user_action": "PAY_NOW",
            "shipping_preference": "NO_SHIPPING",
        }
    }
    resp = http_requests.post(url, headers=headers, json=body, timeout=30)
    if not resp.ok:
        error_detail = resp.text[:500]  # truncate for safety
        raise http_requests.HTTPError(
            f"{resp.status_code} PayPal Error: {error_detail}",
            response=resp
        )
    return resp.json()


def _paypal_capture_order(order_id: str) -> dict:
    """Capture payment for a PayPal order. Returns the captured order JSON."""
    token = _paypal_get_access_token()
    url = f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = http_requests.post(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _paypal_get_order(order_id: str) -> dict:
    """Get PayPal order details (without capturing)."""
    token = _paypal_get_access_token()
    url = f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}"
    headers = {"Authorization": f"Bearer {token}"}
    resp = http_requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ==================== Storage Helpers ====================

def _save_lead(email: str, company: str, url: str, brand: str, plan: str = "free"):
    """Append lead to JSON file (thread-safe)."""
    lead = {
        "email": email,
        "company": company,
        "url": url,
        "brand": brand,
        "plan": plan,
        "timestamp": datetime.now().isoformat(),
    }
    with _file_lock:
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


def _save_order(order_ref: str, paypal_order_id: str, email: str,
                company: str, url: str, brand: str, plan: str, amount: int,
                method: str = "paypal"):
    """Save order metadata for later verification (thread-safe)."""
    record = {
        "order_ref": order_ref,
        "paypal_order_id": paypal_order_id,
        "email": email,
        "company": company,
        "url": url,
        "brand": brand,
        "plan": plan,
        "amount": amount,
        "method": method,
        "status": "created",
        "timestamp": datetime.now().isoformat(),
    }
    with _file_lock:
        orders = []
        if os.path.exists(ORDERS_FILE):
            try:
                with open(ORDERS_FILE, "r", encoding="utf-8") as f:
                    orders = json.load(f)
            except (json.JSONDecodeError, IOError):
                orders = []
        orders.append(record)
        with open(ORDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)


def _get_order_by_ref(order_ref: str) -> dict:
    """Get order metadata by reference ID."""
    if not os.path.exists(ORDERS_FILE):
        return None
    try:
        with open(ORDERS_FILE, "r", encoding="utf-8") as f:
            orders = json.load(f)
        for o in orders:
            if o.get("order_ref") == order_ref:
                return o
    except (json.JSONDecodeError, IOError):
        pass
    return None


def _update_order_status(order_ref: str, status: str):
    """Update order status."""
    if not os.path.exists(ORDERS_FILE):
        return
    try:
        with open(ORDERS_FILE, "r", encoding="utf-8") as f:
            orders = json.load(f)
        for o in orders:
            if o.get("order_ref") == order_ref:
                o["status"] = status
                o["updated_at"] = datetime.now().isoformat()
        with open(ORDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, IOError):
        pass


def _save_payment(order_id: str, email: str, company: str, url: str,
                  brand: str, plan: str, amount: int):
    """Save verified payment record (thread-safe)."""
    record = {
        "order_id": order_id,
        "email": email,
        "company": company,
        "url": url,
        "brand": brand,
        "plan": plan,
        "amount": amount,
        "currency": "JPY",
        "verified": True,
        "timestamp": datetime.now().isoformat(),
    }
    with _file_lock:
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


def _is_valid_email(email: str) -> bool:
    """Email validation: format check + disposable email domain block."""
    if not bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email)):
        return False
    # Block common disposable email providers
    domain = email.split("@")[-1].lower()
    DISPOSABLE_DOMAINS = {
        "tempmail.com", "throwaway.email", "mailinator.com", "guerrillamail.com",
        "10minutemail.com", "temp-mail.org", "sharklasers.com", "getnada.com",
        "trashmail.com", "yopmail.com", "dispostable.com", "fakeinbox.com",
    }
    if domain in DISPOSABLE_DOMAINS:
        return False
    return True


# ==================== Security Headers ====================

@app.after_request
def set_security_headers(response):
    """Add security headers to all responses."""
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # CSP: allow inline styles/scripts (needed for current frontend), Google Fonts
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "frame-ancestors 'self';"
    )
    return response


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
        "paypal_enabled": PAYPAL_AVAILABLE,
        "paypal_mode": PAYPAL_MODE,
        "bank_transfer_enabled": BANK_TRANSFER_ENABLED,
        "bank_name": BANK_NAME if BANK_TRANSFER_ENABLED else None,
    })


@app.route("/api/pricing", methods=["GET"])
def pricing():
    """Return pricing plans."""
    return jsonify({
        "plans": PRICING_PLANS,
        "currency": "JPY",
        "paypal_enabled": PAYPAL_AVAILABLE,
    })


@app.route("/api/scan", methods=["POST"])
@limiter.limit("5 per minute")
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


@app.route("/api/create-paypal-order", methods=["POST"])
@limiter.limit("3 per hour")
def create_paypal_order():
    """
    Create a PayPal order for paid plans.
    Expects: {"plan": "audit|pro|business", "url": "...", "brand_name": "...", "email": "...", "company_name": "..."}
    Returns: {"approval_url": "https://www.paypal.com/...", "order_id": "..."}
    """
    if not PAYPAL_AVAILABLE:
        return jsonify({
            "error": "payment_not_configured",
            "message": "PayPal payment is not configured. Please contact support."
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
        # Generate unique order reference for our internal tracking
        order_ref = str(uuid.uuid4())[:8]

        # Build PayPal return/cancel URLs
        return_url = f"{APP_URL}/payment-success.html?order_ref={order_ref}"
        cancel_url = f"{APP_URL}/payment-cancel.html"

        # Create PayPal order
        description = f"AI GeoLens - {plan['name']}"
        paypal_order = _paypal_create_order(
            amount=plan["price"],
            description=description,
            return_url=return_url,
            cancel_url=cancel_url,
            custom_ref=order_ref,
        )

        paypal_order_id = paypal_order["id"]

        # Find the approval URL
        approval_url = None
        for link in paypal_order.get("links", []):
            if link.get("rel") == "approve":
                approval_url = link["href"]
                break

        if not approval_url:
            return jsonify({
                "error": "paypal_no_approval_url",
                "message": "PayPal did not return an approval URL."
            }), 500

        # Save order metadata locally
        _save_order(order_ref, paypal_order_id, email, company_name,
                    url, brand_name, plan_key, plan["price"])

        # Save lead
        _save_lead(email, company_name, url, brand_name, plan_key)

        return jsonify({
            "approval_url": approval_url,
            "order_id": paypal_order_id,
            "order_ref": order_ref,
        })

    except http_requests.RequestException as e:
        return jsonify({
            "error": "paypal_api_error",
            "message": str(e),
        }), 500
    except Exception as e:
        return jsonify({
            "error": "order_creation_failed",
            "message": str(e),
        }), 500


@app.route("/api/verify-payment", methods=["POST"])
def verify_payment():
    """
    Verify PayPal payment and generate full GEO report.
    Expects: {"order_ref": "abc12345"} or {"order_id": "PAYPAL_ORDER_ID"}
    Returns: Full GEO diagnostic report JSON.
    """
    if not PAYPAL_AVAILABLE:
        return jsonify({"error": "payment_not_configured"}), 503

    data = request.get_json() or {}
    order_ref = data.get("order_ref", "").strip()
    order_id = data.get("order_id", "").strip()

    # Look up order by ref or PayPal order ID
    order_meta = None
    if order_ref:
        order_meta = _get_order_by_ref(order_ref)
    elif order_id:
        # Try to find by PayPal order ID
        if os.path.exists(ORDERS_FILE):
            try:
                with open(ORDERS_FILE, "r", encoding="utf-8") as f:
                    orders = json.load(f)
                for o in orders:
                    if o.get("paypal_order_id") == order_id:
                        order_meta = o
                        break
            except (json.JSONDecodeError, IOError):
                pass

    if not order_meta:
        return jsonify({"error": "order_not_found",
                        "message": "Order reference not found."}), 404

    try:
        # Capture the payment via PayPal API
        captured = _paypal_capture_order(order_meta["paypal_order_id"])

        # Check capture status
        capture_status = captured.get("status", "")
        if capture_status not in ("COMPLETED",):
            return jsonify({
                "error": "payment_not_completed",
                "message": f"Payment status is {capture_status}. Payment may still be processing."
            }), 402

        # Extract payment details
        purchase_units = captured.get("purchase_units", [])
        capture_amount = 0
        if purchase_units:
            captures = purchase_units[0].get("payments", {}).get("captures", [])
            if captures:
                capture_amount = int(float(captures[0].get("amount", {}).get("value", 0)))

        # Update order status
        _update_order_status(order_meta["order_ref"], "paid")

        # Save payment record
        _save_payment(
            order_meta["paypal_order_id"],
            order_meta["email"],
            order_meta["company"],
            order_meta["url"],
            order_meta["brand"],
            order_meta["plan"],
            capture_amount or order_meta["amount"],
        )

        # Generate full report
        analyzer = GEOAnalyzer(order_meta["url"], order_meta["brand"])
        result = analyzer.run_full_analysis()
        result["lead"] = {
            "email": order_meta["email"],
            "company": order_meta["company"],
        }
        result["payment"] = {
            "order_id": order_meta["paypal_order_id"],
            "plan": order_meta["plan"],
            "amount": capture_amount or order_meta["amount"],
            "currency": "JPY",
            "method": "paypal",
        }

        return jsonify(result)

    except http_requests.RequestException as e:
        return jsonify({
            "error": "paypal_capture_error",
            "message": str(e),
        }), 500
    except Exception as e:
        return jsonify({
            "error": "analysis_failed",
            "message": str(e),
        }), 500


@app.route("/api/analyze", methods=["POST"])
@limiter.limit("2 per hour")
def analyze():
    """
    Lead capture endpoint — saves lead and returns Stage 1 preview ONLY.
    Full 4-stage report requires payment verification via /api/verify-payment.
    This endpoint does NOT generate or return the paid product.
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

    # Save lead for marketing follow-up
    try:
        _save_lead(email, company_name, url, brand_name, "lead_capture")
    except Exception:
        pass

    # Return only a Stage 1 scan (lightweight, no DeepSeek API cost)
    try:
        analyzer = GEOAnalyzer(url, brand_name)
        scan_result = analyzer.run_scan_only()
        return jsonify({
            "status": "lead_captured",
            "message": "リードを受け付けました。完全版レポートは決済後にご利用いただけます。",
            "scan_preview": scan_result,
            "url": url,
            "brand": analyzer.brand_name,
            "upgrade_required": True,
            "pricing_url": f"{APP_URL}/#pricing",
        })
    except Exception as e:
        # Even if scan fails, the lead is saved — return a friendly message
        return jsonify({
            "status": "lead_captured",
            "message": "リードを受け付けました。完全版レポートは決済後にご利用いただけます。",
            "scan_error": str(e),
            "upgrade_required": True,
            "pricing_url": f"{APP_URL}/#pricing",
        })


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


# ==================== Bank Transfer (銀行振込) ====================

@app.route("/api/bank-transfer-order", methods=["POST"])
@limiter.limit("3 per hour")
def create_bank_transfer_order():
    """
    Create a bank transfer order.
    Returns: bank account details + order_ref for manual verification.
    The report is generated after admin confirms payment via /api/verify-bank-transfer.
    """
    if not BANK_TRANSFER_ENABLED:
        return jsonify({
            "error": "bank_transfer_not_enabled",
            "message": "Bank transfer is not available."
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
    order_ref = str(uuid.uuid4())[:8]

    # Save order (method=bank_transfer, paypal_order_id placeholder)
    _save_order(order_ref, f"BANK-{order_ref}", email, company_name,
                url, brand_name, plan_key, plan["price"], method="bank_transfer")

    # Save lead
    _save_lead(email, company_name, url, brand_name, f"bank_transfer_{plan_key}")

    # Return bank details for the user
    return jsonify({
        "order_ref": order_ref,
        "plan": plan_key,
        "plan_name": plan["name"],
        "amount": plan["price"],
        "currency": "JPY",
        "bank_details": {
            "bank_name": BANK_NAME,
            "branch": BANK_BRANCH,
            "account_type": BANK_ACCOUNT_TYPE,
            "account_number": BANK_ACCOUNT_NUMBER,
            "account_holder": BANK_ACCOUNT_HOLDER,
        },
        "instructions": [
            f"上記口座へ {plan['price']}円 をお振り込みください",
            f"振込依頼人名を「{order_ref} {company_name}」としてください",
            "入金確認後、レポート生成用のリンクをメールでお送りします",
            "通常1-2営業日以内に確認できます",
        ],
        "order_ref_display": order_ref,
        "status": "awaiting_payment",
    })


@app.route("/api/verify-bank-transfer", methods=["POST"])
def verify_bank_transfer():
    """
    Admin endpoint to verify a bank transfer and generate the full report.
    Requires ADMIN_TOKEN for authentication.
    Expects: {"order_ref": "...", "admin_token": "..."}
    """
    data = request.get_json() or {}
    admin_token = data.get("admin_token", "")
    order_ref = data.get("order_ref", "").strip()

    expected_token = os.getenv("ADMIN_TOKEN", "")
    if not expected_token or admin_token != expected_token:
        return jsonify({"error": "unauthorized"}), 401

    if not order_ref:
        return jsonify({"error": "order_ref_required"}), 400

    order_meta = _get_order_by_ref(order_ref)
    if not order_meta:
        return jsonify({"error": "order_not_found"}), 404

    if order_meta.get("method") != "bank_transfer":
        return jsonify({"error": "not_bank_transfer_order"}), 400

    if order_meta.get("status") == "paid":
        return jsonify({"error": "already_paid", "message": "This order has already been verified."}), 409

    try:
        # Update order status
        _update_order_status(order_ref, "paid")

        # Save payment record
        _save_payment(
            order_meta["paypal_order_id"],
            order_meta["email"],
            order_meta["company"],
            order_meta["url"],
            order_meta["brand"],
            order_meta["plan"],
            order_meta["amount"],
        )

        # Generate full report
        analyzer = GEOAnalyzer(order_meta["url"], order_meta["brand"])
        result = analyzer.run_full_analysis()
        result["lead"] = {
            "email": order_meta["email"],
            "company": order_meta["company"],
        }
        result["payment"] = {
            "order_id": order_meta["paypal_order_id"],
            "plan": order_meta["plan"],
            "amount": order_meta["amount"],
            "currency": "JPY",
            "method": "bank_transfer",
        }

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": "analysis_failed", "message": str(e)}), 500


# ==================== 404 Handler ====================

@app.errorhandler(404)
def not_found(error):
    """Custom Japanese 404 page."""
    notfound_path = os.path.join(FRONTEND_DIR, "404.html")
    if os.path.exists(notfound_path):
        return send_from_directory(FRONTEND_DIR, "404.html"), 404
    return jsonify({"error": "not_found", "message": "Page not found"}), 404


# ==================== Main ====================

if __name__ == "__main__":
    mode_str = "DEMO MODE (no API key)" if DEMO_MODE else f"LIVE MODE (DeepSeek)"
    paypal_str = f"PayPal: ENABLED ({PAYPAL_MODE})" if PAYPAL_AVAILABLE else "PayPal: NOT CONFIGURED"
    bank_str = f"Bank Transfer: ENABLED ({BANK_NAME})" if BANK_TRANSFER_ENABLED else "Bank Transfer: DISABLED"
    print(f"\n{'='*50}")
    print(f"  GEO MVP Diagnostic Engine")
    print(f"  Mode: {mode_str}")
    print(f"  Payment: {paypal_str}")
    print(f"  {bank_str}")
    print(f"  Port: {FLASK_PORT}")
    print(f"  Frontend: {FRONTEND_DIR}")
    print(f"  Data Dir: {DATA_DIR}")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=DEBUG_MODE)
