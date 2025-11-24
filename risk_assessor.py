"""
Operational Risk Assessor - Backend Logic
All functionality consolidated in one file: Excel parsing, internet search, LLM integration, risk assessment
"""

import os
import re
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse, urljoin
import pandas as pd
import requests
from bs4 import BeautifulSoup

# Internet search libraries (optional imports)
try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False

try:
    from googlesearch import search as google_search
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# ==================== EXCEL PARSING ====================

def parse_excel(file) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    Parse Excel file and auto-detect columns.
    Accepts either file path (str) or file object.
    Returns: (DataFrame, column_mapping) where column_mapping identifies key columns
    """
    # Handle both file paths and file objects
    if isinstance(file, str):
        df = pd.read_excel(file)
    else:
        df = pd.read_excel(file)
    
    # Auto-detect columns
    column_mapping = {}
    columns_lower = {col.lower(): col for col in df.columns}
    
    # Find company column
    for key in ['company', 'company name', 'company_name', 'name']:
        if key in columns_lower:
            column_mapping['company'] = columns_lower[key]
            break
    
    # Find comments column
    for key in ['comment', 'comments', 'notes', 'note']:
        if key in columns_lower:
            column_mapping['comments'] = columns_lower[key]
            break
    
    # Find risk rating column
    for key in ['risk', 'risk rating', 'risk_rating', 'rating', 'risk_level', 'risk_level']:
        if key in columns_lower:
            column_mapping['risk_rating'] = columns_lower[key]
            break
    
    # Identify questionnaire columns (all other columns except identified ones)
    identified = set(column_mapping.values())
    questionnaire_cols = [col for col in df.columns if col not in identified]
    column_mapping['questionnaire'] = questionnaire_cols
    
    return df, column_mapping


# ==================== INTERNET SEARCH ====================

# Proxy configuration
HTTP_PROXY = os.getenv("HTTP_PROXY")
HTTPS_PROXY = os.getenv("HTTPS_PROXY")
PROXIES = {}
if HTTP_PROXY:
    PROXIES["http"] = HTTP_PROXY
if HTTPS_PROXY:
    PROXIES["https"] = HTTPS_PROXY

REQUEST_TIMEOUT = 15
VERIFY_SSL = True

BLOCKED_DOMAINS = [
    "linkedin.com", "wikipedia.org", "bloomberg.com", "reuters.com",
    "moneycontrol.com", "economictimes.com", "facebook.com", "twitter.com", "x.com"
]


def is_probably_official_site(url: str, company_name: str) -> bool:
    """Check if URL looks like official company website"""
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    
    if any(block in host for block in BLOCKED_DOMAINS):
        return False
    
    host_clean = host.replace("www.", "")
    key = company_name.lower().split()[0]
    return key in host_clean


def choose_official_url(results: List[Dict], company_name: str) -> Tuple[Optional[str], List[Dict]]:
    """Select best official URL from search results"""
    official_candidates = [r for r in results if is_probably_official_site(r.get("href", ""), company_name)]
    if official_candidates:
        return official_candidates[0].get("href"), official_candidates
    elif results:
        return results[0].get("href"), results
    else:
        return None, []


def find_risk_pages(base_url: str, soup: BeautifulSoup) -> List[str]:
    """Find links to risk-related pages from the main website"""
    risk_keywords = ['risk', 'compliance', 'security', 'governance', 'audit', 'regulatory', 'operational', 'safety', 'control']
    risk_links = []
    
    # Look for links containing risk keywords
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        text = link.get_text().lower()
        href_lower = href.lower()
        
        if any(keyword in href_lower or keyword in text for keyword in risk_keywords):
            if href.startswith('/'):
                full_url = urljoin(base_url, href)
            elif href.startswith('http'):
                full_url = href
            else:
                continue
            
            if full_url not in risk_links and full_url.startswith('http'):
                risk_links.append(full_url)
    
    return risk_links[:5]  # Limit to 5 risk pages


def fetch_url_text(url: str, focus_risk: bool = True) -> str:
    """Fetch and extract text from URL, focusing on risk-related content"""
    try:
        resp = requests.get(url, proxies=PROXIES, timeout=REQUEST_TIMEOUT, verify=VERIFY_SSL, 
                          headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Remove unwanted elements
        for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
            tag.extract()
        
        if focus_risk:
            # Extract risk-related content
            risk_keywords = ['risk', 'compliance', 'security', 'governance', 'audit', 'regulatory', 'operational', 'safety', 'control', 'vulnerability', 'threat']
            risk_content = []
            
            # Get main content areas
            main_content = soup.find_all(['main', 'article', 'section']) or soup.find_all('div', class_=lambda x: x and any(word in x.lower() for word in ['content', 'main', 'body']))
            
            if main_content:
                for section in main_content:
                    text = section.get_text(separator="\n", strip=True)
                    text_lower = text.lower()
                    if any(keyword in text_lower for keyword in risk_keywords):
                        # Extract relevant paragraphs
                        for p in section.find_all(['p', 'li', 'div']):
                            p_text = p.get_text(strip=True)
                            if p_text and len(p_text) > 20:  # Skip very short text
                                p_lower = p_text.lower()
                                if any(keyword in p_lower for keyword in risk_keywords):
                                    risk_content.append(p_text)
            
            # If no risk content found in main sections, search all text
            if not risk_content:
                for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'p', 'li']):
                    text = tag.get_text(strip=True)
                    if text and len(text) > 20:
                        text_lower = text.lower()
                        if any(keyword in text_lower for keyword in risk_keywords):
                            risk_content.append(text)
            
            if risk_content:
                return "\n\n".join(risk_content[:30])  # Top 30 risk-related sections
        
        # Fallback: extract all meaningful text
        text = soup.get_text(separator="\n")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip() and len(ln.strip()) > 10]
        return "\n".join(lines[:100])  # Limit to 100 lines
        
    except Exception as e:
        return f"Error fetching {url}: {str(e)}"


def search_company_ddgs(company_name: str, max_results: int = 8) -> List[Dict]:
    """Search using DuckDuckGo (ddgs)"""
    if not DDGS_AVAILABLE:
        return []
    
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(company_name, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "href": r.get("href", ""),
                    "body": r.get("body", ""),
                    "tool": "DDGS"  # Track tool used
                })
    except Exception as e:
        print(f"DDGS search error: {e}")
    
    return results


def search_company_google(company_name: str, max_results: int = 8) -> List[Dict]:
    """Search using googlesearch-python"""
    if not GOOGLE_AVAILABLE:
        return []
    
    results = []
    try:
        for url in google_search(company_name, num=max_results, stop=max_results, pause=2):
            results.append({
                "title": "",
                "href": url,
                "body": "",
                "tool": "Google"  # Track tool used
            })
    except Exception as e:
        print(f"Google search error: {e}")
    
    return results


def search_company_searxng(company_name: str, searxng_url: str, max_results: int = 8) -> List[Dict]:
    """Search using self-hosted SearXNG"""
    results = []
    try:
        params = {"q": company_name, "format": "json"}
        resp = requests.get(f"{searxng_url}/search", params=params, proxies=PROXIES, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        
        for item in data.get("results", [])[:max_results]:
            results.append({
                "title": item.get("title", ""),
                "href": item.get("url", ""),
                "body": item.get("content", ""),
                "tool": "SearXNG"  # Track tool used
            })
    except Exception as e:
        print(f"SearXNG search error: {e}")
    
    return results


def search_company_playwright(company_name: str, max_results: int = 8) -> List[Dict]:
    """Search using Playwright headless browser"""
    if not PLAYWRIGHT_AVAILABLE:
        return []
    
    results = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://duckduckgo.com/")
            page.fill("input[name='q']", company_name)
            page.press("input[name='q']", "Enter")
            page.wait_for_timeout(3000)
            
            links = page.query_selector_all("a.result__a")
            for link in links[:max_results]:
                href = link.get_attribute("href")
                title = link.inner_text()
                if href:
                    results.append({
                        "title": title,
                        "href": href,
                        "body": "",
                        "tool": "Playwright"  # Track tool used
                    })
            browser.close()
    except Exception as e:
        print(f"Playwright search error: {e}")
    
    return results


def search_company_combined(company_name: str, methods: List[str] = None, max_results: int = 12, searxng_url: Optional[str] = None) -> List[Dict]:
    """Combine results from ALL available search methods"""
    if methods is None:
        # Use all available methods by default
        methods = []
        if DDGS_AVAILABLE:
            methods.append('ddgs')
        if GOOGLE_AVAILABLE:
            methods.append('google')
        if PLAYWRIGHT_AVAILABLE:
            methods.append('playwright')
        if searxng_url:
            methods.append('searxng')
    
    all_results = []
    seen_urls = set()
    errors = []
    
    # Try all methods and accumulate results
    for method in methods:
        try:
            if method == 'ddgs' and DDGS_AVAILABLE:
                results = search_company_ddgs(company_name, max_results)
            elif method == 'google' and GOOGLE_AVAILABLE:
                results = search_company_google(company_name, max_results)
            elif method == 'searxng' and searxng_url:
                results = search_company_searxng(company_name, searxng_url, max_results)
            elif method == 'playwright' and PLAYWRIGHT_AVAILABLE:
                results = search_company_playwright(company_name, max_results)
            else:
                continue
            
            # Add unique results
            for r in results:
                url = r.get("href", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(r)
        except Exception as e:
            errors.append(f"{method}: {str(e)}")
            continue
    
    if errors:
        print(f"Search errors (non-critical): {', '.join(errors)}")
    
    return all_results[:max_results * 2]  # Return more results since we're combining


def search_and_fetch_company_info(company_name: str, search_method: str = 'combined', searxng_url: Optional[str] = None, max_results: int = 10) -> Tuple[str, List[Dict[str, str]]]:
    """
    Search for company using ALL available methods and fetch website content.
    By default uses 'combined' which runs all available search methods.
    Actually scrapes the websites and looks for risk-related pages.
    Returns: (web_text, url_details) where url_details contains url and source info
    """
    # Perform search - default to combined (all methods)
    if search_method == 'combined' or search_method == 'all':
        # Use all available methods
        results = search_company_combined(company_name, methods=None, max_results=max_results, searxng_url=searxng_url)
    elif search_method == 'ddgs':
        results = search_company_ddgs(company_name, max_results)
    elif search_method == 'google':
        results = search_company_google(company_name, max_results)
    elif search_method == 'searxng':
        if searxng_url:
            results = search_company_searxng(company_name, searxng_url, max_results)
        else:
            results = []
    elif search_method == 'playwright':
        results = search_company_playwright(company_name, max_results)
    else:
        # Default: try combined
        results = search_company_combined(company_name, methods=None, max_results=max_results, searxng_url=searxng_url)
    
    if not results:
        return "", []
    
    # Choose official URL and fetch content
    main_url, all_candidates = choose_official_url(results, company_name)
    url_details = []
    web_text_parts = []
    
    # Fetch main URL and look for risk-related pages
    if main_url:
        try:
            # First, get the main page
            resp = requests.get(main_url, proxies=PROXIES, timeout=REQUEST_TIMEOUT, verify=VERIFY_SSL,
                              headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Scrape main page for risk content
            main_result = next((r for r in all_candidates if r.get("href") == main_url), {})
            main_text = fetch_url_text(main_url, focus_risk=True)
            if main_text and "Error" not in main_text:
                web_text_parts.append(f"=== MAIN WEBSITE: {main_url} ===\n{main_text}")
                url_details.append({
                    "url": main_url, 
                    "type": "primary", 
                    "title": main_result.get("title", "Main Website"),
                    "tool": main_result.get("tool", "Unknown"),
                    "content": main_text[:500]  # Store snippet for table
                })
            
            # Find and scrape risk-related pages from the main site
            risk_pages = find_risk_pages(main_url, soup)
            for risk_url in risk_pages[:3]:  # Limit to 3 risk pages
                try:
                    risk_text = fetch_url_text(risk_url, focus_risk=True)
                    if risk_text and "Error" not in risk_text and len(risk_text) > 100:
                        web_text_parts.append(f"\n=== RISK PAGE: {risk_url} ===\n{risk_text[:4000]}")
                        url_details.append({
                            "url": risk_url, 
                            "type": "risk_page", 
                            "title": "Risk/Compliance Page",
                            "tool": main_result.get("tool", "Scraped"),
                            "content": risk_text[:500]  # Store snippet
                        })
                except:
                    pass
        except Exception as e:
            # Fallback: try simple fetch
            main_result = next((r for r in all_candidates if r.get("href") == main_url), {})
            main_text = fetch_url_text(main_url, focus_risk=True)
            if main_text and "Error" not in main_text:
                web_text_parts.append(f"=== MAIN WEBSITE: {main_url} ===\n{main_text}")
                url_details.append({
                    "url": main_url, 
                    "type": "primary", 
                    "title": "Main Website",
                    "tool": main_result.get("tool", "Unknown"),
                    "content": main_text[:500]
                })
    
    # Fetch additional URLs (news, reports) for risk context - scrape more sources
    scraped_count = 0
    for r in all_candidates[1:10]:  # Try more sources
        if scraped_count >= 5:  # Limit to 5 additional sources
            break
        url = r.get("href", "")
        if url and url != main_url:
            try:
                additional_text = fetch_url_text(url, focus_risk=True)
                if additional_text and "Error" not in additional_text and len(additional_text) > 100:
                    web_text_parts.append(f"\n=== ADDITIONAL SOURCE: {url} ===\n{additional_text[:3000]}")
                    url_details.append({
                        "url": url, 
                        "type": "additional", 
                        "title": r.get("title", "Additional Source"),
                        "tool": r.get("tool", "Unknown"),
                        "content": additional_text[:500]  # Store snippet
                    })
                    scraped_count += 1
            except Exception as e:
                # Log but continue
                print(f"Error scraping {url}: {e}")
                continue
    
    web_text = "\n\n".join(web_text_parts)
    
    # Ensure we have actual content
    if not web_text or len(web_text.strip()) < 50:
        return "", url_details
    
    return web_text[:12000], url_details  # Increased limit for accumulated content


# ==================== LLM INTEGRATION (vLLM) ====================

def call_vllm(prompt: str, model: str, api_base: str, max_tokens: int = 2048) -> str:
    """Call vLLM server using /completions endpoint"""
    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "temperature": 0.2,  # Lower temperature for more consistent JSON
            "max_tokens": max_tokens,
            "top_p": 0.9
        }
        
        response = requests.post(
            f"{api_base}/completions",
            json=payload,
            timeout=180,
            proxies=PROXIES
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["text"].strip()
    except Exception as e:
        return f"Error calling vLLM: {str(e)}"


def build_risk_prompt(company_name: str, questionnaire_text: str, comments_text: str, web_text: str, current_rating: str, assessment_type: str) -> str:
    """Build prompt for risk assessment"""
    
    if assessment_type == "questionnaire":
        prompt = f"""You are an operational risk expert. Analyze the company's questionnaire responses and determine if the current risk rating is correct.

