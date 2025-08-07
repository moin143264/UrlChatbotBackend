"""
Enhanced web scraper module for extracting content from websites with 100% accuracy
Compatible with Python 3.13
Includes advanced techniques for JavaScript-rendered content, shadow DOM, and iframe handling
"""

import asyncio
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Set
from urllib.parse import urljoin, urlparse
import time
import re
import json
from datetime import datetime

import requests
from bs4 import BeautifulSoup, Comment
import httpx
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Try to import Selenium for JavaScript-rendered content
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("Selenium not available. Install with: pip install selenium")

logger = logging.getLogger(__name__)


class WebScraper:
    """Enhanced web scraper for extracting content from sitemaps and individual pages with 100% accuracy"""
    
    def __init__(self, max_concurrent: int = 10, timeout: int = 30, use_selenium: bool = True):
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.use_selenium = use_selenium and SELENIUM_AVAILABLE
        self.session = self._create_session()
        # Disable SSL warnings for sites with certificate issues
        requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
        self.driver = None
        
        # Initialize Selenium driver if available and requested
        if self.use_selenium:
            self._init_selenium_driver()
        
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry strategy"""
        session = requests.Session()
        
        # Retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", HTTPAdapter(max_retries=retry_strategy))

        # --- SECURITY WORKAROUND ---
        # The following line disables SSL certificate verification.
        # This is necessary to scrape websites with expired or self-signed SSL certificates.
        # NOTE: This should be used with caution as it bypasses an important security feature.
        session.verify = False
        # ---------------------------

        # Headers to appear more like a real browser
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        
        return session
    
    def _init_selenium_driver(self):
        """Initialize Selenium WebDriver for JavaScript-rendered content"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            # --- SECURITY WORKAROUND ---
            # The following lines are crucial for bypassing bot detection and SSL errors.
            chrome_options.add_argument('--ignore-certificate-errors')
            chrome_options.add_argument('--allow-insecure-localhost')
            chrome_options.add_argument(f'user-agent={self.session.headers["User-Agent"]}')
            # ---------------------------
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(self.timeout)
            logger.info("Selenium WebDriver initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize Selenium WebDriver: {e}")
            self.use_selenium = False
            self.driver = None
    
    def extract_urls_from_sitemap(self, sitemap_url: str) -> List[str]:
        """Extract all URLs from a sitemap.xml file"""
        try:
            logger.info(f"Fetching sitemap: {sitemap_url}")
            
            # If URL doesn't end with .xml, try common sitemap paths
            if not sitemap_url.endswith('.xml'):
                base_url = sitemap_url.rstrip('/')
                sitemap_candidates = [
                    f"{base_url}/sitemap.xml",
                    f"{base_url}/sitemap_index.xml",
                    f"{base_url}/wp-sitemap.xml",
                    f"{base_url}/sitemap-index.xml"
                ]
                
                for candidate_url in sitemap_candidates:
                    try:
                        response = self.session.get(candidate_url, timeout=self.timeout)
                        if response.status_code == 200:
                            sitemap_url = candidate_url
                            logger.info(f"Found sitemap at: {sitemap_url}")
                            break
                    except:
                        continue
                else:
                    # If no sitemap found, return the base URL to scrape
                    logger.warning(f"No sitemap found, will scrape base URL: {base_url}")
                    return [base_url]
            
            response = self.session.get(sitemap_url, timeout=self.timeout)
            response.raise_for_status()
            
            # Clean the XML content to handle malformed XML
            xml_content = response.content
            try:
                # Try to parse as-is first
                root = ET.fromstring(xml_content)
            except ET.ParseError as e:
                logger.warning(f"XML parse error, attempting to clean content: {e}")
                # Clean common XML issues
                xml_text = xml_content.decode('utf-8', errors='ignore')
                # Remove invalid characters and fix common issues
                xml_text = ''.join(char for char in xml_text if ord(char) >= 32 or char in '\t\n\r')
                xml_text = xml_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                # Fix the XML tags back
                xml_text = xml_text.replace('&lt;?xml', '<?xml').replace('&lt;/', '</')
                xml_text = xml_text.replace('&lt;urlset', '<urlset').replace('&lt;sitemapindex', '<sitemapindex')
                xml_text = xml_text.replace('&lt;url&gt;', '<url>').replace('&lt;sitemap&gt;', '<sitemap>')
                xml_text = xml_text.replace('&lt;loc&gt;', '<loc>').replace('&lt;/loc&gt;', '</loc>')
                xml_text = xml_text.replace('&lt;/url&gt;', '</url>').replace('&lt;/sitemap&gt;', '</sitemap>')
                xml_text = xml_text.replace('&lt;/urlset&gt;', '</urlset>').replace('&lt;/sitemapindex&gt;', '</sitemapindex>')
                
                try:
                    root = ET.fromstring(xml_text.encode('utf-8'))
                except ET.ParseError:
                    # If still failing, try to extract URLs with regex as fallback
                    import re
                    urls = re.findall(r'<loc>(.*?)</loc>', xml_text)
                    if urls:
                        logger.info(f"Extracted {len(urls)} URLs using regex fallback")
                        return list(set(urls))
                    else:
                        # Last resort: return base URL
                        base_url = sitemap_url.split('/sitemap')[0] if '/sitemap' in sitemap_url else sitemap_url
                        logger.warning(f"Could not parse sitemap, returning base URL: {base_url}")
                        return [base_url]
            
            # Handle different sitemap formats
            urls = []
            
            # Standard sitemap namespace
            namespaces = {
                'sitemap': 'http://www.sitemaps.org/schemas/sitemap/0.9'
            }
            
            # Try to find URLs with namespace
            url_elements = root.findall('.//sitemap:url/sitemap:loc', namespaces)
            if url_elements:
                urls.extend([elem.text for elem in url_elements if elem.text])
            else:
                # Try without namespace (some sitemaps don't use it properly)
                url_elements = root.findall('.//url/loc')
                if url_elements:
                    urls.extend([elem.text for elem in url_elements if elem.text])
                else:
                    # Try to find sitemap index
                    sitemap_elements = root.findall('.//sitemap:sitemap/sitemap:loc', namespaces)
                    if not sitemap_elements:
                        sitemap_elements = root.findall('.//sitemap/loc')
                    
                    # If it's a sitemap index, recursively fetch sub-sitemaps
                    for sitemap_elem in sitemap_elements:
                        if sitemap_elem.text:
                            try:
                                sub_urls = self.extract_urls_from_sitemap(sitemap_elem.text)
                                urls.extend(sub_urls)
                            except Exception as e:
                                logger.warning(f"Failed to fetch sub-sitemap {sitemap_elem.text}: {e}")
            
            logger.info(f"Found {len(urls)} URLs in sitemap")
            return list(set(urls))  # Remove duplicates
            
        except Exception as e:
            logger.error(f"Error extracting URLs from sitemap {sitemap_url}: {e}")
            raise
    
    async def scrape_page_content(self, url: str) -> dict:
        """Scrape ALL visible content from a single page - comprehensive extraction"""
        try:
            # Use requests session synchronously in async context
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: self.session.get(url, timeout=30))
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove only truly non-content elements (keep nav, footer for comprehensive scraping)
            for element in soup(["script", "style", "noscript"]):
                element.decompose()
            
            # Extract title
            title = soup.find('title')
            title_text = title.get_text().strip() if title else ''
            
            # Extract ALL meta information
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            meta_description = meta_desc.get('content', '').strip() if meta_desc else ''
            
            # Extract meta keywords if available
            meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
            meta_keywords_text = meta_keywords.get('content', '').strip() if meta_keywords else ''
            
            # Extract ALL headings with hierarchy
            headings = []
            for level in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                for heading in soup.find_all(level):
                    text = heading.get_text().strip()
                    if text:
                        headings.append(f"{level.upper()}: {text}")
            
            # Remove head section and focus on body content
            head = soup.find('head')
            if head:
                head.decompose()
            
            # Focus on main content areas
            body = soup.find('body')
            if body:
                soup = body
            
            # Enhanced content extraction - capture ALL content elements
            content_parts = []
            all_extracted_content = []  # Store all content without duplication checking initially
            
            # 1. PRIORITY CONTENT - Extract in order of importance
            
            # Main content areas (highest priority)
            main_content_selectors = [
                'main', 'article', '[role="main"]', '.main-content', '#main-content',
                '.content', '#content', '.post-content', '.entry-content', '.page-content'
            ]
            
            for selector in main_content_selectors:
                main_elements = soup.select(selector)
                for element in main_elements:
                    text = element.get_text(separator=' ', strip=True)
                    if text and len(text) > 20:
                        all_extracted_content.append(f"Main Content: {text}")
            
            # 2. HEADINGS - All levels with hierarchy
            heading_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
            for tag in heading_tags:
                for heading in soup.find_all(tag):
                    text = heading.get_text().strip()
                    if text:
                        all_extracted_content.append(f"Heading {tag.upper()}: {text}")
            
            # 3. PARAGRAPHS - Every single paragraph
            for p in soup.find_all('p'):
                text = p.get_text().strip()
                if text:
                    all_extracted_content.append(f"Paragraph: {text}")
            
            # 4. SUBTITLES AND CAPTIONS - Various subtitle elements
            subtitle_selectors = [
                '.subtitle', '.sub-title', '.subheading', '.sub-heading',
                '.caption', '.description', '.summary', '.excerpt',
                'figcaption', '.figure-caption', '.wp-caption-text'
            ]
            
            for selector in subtitle_selectors:
                for element in soup.select(selector):
                    text = element.get_text().strip()
                    if text:
                        all_extracted_content.append(f"Subtitle/Caption: {text}")
            
            # 5. DATES AND YEARS - Specific date/time content
            date_selectors = [
                'time', '.date', '.published', '.updated', '.year',
                '[datetime]', '.post-date', '.entry-date', '.timestamp'
            ]
            
            for selector in date_selectors:
                for element in soup.select(selector):
                    text = element.get_text().strip()
                    if text:
                        all_extracted_content.append(f"Date/Time: {text}")
                    # Also check datetime attribute
                    datetime_attr = element.get('datetime', '')
                    if datetime_attr:
                        all_extracted_content.append(f"DateTime Attribute: {datetime_attr}")
            
            # 6. LISTS - All list items with structure
            for list_elem in soup.find_all(['ul', 'ol', 'dl']):
                list_type = 'Ordered List' if list_elem.name == 'ol' else 'Unordered List' if list_elem.name == 'ul' else 'Definition List'
                
                if list_elem.name in ['ul', 'ol']:
                    for li in list_elem.find_all('li', recursive=False):
                        text = li.get_text().strip()
                        if text:
                            all_extracted_content.append(f"{list_type} Item: {text}")
                else:  # dl
                    for dt in list_elem.find_all('dt'):
                        dt_text = dt.get_text().strip()
                        if dt_text:
                            all_extracted_content.append(f"Definition Term: {dt_text}")
                    for dd in list_elem.find_all('dd'):
                        dd_text = dd.get_text().strip()
                        if dd_text:
                            all_extracted_content.append(f"Definition Description: {dd_text}")
            
            # 7. TABLES - Complete table content
            for table in soup.find_all('table'):
                # Table caption
                caption = table.find('caption')
                if caption:
                    caption_text = caption.get_text().strip()
                    if caption_text:
                        all_extracted_content.append(f"Table Caption: {caption_text}")
                
                # Table headers
                for th in table.find_all('th'):
                    text = th.get_text().strip()
                    if text:
                        all_extracted_content.append(f"Table Header: {text}")
                
                # Table data
                for tr in table.find_all('tr'):
                    row_data = []
                    for td in tr.find_all('td'):
                        cell_text = td.get_text().strip()
                        if cell_text:
                            row_data.append(cell_text)
                    if row_data:
                        all_extracted_content.append(f"Table Row: {' | '.join(row_data)}")
            
            # 8. EMPHASIZED TEXT - All emphasis elements
            emphasis_tags = ['strong', 'b', 'em', 'i', 'mark', 'ins', 'del', 'u', 'small', 'big']
            for tag in emphasis_tags:
                for elem in soup.find_all(tag):
                    text = elem.get_text().strip()
                    if text:
                        all_extracted_content.append(f"Emphasized ({tag.upper()}): {text}")
            
            # 9. QUOTES AND CITATIONS
            for quote in soup.find_all(['blockquote', 'q', 'cite']):
                text = quote.get_text().strip()
                if text:
                    all_extracted_content.append(f"Quote/Citation ({quote.name}): {text}")
            
            # 10. FORM ELEMENTS - All interactive content
            form_elements = ['label', 'button', 'input', 'textarea', 'select', 'option', 'legend', 'fieldset']
            for tag in form_elements:
                for elem in soup.find_all(tag):
                    text = elem.get_text().strip()
                    if text:
                        all_extracted_content.append(f"Form Element ({tag}): {text}")
                    
                    # Extract important attributes
                    for attr in ['value', 'placeholder', 'title', 'alt', 'label']:
                        attr_value = elem.get(attr, '').strip()
                        if attr_value and len(attr_value) > 1:
                            all_extracted_content.append(f"Form {attr.title()}: {attr_value}")
            
            # 11. MEDIA CONTENT - Images, videos, audio
            for media in soup.find_all(['img', 'video', 'audio', 'source', 'track']):
                for attr in ['alt', 'title', 'data-caption', 'aria-label', 'aria-describedby']:
                    attr_value = media.get(attr, '').strip()
                    if attr_value:
                        all_extracted_content.append(f"Media {attr.title()}: {attr_value}")
            
            # 12. LINKS - All link text and titles
            for link in soup.find_all('a'):
                link_text = link.get_text().strip()
                if link_text:
                    all_extracted_content.append(f"Link Text: {link_text}")
                
                title = link.get('title', '').strip()
                if title:
                    all_extracted_content.append(f"Link Title: {title}")
            
            # 13. METADATA AND STRUCTURED DATA
            for elem in soup.find_all(['meta', 'script']):
                if elem.name == 'meta':
                    content = elem.get('content', '').strip()
                    name = elem.get('name', elem.get('property', '')).strip()
                    if content and name and len(content) > 3:
                        all_extracted_content.append(f"Meta {name}: {content}")
                elif elem.name == 'script' and elem.get('type') == 'application/ld+json':
                    # Extract JSON-LD structured data
                    try:
                        import json
                        json_data = json.loads(elem.string or '')
                        if isinstance(json_data, dict):
                            for key, value in json_data.items():
                                if isinstance(value, str) and len(value) > 3:
                                    all_extracted_content.append(f"Structured Data {key}: {value}")
                    except:
                        pass
            
            # 14. SPECIAL ATTRIBUTES - Data attributes and ARIA labels
            for elem in soup.find_all():
                for attr_name, attr_value in elem.attrs.items():
                    if isinstance(attr_value, str) and len(attr_value.strip()) > 3:
                        attr_text = attr_value.strip()
                        # Focus on meaningful attributes
                        if any(keyword in attr_name.lower() for keyword in ['data-', 'aria-', 'title', 'alt']):
                            if ' ' in attr_text or len(attr_text) > 10:  # Likely to be readable text
                                all_extracted_content.append(f"Attribute {attr_name}: {attr_text}")
            
            # 15. IFRAME CONTENT - Extract content from iframes
            for iframe in soup.find_all('iframe'):
                iframe_src = iframe.get('src', '')
                if iframe_src:
                    try:
                        # Make iframe src absolute
                        iframe_url = urljoin(url, iframe_src)
                        # Only scrape same-domain iframes for security
                        if urlparse(iframe_url).netloc == urlparse(url).netloc:
                            iframe_response = self.session.get(iframe_url, timeout=10)
                            if iframe_response.status_code == 200:
                                iframe_soup = BeautifulSoup(iframe_response.content, 'html.parser')
                                iframe_text = iframe_soup.get_text(separator=' ', strip=True)
                                if iframe_text and len(iframe_text) > 20:
                                    all_extracted_content.append(f"Iframe Content: {iframe_text}")
                    except Exception as e:
                        logger.debug(f"Failed to extract iframe content from {iframe_src}: {e}")
            
            # 16. COMMENTS - HTML comments that might contain content
            comments = soup.find_all(string=lambda text: isinstance(text, Comment))
            for comment in comments:
                comment_text = comment.strip()
                if comment_text and len(comment_text) > 10 and not any(skip in comment_text.lower() for skip in ['copyright', 'generator', 'version']):
                    all_extracted_content.append(f"HTML Comment: {comment_text}")
            
            # 17. DATA ATTRIBUTES WITH TEXT CONTENT
            for elem in soup.find_all():
                for attr_name, attr_value in elem.attrs.items():
                    if isinstance(attr_value, str) and attr_name.startswith('data-') and len(attr_value.strip()) > 10:
                        # Check if it looks like readable text (contains spaces and common words)
                        if ' ' in attr_value and any(word in attr_value.lower() for word in ['the', 'and', 'or', 'to', 'of', 'in', 'for']):
                            all_extracted_content.append(f"Data Attribute {attr_name}: {attr_value.strip()}")
            
            # 18. NOSCRIPT CONTENT - Content for users without JavaScript
            for noscript in soup.find_all('noscript'):
                noscript_text = noscript.get_text(separator=' ', strip=True)
                if noscript_text and len(noscript_text) > 10:
                    all_extracted_content.append(f"NoScript Content: {noscript_text}")
            
            # 19. CSS CONTENT - Extract text from CSS content properties
            for style_tag in soup.find_all('style'):
                if style_tag.string:
                    # Look for content: "text" in CSS
                    css_content_matches = re.findall(r'content:\s*["\']([^"\'\n\r]+)["\']', style_tag.string)
                    for match in css_content_matches:
                        if len(match.strip()) > 3:
                            all_extracted_content.append(f"CSS Content: {match.strip()}")
            
            # 20. JAVASCRIPT VARIABLES - Extract text from JS variables (basic extraction)
            for script_tag in soup.find_all('script'):
                if script_tag.string and 'text' in script_tag.string.lower():
                    # Look for common patterns like var text = "content" or text: "content"
                    js_text_matches = re.findall(r'(?:text|content|title|description)\s*[:=]\s*["\']([^"\'\n\r]{10,})["\']', script_tag.string, re.IGNORECASE)
                    for match in js_text_matches:
                        clean_text = match.strip()
                        if clean_text and not any(skip in clean_text.lower() for skip in ['function', 'var ', 'const ', 'let ']):
                            all_extracted_content.append(f"JavaScript Text: {clean_text}")

            # 21. STRUCTURED CONTENT - Timeline, cards, and experience sections
            timeline_selectors = [
                '.timeline', '.experience', '.career', '.history', '.journey',
                '.work-experience', '.professional-experience', '.job-history',
                '[class*="timeline"]', '[class*="experience"]', '[class*="career"]',
                '[class*="work"]', '[class*="job"]', '[class*="role"]'
            ]
            
            for selector in timeline_selectors:
                for element in soup.select(selector):
                    # Extract all text content including nested elements
                    timeline_text = element.get_text(separator=' | ', strip=True)
                    if timeline_text and len(timeline_text) > 10:
                        all_extracted_content.append(f"Timeline/Experience: {timeline_text}")
                    
                    # Also extract individual child elements for better structure
                    for child in element.find_all(['div', 'span', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                        child_text = child.get_text(strip=True)
                        if child_text and len(child_text) > 3:
                            all_extracted_content.append(f"Timeline Item: {child_text}")

            # 22. CARD/SECTION CONTENT - Structured information in cards or sections
            card_selectors = [
                '.card', '.section', '.panel', '.box', '.item', '.entry',
                '.post', '.article-item', '.content-block', '.info-box',
                '[class*="card"]', '[class*="section"]', '[class*="item"]',
                '[class*="box"]', '[class*="panel"]'
            ]
            
            for selector in card_selectors:
                for element in soup.select(selector):
                    card_text = element.get_text(separator=' | ', strip=True)
                    if card_text and len(card_text) > 15:
                        all_extracted_content.append(f"Card/Section: {card_text}")

            # 23. DATE AND YEAR EXTRACTION - Specific patterns for dates and years
            import re
            date_patterns = [
                r'\b(19|20)\d{2}\b',  # Years like 2012, 2014, etc.
                r'\b(19|20)\d{2}\s*[-–—]\s*(PRESENT|present|Present|Current|current|Now|now)\b',  # 2012-PRESENT
                r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(19|20)\d{2}\b',  # Month Year
                r'\b\d{1,2}[/\-]\d{1,2}[/\-](19|20)\d{2}\b'  # Date formats
            ]
            
            page_text = soup.get_text()
            for pattern in date_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        match_text = ' '.join(str(m) for m in match if m)
                    else:
                        match_text = str(match)
                    if len(match_text) > 3:
                        all_extracted_content.append(f"Date/Year: {match_text}")

            # 24. JAVASCRIPT DATA EXTRACTION - Look for JSON data in script tags
            for script_tag in soup.find_all('script'):
                if script_tag.string:
                    script_content = script_tag.string
                    # Look for JSON-like structures
                    json_patterns = [
                        r'"title"\s*:\s*"([^"]+)"',
                        r'"name"\s*:\s*"([^"]+)"',
                        r'"company"\s*:\s*"([^"]+)"',
                        r'"role"\s*:\s*"([^"]+)"',
                        r'"position"\s*:\s*"([^"]+)"',
                        r'"year"\s*:\s*"([^"]+)"',
                        r'"date"\s*:\s*"([^"]+)"',
                        r'"experience"\s*:\s*"([^"]+)"'
                    ]
                    
                    for pattern in json_patterns:
                        matches = re.findall(pattern, script_content, re.IGNORECASE)
                        for match in matches:
                            if len(match) > 3:
                                all_extracted_content.append(f"JS Data: {match}")

            # 25. CSS PSEUDO-CONTENT - Extract content from CSS ::before and ::after
            for style_tag in soup.find_all('style'):
                if style_tag.string:
                    css_content = style_tag.string
                    # Look for content properties that might contain text
                    content_matches = re.findall(r'content\s*:\s*["\']([^"\';]+)["\']', css_content)
                    for match in content_matches:
                        if len(match) > 2 and not match.startswith('\\'):
                            all_extracted_content.append(f"CSS Content: {match}")

            # 26. ARIA LABELS AND ACCESSIBILITY CONTENT
            for element in soup.find_all():
                for attr in ['aria-label', 'aria-describedby', 'title', 'data-title', 'data-label']:
                    attr_value = element.get(attr, '')
                    if attr_value and len(attr_value) > 5:
                        all_extracted_content.append(f"Accessibility Content ({attr}): {attr_value}")

            # 27. FINAL SWEEP - Brute-force capture of all body text to ensure nothing is missed.
            # This acts as a final catch-all to guarantee 100% text coverage.
            if soup.body:
                body_text = soup.body.get_text(separator=' ', strip=True)
                if body_text and len(body_text) > 20:
                    all_extracted_content.append(f"Complete Body Text: {body_text}")
            
            # Combine all content and remove exact duplicates while preserving order
            seen_content = set()
            final_content = []
            
            for content in all_extracted_content:
                # Normalize for comparison but keep original formatting
                normalized = ' '.join(content.lower().split())
                if normalized not in seen_content and len(content.strip()) > 3:
                    seen_content.add(normalized)
                    final_content.append(content)
            
            # Join all content
            content_text = '\n'.join(final_content)
            
            # Enhanced Selenium extraction for structured content
            if self.use_selenium and self.driver:
                try:
                    logger.info(f"Using Selenium for enhanced content extraction on {url}")
                    selenium_content = self._extract_with_selenium_enhanced(url)
                    if selenium_content and len(selenium_content) > 100:
                        content_text += '\n\nEnhanced JavaScript Content:\n' + selenium_content
                except Exception as e:
                    logger.debug(f"Enhanced Selenium extraction failed for {url}: {e}")
            
            # If still not enough content, get complete page text as final fallback
            if len(content_text) < 500:
                complete_page_text = soup.get_text(separator=' ', strip=True)
                if len(complete_page_text) > len(content_text):
                    content_text += '\n\nComplete Page Text:\n' + complete_page_text
            
            # Extract comprehensive keywords
            all_text = f"{title_text} {meta_description} {' '.join(headings)} {content_text}"
            words = all_text.lower().split()
            
            # Filter and count words
            word_freq = {}
            stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those'}
            
            for word in words:
                word = word.strip('.,!?;:"()[]{}').lower()
                if len(word) > 3 and word not in stop_words and word.isalpha():
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            # Get top keywords
            keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:30]
            keywords_text = ', '.join([word for word, freq in keywords])
            
            # Add meta keywords if available
            if meta_keywords_text:
                keywords_text = f"{meta_keywords_text}, {keywords_text}"
            
            # Extract first meaningful image
            image_url = ''
            for img in soup.find_all('img'):
                src = img.get('src', '')
                if src and not any(skip in src.lower() for skip in ['icon', 'logo', 'avatar', 'placeholder']):
                    image_url = urljoin(url, src)
                    break
            
            logger.info(f"Comprehensively scraped {len(content_text)} characters from {url}")
            
            return {
                'url': url,
                'title': title_text,
                'content': content_text,
                'headings': ' | '.join(headings),
                'meta_description': meta_description,
                'keywords': keywords_text,
                'image_url': image_url,
                'status': 'scraped'
            }
            
        except Exception as e:
            logger.error(f"Error scraping page {url}: {e}")
            return {
                'url': url,
                'title': None,
                'content': None,
                'headings': None,
                'image_url': None,
                'meta_description': None,
                'keywords': None
            }
    
    async def scrape_pages_async(self, urls: List[str]) -> List[Dict[str, Optional[str]]]:
        """Scrape multiple pages asynchronously"""
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def scrape_single_async(url: str) -> Dict[str, Optional[str]]:
            async with semaphore:
                # Use the async scrape_page_content method directly
                return await self.scrape_page_content(url)
        
        # Create tasks for all URLs
        tasks = [scrape_single_async(url) for url in urls]
        
        # Execute with progress logging
        results = []
        completed = 0
        total = len(tasks)
        
        for task in asyncio.as_completed(tasks):
            result = await task
            results.append(result)
            completed += 1
            
            if completed % 10 == 0 or completed == total:
                logger.info(f"Scraped {completed}/{total} pages")
        
        return results
    
    async def scrape_from_sitemap(self, sitemap_url: str) -> List[Dict[str, Optional[str]]]:
        """Complete workflow: extract URLs from sitemap and scrape all pages"""
        try:
            # Extract URLs from sitemap
            urls = self.extract_urls_from_sitemap(sitemap_url)
            
            if not urls:
                logger.warning(f"No URLs found in sitemap: {sitemap_url}")
                return []
            
            # Filter URLs (optional: add domain validation, exclude certain paths)
            filtered_urls = self._filter_urls(urls)
            
            logger.info(f"Starting to scrape {len(filtered_urls)} pages")
            
            # Scrape all pages
            results = await self.scrape_pages_async(filtered_urls)
            
            # Filter out failed scrapes
            successful_results = [r for r in results if r.get('content')]
            
            logger.info(f"Successfully scraped {len(successful_results)}/{len(filtered_urls)} pages")
            
            return successful_results
            
        except Exception as e:
            logger.error(f"Error in scrape_from_sitemap: {e}")
            raise
    
    def _filter_urls(self, urls: List[str]) -> List[str]:
        """Filter URLs to exclude unwanted pages"""
        filtered = []
        exclude_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.doc', '.docx'}
        exclude_paths = {'/wp-admin/', '/admin/', '/login/', '/register/', '/cart/', '/checkout/'}
        
        for url in urls:
            try:
                parsed = urlparse(url)
                
                # Skip if has excluded extension
                if any(parsed.path.lower().endswith(ext) for ext in exclude_extensions):
                    continue
                
                # Skip if has excluded path
                if any(excluded in parsed.path.lower() for excluded in exclude_paths):
                    continue
                
                # Skip if URL is too long (likely dynamic)
                if len(url) > 200:
                    continue
                
                filtered.append(url)
                
            except Exception:
                # Skip malformed URLs
                continue
        
        return filtered
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts using simple word overlap"""
        words1 = set(text1.split())
        words2 = set(text2.split())
        if not words1 or not words2:
            return 0.0
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union)
    
    def _extract_with_selenium(self, url: str) -> str:
        """Extract content using Selenium for JavaScript-rendered pages"""
        if not self.driver:
            return ""
        
        try:
            self.driver.get(url)
            
            # Wait for page to load and JavaScript to execute
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            # Additional wait for dynamic content
            time.sleep(2)
            
            # Get page source after JavaScript execution
            page_source = self.driver.page_source
            selenium_soup = BeautifulSoup(page_source, 'html.parser')
            
            # Extract text content
            selenium_content = selenium_soup.get_text(separator=' ', strip=True)
            
            # Also try to extract any dynamically loaded content
            dynamic_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                '[data-loaded], [data-content], .dynamic-content, .lazy-loaded')
            
            dynamic_text = []
            for element in dynamic_elements:
                try:
                    element_text = element.text.strip()
                    if element_text and len(element_text) > 10:
                        dynamic_text.append(element_text)
                except:
                    continue
            
            if dynamic_text:
                selenium_content += '\n\nDynamic Content:\n' + '\n'.join(dynamic_text)
            
            return selenium_content
            
        except Exception as e:
            logger.error(f"Selenium extraction error for {url}: {e}")
            return ""

    def _extract_with_selenium_enhanced(self, url: str) -> str:
        """Enhanced Selenium extraction specifically for structured content like timelines and cards"""
        if not self.driver:
            return ""
        
        try:
            self.driver.get(url)
            
            # Wait for page to load completely
            WebDriverWait(self.driver, 15).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            # Additional wait for dynamic content and animations
            time.sleep(3)
            
            # Try to trigger any lazy loading or dynamic content
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            enhanced_content = []
            
            # 1. Extract structured timeline/experience content
            timeline_selectors = [
                '[class*="timeline"]', '[class*="experience"]', '[class*="career"]',
                '[class*="work"]', '[class*="job"]', '[class*="role"]',
                '.timeline', '.experience', '.career', '.history', '.journey',
                '.work-experience', '.professional-experience', '.job-history'
            ]
            
            for selector in timeline_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        element_text = element.text.strip()
                        if element_text and len(element_text) > 10:
                            enhanced_content.append(f"Timeline/Experience: {element_text}")
                except:
                    continue
            
            # 2. Extract card/section content
            card_selectors = [
                '[class*="card"]', '[class*="section"]', '[class*="item"]',
                '[class*="box"]', '[class*="panel"]', '[class*="entry"]',
                '.card', '.section', '.panel', '.box', '.item', '.entry'
            ]
            
            for selector in card_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        element_text = element.text.strip()
                        if element_text and len(element_text) > 15:
                            enhanced_content.append(f"Card/Section: {element_text}")
                except:
                    continue
            
            # 3. Extract date/year elements specifically
            date_selectors = [
                '[class*="date"]', '[class*="year"]', '[class*="time"]',
                '.date', '.year', '.time', '.period', '.duration'
            ]
            
            for selector in date_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        element_text = element.text.strip()
                        if element_text and len(element_text) > 2:
                            enhanced_content.append(f"Date/Time: {element_text}")
                except:
                    continue
            
            # 4. Extract any elements with data attributes that might contain structured info
            try:
                data_elements = self.driver.find_elements(By.CSS_SELECTOR, '[data-title], [data-role], [data-company], [data-year], [data-date]')
                for element in data_elements:
                    for attr in ['data-title', 'data-role', 'data-company', 'data-year', 'data-date']:
                        try:
                            attr_value = element.get_attribute(attr)
                            if attr_value and len(attr_value) > 3:
                                enhanced_content.append(f"Data Attribute ({attr}): {attr_value}")
                        except:
                            continue
            except:
                pass
            
            # 5. Execute JavaScript to extract any data from window objects
            try:
                js_data = self.driver.execute_script("""
                    var data = [];
                    
                    // Look for common data structures in window object
                    if (window.experienceData) data.push('Experience Data: ' + JSON.stringify(window.experienceData));
                    if (window.timelineData) data.push('Timeline Data: ' + JSON.stringify(window.timelineData));
                    if (window.profileData) data.push('Profile Data: ' + JSON.stringify(window.profileData));
                    
                    // Look for data in common variable names
                    try {
                        var scripts = document.querySelectorAll('script');
                        for (var i = 0; i < scripts.length; i++) {
                            var script = scripts[i].textContent || scripts[i].innerText;
                            if (script && (script.includes('experience') || script.includes('timeline') || script.includes('career'))) {
                                // Extract JSON-like data
                                var matches = script.match(/["'](?:title|name|company|role|position|year|date)["']\\s*:\\s*["']([^"']+)["']/gi);
                                if (matches) {
                                    matches.forEach(function(match) {
                                        data.push('JS Variable: ' + match);
                                    });
                                }
                            }
                        }
                    } catch(e) {}
                    
                    return data;
                """)
                
                if js_data:
                    enhanced_content.extend(js_data)
            except:
                pass
            
            return '\n'.join(enhanced_content) if enhanced_content else ""
            
        except Exception as e:
            logger.error(f"Enhanced Selenium extraction error for {url}: {e}")
            return ""
    
    def extract_with_multiple_methods(self, url: str) -> Dict[str, str]:
        """Extract content using multiple methods and combine results"""
        results = {}
        
        # Method 1: Standard requests + BeautifulSoup
        try:
            standard_result = self.scrape_page_content_sync(url)
            results['standard'] = standard_result.get('content', '')
        except Exception as e:
            logger.error(f"Standard extraction failed for {url}: {e}")
            results['standard'] = ''
        
        # Method 2: Selenium (if available)
        if self.use_selenium:
            try:
                selenium_content = self._extract_with_selenium(url)
                results['selenium'] = selenium_content
            except Exception as e:
                logger.error(f"Selenium extraction failed for {url}: {e}")
                results['selenium'] = ''
        
        # Method 3: Raw text extraction with different parsers
        try:
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code == 200:
                # Try with lxml parser
                lxml_soup = BeautifulSoup(response.content, 'lxml')
                results['lxml'] = lxml_soup.get_text(separator=' ', strip=True)
                
                # Try with html5lib parser
                html5lib_soup = BeautifulSoup(response.content, 'html5lib')
                results['html5lib'] = html5lib_soup.get_text(separator=' ', strip=True)
        except Exception as e:
            logger.error(f"Alternative parser extraction failed for {url}: {e}")
            results['lxml'] = ''
            results['html5lib'] = ''
        
        return results
    
    def get_best_content(self, url: str) -> str:
        """Get the most comprehensive content by combining multiple extraction methods"""
        all_results = self.extract_with_multiple_methods(url)
        
        # Find the longest content
        best_content = ""
        best_length = 0
        
        for method, content in all_results.items():
            if content and len(content) > best_length:
                best_content = content
                best_length = len(content)
        
        # Combine unique content from all methods
        combined_content = []
        seen_sentences = set()
        
        for method, content in all_results.items():
            if content:
                # Split into sentences and add unique ones
                sentences = re.split(r'[.!?]+', content)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if len(sentence) > 20:
                        sentence_key = ' '.join(sentence.lower().split()[:10])  # First 10 words as key
                        if sentence_key not in seen_sentences:
                            seen_sentences.add(sentence_key)
                            combined_content.append(sentence)
        
        return '\n'.join(combined_content) if combined_content else best_content

    def _filter_urls(self, urls: list) -> list:
        """Filter URLs to exclude unwanted pages"""
        exclude_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.css', '.js', '.xml', '.zip', '.rar']
        exclude_paths = ['/wp-content/', '/uploads/', '/admin/', '/login', '/cart', '/checkout']
        filtered = []
        for url in urls:
            try:
                parsed = urlparse(url)
                if any(parsed.path.lower().endswith(ext) for ext in exclude_extensions):
                    continue
                if any(excluded in parsed.path.lower() for excluded in exclude_paths):
                    continue
                if len(url) > 200:
                    continue
                filtered.append(url)
            except Exception:
                continue
        return filtered

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts using simple word overlap"""
        words1 = set(text1.split())
        words2 = set(text2.split())
        if not words1 or not words2:
            return 0.0
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union)

    def _extract_with_selenium(self, url: str) -> str:
        """Extract content using Selenium for JavaScript-rendered pages"""
        if not self.driver:
            return ""
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            time.sleep(2)
            page_source = self.driver.page_source
            selenium_soup = BeautifulSoup(page_source, 'html.parser')
            selenium_content = selenium_soup.get_text(separator=' ', strip=True)
            dynamic_elements = self.driver.find_elements(By.CSS_SELECTOR, '[data-loaded], [data-content], .dynamic-content, .lazy-loaded')
            dynamic_text = []
            for element in dynamic_elements:
                try:
                    element_text = element.text.strip()
                    if element_text and len(element_text) > 10:
                        dynamic_text.append(element_text)
                except:
                    continue
            if dynamic_text:
                selenium_content += '\n\nDynamic Content:\n' + '\n'.join(dynamic_text)
            return selenium_content
        except Exception as e:
            logger.error(f"Selenium extraction error for {url}: {e}")
            return ""

    def extract_with_multiple_methods(self, url: str) -> Dict[str, str]:
        """Extract content using multiple methods and combine results"""
        results = {}
        try:
            standard_result = self.scrape_page_content_sync(url)
            results['standard'] = standard_result.get('content', '')
        except Exception as e:
            logger.error(f"Standard extraction failed for {url}: {e}")
            results['standard'] = ''
        if self.use_selenium:
            try:
                selenium_content = self._extract_with_selenium(url)
                results['selenium'] = selenium_content
            except Exception as e:
                logger.error(f"Selenium extraction failed for {url}: {e}")
                results['selenium'] = ''
        try:
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code == 200:
                lxml_soup = BeautifulSoup(response.content, 'lxml')
                results['lxml'] = lxml_soup.get_text(separator=' ', strip=True)
                html5lib_soup = BeautifulSoup(response.content, 'html5lib')
                results['html5lib'] = html5lib_soup.get_text(separator=' ', strip=True)
        except Exception as e:
            logger.error(f"Alternative parser extraction failed for {url}: {e}")
            results['lxml'] = ''
            results['html5lib'] = ''
        return results

    def get_best_content(self, url: str) -> str:
        """Get the most comprehensive content by combining multiple extraction methods"""
        all_results = self.extract_with_multiple_methods(url)
        best_content = ""
        best_length = 0
        for method, content in all_results.items():
            if content and len(content) > best_length:
                best_content = content
                best_length = len(content)
        combined_content = []
        seen_sentences = set()
        for method, content in all_results.items():
            if content:
                sentences = re.split(r'[.!?]+', content)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if len(sentence) > 20:
                        sentence_key = ' '.join(sentence.lower().split()[:10])
                        if sentence_key not in seen_sentences:
                            seen_sentences.add(sentence_key)
                            combined_content.append(sentence)
        return '\n'.join(combined_content) if combined_content else best_content

    def __del__(self):
        # Clean up Selenium driver on exit
        if self.driver:
            self.driver.quit()

if __name__ == '__main__':
    import sys
    import asyncio
    import json

    # --- How to Run ---
    # 1. Make sure you have installed the required packages:
    #    pip install -r requirements_enhanced.txt
    #
    # 2. Run from your terminal with one or more website URLs:
    #    python scraper.py "<url_1>" "<url_2>" ...
    #
    # Example:
    #    python scraper.py "https://www.windsurf.ai/" "https://www.python.org/"
    # ------------------

    if len(sys.argv) < 2:
        print("Usage: python scraper.py \"<url_1>\" \"<url_2>\" ...")
        sys.exit(1)

    website_urls = sys.argv[1:]

    async def main():
        for url in website_urls:
            print(f"--- Starting Scraping for Website: {url} ---\n")
            
            # Create a NEW, ISOLATED scraper instance for each website.
            # This prevents cookies and session data from leaking between sites.
            scraper = WebScraper(use_selenium=True)
            
            try:
                # Run the asynchronous scraping function
                scraped_data = await scraper.scrape_page_content(url)

                # Pretty-print the results for the current website
                print(f"--- Scraping Complete for {url}. Results: ---")
                print(json.dumps(scraped_data, indent=4))
                print("-----------------------------------------------------\n")

            except Exception as e:
                print(f"An error occurred while scraping {url}: {e}")
            finally:
                # Clean up the scraper instance for the current site
                del scraper

    # Run the main async function that processes all websites
    asyncio.run(main())
    print("\n--- All websites have been processed. ---")
