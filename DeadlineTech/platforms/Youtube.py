import asyncio
import os
import re
import json
import uuid
import random
import logging
import time
import aiohttp
import aiofiles
import yt_dlp
from pathlib import Path
from urllib.parse import urlparse
from typing import Union, Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorClient

# Pyrogram
from pyrogram.types import Message
from pyrogram.enums import MessageEntityType
from pyrogram.errors import FloodWait

from youtubesearchpython.__future__ import VideosSearch
from DeadlineTech import app as TG_APP
from DeadlineTech.utils.database import is_on_off
from DeadlineTech.utils.formatters import time_to_seconds
import config

# === Configuration & Constants ===
YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")
CHUNK_SIZE = 1024 * 1024

# Polling Settings (Like downloader.py)
JOB_POLL_ATTEMPTS = 10     # How many times to check status
JOB_POLL_INTERVAL = 2.0    # Seconds between checks
JOB_POLL_BACKOFF = 1.1     # Increase interval slightly each time
HARD_TIMEOUT = 60         # 5 Minutes Max Total
TG_FLOOD_COOLDOWN = 0.0

# === Database Config ===
MEDIA_CHANNEL_ID = config.MEDIA_CHANNEL_ID
DB_URI = config.DB_URI
MEDIA_DB_NAME = getattr(config, "MEDIA_DB_NAME", "arcapi")
MEDIA_COLLECTION_NAME = getattr(config, "MEDIA_COLLECTION_NAME", "medias")

# === Statistics System ===
DOWNLOAD_STATS: Dict[str, int] = {
    "total": 0, "success": 0, "failed": 0,
    "db_hit": 0, "v2_success": 0, "cookie_success": 0,
    "db_miss": 0, "db_fail": 0
}

def _inc(key: str):
    DOWNLOAD_STATS[key] = DOWNLOAD_STATS.get(key, 0) + 1

def get_stats() -> Dict[str, Any]:
    s = DOWNLOAD_STATS.copy()
    total = s["total"]
    s["success_rate"] = f"{(s['success'] / total) * 100:.2f}%" if total > 0 else "0.00%"
    return s

# === Database & Media Channel Helpers ===

_MONGO_CLIENT = None

def _get_media_collection():
    global _MONGO_CLIENT
    if not DB_URI: return None
    if _MONGO_CLIENT is None:
        _MONGO_CLIENT = AsyncIOMotorClient(DB_URI)
    return _MONGO_CLIENT[MEDIA_DB_NAME][MEDIA_COLLECTION_NAME]

async def is_media(track_id: str, isVideo: bool = False) -> bool:
    col = _get_media_collection()
    if col is None: return False
    doc = await col.find_one({
        "$or": [
            {"track_id": track_id, "isVideo": isVideo},
            {"track_id": f"{track_id}.{'mp4' if isVideo else 'mp3'}"}
        ]
    }, {"_id": 1})
    return bool(doc)

async def get_media_id(track_id: str, isVideo: bool = False) -> Optional[int]:
    col = _get_media_collection()
    if col is None: return None
    doc = await col.find_one({
        "$or": [
            {"track_id": track_id, "isVideo": isVideo},
            {"track_id": f"{track_id}.{'mp4' if isVideo else 'mp3'}"}
        ]
    }, {"message_id": 1})
    return int(doc.get("message_id")) if doc and doc.get("message_id") else None

def _resolve_if_dir(path_str: str) -> Optional[str]:
    if not path_str: return None
    p = Path(path_str)
    if p.exists() and p.is_file(): return str(p)
    if p.exists() and p.is_dir():
        files = [x for x in p.iterdir() if x.is_file()]
        return str(max(files, key=lambda x: x.stat().st_mtime)) if files else None
    return path_str

