# AnnieXMedia/utils/downloader.py
# Authored By Certified Coders © 2025

import asyncio
import os
import re
import time
import uuid
import aiofiles
import aiohttp
from pathlib import Path
from typing import Dict, Optional, Any
from urllib.parse import urlparse, unquote
from aiohttp import TCPConnector

from AnnieXMedia.core.dir import DOWNLOAD_DIR
from AnnieXMedia.logging import LOGGER as _LOGGER
from config import API_KEY, API_URL

LOGGER = _LOGGER(__name__)

# -----------------------
# STATS
# -----------------------
DOWNLOAD_STATS: Dict[str, int] = {
    "total": 0,
    "success": 0,
    "failed": 0,
    "api_hit": 0,
    "timeout_fail": 0,
    "network_fail": 0,
    "security_blocked": 0,
    "no_candidate": 0,
    "cdn_fail": 0,
}

def _inc(key: str, n: int = 1) -> None:
    DOWNLOAD_STATS[key] = DOWNLOAD_STATS.get(key, 0) + n

def get_download_stats() -> Dict[str, int]:
    return dict(DOWNLOAD_STATS)

# -----------------------
# CONFIGURATION
# -----------------------
# API & Polling Settings
V2_HTTP_RETRIES = 5
V2_DOWNLOAD_CYCLES = 5
JOB_POLL_ATTEMPTS = 15
JOB_POLL_INTERVAL = 2.0
JOB_POLL_BACKOFF = 1.2
NO_CANDIDATE_WAIT = 4
CDN_RETRIES = 5
CDN_RETRY_DELAY = 2

# Global Timeout
HARD_TIMEOUT = 80
CHUNK_SIZE = 1024 * 1024

# -----------------------
# SECURITY CONFIG
# -----------------------
DANGEROUS_CHARS = [
    ";", "|", "$", "`", "\n", "\r", 
    "&", "(", ")", "<", ">", "{", "}", 
    "\\", "'", '"'
]
ALLOWED_DOMAINS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", 
    "youtu.be", "music.youtube.com"
}

# -----------------------
# REGEX & HELPERS
# -----------------------
YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")
YOUTUBE_ID_IN_URL_RE = re.compile(r"""(?x)(?:v=|\/)([A-Za-z0-9_-]{11})|youtu\.be\/([A-Za-z0-9_-]{11})""")

_inflight: Dict[str, asyncio.Future] = {}
_inflight_lock = asyncio.Lock()

_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()

def extract_video_id(link: str) -> str:
    """Extracts YouTube Video ID from various link formats."""
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

def _ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

# -----------------------
# SECURITY CHECKER
# -----------------------
def is_safe_url(text: str) -> bool:
    """
    Validates URL safety to prevent injection.
    """
    if not text: return False
    
    # 1. Check if it looks like a URL
    is_url = text.strip().lower().startswith(("http:", "https:", "www."))
    if not is_url:
        return True # Text query is safe

    try:
        # Normalize
        target_url = text.strip()
        if target_url.lower().startswith("www."):
            target_url = "https://" + target_url

        # Decode
        decoded_url = unquote(target_url)

        # Dangerous Chars
        if any(char in decoded_url for char in DANGEROUS_CHARS):
            LOGGER.warning(f"🚫 Blocked URL (Dangerous Chars): {text}")
            return False

        # Domain Check
        p = urlparse(target_url)
        if p.netloc.replace("www.", "") not in ALLOWED_DOMAINS:
            # Allow empty netloc for relative paths if needed, but strict for now
            if not p.netloc: return False 
            LOGGER.warning(f"🚫 Blocked URL (Invalid Domain): {p.netloc}")
            return False
            
        return True
    except Exception as e:
        LOGGER.error(f"URL Parsing Error: {e}")
        return False

