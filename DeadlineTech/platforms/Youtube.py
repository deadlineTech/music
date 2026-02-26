import asyncio
import os
import re
import uuid
import random
import aiohttp
import aiofiles
import yt_dlp
from pathlib import Path
from urllib.parse import urlparse, unquote
from typing import Union, Optional, Dict, Any, Tuple

# Pyrogram
from pyrogram.types import Message
from pyrogram.enums import MessageEntityType

# Search & Utils
from youtubesearchpython.__future__ import VideosSearch
from DeadlineTech import app as TG_APP
from DeadlineTech.utils.database import is_on_off
from DeadlineTech.utils.formatters import time_to_seconds
from DeadlineTech.logging import LOGGER
import config

# === Configuration & Constants ===
YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")
CHUNK_SIZE = 1024 * 1024

# Security Constants
DANGEROUS_CHARS = [
    ";", "|", "$", "`", "\n", "\r", 
    "&", "(", ")", "<", ">", "{", "}", 
    "\\", "'", '"'
]
ALLOWED_DOMAINS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", 
    "youtu.be", "music.youtube.com"
}

# Polling & Request Settings
JOB_POLL_ATTEMPTS = 15     
JOB_POLL_INTERVAL = 2.0    
JOB_POLL_BACKOFF = 1.2     
HARD_TIMEOUT = 80          

V2_HTTP_RETRIES = 5
V2_DOWNLOAD_CYCLES = 5
NO_CANDIDATE_WAIT = 4
CDN_RETRIES = 5
CDN_RETRY_DELAY = 2

# === Statistics System ===
DOWNLOAD_STATS: Dict[str, int] = {
    "total": 0, "success": 0, "failed": 0,
    "api_hit": 0, "timeout_fail": 0,
    "no_candidate": 0, "cdn_fail": 0,
    "security_blocked": 0
}

def _inc(key: str):
    DOWNLOAD_STATS[key] = DOWNLOAD_STATS.get(key, 0) + 1

def get_stats() -> Dict[str, Any]:
    s = DOWNLOAD_STATS.copy()
    total = s["total"]
    s["success_rate"] = f"{(s['success'] / total) * 100:.2f}%" if total > 0 else "0.00%"
    return s

# === Security Helpers ===

def is_safe_url(text: str) -> bool:
    if not text: return False
    
    is_url = text.strip().lower().startswith(("http:", "https:", "www."))
    if not is_url:
        return True

    try:
        target_url = text.strip()
        if target_url.lower().startswith("www."):
            target_url = "https://" + target_url

        decoded_url = unquote(target_url)

        if any(char in decoded_url for char in DANGEROUS_CHARS):
            LOGGER(__name__).warning(f"🚫 Blocked URL (Dangerous Chars): {text}")
            return False

        p = urlparse(target_url)
        if p.netloc.replace("www.", "") not in ALLOWED_DOMAINS:
            LOGGER(__name__).warning(f"🚫 Blocked URL (Invalid Domain): {p.netloc}")
            return False
            
        return True
    except Exception as e:
        LOGGER(__name__).error(f"URL Parsing Error: {e}")
        return False

def extract_safe_id(link: str) -> Optional[str]:
    try:
        if "v=" in link: vid = link.split("v=")[-1].split("&")[0]
        elif "youtu.be" in link: vid = link.split("/")[-1].split("?")[0]
        else: return None
        if YOUTUBE_ID_RE.match(vid): return vid
    except: pass
    return None

def cookie_txt_file():
    cookie_dir = f"{os.getcwd()}/cookies"
    if not os.path.exists(cookie_dir): return None
    files = [f for f in os.listdir(cookie_dir) if f.endswith(".txt")]
    return os.path.join(cookie_dir, random.choice(files)) if files else None

# === API Logic ===

_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()

async def get_http_session() -> aiohttp.ClientSession:
    global _session
    if _session and not _session.closed:
        return _session
    async with _session_lock:
        if _session and not _session.closed:
            return _session
        timeout = aiohttp.ClientTimeout(total=HARD_TIMEOUT, sock_connect=10, sock_read=30)
        connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300, enable_cleanup_closed=True)
        _session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return _session

def _looks_like_status_text(s: Optional[str]) -> bool:
    if not s: return False
    low = s.lower()
    return any(x in low for x in ("download started", "background", "jobstatus", "job_id", "processing", "queued"))

