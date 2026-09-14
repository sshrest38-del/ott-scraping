"""
OTT Poster API - Vercel Serverless Function
Netflix, SonyLIV, Apple TV + URL support
Usage:
  /api/poster?q=Money+Heist          → search by name
  /api/poster?url=https://netflix.com/title/81040344  → extract from URL
"""

import json
import re
import base64
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler

try:
    import requests
except ImportError:
    requests = None

try:
    from curl_cffi import requests as cffi_requests
except Exception:
    cffi_requests = None


def get_req():
    return cffi_requests if cffi_requests else requests


# ==================== NETFLIX ====================

GRAPHQL_URL = "https://web.prod.cloud.netflix.com/graphql"
MINI_MODAL_ID = "96c87721-2e20-416f-aa6f-87c8a889c955"
MINI_MODAL_VERSION = 102
ARTWORK_CONTEXT = "eyJrLnR5cGUiOiJ3aW5kb3dlZGNvbWluZ3Nvb24iLCJrLnRpbWVXaW5kb3ciOiJuZXh0d2VlayJ9"

NETFLIX_IDS = {
    "squid game": "81040344", "stranger things": "80057281",
    "money heist": "80192098", "the witcher": "80100172",
    "sacred games": "80115328", "killer soup": "81241510",
    "heeramandi": "81122198", "delhi crime": "81173710",
    "mismatched": "81317570", "maharani": "81445140",
    "kohrra": "81716406", "ic 814": "81768236",
    "maamla legal hai": "81672498", "she": "81080351",
    "jamtaara": "81197500", "ghoul": "81028792",
    "lust stories": "81028792", "article 15": "81175834",
    "guns & gulaabs": "81699082", "kaala paani": "81713616",
    "dahaad": "81653684", "scam 2003": "81785722",
    "masaba masaba": "81137034", "the family man": "81260680",
    "nobody": "81743330", "klass": "81774304",
    "trial": "81677700", "dupahiya": "81616942",
    "nirmal pathak": "81615608", "ghar waapsi": "81626760",
    "yeh kaali kaali ankhein": "81508136",
    "panchayat": "81479512", "mirzapur": "81032489",
    "farzi": "81695218", "guns and gulaabs": "81699082",
    "khakee": "81724320", "jubilee": "81635720",
}


def netflix_graphql(video_id):
    """Netflix GraphQL API se poster fetch karo by video ID"""
    try:
        payload = {
            "operationName": "MiniModalQuery",
            "variables": {
                "opaqueImageFormat": "WEBP", "transparentImageFormat": "WEBP",
                "videoMerchEnabled": True, "fetchPromoVideoOverride": False,
                "hasPromoVideoOverride": False, "promoVideoId": 0,
                "videoMerchContext": "BROWSE", "isLiveEpisodic": False,
                "artworkContext": {"groupLoc": ARTWORK_CONTEXT},
                "textEvidenceUiContext": "BOB",
                "unifiedEntityIds": [f"Video:{video_id}"],
            },
            "extensions": {"persistedQuery": {"id": MINI_MODAL_ID, "version": MINI_MODAL_VERSION}},
        }

        req = get_req()
        r = req.post(GRAPHQL_URL, json=payload, timeout=15)
        r.raise_for_status()
        entities = r.json().get("data", {}).get("unifiedEntities", [])
        if not entities or not entities[0]:
            return None

        entity = entities[0]
        title = entity.get("title", "")
        year = entity.get("latestYear", "")
        boxart = entity.get("boxartHighRes", {})
        url = boxart.get("url", "") if isinstance(boxart, dict) else ""

        if not url:
            return None

        return {"title": title, "year": year, "poster_url": url, "source": "netflix"}
    except Exception:
        return None


def netflix_poster(query):
    """Netflix - search by name"""
    vid = NETFLIX_IDS.get(query.lower().strip())
    if not vid:
        return None
    return netflix_graphql(vid)


def netflix_from_url(url):
    """Netflix URL se video ID extract karo"""
    # https://www.netflix.com/title/81040344
    # https://www.netflix.com/watch/81040344
    match = re.search(r"netflix\.com/(?:title|watch)/(\d+)", url)
    if match:
        return netflix_graphql(match.group(1))
    return None


# ==================== SONYLIV ====================