Company: {company_name}
Current Risk Rating: {current_rating}

QUESTIONNAIRE RESPONSES:
{questionnaire_text}

Analyze the responses and determine:
1. Is the current risk rating ({current_rating}) correct based on the questionnaire responses?
2. What should be the recommended risk rating? (High/Medium/Low)
3. Provide a clear explanation with bullet points.

Respond in JSON format:
{{
    "is_correct": true/false,
    "recommended_rating": "High/Medium/Low",
    "explanation": "Detailed explanation with bullet points"
}}"""
    
    elif assessment_type == "comments":
        prompt = f"""You are an operational risk expert. Analyze the comments about the company and determine if the current risk rating is correct.

Company: {company_name}
Current Risk Rating: {current_rating}

COMMENTS:
{comments_text}

Analyze the comments and determine:
1. Is the current risk rating ({current_rating}) correct based on the comments?
2. What should be the recommended risk rating? (High/Medium/Low)
3. Provide a clear explanation with bullet points.

Respond in JSON format:
{{
    "is_correct": true/false,
    "recommended_rating": "High/Medium/Low",
    "explanation": "Detailed explanation with bullet points"
}}"""
    
    else:  # internet
        prompt = f"""You are an operational risk expert. Analyze the scraped website content to validate the current risk rating.