# -----------------------
# HTTP SESSION
# -----------------------
async def get_http_session() -> aiohttp.ClientSession:
    global _session
    if _session and not _session.closed:
        return _session
    async with _session_lock:
        if _session and not _session.closed:
            return _session
        # Socket timeouts
        timeout = aiohttp.ClientTimeout(total=HARD_TIMEOUT, sock_connect=10, sock_read=30)
        connector = TCPConnector(limit=100, ttl_dns_cache=300, enable_cleanup_closed=True)
        _session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return _session

# -----------------------
# API HELPERS
# -----------------------
def _extract_candidate(obj: Any) -> Optional[str]:
    if not obj: return None
    if isinstance(obj, str):
        s = obj.strip()
        return s if s else None
    if isinstance(obj, list) and obj:
        return _extract_candidate(obj[0])
    if isinstance(obj, dict):
        # Priority: Job Result -> Direct Fields -> Nested
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

def _looks_like_status_text(s: Optional[str]) -> bool:
    if not s: return False
    low = s.lower()
    return any(x in low for x in ("download started", "background", "jobstatus", "job_id", "processing", "queued"))

def _normalize_candidate_to_url(candidate: str) -> Optional[str]:
    if not candidate: return None
    c = candidate.strip()
    if c.startswith(("http://", "https://")): return c
    if c.startswith("/"):
        if c.startswith(("/root", "/home")): return None
        return f"{API_URL.rstrip('/')}{c}"
    return f"{API_URL.rstrip('/')}/{c.lstrip('/')}"

