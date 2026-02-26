# Music Bot by Team DeadlineTech
import asyncio
import os
import re
import time
import uuid
import logging
import random
import aiohttp
import aiofiles
import yt_dlp
from pathlib import Path
from typing import Union, Optional, Dict, Any, List
from urllib.parse import urlparse
from aiohttp import TCPConnector

from pyrogram.types import Message
from pyrogram.enums import MessageEntityType

from youtubesearchpython.__future__ import VideosSearch

from DeadlineTech import app as TG_APP
from DeadlineTech.core.dir import DOWNLOAD_DIR
import config

# === Configuration & Constants ===
API_KEY = config.API_KEY
API_URL = config.API_URL

# Polling & Retry Settings
CHUNK_SIZE = 1024 * 1024
V2_HTTP_RETRIES = 5
V2_DOWNLOAD_CYCLES = 5
JOB_POLL_ATTEMPTS = 15
JOB_POLL_INTERVAL = 2.0
JOB_POLL_BACKOFF = 1.1
CDN_RETRIES = 5
CDN_RETRY_DELAY = 2
HARD_TIMEOUT = 60  # 5 Minutes

# Regex
YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")
YOUTUBE_ID_IN_URL_RE = re.compile(r"""(?x)(?:v=|\/)([A-Za-z0-9_-]{11})|youtu\.be\/([A-Za-z0-9_-]{11})""")

# Globals
_inflight: Dict[str, asyncio.Future] = {}
_inflight_lock = asyncio.Lock()
_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()

LOGGER = logging.getLogger(__name__)

# === Statistics ===
DOWNLOAD_STATS: Dict[str, int] = {
    "total": 0, "success": 0, "failed": 0,
    "api_hit": 0, "cookie_hit": 0
}

def _inc(key: str):
    DOWNLOAD_STATS[key] = DOWNLOAD_STATS.get(key, 0) + 1

# === Helper Functions ===

def extract_video_id(link: str) -> str:
    if not link: return ""
    s = link.strip()
    if YOUTUBE_ID_RE.match(s): return s
    m = YOUTUBE_ID_IN_URL_RE.search(s)
    if m: return m.group(1) or m.group(2) or ""
    if "v=" in s: return s.split("v=")[-1].split("&")[0]
    try:
        last = s.split("/")[-1].split("?")[0]
        if YOUTUBE_ID_RE.match(last): return last
    except: pass
    return ""

def seconds_to_time(seconds: int) -> str:
    if not seconds: return "00:00"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h: return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def _ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

def cookie_txt_file():
    cookie_dir = f"{os.getcwd()}/cookies"
    if not os.path.exists(cookie_dir): return None
    files = [f for f in os.listdir(cookie_dir) if f.endswith(".txt")]
    return os.path.join(cookie_dir, random.choice(files)) if files else None

async def get_http_session() -> aiohttp.ClientSession:
    global _session
    if _session and not _session.closed: return _session
    async with _session_lock:
        if _session and not _session.closed: return _session
        timeout = aiohttp.ClientTimeout(total=HARD_TIMEOUT, sock_connect=10, sock_read=30)
        connector = TCPConnector(limit=100, ttl_dns_cache=300, enable_cleanup_closed=True)
        _session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return _session

# === API Interaction Functions ===

async def _api_request(endpoint: str, params: Dict[str, Any]) -> Optional[Any]:
    if not API_URL or not API_KEY: return None
    
    base = API_URL.rstrip("/")
    url = f"{base}/{endpoint.lstrip('/')}"
    params["api_key"] = API_KEY

    for attempt in range(1, V2_HTTP_RETRIES + 1):
        try:
            session = await get_http_session()
            async with session.get(url, params=params, headers={"X-API-Key": API_KEY, "Accept": "application/json"}) as resp:
                if 200 <= resp.status < 300:
                    return await resp.json()
                elif resp.status in (404, 400):
                    return None
        except Exception:
            pass
        if attempt < V2_HTTP_RETRIES: await asyncio.sleep(1)
    return None

