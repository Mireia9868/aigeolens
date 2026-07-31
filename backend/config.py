"""
GEO MVP - Configuration
Multi-AI model support: DeepSeek (primary), future: ChatGPT/Gemini/Perplexity/Claude
PayPal payment integration for JPY pricing.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# === DeepSeek API ===
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# === Future AI Models (placeholders) ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "")

# === PayPal Payment ===
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox")  # "sandbox" or "live"
PAYPAL_BASE_URL = (
    "https://api-m.paypal.com"
    if PAYPAL_MODE == "live"
    else "https://api-m.sandbox.paypal.com"
)
PAYPAL_CURRENCY = "JPY"

# === App Settings ===
FLASK_PORT = int(os.getenv("PORT", 5000))
DEBUG_MODE = os.getenv("DEBUG", "true").lower() == "true"
APP_URL = os.getenv("APP_URL", "https://aigeolens.com")  # for PayPal redirect URLs

# === Analysis Settings ===
MAX_CONTENT_LENGTH = 8000  # chars sent to AI per request
CRAWL_TIMEOUT = 15  # seconds
AI_TEMPERATURE = 0.3  # low temperature for consistent analysis
AI_MAX_TOKENS = 4000

# === Demo Mode ===
DEMO_MODE = not DEEPSEEK_API_KEY  # auto-enable demo mode if no API key

# === Pricing Plans (JPY) ===
# Competitive pricing based on market research:
# - Entry competitors: $29-50/mo (Otterly, LLMClicks)
# - Mid-tier competitors: $89-105/mo (Peec AI, Profound)
# - Pro competitors: $199-299/mo (Writesonic, Clearscope)
# All plans are one-time payments via PayPal (subscriptions coming soon)
PRICING_PLANS = {
    "free": {
        "name": "フリースキャン",
        "price": 0,
        "description": "基本スキャン・GEOスコア",
        "type": "free",
        "features": [
            "GEOスコア即時取得",
            "主要問題点TOP3",
            "15項目の基建チェック",
            "回数制限なし",
        ],
    },
    "audit": {
        "name": "お試し診断",
        "price": 4980,
        "description": "完全版GEO診断レポート（単発）",
        "type": "one_time",
        "features": [
            "全25+因子の詳細分析",
            "DeepSeek AI可視性シミュレーション",
            "優先順位付き改善提案",
            "競合3-5社ベンチマーク",
            "PDFレポート出力",
            "1回限り",
        ],
    },
    "pro": {
        "name": "プロプラン",
        "price": 9800,
        "description": "月次診断・継続モニタリング（1ヶ月分）",
        "type": "one_time",
        "features": [
            "月10回の詳細診断",
            "継続的なAI可視性モニタリング",
            "競合変動トラッキング",
            "週次レポート自動配信",
            "優先サポート",
        ],
    },
    "business": {
        "name": "ビジネスプラン",
        "price": 29800,
        "description": "代理店・ホワイトラベル対応（1ヶ月分）",
        "type": "one_time",
        "features": [
            "無制限の詳細診断",
            "5サイト監視",
            "API アクセス",
            "ホワイトラベルレポート",
            "専任サポート",
            "カスタムAIモデル設定",
        ],
    },
}