def _extract_candidate(obj: Any) -> Optional[str]:
    if obj is None: return None
    if isinstance(obj, str):
        s = obj.strip()
        return s if s else None
    if isinstance(obj, list) and obj:
        return _extract_candidate(obj[0])
    if isinstance(obj, dict):
        job = obj.get("job")
        if isinstance(job, dict):
            res = job.get("result")
            if isinstance(res, dict):
                for k in ("public_url", "cdnurl", "download_url", "url"):
                    v = res.get(k)
                    if isinstance(v, str) and v.strip(): return v.strip()
        for k in ("public_url", "cdnurl", "download_url", "url", "tg_link"):
            v = obj.get(k)
            if isinstance(v, str) and v.strip(): return v.strip()
        for wrap in ("result", "results", "data", "items"):
            v = obj.get(wrap)
            if v: return _extract_candidate(v)
    return None

def _normalize_url(candidate: str) -> Optional[str]:
    api_url = getattr(config, "API_URL", None)
    if not api_url or not candidate: return None
    c = candidate.strip()
    if c.startswith(("http://", "https://")): return c
    if c.startswith("/"):
        if c.startswith(("/root", "/home")): return None
        return f"{api_url.rstrip('/')}{c}"
    return f"{api_url.rstrip('/')}/{c.lstrip('/')}"

