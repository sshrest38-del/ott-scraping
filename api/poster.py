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
    scrapers = [netflix_poster, appletv_poster]
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
    INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>OTT Poster API</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0a;color:#fff;min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:40px 20px}
.container{max-width:800px;width:100%}
h1{font-size:2.5rem;margin-bottom:10px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.subtitle{color:#888;margin-bottom:40px;font-size:1.1rem}
.search-box{display:flex;gap:10px;margin-bottom:20px}
.search-box input{flex:1;padding:14px 20px;border:1px solid #333;border-radius:8px;background:#1a1a1a;color:#fff;font-size:1rem;outline:none}
.search-box input:focus{border-color:#667eea}
.search-box button{padding:14px 28px;border:none;border-radius:8px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;font-size:1rem;cursor:pointer;font-weight:600}
.tab-bar{display:flex;gap:0;margin-bottom:20px}
.tab{flex:1;padding:12px;text-align:center;background:#1a1a1a;border:1px solid #333;cursor:pointer;font-size:.9rem;color:#888;transition:all .2s}
.tab:first-child{border-radius:8px 0 0 8px}.tab:last-child{border-radius:0 8px 8px 0}
.tab.active{background:#667eea;color:#fff;border-color:#667eea}
.results{display:flex;flex-direction:column;gap:16px}
.result-card{background:#1a1a1a;border:1px solid #333;border-radius:12px;padding:20px;display:flex;gap:20px;align-items:center}
.result-card img{width:120px;height:80px;object-fit:cover;border-radius:8px;background:#222}
.result-info{flex:1}.result-title{font-size:1.1rem;font-weight:600;margin-bottom:6px}
.result-source{font-size:.85rem;color:#888;text-transform:uppercase;letter-spacing:1px}
.result-url{font-size:.75rem;color:#667eea;word-break:break-all;margin-top:8px}
.platforms{display:flex;gap:10px;margin-bottom:30px;flex-wrap:wrap}
.platform-badge{padding:6px 14px;border-radius:20px;background:#1a1a1a;border:1px solid #333;font-size:.85rem;color:#aaa}
.api-info{background:#1a1a1a;border:1px solid #333;border-radius:12px;padding:20px;margin-top:30px}
.api-info h3{margin-bottom:12px;color:#667eea}
.api-info code{background:#0a0a0a;padding:2px 8px;border-radius:4px;font-size:.9rem;color:#e0e0e0}
.api-info p{margin:8px 0;color:#aaa}
.loading{text-align:center;padding:40px;color:#888}
.error{text-align:center;padding:20px;color:#ff6b6b}
.examples code{display:block;margin:4px 0;font-size:.8rem;color:#666}
</style>
</head>
<body>
<div class="container">
<h1>OTT Poster API</h1>
<p class="subtitle">Search by name or paste OTT URL to get poster</p>
<div class="platforms"><span class="platform-badge">Netflix</span><span class="platform-badge">Prime Video</span><span class="platform-badge">ZEE5</span><span class="platform-badge">Apple TV</span></div>
<div class="tab-bar"><div class="tab active" onclick="switchTab('search')">Search by Name</div><div class="tab" onclick="switchTab('url')">Paste OTT URL</div></div>
<div class="search-box"><input type="text" id="searchInput" placeholder="Money Heist, Sacred Games, Gullak..."/><button id="searchBtn" onclick="search()">Get Poster</button></div>
<div id="results" class="results"></div>
<div class="api-info"><h3>API Usage</h3>
<p><strong>Search by name:</strong></p><code>GET /api/poster?q=Money+Heist</code>
<p><strong>Paste OTT URL:</strong></p><code>GET /api/poster?url=https://www.netflix.com/title/81040344</code>
<div class="examples"><p style="margin-top:12px"><strong>Supported URLs:</strong></p>
<code>netflix.com/title/81040344</code>
<code>primevideo.com/detail/XYZ123/...</code>
<code>zee5.com/tv-shows/details/show/0-0-12345</code>
<code>tv.apple.com/in/show/slug/umc.xxx</code></div></div>
</div>
<script>
let mode='search';
const inp=document.getElementById('searchInput');
inp.addEventListener('keypress',function(e){if(e.key==='Enter')search()});
function switchTab(m){mode=m;var tabs=document.querySelectorAll('.tab');tabs[0].className=m==='search'?'tab active':'tab';tabs[1].className=m==='url'?'tab active':'tab';inp.placeholder=m==='url'?'Paste Netflix/Prime/ZEE5 URL...':'Money Heist, Sacred Games, Gullak...';inp.value='';inp.focus()}
async function search(){var q=inp.value.trim();if(!q)return;var rd=document.getElementById('results');rd.innerHTML='<div class="loading">Fetching poster...</div>';try{var url;if(q.indexOf('netflix.com')>-1||q.indexOf('primevideo.com')>-1||q.indexOf('zee5.com')>-1||q.indexOf('tv.apple.com')>-1||q.indexOf('amazon.')>-1){url='/api/poster?url='+encodeURIComponent(q)}else{url='/api/poster?q='+encodeURIComponent(q)}var res=await fetch(url);var data=await res.json();if(!data.results.length){rd.innerHTML='<div class="error">No poster found</div>';return}rd.innerHTML=data.results.map(function(r){return '<div class="result-card"><img src="'+r.poster_url+'" alt="'+r.title+'" onerror="this.style.display=\'none\'"/><div class="result-info"><div class="result-title">'+r.title+'</div><div class="result-source">'+r.source+'</div><div class="result-url">'+r.poster_url+'</div></div></div>'}).join('')}catch(e){rd.innerHTML='<div class="error">Error: '+e.message+'</div>'}}
</script>
</body>
</html>"""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(self.INDEX_HTML.encode())
            return

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
                "platforms": ["netflix", "prime_video", "zee5", "apple_tv"],
                "usage": {
                    "search": "/api/poster?q=Money+Heist",
                    "netflix_url": "/api/poster?url=https://www.netflix.com/title/81040344",
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