def sonyliv_poster(query):
    """SonyLIV - search by name"""
    try:
        r = get_req().get(
            "https://apiv3.sonyliv.com/AGL/4.8/A/ENG/WEB/IN/HR/TRAY/SEARCH",
            params={"query": query, "from": "0", "to": "10", "app_version": "3.10.3"},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
            },
            timeout=15
        )
        if r.status_code != 200:
            return None

        data = r.json()
        containers = data.get("resultObj", {}).get("containers", [])
        if not containers:
            return None

        tabs = containers[0].get("containers", [])
        if not tabs:
            return None

        assets = tabs[0].get("assets", [])
        if not assets:
            return None

        asset = assets[0]
        metadata = asset.get("metadata", {})
        title = metadata.get("title", "") or metadata.get("title_hin", "") or query

        query_lower = query.lower().strip()
        title_lower = title.lower().strip()
        if query_lower not in title_lower and title_lower not in query_lower:
            return None

        emf = metadata.get("emfAttributes", {})
        poster = emf.get("apv_poster_art", "") or emf.get("apv_cover_art", "") or emf.get("img_cover_3840_2160", "")

        if poster:
            return {"title": title, "poster_url": poster, "source": "sonyliv"}
    except Exception:
        pass
    return None


def sonyliv_from_url(url):
    """SonyLIV URL se content ID extract karo"""
    # https://www.sonyliv.com/detail/1700000292
    match = re.search(r"sonyliv\.com/detail/(\d+)", url)
    if match:
        cid = match.group(1)
        try:
            r = get_req().get(
                "https://apiv3.sonyliv.com/AGL/4.8/A/ENG/WEB/IN/HR/TRAY/SEARCH",
                params={"query": cid, "from": "0", "to": "10", "app_version": "3.10.3"},
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
                timeout=15
            )
            if r.status_code == 200:
                data = r.json()
                containers = data.get("resultObj", {}).get("containers", [])
                if containers:
                    tabs = containers[0].get("containers", [])
                    if tabs:
                        assets = tabs[0].get("assets", [])
                        if assets:
                            for asset in assets:
                                if str(asset.get("contentId", "")) == cid:
                                    metadata = asset.get("metadata", {})
                                    title = metadata.get("title", "")
                                    emf = metadata.get("emfAttributes", {})
                                    poster = emf.get("apv_poster_art", "") or emf.get("apv_cover_art", "")
                                    if poster:
                                        return {"title": title, "poster_url": poster, "source": "sonyliv"}
        except Exception:
            pass
    return None


# ==================== AMAZON PRIME VIDEO ====================

def prime_from_url(url):
    """Prime Video URL se poster fetch karo"""
    # https://www.primevideo.com/detail/0LC3EGV2SMFRLHNF/...
    # https://www.amazon.com/dp/B0...
    match = re.search(r"primevideo\.com/detail/([A-Z0-9]+)", url)
    if not match:
        match = re.search(r"amazon\.(?:com|in)/dp/([A-Z0-9]+)", url)
    if match:
        did = match.group(1)
        try:
            api = f"https://www.primevideo.com/detail/{did}?dvWebAppClientVersion=1.0.125203.0"
            r = get_req().get(api, headers={
                "Accept": "application/json", "User-Agent": "Mozilla/5.0",
                "x-requested-with": "WebAppSPA"
            }, timeout=10)
            if r.status_code == 200:
                data = r.json()
                page = data.get("body", [])
                if page:
                    hd = page.get("atf", {}).get("state", {}).get("detail", {}).get("headerDetail", {})
                    for k, v in hd.items():
                        title = v.get("title", "")
                        year = v.get("releaseYear", "")
                        images = v.get("images", {})
                        poster = images.get("heroshot", "") or images.get("covershot", "")
                        if poster:
                            return {"title": f"{title} ({year})" if year else title, "poster_url": poster, "source": "prime_video"}
        except Exception:
            pass
    return None


# ==================== ZEE5 ====================

ZEE5_CDN = "https://akamaividz2.zee5.com/image/upload/resources"


def zee5_token():
    HEADER = {"alg": "HS256", "typ": "JWT"}
    PAYLOAD = {"platform_code": "Web@$!t38712", "product_code": "zee5@975", "ttl": 86400000}
    SIGNATURE = "1jxJ9Qw1PSebtfiuaE3vrSJPyk5aBnADucdU7bPP6gI"
    now = datetime.now(timezone.utc)
    PAYLOAD["issuedAt"] = now.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    PAYLOAD["iat"] = int(now.timestamp())
    h = base64.urlsafe_b64encode(json.dumps(HEADER, separators=(",", ":")).encode()).decode().rstrip("=")
    p = base64.urlsafe_b64encode(json.dumps(PAYLOAD, separators=(",", ":")).encode()).decode().rstrip("=")
    return f"{h}.{p}.{SIGNATURE}"