async def _download_from_cdn(cdn_url: str, out_path: str) -> Optional[str]:
    if not cdn_url: return None
    
    LOGGER.info(f"🔗 Downloading from CDN: {cdn_url}")
    _ensure_dir(str(Path(out_path).parent))

    for attempt in range(1, CDN_RETRIES + 1):
        try:
            session = await get_http_session()
            async with session.get(cdn_url, timeout=HARD_TIMEOUT) as resp:
                if resp.status != 200:
                    if attempt < CDN_RETRIES:
                        await asyncio.sleep(CDN_RETRY_DELAY)
                        continue
                    return None

                async with aiofiles.open(out_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                        if not chunk: break
                        await f.write(chunk)

            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                return out_path

        except asyncio.TimeoutError:
            _inc("timeout_fail")
            if attempt < CDN_RETRIES: await asyncio.sleep(CDN_RETRY_DELAY)
        except Exception as e:
            LOGGER.error(f"CDN Fail: {e}")
            _inc("network_fail")
            if attempt < CDN_RETRIES: await asyncio.sleep(CDN_RETRY_DELAY)

    return None

# -----------------------
# V2 API LOGIC
# -----------------------
async def _v2_request_json(endpoint: str, params: Dict[str, Any]) -> Optional[Any]:
    if not API_URL or not API_KEY:
        LOGGER.error("API_URL or API_KEY missing in config")
        return None

    base = API_URL.rstrip("/")
    url = f"{base}/{endpoint.lstrip('/')}"
    params["api_key"] = API_KEY

    for attempt in range(1, V2_HTTP_RETRIES + 1):
        try:
            session = await get_http_session()
            async with session.get(url, params=params, headers={"X-API-Key": API_KEY}) as resp:
                if 200 <= resp.status < 300:
                    return await resp.json()
                elif resp.status in (404, 400):
                    return None # Invalid request, don't retry
        except Exception:
            _inc("network_fail")
        
        if attempt < V2_HTTP_RETRIES:
            await asyncio.sleep(1)
            
    return None

async def v2_download(link: str, media_type: str) -> Optional[str]:
    """
    Handles the full V2 API lifecycle: Job Start -> Polling -> CDN Download.
    """
    is_video = (media_type == "video")
    vid = extract_video_id(link)
    query = vid or link
    ext = "mp4" if is_video else "m4a"
    base_name = vid if vid else uuid.uuid4().hex[:10]
    out_path = os.path.join(str(Path(DOWNLOAD_DIR)), f"{base_name}.{ext}")

    # Check cache first
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return out_path

    # Retry Cycles
    for cycle in range(1, V2_DOWNLOAD_CYCLES + 1):
        # 1. Start Job
        resp = await _v2_request_json(
            "youtube/v2/download",
            {"query": query, "isVideo": str(is_video).lower()},
        )
        
        if not resp:
            if cycle < V2_DOWNLOAD_CYCLES: await asyncio.sleep(1); continue
            return None

        # 2. Extract Immediate Result or Job ID
        candidate = _extract_candidate(resp)
        if candidate and _looks_like_status_text(candidate):
            candidate = None # It's a status message, not a link

        job_id = resp.get("job_id")
        if isinstance(resp.get("job"), dict):
            job_id = resp.get("job").get("id")

        # 3. Poll if Job ID exists and no direct link
        if job_id and not candidate:
            interval = JOB_POLL_INTERVAL
            LOGGER.info(f"⏳ Polling Job: {job_id}")
            
            for _ in range(JOB_POLL_ATTEMPTS):
                await asyncio.sleep(interval)
                status = await _v2_request_json("youtube/jobStatus", {"job_id": str(job_id)})
                
                # Check for link
                candidate = _extract_candidate(status)
                if candidate and not _looks_like_status_text(candidate):
                    break
                
                # Check for error
                if status and status.get("job", {}).get("status") == "error":
                    LOGGER.error(f"❌ Job Failed: {status.get('job', {}).get('error')}")
                    break
                    
                interval *= JOB_POLL_BACKOFF

        # 4. Process Candidate
        if not candidate:
            _inc("no_candidate")
            if cycle < V2_DOWNLOAD_CYCLES: await asyncio.sleep(NO_CANDIDATE_WAIT); continue
            return None

        normalized = _normalize_candidate_to_url(candidate)
        if not normalized:
            if cycle < V2_DOWNLOAD_CYCLES: await asyncio.sleep(NO_CANDIDATE_WAIT); continue
            return None

        # 5. Download from CDN
        path = await _download_from_cdn(normalized, out_path)
        if path:
            return path
        
        _inc("cdn_fail")
        if cycle < V2_DOWNLOAD_CYCLES: await asyncio.sleep(2)

    return None

# -----------------------
# DEDUPLICATION & WRAPPER
# -----------------------
async def deduplicate_download(key: str, runner):
    async with _inflight_lock:
        if fut := _inflight.get(key):
            return await fut
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
            if _inflight.get(key) == fut:
                _inflight.pop(key, None)

async def media_download(link: str, type: str, title: str = "", video_id: str = None) -> Optional[str]:
    """
    Main entry point for downloading media via API Only.
    """
    start_t = time.perf_counter()
    _inc("total")

    # 1. Security Check
    if not is_safe_url(link):
        _inc("security_blocked")
        return None

    vid = video_id if video_id else extract_video_id(link)
    dedup_id = vid or link.strip()
    key = f"{type}:{dedup_id}"
    
    clean_title = (title or dedup_id)[:30]
    LOGGER.info(f"📥 START | {type.upper()} | {clean_title}")

    async def _cycle():
        # API ONLY Strategy
        path = await v2_download(link, media_type=type)
        if path and os.path.exists(path):
            _inc("success")
            _inc("api_hit")
            dt = time.perf_counter() - start_t
            LOGGER.info(f"✅ DONE | API | {dt:.2f}s | {clean_title}")
            return path

        _inc("failed")
        dt = time.perf_counter() - start_t
        LOGGER.error(f"❌ FAILED | {dt:.2f}s | {clean_title}")
        return None

    try:
        # Enforce global timeout
        return await deduplicate_download(key, lambda: asyncio.wait_for(_cycle(), timeout=HARD_TIMEOUT))
    except asyncio.TimeoutError:
        _inc("timeout_fail")
        _inc("failed")
        LOGGER.error(f"⌛ TIMEOUT | >{HARD_TIMEOUT}s | {clean_title}")
        return None