Company: {company_name}
Current Risk Rating: {current_rating}

INTERNAL CONTEXT:
- Comments: {comments_text if comments_text else "None provided"}

SCRAPED WEBSITE CONTENT (from company website and public sources):
{web_text[:10000]}

TASK:
1. Extract operational risk information from the scraped content (risk management, compliance, security, governance, incidents, vulnerabilities)
2. Determine if current rating ({current_rating}) is correct based on the website content
3. Recommend the correct rating: High, Medium, or Low
4. Explain your reasoning with specific references to the scraped content

IMPORTANT: 
- You MUST provide a specific rating (High/Medium/Low), NOT "Unknown"
- Quote specific text from the scraped content to support your assessment
- If website content is insufficient, state that clearly but still provide a rating based on available information

Respond ONLY with valid JSON (no markdown, no code blocks):
{{
    "is_correct": true or false,
    "recommended_rating": "High" or "Medium" or "Low",
    "explanation": "Detailed explanation with: 1) Internal Data Analysis, 2) External Web Data Analysis (with quotes from scraped content), 3) Comprehensive Assessment explaining why rating is correct/incorrect",
    "external_signals": "Key risk signals found with specific quotes from the website",
    "risk_factors_found": "List of specific risk factors identified from the scraped content"
}}"""
    
    return prompt


def assess_risk_from_questionnaire(company_name: str, questionnaire_data: Dict, current_rating: str, vllm_config: Dict) -> Dict:
    """Assess risk based on questionnaire answers"""
    # Format questionnaire data as text
    questionnaire_text = "\n".join([f"{k}: {v}" for k, v in questionnaire_data.items() if pd.notna(v)])
    
    prompt = build_risk_prompt(company_name, questionnaire_text, "", "", current_rating, "questionnaire")
    response = call_vllm(prompt, vllm_config["model"], vllm_config["api_base"])
    
    # Parse JSON response
    try:
        import json
        # Extract JSON from response
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = {"is_correct": False, "recommended_rating": current_rating, "explanation": response}
    except:
        result = {"is_correct": False, "recommended_rating": current_rating, "explanation": response}
    
    result["links"] = []
    return result


def assess_risk_from_comments(company_name: str, comments: str, current_rating: str, vllm_config: Dict) -> Dict:
    """Assess risk based on comments"""
    comments_text = str(comments) if pd.notna(comments) else ""
    
    prompt = build_risk_prompt(company_name, "", comments_text, "", current_rating, "comments")
    response = call_vllm(prompt, vllm_config["model"], vllm_config["api_base"])
    
    # Parse JSON response
    try:
        import json
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = {"is_correct": False, "recommended_rating": current_rating, "explanation": response}
    except:
        result = {"is_correct": False, "recommended_rating": current_rating, "explanation": response}
    
    result["links"] = []
    return result


def assess_risk_from_internet(company_name: str, questionnaire_data: Dict, comments: str, web_data: str, current_rating: str, url_details: List[Dict], vllm_config: Dict) -> Dict:
    """Assess risk based on internet search"""
    comments_text = str(comments) if pd.notna(comments) else ""
    
    # Check if we actually have web data
    if not web_data or len(web_data.strip()) < 50:
        return {
            "is_correct": False,
            "recommended_rating": current_rating,
            "explanation": "Unable to scrape sufficient website content for assessment. Please check if the company website is accessible.",
            "external_signals": "No web data available",
            "risk_factors_found": "None - website content not available",
            "links": [f"{ud['url']} ({ud.get('title', 'No title')})" for ud in url_details],
            "url_details": url_details
        }
    
    prompt = build_risk_prompt(company_name, "", comments_text, web_data, current_rating, "internet")
    response = call_vllm(prompt, vllm_config["model"], vllm_config["api_base"], max_tokens=2048)
    
    # Parse JSON response with better error handling
    try:
        import json
        # Try to extract JSON - handle both wrapped and unwrapped JSON
        response_clean = response.strip()
        if response_clean.startswith("```json"):
            response_clean = response_clean[7:]
        if response_clean.startswith("```"):
            response_clean = response_clean[3:]
        if response_clean.endswith("```"):
            response_clean = response_clean[:-3]
        response_clean = response_clean.strip()
        
        # Try to find JSON object
        json_match = re.search(r'\{.*\}', response_clean, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            # Ensure required fields exist
            if "recommended_rating" not in result or result["recommended_rating"] == "Unknown":
                result["recommended_rating"] = current_rating
            if "is_correct" not in result:
                result["is_correct"] = False
        else:
            # Fallback: try to parse entire response as JSON
            result = json.loads(response_clean)
    except json.JSONDecodeError as e:
        # If JSON parsing fails, create a structured response from the text
        result = {
            "is_correct": False,
            "recommended_rating": current_rating,
            "explanation": f"LLM response parsing issue. Raw response: {response[:500]}",
            "external_signals": "Unable to parse assessment",
            "risk_factors_found": "Assessment parsing failed"
        }
    except Exception as e:
        result = {
            "is_correct": False,
            "recommended_rating": current_rating,
            "explanation": f"Error in assessment: {str(e)}. Response: {response[:500]}",
            "external_signals": "Error occurred",
            "risk_factors_found": "Assessment error"
        }
    
    # Add URL details
    result["links"] = [f"{ud['url']} ({ud.get('title', 'No title')})" for ud in url_details[:5]]
    result["url_details"] = url_details[:5]
    return result


# ==================== RISK ASSESSMENT ORCHESTRATION ====================

def run_assessment(
    company_name: str,
    questionnaire_data: Dict,
    comments: str,
    current_rating: str,
    assessment_types: List[str],
    search_method: str,
    searxng_url: Optional[str],
    vllm_config: Dict
) -> Dict[str, Any]:
    """
    Main function to run all assessments.
    Returns: Dictionary with results for each assessment type
    """
    results = {
        "company_name": company_name,
        "current_rating": current_rating,
        "assessments": {}
    }
    
    # Get internet data if needed
    web_data = ""
    url_details = []
    if "internet" in assessment_types:
        web_data, url_details = search_and_fetch_company_info(company_name, search_method, searxng_url)
    
    # Run each assessment type
    if "questionnaire" in assessment_types:
        results["assessments"]["questionnaire"] = assess_risk_from_questionnaire(
            company_name, questionnaire_data, current_rating, vllm_config
        )
    
    if "comments" in assessment_types:
        results["assessments"]["comments"] = assess_risk_from_comments(
            company_name, comments, current_rating, vllm_config
        )
    
    if "internet" in assessment_types:
        results["assessments"]["internet"] = assess_risk_from_internet(
            company_name, questionnaire_data, comments, web_data, current_rating, url_details, vllm_config
        )
    
    return results