async def _download_from_cdn(cdn_url: str, out_path: str) -> Optional[str]:
    if not cdn_url: return None
    if "/root/" in cdn_url or "/home/" in cdn_url: return None

    for attempt in range(1, CDN_RETRIES + 1):
        try:
            session = await get_http_session()
            async with session.get(cdn_url, timeout=HARD_TIMEOUT) as resp:
                if resp.status != 200:
                    if attempt < CDN_RETRIES: await asyncio.sleep(CDN_RETRY_DELAY); continue
                    return None
                
                _ensure_dir(str(Path(out_path).parent))
                async with aiofiles.open(out_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                        if not chunk: break
                        await f.write(chunk)
            
            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                return out_path
        except Exception:
            if attempt < CDN_RETRIES: await asyncio.sleep(CDN_RETRY_DELAY)
    return None

def _extract_candidate(obj: Any) -> Optional[str]:
    if not obj: return None
    if isinstance(obj, str) and obj.strip().startswith("http"): return obj.strip()
    if isinstance(obj, dict):
        for k in ["public_url", "url", "download_url", "cdnurl"]:
            val = obj.get(k)
            if val and isinstance(val, str) and val.startswith("http"): return val
        if "result" in obj: return _extract_candidate(obj["result"])
        if "job" in obj: return _extract_candidate(obj["job"])
    return None

def _looks_like_status(s: str) -> bool:
    if not s: return True
    return any(x in s.lower() for x in ["processing", "queued", "job_id", "background"])

async def v2_download_process(link: str, video: bool) -> Optional[str]:
    vid = extract_video_id(link)
    query = vid or link
    ext = "mp4" if video else "m4a"
    base_name = vid if vid else uuid.uuid4().hex[:10]
    out_path = os.path.join(str(Path(DOWNLOAD_DIR)), f"{base_name}.{ext}")
    
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0: return out_path

    for cycle in range(1, V2_DOWNLOAD_CYCLES + 1):
        resp = await _api_request("youtube/v2/download", {"query": query, "isVideo": str(video).lower()})
        if not resp: 
            if cycle < V2_DOWNLOAD_CYCLES: await asyncio.sleep(1); continue
            return None
            
        job_id = None
        if isinstance(resp, dict):
             job_id = resp.get("job_id") or resp.get("job", {}).get("id")

        if not job_id:
            candidate = _extract_candidate(resp)
            if candidate and not _looks_like_status(candidate):
                 path = await _download_from_cdn(candidate, out_path)
                 if path: return path
            continue

        candidate_url = None
        interval = JOB_POLL_INTERVAL
        
        for _ in range(JOB_POLL_ATTEMPTS):
            await asyncio.sleep(interval)
            status_resp = await _api_request("youtube/jobStatus", {"job_id": job_id})
            candidate_url = _extract_candidate(status_resp)
            if candidate_url and not _looks_like_status(candidate_url): break
            if status_resp and status_resp.get("job", {}).get("status") == "error": break
            interval *= JOB_POLL_BACKOFF
        
        if candidate_url:
            path = await _download_from_cdn(candidate_url, out_path)
            if path: return path

    return None

async def cookie_download_process(link: str, video: bool) -> Optional[str]:
    cookie_file = cookie_txt_file()
    if not cookie_file: 
        LOGGER.warning("No cookie file found for fallback download.")
        return None

    ext = "mp4" if video else "m4a"
    vid = extract_video_id(link)
    out_path = os.path.join(str(Path(DOWNLOAD_DIR)), f"{vid}.{ext}")
    
    loop = asyncio.get_running_loop()
    
    def _run_ytdl():
        opts = {
            "format": "bestvideo+bestaudio/best" if video else "bestaudio/best",
            "outtmpl": f"{str(Path(DOWNLOAD_DIR))}/%(id)s.%(ext)s",
            "quiet": True, 
            "cookiefile": cookie_file,
            "no_warnings": True,
            "noplaylist": True
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(link, download=True)
            return ydl.prepare_filename(info)

    try:
        path = await loop.run_in_executor(None, _run_ytdl)
        if path and os.path.exists(path): return path
    except Exception as e:
        LOGGER.error(f"Cookie Download Error: {e}")
    
    return None

async def deduplicate_download(key: str, runner):
    async with _inflight_lock:
        if fut := _inflight.get(key): return await fut
        fut = asyncio.get_running_loop().create_future()
        _inflight[key] = fut
    try:
        result = await runner()
        if not fut.done(): fut.set_result(result)
        return result
    except Exception as e:
        if not fut.done(): fut.set_exception(e)
        return None
    finally:
        async with _inflight_lock:
            if _inflight.get(key) == fut: _inflight.pop(key, None)

# === MAIN CLASS ===

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"

    async def _hybrid_search(self, link: str):
        # 1. Try YouTubeSearchPython
        try:
            results = VideosSearch(link, limit=1)
            res = (await results.next())["result"][0]
            return {
                "title": res["title"],
                "duration": res["duration"], # String "04:00"
                "thumbnail": res["thumbnails"][0]["url"].split("?")[0],
                "url": res["link"],
                "id": res["id"]
            }
        except Exception:
            pass
        
        # 2. Fallback to API
        if API_URL and API_KEY:
            try:
                res = await _api_request("youtube/search", {"query": link})
                if res and res.get("status") == "success":
                    data = res.get("result")
                    return {
                        "title": data.get("title"),
                        "duration": seconds_to_time(data.get("duration", 0)),
                        "thumbnail": data.get("thumbnail"),
                        "url": data.get("url"),
                        "id": extract_video_id(data.get("url"))
                    }
            except Exception:
                pass
        
        return None

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        res = await self._hybrid_search(link)
        return bool(res)

    async def url(self, message: Message) -> Union[str, None]:
        msgs = [message]
        if message.reply_to_message: msgs.append(message.reply_to_message)
        for msg in msgs:
            text = msg.text or msg.caption or ""
            if not text: continue
            if msg.entities:
                for entity in msg.entities:
                    if entity.type == MessageEntityType.URL:
                        return text[entity.offset:entity.offset+entity.length]
            if msg.caption_entities:
                for entity in msg.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        res = await self._hybrid_search(link)
        if res:
            # Convert Duration String to Seconds
            try:
                parts = list(map(int, res["duration"].split(":")))
                sec = sum(x * 60**i for i, x in enumerate(reversed(parts)))
            except: sec = 0
            return res["title"], res["duration"], sec, res["thumbnail"], res["id"]
        return "Unknown", "00:00", 0, "", ""

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        res = await self._hybrid_search(link)
        return res["title"] if res else ""

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        res = await self._hybrid_search(link)
        return res["duration"] if res else "00:00"

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        res = await self._hybrid_search(link)
        return res["thumbnail"] if res else ""

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        res = await self._hybrid_search(link)
        if res:
            return {
                "title": res["title"],
                "link": res["url"],
                "vidid": res["id"],
                "duration_min": res["duration"],
                "thumb": res["thumbnail"],
            }, res["id"]
        return None, None

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        path, _ = await self.download(link, None, video=True)
        if path: return 1, path
        return 0, "Failed"

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        _inc("total")
        if videoid: link = self.base + link
        
        is_vid = True if (video or songvideo) else False
        vid = extract_video_id(link)
        dedup_id = vid or link
        key = f"{'video' if is_vid else 'audio'}:{dedup_id}"
        
        async def _download_logic():
            # 1. API Strategy
            if API_URL and API_KEY:
                path = await v2_download_process(link, video=is_vid)
                if path:
                    _inc("api_hit")
                    _inc("success")
                    return path
            else:
                LOGGER.warning("API_URL AND KEY NOT CONFIGURED SKipping fast fetching")

            # 2. Cookie Fallback
            path = await cookie_download_process(link, video=is_vid)
            if path:
                _inc("cookie_hit")
                _inc("success")
                return path

            _inc("failed")
            return None

        try:
            path = await asyncio.wait_for(
                deduplicate_download(key, _download_logic), 
                timeout=HARD_TIMEOUT
            )
            if path: return path, True
        except Exception as e:
            LOGGER.error(f"Download Exception: {e}")

        return None, None

