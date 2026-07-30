"""
GEO Analysis Engine - Core diagnosis logic.
Adapts geo-diag-report skill's 4-stage pipeline into a standalone product.
Stage 1: Infrastructure + Content Audit (crawl-based)
Stage 2: AI Visibility Simulation (DeepSeek-powered)
Stage 3: Competitive Position Analysis
Stage 4: Scoring + Recommendations
"""
import json
import time
import hashlib
from datetime import datetime
from engine.crawler import WebsiteCrawler
from engine.ai_client import get_ai_client
from config import DEMO_MODE


class GEOAnalyzer:
    """Main GEO analysis engine."""

    def __init__(self, url: str, brand_name: str = "", ai_provider: str = "deepseek"):
        self.url = url
        self.brand_name = brand_name or self._extract_brand_from_url(url)
        self.ai_provider = ai_provider
        self.crawler = WebsiteCrawler(url)
        self.crawl_data = None
        self.ai_client = None
        self.analysis_id = hashlib.md5(f"{url}{time.time()}".encode()).hexdigest()[:12]

        if not DEMO_MODE:
            self.ai_client = get_ai_client(ai_provider)

    @staticmethod
    def _extract_brand_from_url(url: str) -> str:
        from urllib.parse import urlparse
        domain = urlparse("https://" + url if not url.startswith("http") else url).netloc
        parts = domain.replace("www.", "").split(".")
        return parts[0].capitalize() if parts else "Brand"

    def run_scan_only(self) -> dict:
        """
        Lightweight scan: Stage 1 only (no DeepSeek API call).
        Returns GEO score + top 3 key issues for the free tier.
        Cost: ~$0.02 (crawler only)
        """
        stage1 = self._run_stage1()

        if "error" in stage1:
            return {"score": 0, "level": "N/A", "stage1": stage1, "top_issues": []}

        score = stage1.get("score", 0)
        level = self._score_to_level(score)

        # Extract top 3 failed checks (highest priority)
        priority_codes = {"structured_data", "ssl_https", "title_tag", "content_depth", "meta_description"}
        failed = [c for c in stage1.get("checks", []) if not c["passed"]]
        # Sort: priority codes first, then others
        failed.sort(key=lambda c: (0 if c["code"] in priority_codes else 1, c["code"]))
        top_issues = [
            {
                "code": c["code"],
                "name": c["name"],
                "message": c["message"],
            }
            for c in failed[:3]
        ]

        # Preview of what's in the full report (locked)
        full_report_preview = [
            "AI\u53ef\u8996\u60275\u6b21\u5143\u30b9\u30b3\u30a2\uff08DeepSeek AI\u5206\u6790\uff09",
            "\u7af6\u54083-5\u793e\u306eGEO\u5f37\u5ea6\u6bd4\u8f03",
            "AIVO\u7dcf\u5408\u30b9\u30b3\u30a2 + \u512a\u5148\u9806\u4f4d\u4ed8\u304d\u6539\u5584\u63d0\u6848",
        ]

        return {
            "score": score,
            "level": level,
            "passed_checks": stage1.get("passed_checks", 0),
            "total_checks": stage1.get("total_checks", 15),
            "crawl_summary": stage1.get("crawl_summary", {}),
            "top_issues": top_issues,
            "full_report_preview": full_report_preview,
            "stage1": stage1,
        }

    def run_full_analysis(self) -> dict:
        """Run the complete 4-stage GEO analysis pipeline."""
        result = {
            "analysis_id": self.analysis_id,
            "url": self.url,
            "brand": self.brand_name,
            "timestamp": datetime.now().isoformat(),
            "stages": {},
        }

        # Stage 1: Crawl + Infrastructure Audit
        result["stages"]["stage1_infrastructure"] = self._run_stage1()

        # Stage 2: AI Visibility Analysis
        result["stages"]["stage2_ai_visibility"] = self._run_stage2()

        # Stage 3: Competitive Position
        result["stages"]["stage3_competitive"] = self._run_stage3()

        # Stage 4: Scoring + Recommendations
        result["stages"]["stage4_scoring"] = self._run_stage4(result["stages"])

        result["overall_score"] = result["stages"]["stage4_scoring"].get("aivo_score", {}).get("total_score", 0)
        result["score_level"] = self._score_to_level(result["overall_score"])

        return result

    # ==================== Stage 1: Infrastructure Audit ====================

    def _run_stage1(self) -> dict:
        """Crawl website and assess GEO infrastructure readiness."""
        self.crawl_data = self.crawler.fetch()

        if "error" in self.crawl_data:
            return {"error": self.crawl_data["error"], "message": self.crawl_data["message"]}

        data = self.crawl_data
        checks = []

        # 1. Title tag
        checks.append(self._check(
            "title_tag", "Title Tag",
            bool(data.get("title")) and len(data.get("title", "")) > 10,
            "Page has a descriptive title tag" if data.get("title") else "Missing or empty title tag",
            data.get("title", "")
        ))

        # 2. Meta description
        checks.append(self._check(
            "meta_description", "Meta Description",
            bool(data.get("description")) and len(data.get("description", "")) > 50,
            "Meta description present and descriptive" if data.get("description") else "Missing meta description",
            data.get("description", "")
        ))

        # 3. Structured data (JSON-LD)
        has_schema = bool(data.get("structured_data"))
        checks.append(self._check(
            "structured_data", "Structured Data (Schema.org)",
            has_schema,
            f"Found {len(data.get('structured_data', []))} JSON-LD blocks" if has_schema else "No structured data found - critical for AI understanding",
            json.dumps(data.get("structured_data", [])[:2], ensure_ascii=False)[:500]
        ))

        # 4. Open Graph tags
        has_og = bool(data.get("open_graph"))
        checks.append(self._check(
            "open_graph", "Open Graph Tags",
            has_og,
            f"{len(data.get('open_graph', {}))} OG tags found" if has_og else "No Open Graph tags - poor social sharing",
            json.dumps(data.get("open_graph", {}), ensure_ascii=False)[:300]
        ))

        # 5. Heading structure
        h1_count = len(data.get("headings", {}).get("h1", []))
        checks.append(self._check(
            "heading_structure", "Heading Structure (H1-H6)",
            h1_count >= 1,
            f"{h1_count} H1 tag(s) found" if h1_count else "No H1 tag - poor content hierarchy",
            str(data.get("headings", {}).get("h1", [])[:3])
        ))

        # 6. Image alt text
        img_total = data.get("images_count", 0)
        img_with_alt = data.get("images_with_alt", 0)
        alt_ratio = img_with_alt / img_total if img_total > 0 else 0
        checks.append(self._check(
            "image_alt", "Image Alt Text",
            alt_ratio >= 0.8 and img_total > 0,
            f"{img_with_alt}/{img_total} images have alt text ({alt_ratio*100:.0f}%)" if img_total else "No images found",
            f"{img_with_alt}/{img_total}"
        ))

        # 7. SSL/HTTPS
        checks.append(self._check(
            "ssl_https", "SSL/HTTPS",
            data.get("has_ssl", False),
            "Site uses HTTPS" if data.get("has_ssl") else "No SSL - AI engines deprioritize non-HTTPS",
            str(data.get("has_ssl"))
        ))

        # 8. Language declaration
        lang = data.get("language", "")
        checks.append(self._check(
            "language_decl", "Language Declaration",
            bool(lang),
            f"Language declared: {lang}" if lang else "No lang attribute - AI may misidentify language",
            lang
        ))

        # 9. Canonical URL
        checks.append(self._check(
            "canonical", "Canonical URL",
            bool(data.get("canonical_url")),
            "Canonical URL set" if data.get("canonical_url") else "No canonical URL - duplicate content risk",
            data.get("canonical_url", "")
        ))

        # 10. Content depth
        wc = data.get("word_count", 0)
        checks.append(self._check(
            "content_depth", "Content Depth",
            wc >= 500,
            f"{wc} words on page" if wc >= 500 else f"Only {wc} words - thin content for AI extraction",
            str(wc)
        ))

        # 11. Internal linking
        internal = data.get("internal_links_count", 0)
        checks.append(self._check(
            "internal_links", "Internal Linking",
            internal >= 5,
            f"{internal} internal links" if internal >= 5 else f"Only {internal} internal links - weak site structure",
            str(internal)
        ))

        # 12. External authority links
        external = data.get("external_links_count", 0)
        checks.append(self._check(
            "external_links", "External Authority Links",
            external >= 2,
            f"{external} external links" if external >= 2 else f"Only {external} external links - low authority signals",
            str(external)
        ))

        # 13. Robots meta
        robots = data.get("robots_meta", "").lower()
        is_blocked = "noindex" in robots or "nofollow" in robots
        checks.append(self._check(
            "robots_meta", "Robots Meta Directives",
            not is_blocked,
            "Page is indexable" if not is_blocked else f"Page blocked: {robots}",
            robots or "none"
        ))

        # 14. Page performance (size proxy)
        size_kb = data.get("page_size_kb", 0)
        checks.append(self._check(
            "page_size", "Page Size (Performance Proxy)",
            size_kb < 500,
            f"Page size: {size_kb}KB" if size_kb < 500 else f"Page too large: {size_kb}KB - may slow AI crawlers",
            f"{size_kb}KB"
        ))

        # 15. Sitemap reference
        checks.append(self._check(
            "sitemap", "Sitemap Reference",
            bool(data.get("sitemap_url")),
            "Sitemap referenced" if data.get("sitemap_url") else "No sitemap reference found",
            data.get("sitemap_url", "")
        ))

        passed = sum(1 for c in checks if c["passed"])
        score = round(passed / len(checks) * 100) if checks else 0

        return {
            "score": score,
            "passed_checks": passed,
            "total_checks": len(checks),
            "checks": checks,
            "crawl_summary": {
                "title": data.get("title", ""),
                "description": data.get("description", ""),
                "word_count": data.get("word_count", 0),
                "language": data.get("language", ""),
                "page_size_kb": data.get("page_size_kb", 0),
                "has_ssl": data.get("has_ssl", False),
                "has_schema": bool(data.get("structured_data")),
                "domain": data.get("domain", ""),
            }
        }

    # ==================== Stage 2: AI Visibility ====================

    def _run_stage2(self) -> dict:
        """Simulate AI search visibility using DeepSeek."""
        if DEMO_MODE or not self.ai_client:
            return self._demo_stage2()

        content_summary = self.crawler.get_content_summary()
        data = self.crawl_data or {}

        system_prompt = """You are a GEO (Generative Engine Optimization) visibility analyst.
Analyze the given website content and predict how likely AI search engines (ChatGPT, Gemini, Perplexity, DeepSeek, Claude) would reference this site when answering relevant user queries.

Output strict JSON only, no markdown fences.

Evaluate these dimensions:
1. ai_citability (0-100): How easily can AI extract and cite facts from this content?
2. entity_clarity (0-100): Is the brand/entity clearly defined for AI knowledge graphs?
3. content_authority (0-100): Does the content demonstrate expertise and authority?
4. semantic_structure (0-100): Is the content well-structured for AI parsing (headings, schema, FAQ)?
5. factual_density (0-100): Ratio of concrete facts/stats/data vs marketing fluff.

Also generate:
- 5 sample user queries where AI engines might reference this site
- 5 sample queries where this site would likely NOT be referenced (gaps)
- 3 specific recommendations to improve AI visibility

Response format:
{
  "dimensions": {
    "ai_citability": {"score": 0, "comment": ""},
    "entity_clarity": {"score": 0, "comment": ""},
    "content_authority": {"score": 0, "comment": ""},
    "semantic_structure": {"score": 0, "comment": ""},
    "factual_density": {"score": 0, "comment": ""}
  },
  "likely_cited_queries": ["query1", "query2"],
  "unlikely_cited_queries": ["query1", "query2"],
  "visibility_score": 0,
  "recommendations": ["rec1", "rec2"]
}"""

        user_prompt = f"""Website: {self.url}
Brand: {self.brand_name}
Title: {data.get('title', 'N/A')}
Language: {data.get('language', 'N/A')}
Has Schema: {bool(data.get('structured_data'))}
Word Count: {data.get('word_count', 0)}

Content Sample (first 3000 chars):
{content_summary[:3000]}

Analyze this website's AI search visibility potential."""

        try:
            result = self.ai_client.chat_json(system_prompt, user_prompt)
            result["mode"] = "live"
            return result
        except Exception as e:
            return {"error": str(e), "mode": "live", "fallback": self._demo_stage2()}

    # ==================== Stage 3: Competitive ====================

    def _run_stage3(self) -> dict:
        """Competitive position analysis."""
        if DEMO_MODE or not self.ai_client:
            return self._demo_stage3()

        data = self.crawl_data or {}
        external_links = data.get("external_links_sample", [])
        domain = data.get("domain", "")

        system_prompt = """You are a competitive GEO analyst. Analyze the given website's competitive position in AI search.
Output strict JSON only.

Provide:
1. 3-5 likely competitors (based on domain and content)
2. For each competitor: name, website, estimated GEO strength (0-100), key advantage
3. Overall competitive position assessment
4. 3 differentiation opportunities for this brand in AI search

Response format:
{
  "competitors": [
    {"name": "", "website": "", "geo_strength": 0, "advantage": ""}
  ],
  "brand_position": "",
  "differentiation_opportunities": ["", ""],
  "competitive_score": 0
}"""

        user_prompt = f"""Website: {self.url}
Domain: {domain}
Brand: {self.brand_name}
External links found: {', '.join(external_links[:10])}
Title: {data.get('title', 'N/A')}
Content sample: {(self.crawler.get_content_summary() or '')[:1500]}

Analyze competitive position for AI search visibility."""

        try:
            result = self.ai_client.chat_json(system_prompt, user_prompt)
            result["mode"] = "live"
            return result
        except Exception as e:
            return {"error": str(e), "mode": "live", "fallback": self._demo_stage3()}

    # ==================== Stage 4: Scoring ====================

    def _run_stage4(self, stages: dict) -> dict:
        """Calculate AIVO-style score and generate recommendations."""
        s1 = stages.get("stage1_infrastructure", {})
        s2 = stages.get("stage2_ai_visibility", {})
        s3 = stages.get("stage3_competitive", {})

        # Infrastructure score
        infra_score = s1.get("score", 50) if "error" not in s1 else 30

        # AI visibility score
        if "dimensions" in s2:
            dims = s2["dimensions"]
            vis_score = sum(d.get("score", 50) for d in dims.values()) // len(dims) if dims else 50
        else:
            vis_score = s2.get("visibility_score", 50)

        # Competitive score
        comp_score = s3.get("competitive_score", 50)

        # Sentiment/authority heuristic (based on content quality)
        content_data = s1.get("crawl_summary", {})
        authority_signals = 0
        if content_data.get("has_schema"):
            authority_signals += 20
        if content_data.get("word_count", 0) > 1000:
            authority_signals += 15
        if s1.get("passed_checks", 0) > 10:
            authority_signals += 15
        authority_score = min(100, 40 + authority_signals)

        # AIVO-style weighted score
        total_score = round(
            vis_score * 0.25 +
            infra_score * 0.25 +
            comp_score * 0.25 +
            authority_score * 0.25
        )

        level = self._score_to_level(total_score)

        # Generate recommendations
        recommendations = self._generate_recommendations(s1, s2, s3, total_score)

        return {
            "aivo_score": {
                "total_score": total_score,
                "level": level,
                "dimensions": [
                    {"code": "AI_SEARCH_VISIBILITY", "name": "AI\u691c\u7d22\u53ef\u8996\u6027", "score": vis_score, "weight": 0.25,
                     "comment": s2.get("dimensions", {}).get("ai_citability", {}).get("comment", "Based on content analysis")},
                    {"code": "INFRA_COMPLETENESS", "name": "\u57fa\u5efa\u5b8c\u6210\u5ea6", "score": infra_score, "weight": 0.25,
                     "comment": f"{s1.get('passed_checks', 0)}/{s1.get('total_checks', 15)} checks passed"},
                    {"code": "COMPETITIVE_ADVANTAGE", "name": "\u7af6\u4e89\u512a\u52e2", "score": comp_score, "weight": 0.25,
                     "comment": s3.get("brand_position", "Competitive analysis completed")},
                    {"code": "AUTHORITY_SIGNALS", "name": "\u6b0a\u5a01\u4fe1\u865f", "score": authority_score, "weight": 0.25,
                     "comment": f"Schema: {'Yes' if content_data.get('has_schema') else 'No'}, Words: {content_data.get('word_count', 0)}"},
                ],
            },
            "recommendations": recommendations,
            "projected_score": min(100, total_score + 20),
            "mode": "live" if not DEMO_MODE else "demo"
        }

    # ==================== Helpers ====================

    @staticmethod
    def _check(code, name, passed, message, detail=""):
        return {"code": code, "name": name, "passed": passed, "message": message, "detail": detail}

    @staticmethod
    def _score_to_level(score: int) -> str:
        if score >= 90:
            return "\u512a\u79c0"
        elif score >= 75:
            return "\u826f\u597d"
        elif score >= 60:
            return "\u4e00\u822c"
        else:
            return "\u8f03\u5dee"

    def _generate_recommendations(self, s1, s2, s3, current_score):
        recs = []
        checks = s1.get("checks", [])

        # Infrastructure-based recommendations
        for check in checks:
            if not check["passed"]:
                priority = "high" if check["code"] in ("structured_data", "ssl_https", "title_tag", "content_depth") else "medium"
                recs.append({
                    "priority": priority,
                    "category": "\u57fa\u5efa\u512a\u5316",
                    "title": f"\u4fee\u5fa9: {check['name']}",
                    "description": check["message"],
                    "impact": "+3-5\u5206" if priority == "high" else "+1-3\u5206",
                    "effort": "\u5feb\u901f\u4fee\u5fa9" if priority == "high" else "\u4e2d\u7b49",
                })

        # AI visibility recommendations
        if "recommendations" in s2:
            for r in s2["recommendations"][:3]:
                recs.append({
                    "priority": "high",
                    "category": "AI\u53ef\u8996\u6027",
                    "title": r[:60] + ("..." if len(r) > 60 else ""),
                    "description": r,
                    "impact": "+2-5\u5206",
                    "effort": "\u4e2d\u7b49",
                })

        # Competitive recommendations
        for opp in s3.get("differentiation_opportunities", [])[:2]:
            recs.append({
                "priority": "medium",
                "category": "\u7af6\u4e89\u5dee\u7570\u5316",
                "title": opp[:60] + ("..." if len(opp) > 60 else ""),
                "description": opp,
                "impact": "+2-4\u5206",
                "effort": "\u4e2d\u7b49",
            })

        # If everything looks good, add growth recommendations
        if len(recs) < 3:
            recs.append({
                "priority": "medium",
                "category": "\u9577\u671f\u589e\u9577",
                "title": "\u5efa\u7acb AI \u5f15\u7528\u76e3\u6e2c\u9ad4\u7cfb",
                "description": "\u6301\u7e8c\u76e3\u6e2c\u54c1\u724c\u5728 AI \u641c\u5c0b\u4e2d\u7684\u53ef\u898b\u5ea6\uff0c\u8ffd\u8e64\u7af6\u54c1\u52d5\u614b",
                "impact": "\u9577\u671f",
                "effort": "\u4e2d\u7b49",
            })

        return recs

    # ==================== Demo Data ====================

    def _demo_stage2(self) -> dict:
        data = self.crawl_data or {}
        wc = data.get("word_count", 0)
        has_schema = bool(data.get("structured_data"))
        return {
            "dimensions": {
                "ai_citability": {"score": 45 if wc < 500 else 65, "comment": f"Content has {wc} words. {'Thin content reduces AI citation likelihood.' if wc < 500 else 'Adequate content depth for AI extraction.'}"},
                "entity_clarity": {"score": 50, "comment": "Brand entity definition needs structured data improvement."},
                "content_authority": {"score": 55, "comment": "Content authority signals are moderate. Add expert citations."},
                "semantic_structure": {"score": 35 if not has_schema else 70, "comment": "Structured data " + ("present" if has_schema else "missing") + ". " + ("Good for AI parsing." if has_schema else "Critical gap for AI understanding.")},
                "factual_density": {"score": 50, "comment": "Balance factual data with marketing content for better AI citation."},
            },
            "likely_cited_queries": [
                f"What is {self.brand_name}?",
                f"{self.brand_name} features",
                f"{self.brand_name} vs alternatives",
            ],
            "unlikely_cited_queries": [
                f"best {self.brand_name} alternatives",
                f"is {self.brand_name} reliable",
                f"{self.brand_name} pricing comparison",
            ],
            "visibility_score": 50,
            "recommendations": [
                "Add FAQ schema to increase AI citation probability by 30%+",
                "Include concrete statistics and data points that AI can cite",
                "Create comparison pages with structured data for competitive queries",
            ],
            "mode": "demo"
        }

    def _demo_stage3(self) -> dict:
        return {
            "competitors": [
                {"name": "Competitor A", "website": "", "geo_strength": 72, "advantage": "Strong structured data and FAQ content"},
                {"name": "Competitor B", "website": "", "geo_strength": 65, "advantage": "High content authority with expert citations"},
                {"name": "Competitor C", "website": "", "geo_strength": 58, "advantage": "Better semantic markup and entity definitions"},
            ],
            "brand_position": "\u4e2d\u7b49\u4f4d\u7f6e - \u6709\u57fa\u672c\u5167\u5bb9\u4f46\u7f3a\u4e4f AI \u53cb\u597d\u4fe1\u865f",
            "differentiation_opportunities": [
                "\u5efa\u7acb\u5c08\u5bb6\u5167\u5bb9\u6b0a\u5a01 - \u9080\u8acb\u884c\u696d\u5c08\u5bb6\u64b0\u5beb\u6df1\u5ea6\u6587\u7ae0",
                "\u5efa\u7acb\u7d50\u69cb\u5316\u8cc7\u6599\u9ad4\u7cfb - Schema.org \u5168\u9762\u8986\u84cb",
            ],
            "competitive_score": 48,
            "mode": "demo"
        }
