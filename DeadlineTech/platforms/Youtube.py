import asyncio
import os
import re
import json
import uuid
import random
import logging
import aiohttp
import aiofiles
import config
import time
import yt_dlp
from pathlib import Path
from urllib.parse import urlparse
from typing import Union, Optional, Dict, Any, List
from pyrogram.types import Message
from pyrogram.enums import MessageEntityType
from youtubesearchpython.__future__ import VideosSearch

from DeadlineTech.utils.database import is_on_off
from DeadlineTech.utils.formatters import time_to_seconds

# === Configuration & Constants ===
YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")

# Download Constraints
TOTAL_RETRIES = 3            # Try the whole process 3 times
CYCLE_TIMEOUT = 60           # 60s hard limit per full attempt
V2_HTTP_RETRIES = 2          # Retries for small HTTP requests
CHUNK_SIZE = 1024 * 1024     # 1MB chunks

# Job Polling Config
JOB_POLL_ATTEMPTS = 15
JOB_POLL_INTERVAL = 1.5
JOB_POLL_BACKOFF = 1.1

# === Security & Helpers ===

def is_safe_url(url: str) -> bool:
    """Strictly validates that the URL is a safe YouTube link."""
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return False
        
        allowed_domains = (
            "youtube.com", "www.youtube.com", "m.youtube.com", 
            "youtu.be", "music.youtube.com"
        )
        if not any(domain in p.netloc for domain in allowed_domains):
            return False

        if any(char in url for char in [";", "|", "$", "`", "\n", "\r", "<", ">"]):
            return False

        return True
    except Exception:
        return False

def extract_safe_id(link: str) -> Optional[str]:
    """Extracts and validates ID to prevent Path Traversal."""
    try:
        if "v=" in link:
            vid = link.split("v=")[-1].split("&")[0]
        elif "youtu.be" in link:
            vid = link.split("/")[-1].split("?")[0]
        else:
            return None
            
        if YOUTUBE_ID_RE.match(vid):
            return vid
    except Exception:
        pass
    return None

def cookie_txt_file():
    cookie_dir = f"{os.getcwd()}/cookies"
    if not os.path.exists(cookie_dir):
        return None
    cookies_files = [f for f in os.listdir(cookie_dir) if f.endswith(".txt")]
    if not cookies_files:
        return None
    return os.path.join(cookie_dir, random.choice(cookies_files))

# === V2 API Implementation ===

class V2HardAPIError(Exception):
    def __init__(self, status: int):
        super().__init__(f"Hard API error status={status}")
        self.status = status

def _extract_candidate(obj: Any) -> Optional[str]:
    """Recursively finds a URL in the JSON response."""
    if not obj: return None
    if isinstance(obj, str) and obj.startswith("http"): return obj.strip()
    if isinstance(obj, list) and obj: return _extract_candidate(obj[0])
    if isinstance(obj, dict):
        for key in ["public_url", "cdnurl", "download_url", "url", "tg_link"]:
            val = obj.get(key)
            if val and isinstance(val, str) and val.startswith("http"):
                return val.strip()
        for key in ["job", "result", "results", "data"]:
            if obj.get(key):
                found = _extract_candidate(obj.get(key))
                if found: return found
    return None

def _looks_like_status(s: Optional[str]) -> bool:
    if not s: return False
    return any(x in s.lower() for x in ("job", "processing", "queued", "started"))

def _normalize_url(candidate: str) -> Optional[str]:
    api_url = getattr(config, "API_URL", None)
    if not api_url or not candidate: return None
    c = candidate.strip()
    
    # 1. Handle absolute
    if c.startswith("http"): return c

    # 2. Fix /root/ internal paths (The "Connection Reset" Fix)
    if "/root/" in c or "/home/" in c:
        if "downloads/" in c:
            clean_part = c.split("downloads/")[-1]
            # Assuming standard API structure: API_URL/media/downloads/...
            return f"{api_url.rstrip('/')}/media/downloads/{clean_part}"
        return None 

    # 3. Relative
    return f"{api_url.rstrip('/')}/{c.lstrip('/')}"