async def _download_from_media_db(track_id: str, is_video: bool) -> Optional[str]:
    global TG_FLOOD_COOLDOWN
    if not track_id or not TG_APP or not MEDIA_CHANNEL_ID: return None

    if time.time() < TG_FLOOD_COOLDOWN: 
        _inc("db_fail")
        return None

    msg_id = await get_media_id(track_id, isVideo=is_video)
    
    if not msg_id:
        _inc("db_miss")
        return None

    _inc("db_hit")
    print(f"⚡ Media DB Hit: {track_id} (MsgID: {msg_id})")
    
    ext = "mp4" if is_video else "mp3"
    out_dir = Path("downloads/video" if is_video else "downloads/audio")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    final_path = out_dir / f"{track_id}.{ext}"
    tmp_path = str(final_path) + ".temp"

    if final_path.exists() and final_path.stat().st_size > 0:
        return str(final_path)

    try:
        msg = await TG_APP.get_messages(MEDIA_CHANNEL_ID, msg_id)
        if not msg or not msg.media: return None

        dl_res = await asyncio.wait_for(
            TG_APP.download_media(msg, file_name=tmp_path),
            timeout=HARD_TIMEOUT
        )
        
        fixed = _resolve_if_dir(dl_res)
        if fixed and os.path.exists(fixed):
            if fixed != str(final_path):
                os.replace(fixed, final_path)
            return str(final_path)

    except FloodWait as e:
        TG_FLOOD_COOLDOWN = time.time() + e.value + 10
        print(f"⚠️ FloodWait: {e.value}s")
    except Exception as e:
        print(f"❌ DB Download Fail: {e}")
        _inc("db_fail")
    
    return None

# === Existing Helpers ===

def is_safe_url(url: str) -> bool:
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https"): return False
        allowed = ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "music.youtube.com")
        return any(d in p.netloc for d in allowed)
    except: return False

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

# === V2 API with Polling (Logic from downloader.py) ===

def _normalize_url(candidate: str) -> Optional[str]:
    api_url = getattr(config, "API_URL", None)
    if not api_url or not candidate: return None
    c = candidate.strip()
    # Remove internal server paths
    if "/root/" in c or "/home/" in c:
        if "downloads/" in c:
            clean = c.split("downloads/")[-1]
            return f"{api_url.rstrip('/')}/media/downloads/{clean}"
        return None 
    if c.startswith("http"): return c
    return f"{api_url.rstrip('/')}/{c.lstrip('/')}"

def _extract_candidate(obj: Any) -> Optional[str]:
    if not obj: return None
    if isinstance(obj, str) and obj.startswith("http"): return obj
    if isinstance(obj, dict):
        # Check job result
        job = obj.get("job")
        if isinstance(job, dict):
            res = job.get("result")
            if isinstance(res, dict):
                 return res.get("public_url") or res.get("url")
        # Check direct result
        return obj.get("public_url") or obj.get("url")
    return None

