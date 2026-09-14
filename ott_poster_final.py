"""
OTT Poster API - Local Version
Netflix, SonyLIV, Prime Video, ZEE5, Apple TV
Search by name or paste OTT URL
"""

import requests
import json
import re
import base64
import urllib.parse
from datetime import datetime, timezone
from curl_cffi import requests as cffi_requests


def get_req():
    return cffi_requests


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
        r = cffi_requests.post(GRAPHQL_URL, json=payload, timeout=15)
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
    except:
        return None


def netflix_poster(query):
    vid = NETFLIX_IDS.get(query.lower().strip())
    if not vid:
        return None
    return netflix_graphql(vid)


def netflix_from_url(url):
    match = re.search(r"netflix\.com/(?:title|watch)/(\d+)", url)
    if match:
        return netflix_graphql(match.group(1))
    return None


# ==================== SONYLIV ====================

def sonyliv_poster(query):
    try:
        r = cffi_requests.get(
            "https://apiv3.sonyliv.com/AGL/4.8/A/ENG/WEB/IN/HR/TRAY/SEARCH",
            params={"query": query, "from": "0", "to": "10", "app_version": "3.10.3"},
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
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
    except:
        pass
    return None


def sonyliv_from_url(url):
    match = re.search(r"sonyliv\.com/detail/(?:[^/]+/)?(\d+)", url)
    if match:
        cid = match.group(1)
        try:
            r = cffi_requests.get(
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
        except:
            pass
    return None


# ==================== PRIME VIDEO ====================

def prime_poster(query):
    try:
        r = cffi_requests.get(
            f"https://www.primevideo.com/search/ref=at_dp_mk_tv_ns?phrase={query}",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=15
        )
        ids = list(set(re.findall(r"/detail/([A-Z0-9]+)", r.text)))
        for did in ids[:15]:
            try:
                api = f"https://www.primevideo.com/detail/{did}?dvWebAppClientVersion=1.0.125203.0"
                r2 = cffi_requests.get(api, headers={
                    "Accept": "application/json", "User-Agent": "Mozilla/5.0",
                    "x-requested-with": "WebAppSPA"
                }, timeout=10)
                if r2.status_code == 200:
                    data = r2.json()
                    page = data.get("body", [])
                    if page:
                        hd = page.get("atf", {}).get("state", {}).get("detail", {}).get("headerDetail", {})
                        for k, v in hd.items():
                            title = v.get("title", "")
                            year = v.get("releaseYear", "")
                            images = v.get("images", {})
                            if query.lower() in title.lower():
                                poster = images.get("heroshot", "") or images.get("covershot", "")
                                if poster:
                                    return {"title": f"{title} ({year})", "poster_url": poster, "source": "prime_video"}
            except:
                pass
    except:
        pass
    return None


def prime_from_url(url):
    match = re.search(r"primevideo\.com/detail/([A-Z0-9]+)", url)
    if not match:
        match = re.search(r"amazon\.(?:com|in)/dp/([A-Z0-9]+)", url)
    if match:
        did = match.group(1)
        try:
            api = f"https://www.primevideo.com/detail/{did}?dvWebAppClientVersion=1.0.125203.0"
            r = cffi_requests.get(api, headers={
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
        except:
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


def zee5_poster(query):
    try:
        token = zee5_token()
        r = cffi_requests.get(
            f"https://www.zee5.com/search?q={query}",
            headers={"User-Agent": "Mozilla/5.0"}, impersonate="chrome110", timeout=15
        )
        if r.status_code != 200:
            return None
        matches = re.findall(r"/(?:tv-shows|movies)/details/[^/]+/(\d+-\d+-\d+)", r.text)
        if not matches:
            return None
        cid = matches[0]
        for ctype in ["tvshow", "movie"]:
            api = f"https://gwapi.zee5.com/content/{ctype}/{cid}?translation=en&country=IN"
            r2 = cffi_requests.get(api, headers={"User-Agent": "Mozilla/5.0", "x-access-token": token}, timeout=10)
            if r2.status_code == 200:
                data = r2.json()
                title = data.get("title", query)
                images = data.get("image", {})
                if query.lower() not in title.lower():
                    continue
                banner = images.get("4k_banner", "") or images.get("list", "")
                if banner:
                    img_type = "4k_banner" if images.get("4k_banner") else "list"
                    url = f"{ZEE5_CDN}/{cid}/{img_type}/{banner}"
                    return {"title": title, "poster_url": url, "source": "zee5"}
    except:
        pass
    return None


def zee5_from_url(url):
    match = re.search(r"zee5\.com/(?:tv-shows|movies)/details/[^/]+/(\d+-\d+-\d+)", url)
    if match:
        cid = match.group(1)
        try:
            token = zee5_token()
            for ctype in ["tvshow", "movie"]:
                api = f"https://gwapi.zee5.com/content/{ctype}/{cid}?translation=en&country=IN"
                r = cffi_requests.get(api, headers={"User-Agent": "Mozilla/5.0", "x-access-token": token}, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    title = data.get("title", "")
                    images = data.get("image", {})
                    banner = images.get("4k_banner", "") or images.get("list", "")
                    if banner:
                        img_type = "4k_banner" if images.get("4k_banner") else "list"
                        return {"title": title, "poster_url": f"{ZEE5_CDN}/{cid}/{img_type}/{banner}", "source": "zee5"}
        except:
            pass
    return None


# ==================== APPLE TV ====================

def appletv_poster(query):
    try:
        r = cffi_requests.get(
            f"https://itunes.apple.com/search?term={urllib.parse.quote(query)}&country=in&media=all&limit=20",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=10
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
                        return {"title": name, "poster_url": poster.replace("600x600", "1200x1200"), "source": "apple_tv"}
            for result in data["results"]:
                kind = result.get("kind", "")
                if kind not in ("podcast", "audiobook", "podcast-episode"):
                    name = result.get("trackName", result.get("collectionName", query))
                    poster = result.get("artworkUrl600", "")
                    if poster:
                        return {"title": name, "poster_url": poster.replace("600x600", "1200x1200"), "source": "apple_tv"}
    except:
        pass
    return None


def appletv_from_url(url):
    match = re.search(r"(?:tv\.apple\.com|itunes\.apple\.com).+?/(?:show|movie)/([^/]+)", url)
    if match:
        slug = match.group(1).replace("-", " ")
        return appletv_poster(slug)
    return None


# ==================== URL DETECTION ====================

def detect_platform_and_fetch(url):
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
    results = []
    for scraper in [netflix_poster, prime_poster, zee5_poster, sonyliv_poster, appletv_poster]:
        try:
            result = scraper(query)
            if result:
                results.append(result)
        except:
            pass
    return results


def get_poster_from_url(url):
    return detect_platform_and_fetch(url)


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if not args:
        args = ["Money Heist", "Sacred Games", "Gullak", "https://www.netflix.com/title/81040344"]

    for arg in args:
        print(f"\n{'='*60}")
        print(f"  {arg}")
        print(f"{'='*60}")

        if arg.startswith("http"):
            results = get_poster_from_url(arg)
        else:
            results = get_poster(arg)

        if results:
            for r in results:
                print(f"  [{r['source'].upper()}] {r['title']}")
                print(f"  {r['poster_url'][:100]}")
        else:
            print("  Not found")