async def _v2_request(endpoint: str, params: Dict[str, Any], attempt_label: str) -> Optional[Any]:
    api_key = getattr(config, "API_KEY", None)
    api_url = getattr(config, "API_URL", None)
    
    if not api_url or not api_key:
        print("❌ API Config Missing")
        return None

    base = api_url.rstrip("/")
    url = f"{base}/{endpoint.lstrip('/')}"
    if "api_key" not in params:
        params["api_key"] = api_key

    timeout = aiohttp.ClientTimeout(total=15)
    
    for i in range(1, V2_HTTP_RETRIES + 1):
        try:
            print(f"📡 {attempt_label} | Req {i}/{V2_HTTP_RETRIES}")
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params, headers={"X-API-Key": api_key}) as resp:
                    if resp.status in (401, 403):
                        print(f"⛔ Auth Error {resp.status}")
                        raise V2HardAPIError(resp.status)
                    
                    if 200 <= resp.status < 300:
                        try:
                            return await resp.json(content_type=None)
                        except:
                            return None
                    
                    await asyncio.sleep(1)
        except V2HardAPIError:
            raise
        except Exception as e:
            print(f"⚠️ Req Fail")
            await asyncio.sleep(1)
    return None

async def _download_cdn(url: str, out_path: str) -> bool:
    print(f"🔗 CDN Download Start: {url}")
    folder = Path(out_path).parent
    folder.mkdir(parents=True, exist_ok=True)
    
    for i in range(1, 4): # 3 CDN retries
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        print(f"⚠️ CDN Status {resp.status} (Try {i})")
                        await asyncio.sleep(1)
                        continue
                    
                    async with aiofiles.open(out_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                            if not chunk: break
                            await f.write(chunk)
            
            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                print(f"✅ Downloaded: {out_path}")
                return True
        except Exception as e:
            print(f"⚠️ CDN Error")
            await asyncio.sleep(1)
    return False

# === Main V2 Logic ===

async def v2_download_process(link: str, video: bool) -> Optional[str]:
    """
    Full V2 download cycle with:
    - 3 Global Retries
    - 60s Timeout per cycle
    - Job Polling logging
    """
    vid = extract_safe_id(link)
    query = vid or link
    ext = "mp4" if video else "m4a"
    folder = Path("downloads/video" if video else "downloads/audio")
    safe_name = vid if vid else uuid.uuid4().hex[:10]
    out_path = folder / f"{safe_name}.{ext}"

    # Cache check
    if out_path.exists() and out_path.stat().st_size > 0:
        return str(out_path)

    async def _single_attempt(attempt_num: int):
        print(f"\n🔄 V2 Cycle {attempt_num}/{TOTAL_RETRIES} Started for {query}")
        
        # 1. Search / Init
        resp = await _v2_request(
            "youtube/v2/download", 
            {"query": query, "isVideo": str(video).lower()},
            f"Search (Cycle {attempt_num})"
        )
        if not resp: return None

        # 2. Extract Job ID
        job_id = None
        candidate = _extract_candidate(resp)
        
        if not candidate and isinstance(resp, dict):
            job = resp.get("job") or resp.get("job_id")
            if isinstance(job, dict): job_id = job.get("id")
            elif isinstance(job, str): job_id = job

        # 3. Poll if needed
        if job_id and (not candidate or _looks_like_status(candidate)):
            print(f"⏳ Job {job_id} Queued. Polling...")
            interval = JOB_POLL_INTERVAL
            
            for p_try in range(1, JOB_POLL_ATTEMPTS + 1):
                await asyncio.sleep(interval)
                print(f"🔎 Polling {p_try}/{JOB_POLL_ATTEMPTS} (Int: {interval:.1f}s)")
                
                status = await _v2_request("youtube/jobStatus", {"job_id": str(job_id)}, "Poll")
                candidate = _extract_candidate(status)
                
                if candidate and not _looks_like_status(candidate):
                    print("✅ Job Completed!")
                    break
                
                interval *= JOB_POLL_BACKOFF

        # 4. Normalize & Download
        final_url = _normalize_url(candidate)
        if not final_url:
            print("❌ No valid URL found after polling.")
            return None

        if await _download_cdn(final_url, str(out_path)):
            return str(out_path)
        return None

    # Global Retry Loop
    for cycle in range(1, TOTAL_RETRIES + 1):
        try:
            # ENFORCE 60s TIMEOUT HERE
            path = await asyncio.wait_for(
                _single_attempt(cycle), 
                timeout=CYCLE_TIMEOUT
            )
            if path: return path
            
        except asyncio.TimeoutError:
            print(f"⌛ Cycle {cycle} Timed Out (> {CYCLE_TIMEOUT}s)")
        except Exception as e:
            print(f"💥 Cycle {cycle} Crashed: {e}")
            
        await asyncio.sleep(2)

    return None


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if re.search(self.regex, link) and is_safe_url(link): return True
        return False

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
        for result in (await results.next())["result"]:
            title = result["title"]
            duration = result["duration"]
            thumb = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            sec = int(time_to_seconds(duration)) if duration else 0
            return title, duration, sec, thumb, vidid
        return None

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["title"]
        return ""

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["duration"]
        return "00:00"

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["thumbnails"][0]["url"].split("?")[0]
        return ""

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if not is_safe_url(link): return 0, "Unsafe URL"

        # 1. Try V2
        path = await v2_download_process(link, video=True)
        if path: return 1, path
        
        # 2. Cookies Fallback
        print("⚠️ V2 failed, trying Cookie fallback...")
        cookie_file = cookie_txt_file()
        if not cookie_file: return 0, "No cookies"
        
        cmd = ["yt-dlp", "--cookies", cookie_file, "-g", "-f", "best[height<=?720]", "--", link]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if stdout: return 1, stdout.decode().split("\n")[0]
        return 0, stderr.decode()

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
            if stdout:
                return [x for x in stdout.decode().split("\n") if x]
        except: pass
        return []

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return {
                "title": result["title"],
                "link": result["link"],
                "vidid": result["id"],
                "duration_min": result["duration"],
                "thumb": result["thumbnails"][0]["url"].split("?")[0],
            }, result["id"]
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
                        "format": f.get("format"),
                        "filesize": f.get("filesize"),
                        "format_id": f.get("format_id"),
                        "ext": f.get("ext"),
                        "format_note": f.get("format_note"),
                        "yturl": link
                    })
        except: pass
        return out, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        if not result or query_type >= len(result): return None
        r = result[query_type]
        return r["title"], r["duration"], r["thumbnails"][0]["url"].split("?")[0], r["id"]

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
        if videoid: link = self.base + link
        
        # Security
        if not is_safe_url(link):
            print("❌ Unsafe URL")
            return None, None

        # Prioritize V2 System
        is_vid = True if (video or songvideo) else False
        print(f"🚀 Starting Download for {link} (Video={is_vid})")

        path = await v2_download_process(link, video=is_vid)
        
        if path:
            return path, True
            
        print("❌ V2 System Failed All Retries.")
        
        # Legacy/Cookie Fallback (Only if V2 fails completely)
        cookie_file = cookie_txt_file()
        if not cookie_file: return None, None
        
        loop = asyncio.get_running_loop()
        def _legacy_dl():
            opts = {
                "format": "bestaudio/best" if not is_vid else "(bestvideo+bestaudio)",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "quiet": True, "cookiefile": cookie_file, "no_warnings": True
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=True)
                return os.path.join("downloads", f"{info['id']}.{info['ext']}")

        try:
            print("⚠️ Attempting Legacy Cookie Download...")
            path = await loop.run_in_executor(None, _legacy_dl)
            if path and os.path.exists(path): return path, True
        except Exception as e:
            print(f"Legacy Fail: {e}")

        return None, None