async def _download_cdn(url: str, out_path: str) -> bool:
    print(f"🔗 Downloading from CDN: {url}")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    for i in range(1, 3):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600)) as session:
                async with session.get(url) as resp:
                    if resp.status != 200: 
                        await asyncio.sleep(1)
                        continue
                    async with aiofiles.open(out_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                            if not chunk: break
                            await f.write(chunk)
            if os.path.exists(out_path) and os.path.getsize(out_path) > 0: return True
        except Exception as e:
            print(f"CDN Fail: {e}")
        await asyncio.sleep(1)
    return False

async def v2_download_process(link: str, video: bool) -> Optional[str]:
    vid = extract_safe_id(link) or uuid.uuid4().hex[:10]
    ext = "mp4" if video else "m4a"
    out_path = Path("downloads/video" if video else "downloads/audio") / f"{vid}.{ext}"

    if out_path.exists() and out_path.stat().st_size > 0: return str(out_path)

    api_key = getattr(config, "API_KEY", None)
    api_url = getattr(config, "API_URL", None)
    if not api_url or not api_key: return None

    # V2 Logic: Start Job -> Get ID -> Poll
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # 1. Start Job
            url = f"{api_url.rstrip('/')}/youtube/v2/download"
            params = {"query": vid, "isVideo": str(video).lower(), "api_key": api_key}
            
            print(f"📡 V2 Job Start: {vid}...")
            async with session.get(url, params=params) as resp:
                if resp.status != 200: return None
                data = await resp.json()

            job_id = data.get("job_id")
            if not job_id: return None

            # 2. Poll Status
            print(f"⏳ Polling Job: {job_id}")
            interval = JOB_POLL_INTERVAL
            final_url = None

            for _ in range(JOB_POLL_ATTEMPTS):
                await asyncio.sleep(interval)
                status_url = f"{api_url.rstrip('/')}/youtube/jobStatus"
                async with session.get(status_url, params={"job_id": job_id}) as s_resp:
                    if s_resp.status == 200:
                        s_data = await s_resp.json()
                        job_data = s_data.get("job", {})
                        status = job_data.get("status")
                        
                        if status == "done":
                            final_url = _normalize_url(_extract_candidate(s_data))
                            break
                        elif status == "error":
                            print(f"❌ Job Error: {job_data.get('error')}")
                            return None
                
                interval *= JOB_POLL_BACKOFF
            
            # 3. Download if success
            if final_url:
                if await _download_cdn(final_url, str(out_path)):
                    return str(out_path)

    except Exception as e:
        print(f"V2 Polling Error: {e}")
    
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
        for r in (await results.next())["result"]:
            sec = int(time_to_seconds(r["duration"])) if r["duration"] else 0
            return r["title"], r["duration"], sec, r["thumbnails"][0]["url"].split("?")[0], r["id"]
        return None

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        results = VideosSearch(link, limit=1)
        for r in (await results.next())["result"]: return r["title"]
        return ""

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        results = VideosSearch(link, limit=1)
        for r in (await results.next())["result"]: return r["duration"]
        return "00:00"

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        results = VideosSearch(link, limit=1)
        for r in (await results.next())["result"]: return r["thumbnails"][0]["url"].split("?")[0]
        return ""

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if not is_safe_url(link): return 0, "Unsafe URL"
        
        # 1. DB CHECK
        vid = extract_safe_id(link)
        if vid:
            db_path = await _download_from_media_db(vid, is_video=True)
            if db_path: return 1, db_path

        # 2. V2 API (Polling)
        path = await v2_download_process(link, video=True)
        if path: return 1, path
        
        # 3. Cookies
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
            if stdout: return [x for x in stdout.decode().split("\n") if x]
        except: pass
        return []

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        results = VideosSearch(link, limit=1)
        for r in (await results.next())["result"]:
            return {
                "title": r["title"], "link": r["link"], "vidid": r["id"],
                "duration_min": r["duration"], "thumb": r["thumbnails"][0]["url"].split("?")[0],
            }, r["id"]
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
        _inc("total")
        if videoid: link = self.base + link
        if not is_safe_url(link):
            _inc("failed")
            return None, None

        is_vid = True if (video or songvideo) else False
        vid = extract_safe_id(link) or videoid

        # 1. PRIORITY: MEDIA DB
        if vid:
            db_path = await _download_from_media_db(vid, is_video=is_vid)
            if db_path:
                _inc("success")
                return db_path, True
        
        # 2. V2 API (Polling)
        path = await v2_download_process(link, video=is_vid)
        if path:
            _inc("success")
            _inc("v2_success")
            return path, True
            
        # 3. COOKIE FALLBACK
        _inc("v2_error")
        cookie_file = cookie_txt_file()
        if not cookie_file:
            _inc("failed")
            return None, None
        
        loop = asyncio.get_running_loop()
        def _legacy_dl():
            opts = {
                "format": "bestaudio/best" if not is_vid else "(bestvideo+bestaudio)",
                "outtmpl": "downloads/%(id)s.%(ext)s", "quiet": True, 
                "cookiefile": cookie_file, "no_warnings": True
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=True)
                return os.path.join("downloads", f"{info['id']}.{info['ext']}")

        try:
            path = await loop.run_in_executor(None, _legacy_dl)
            if path and os.path.exists(path):
                _inc("success")
                _inc("cookie_success")
                return path, True
        except Exception:
            _inc("cookie_error")

        _inc("failed")
        return None, None