def zee5_from_url(url):
    """ZEE5 URL se poster fetch karo"""
    # https://www.zee5.com/tv-shows/details/some-show/0-0-35166
    # https://www.zee5.com/movies/details/some-movie/0-0-12345
    match = re.search(r"zee5\.com/(?:tv-shows|movies)/details/[^/]+/(\d+-\d+-\d+)", url)
    if match:
        cid = match.group(1)
        try:
            token = zee5_token()
            for ctype in ["tvshow", "movie"]:
                api = f"https://gwapi.zee5.com/content/{ctype}/{cid}?translation=en&country=IN"
                r = get_req().get(api, headers={"User-Agent": "Mozilla/5.0", "x-access-token": token}, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    title = data.get("title", "")
                    images = data.get("image", {})
                    banner = images.get("4k_banner", "") or images.get("list", "")
                    if banner:
                        img_type = "4k_banner" if images.get("4k_banner") else "list"
                        return {"title": title, "poster_url": f"{ZEE5_CDN}/{cid}/{img_type}/{banner}", "source": "zee5"}
        except Exception:
            pass
    return None


# ==================== APPLE TV ====================

def appletv_poster(query):
    """Apple TV - iTunes Search API"""
    try:
        r = get_req().get(
            f"https://itunes.apple.com/search?term={urllib.parse.quote(query)}&country=in&media=all&limit=20",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        data = r.json()

        if data.get("resultCount", 0) > 0:
            for result in data["results"]:
                name = result.get("trackName", result.get("collectionName", ""))
                kind = result.get("kind", "")
                if kind in ("podcast", "audiobook", "podcast-episode"):
                    continue
                if query.lower() in name.lower() or name.lower() in query.lower():
                    poster = result.get("artworkUrl600", "")
                    if poster:
                        poster_hd = poster.replace("600x600", "1200x1200")
                        return {"title": name, "poster_url": poster_hd, "source": "apple_tv"}

            for result in data["results"]:
                kind = result.get("kind", "")
                if kind not in ("podcast", "audiobook", "podcast-episode"):
                    name = result.get("trackName", result.get("collectionName", query))
                    poster = result.get("artworkUrl600", "")
                    if poster:
                        poster_hd = poster.replace("600x600", "1200x1200")
                        return {"title": name, "poster_url": poster_hd, "source": "apple_tv"}
    except Exception:
        pass
    return None


def appletv_from_url(url):
    """Apple TV URL se poster fetch karo"""
    # https://tv.apple.com/in/show/some-show/umc.xxx
    # https://itunes.apple.com/in/movie/some-movie/id123456
    match = re.search(r"(?:tv\.apple\.com|itunes\.apple\.com).+?/(?:show|movie)/([^/]+)", url)
    if match:
        slug = match.group(1).replace("-", " ")
        return appletv_poster(slug)
    return None


# ==================== URL DETECTION ====================

def detect_platform_and_fetch(url):
    """URL detect karo aur uss platform se poster fetch karo"""
    url_lower = url.lower()

    if "netflix.com" in url_lower:
        result = netflix_from_url(url)
        if result:
            return [result]

    if "sonyliv.com" in url_lower:
        result = sonyliv_from_url(url)
        if result:
            return [result]

    if "primevideo.com" in url_lower or "amazon." in url_lower:
        result = prime_from_url(url)
        if result:
            return [result]

    if "zee5.com" in url_lower:
        result = zee5_from_url(url)
        if result:
            return [result]

    if "tv.apple.com" in url_lower or "itunes.apple.com" in url_lower:
        result = appletv_from_url(url)
        if result:
            return [result]

    return []


# ==================== MAIN API ====================

def get_poster(query):
    """Search by name - sabhi platforms se"""
    results = []
    scrapers = [netflix_poster, sonyliv_poster, appletv_poster]
    for scraper in scrapers:
        try:
            result = scraper(query)
            if result:
                results.append(result)
        except Exception:
            pass
    return results


def get_poster_from_url(url):
    """URL se poster fetch karo"""
    return detect_platform_and_fetch(url)


# ==================== VERCEL HANDLER ====================

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/api/poster":
            query = params.get("q", [""])[0]
            url = params.get("url", [""])[0]

            if not query and not url:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": "Provide 'q' for search or 'url' for OTT link",
                    "usage": {
                        "search": "/api/poster?q=Money+Heist",
                        "url": "/api/poster?url=https://www.netflix.com/title/81040344"
                    }
                }).encode())
                return

            if url:
                results = get_poster_from_url(url)
            else:
                results = get_poster(query)

            response = {
                "query": query or url,
                "results": results,
                "total": len(results)
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode())

        elif parsed.path == "/api/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "platforms": ["netflix", "sonyliv", "prime_video", "zee5", "apple_tv"],
                "usage": {
                    "search": "/api/poster?q=Money+Heist",
                    "netflix_url": "/api/poster?url=https://www.netflix.com/title/81040344",
                    "sonyliv_url": "/api/poster?url=https://www.sonyliv.com/detail/1700000292",
                    "prime_url": "/api/poster?url=https://www.primevideo.com/detail/XYZ123/...",
                    "zee5_url": "/api/poster?url=https://www.zee5.com/tv-shows/details/show/0-0-12345"
                }
            }).encode())

        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        pass
