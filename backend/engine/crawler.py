"""
Website Crawler - extracts content for GEO analysis.
"""
import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from config import CRAWL_TIMEOUT, MAX_CONTENT_LENGTH


class WebsiteCrawler:
    """Crawl a URL and extract structured content for GEO analysis."""

    def __init__(self, url: str):
        self.url = self._normalize_url(url)
        self.domain = urlparse(self.url).netloc
        self.soup = None
        self.raw_html = ""
        self.status_code = None

    @staticmethod
    def _normalize_url(url: str) -> str:
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        return url

    def fetch(self) -> dict:
        """Fetch and parse the website. Returns structured data dict."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; GEO-Audit-Bot/1.0; +https://geopti.io)"
            }
            resp = requests.get(self.url, headers=headers, timeout=CRAWL_TIMEOUT, allow_redirects=True)
            self.status_code = resp.status_code
            # Force correct encoding: if server didn't specify charset,
            # requests defaults to ISO-8859-1 which causes mojibake on UTF-8 pages
            if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
                resp.encoding = resp.apparent_encoding or "utf-8"
            self.raw_html = resp.text
            self.soup = BeautifulSoup(resp.text, "lxml")
        except requests.exceptions.Timeout:
            return {"error": "timeout", "message": f"Request timed out after {CRAWL_TIMEOUT}s"}
        except requests.exceptions.ConnectionError:
            return {"error": "connection_error", "message": "Could not connect to the URL"}
        except Exception as e:
            return {"error": "fetch_error", "message": str(e)}

        return self._extract()

    def _extract(self) -> dict:
        """Extract GEO-relevant data from the page."""
        soup = self.soup

        # Basic metadata
        title = soup.find("title")
        title_text = title.get_text(strip=True) if title else ""

        meta_desc = soup.find("meta", attrs={"name": "description"})
        description = meta_desc.get("content", "") if meta_desc else ""

        meta_keywords = soup.find("meta", attrs={"name": "keywords"})
        keywords = meta_keywords.get("content", "") if meta_keywords else ""

        # Open Graph
        og_tags = {}
        for tag in soup.find_all("meta", attrs={"property": re.compile(r"^og:")}):
            og_tags[tag.get("property")] = tag.get("content", "")

        # Twitter Cards
        twitter_tags = {}
        for tag in soup.find_all("meta", attrs={"name": re.compile(r"^twitter:")}):
            twitter_tags[tag.get("name")] = tag.get("content", "")

        # Structured data (JSON-LD)
        json_ld = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                json_ld.append(json.loads(script.string))
            except:
                pass

        # Headings
        headings = {}
        for level in range(1, 7):
            tags = soup.find_all(f"h{level}")
            headings[f"h{level}"] = [t.get_text(strip=True) for t in tags[:10]]

        # Paragraphs (content sample)
        paragraphs = []
        for p in soup.find_all("p"):
            text = p.get_text(strip=True)
            if len(text) > 20:
                paragraphs.append(text)
        content_text = " ".join(paragraphs)[:MAX_CONTENT_LENGTH]

        # Links
        internal_links = []
        external_links = []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            full_url = urljoin(self.url, href)
            if self.domain in full_url:
                internal_links.append(full_url)
            elif href.startswith(("http://", "https://")):
                external_links.append(full_url)

        # Images with alt text
        images = []
        for img in soup.find_all("img", src=True):
            images.append({
                "src": urljoin(self.url, img.get("src", "")),
                "alt": img.get("alt", ""),
            })

        # Language
        html_tag = soup.find("html")
        lang = html_tag.get("lang", "") if html_tag else ""

        # Canonical
        canonical = soup.find("link", rel="canonical")
        canonical_url = canonical.get("href", "") if canonical else ""

        # Robots meta
        robots = soup.find("meta", attrs={"name": "robots"})
        robots_content = robots.get("content", "") if robots else ""

        # Sitemap reference
        sitemap_link = soup.find("link", rel="sitemap")
        sitemap_url = sitemap_link.get("href", "") if sitemap_link else ""

        # Word count estimate
        all_text = soup.get_text(separator=" ", strip=True)
        word_count = len(all_text.split())

        # Page size
        page_size_kb = round(len(self.raw_html) / 1024, 1)

        return {
            "url": self.url,
            "domain": self.domain,
            "status_code": self.status_code,
            "page_size_kb": page_size_kb,
            "word_count": word_count,
            "title": title_text,
            "description": description,
            "keywords": keywords,
            "language": lang,
            "canonical_url": canonical_url,
            "robots_meta": robots_content,
            "open_graph": og_tags,
            "twitter_cards": twitter_tags,
            "structured_data": json_ld,
            "headings": headings,
            "content_sample": content_text,
            "internal_links_count": len(internal_links),
            "external_links_count": len(external_links),
            "external_links_sample": external_links[:20],
            "images_count": len(images),
            "images_with_alt": sum(1 for i in images if i["alt"]),
            "images_without_alt": sum(1 for i in images if not i["alt"]),
            "sitemap_url": sitemap_url,
            "has_ssl": self.url.startswith("https://"),
        }

    def get_content_summary(self) -> str:
        """Get a truncated text summary for AI analysis."""
        if not self.soup:
            return ""
        # Remove scripts and styles
        for tag in self.soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = self.soup.get_text(separator="\n", strip=True)
        return text[:MAX_CONTENT_LENGTH]
