"""
OTT Poster API - Vercel Serverless Function
Netflix, SonyLIV, Apple TV
"""

import json
import urllib.parse
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
    "nirmal pathak ki ghar wapsi": "81615608",
    "gullak": "81380794",
    "ted lasso": None,
}


def netflix_poster(query):
    vid = NETFLIX_IDS.get(query.lower().strip())
    if not vid:
        return None

    payload = {
        "operationName": "MiniModalQuery",
        "variables": {
            "opaqueImageFormat": "WEBP", "transparentImageFormat": "WEBP",
            "videoMerchEnabled": True, "fetchPromoVideoOverride": False,
            "hasPromoVideoOverride": False, "promoVideoId": 0,
            "videoMerchContext": "BROWSE", "isLiveEpisodic": False,
            "artworkContext": {"groupLoc": ARTWORK_CONTEXT},
            "textEvidenceUiContext": "BOB",
            "unifiedEntityIds": [f"Video:{vid}"],
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
    title = entity.get("title", query)
    year = entity.get("latestYear", "")
    boxart = entity.get("boxartHighRes", {})
    url = boxart.get("url", "") if isinstance(boxart, dict) else ""

    if not url:
        return None

    return {"title": title, "year": year, "poster_url": url, "source": "netflix"}


# ==================== SONYLIV ====================

def sonyliv_poster(query):
    try:
        r = requests.get(
            "https://apiv3.sonyliv.com/AGL/4.8/A/ENG/WEB/IN/HR/TRAY/SEARCH",
            params={"query": query, "from": "0", "to": "10", "app_version": "3.10.3"},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
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
    except Exception as e:
        import sys
        print(f"SonyLIV error: {e}", file=sys.stderr)
    return None


# ==================== APPLE TV ====================

def appletv_poster(query):
    try:
        req = get_req()
        r = req.get(
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


# ==================== MAIN API ====================

def get_poster(query):
    results = []
    scrapers = [
        netflix_poster,
        sonyliv_poster,
        appletv_poster,
    ]

    for scraper in scrapers:
        try:
            result = scraper(query)
            if result:
                results.append(result)
        except Exception:
            pass

    return results


# ==================== VERCEL HANDLER ====================

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/api/poster":
            query = params.get("q", [""])[0]
            if not query:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing 'q' parameter"}).encode())
                return

            results = get_poster(query)
            response = {
                "query": query,
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
            self.wfile.write(json.dumps({"status": "ok", "platforms": ["netflix", "sonyliv", "apple_tv"]}).encode())

        elif parsed.path == "/api/debug":
            import sys
            info = {
                "python": sys.version,
                "requests_available": requests is not None,
                "curl_cffi_available": cffi_requests is not None,
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(info).encode())

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