async def _download_cdn(url: str, out_path: str) -> bool:
    LOGGER(__name__).info(f"🔗 Downloading from CDN: {url}")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    
    for attempt in range(1, CDN_RETRIES + 1):
        try:
            session = await get_http_session()
            async with session.get(url, timeout=HARD_TIMEOUT) as resp:
                if resp.status != 200:
                    if attempt < CDN_RETRIES:
                        await asyncio.sleep(CDN_RETRY_DELAY)
                        continue
                    return False

                async with aiofiles.open(out_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                        if not chunk: break
                        await f.write(chunk)
            
            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                return True

        except asyncio.TimeoutError:
            _inc("timeout_fail")
            if attempt < CDN_RETRIES: await asyncio.sleep(CDN_RETRY_DELAY)
        except Exception as e:
            LOGGER(__name__).error(f"CDN Fail: {e}")
            if attempt < CDN_RETRIES: await asyncio.sleep(CDN_RETRY_DELAY)
    
    return False

async def v2_download_process(link: str, video: bool) -> Optional[str]:
    # Fixed UUID bug: Fallback to raw link if extract_safe_id fails
    vid = extract_safe_id(link) or link 
    file_id = extract_safe_id(link) or uuid.uuid4().hex[:10]
    
    ext = "mp4" if video else "m4a"
    out_path = Path("downloads/video" if video else "downloads/audio") / f"{file_id}.{ext}"

    if out_path.exists() and out_path.stat().st_size > 0:
        return str(out_path)

    api_key = getattr(config, "API_KEY", None)
    api_url = getattr(config, "API_URL", None)
    if not api_url or not api_key:
        LOGGER(__name__).error("API Creds Missing")
        return None

    for cycle in range(1, V2_DOWNLOAD_CYCLES + 1):
        try:
            session = await get_http_session()
            url = f"{api_url.rstrip('/')}/youtube/v2/download"
            params = {"query": vid, "isVideo": str(video).lower(), "api_key": api_key}
            
            LOGGER(__name__).info(f"📡 V2 Job Start (Cycle {cycle}): {vid}...")
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    if cycle < V2_DOWNLOAD_CYCLES: await asyncio.sleep(1); continue
                    return None
                data = await resp.json()

            candidate = _extract_candidate(data)
            if candidate and _looks_like_status_text(candidate):
                candidate = None

            job_id = data.get("job_id")
            if isinstance(data.get("job"), dict):
                 job_id = data.get("job").get("id")

            if job_id and not candidate:
                LOGGER(__name__).info(f"⏳ Polling Job: {job_id}")
                interval = JOB_POLL_INTERVAL
                
                for _ in range(JOB_POLL_ATTEMPTS):
                    await asyncio.sleep(interval)
                    status_url = f"{api_url.rstrip('/')}/youtube/jobStatus"
                    
                    try:
                        async with session.get(status_url, params={"job_id": job_id}) as s_resp:
                            if s_resp.status == 200:
                                s_data = await s_resp.json()
                                candidate = _extract_candidate(s_data)
                                if candidate and not _looks_like_status_text(candidate):
                                    break
                                
                                job_data = s_data.get("job", {}) if isinstance(s_data, dict) else {}
                                if job_data.get("status") == "error":
                                    LOGGER(__name__).error(f"❌ Job Error: {job_data.get('error')}")
                                    break
                    except Exception:
                        pass
                    
                    interval *= JOB_POLL_BACKOFF
            
            if not candidate:
                _inc("no_candidate")
                if cycle < V2_DOWNLOAD_CYCLES: await asyncio.sleep(NO_CANDIDATE_WAIT); continue
                return None

            final_url = _normalize_url(candidate)
            if not final_url:
                 if cycle < V2_DOWNLOAD_CYCLES: await asyncio.sleep(NO_CANDIDATE_WAIT); continue
                 return None

            if await _download_cdn(final_url, str(out_path)):
                return str(out_path)
            else:
                _inc("cdn_fail")
        
        except Exception as e:
            LOGGER(__name__).error(f"V2 Cycle Error: {e}")
            if cycle < V2_DOWNLOAD_CYCLES: await asyncio.sleep(1)
    
    return None

# === MAIN CLASS ===

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        return bool(re.search(self.regex, link) and is_safe_url(link))

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
        if "&" in link: link = link.split("&")[0]
        
        if not is_safe_url(link): return "Unsafe URL", "0", 0, "", ""
        
        results = VideosSearch(link, limit=1)
        res_list = (await results.next()).get("result", [])
        
        if res_list:
            r = res_list[0]
            sec = int(time_to_seconds(r.get("duration", "0:00"))) if r.get("duration") else 0
            # Return empty string for thumbnail
            return r.get("title", "Unknown"), r.get("duration", "0:00"), sec, "", r.get("id", "")
            
        return None

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        results = VideosSearch(link, limit=1)
        res_list = (await results.next()).get("result", [])
        if res_list: return res_list[0].get("title", "Unknown")
        return ""

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        results = VideosSearch(link, limit=1)
        res_list = (await results.next()).get("result", [])
        if res_list: return res_list[0].get("duration", "0:00")
        return "00:00"

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        # Disabled as per request, returning empty string
        return ""

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if not is_safe_url(link): return 0, "Unsafe URL"
        
        path = await v2_download_process(link, video=True)
        if path: return 1, path
        
        return 0, "Download Failed"

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid: link = self.listbase + link
        if not is_safe_url(link): return []
        
        cookie_file = cookie_txt_file()
        if not cookie_file: return []
        
        cmd = [
            "yt-dlp", "-i", "--get-id", "--flat-playlist", "--cookies", cookie_file,
            "--playlist-end", str(limit), "--skip-download", "--", link
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            if stdout: return [x for x in stdout.decode().split("\n") if x]
        except: pass
        return []

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        results = VideosSearch(link, limit=1)
        res_list = (await results.next()).get("result", [])
        
        if res_list:
            r = res_list[0]
            # Safely fetch dict values and return an empty string for the thumbnail
            return {
                "title": r.get("title", "Unknown"), 
                "link": r.get("link", link), 
                "vidid": r.get("id", ""),
                "duration_min": r.get("duration", "0:00"), 
                "thumb": "", 
            }, r.get("id", "")
            
        return None, None

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if not is_safe_url(link): return [], link
        
        cookie_file = cookie_txt_file()
        if not cookie_file: return [], link
        
        ytdl_opts = {"quiet": True, "cookiefile": cookie_file}
        out = []
        try:
            with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
                r = ydl.extract_info(link, download=False)
                for f in r.get("formats", []):
                    if "dash" in str(f.get("format")).lower(): continue
                    out.append({
                        "format": f.get("format"), "filesize": f.get("filesize"),
                        "format_id": f.get("format_id"), "ext": f.get("ext"),
                        "format_note": f.get("format_note"), "yturl": link
                    })
        except: pass
        return out, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        
        if not result or query_type >= len(result): 
            return None, None, "", None
            
        r = result[query_type]
        # Return empty string for the thumbnail
        return r.get("title", "Unknown"), r.get("duration", "0:00"), "", r.get("id", "")

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
    ) -> Tuple[Optional[str], Optional[bool]]:
        _inc("total")
        if videoid: link = self.base + link
        
        if not is_safe_url(link):
            _inc("security_blocked")
            return None, None

        is_vid = True if (video or songvideo) else False
        
        path = await v2_download_process(link, video=is_vid)
        if path:
            _inc("success")
            _inc("api_hit")
            return path, True

        _inc("failed")
        return None, None
