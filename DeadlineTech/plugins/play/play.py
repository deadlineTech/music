# Powered By Team DeadlineTech

import random
import string

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, Message
from pytgcalls.exceptions import NoActiveGroupCall

import config
from DeadlineTech import Spotify, Telegram, YouTube, app
from DeadlineTech.core.call import Anony
from DeadlineTech.utils import seconds_to_min, time_to_seconds
from DeadlineTech.utils.database import get_user_playlists
from DeadlineTech.utils.decorators.language import languageCB
from DeadlineTech.utils.decorators.play import PlayWrapper
from DeadlineTech.utils.formatters import formats
from DeadlineTech.utils.inline import (
    botplaylist_markup,
    livestream_markup,
    playlist_markup,
    slider_markup,
    track_markup,
)
from DeadlineTech.utils.logger import play_logs
from DeadlineTech.utils.stream.stream import stream
from config import lyrical


@app.on_message(
    filters.command(["play", "vplay", "playforce", "vplayforce"])
    & filters.group
)
@PlayWrapper
async def play_commnd(
    client,
    message: Message,
    _,
    chat_id,
    video,
    playmode,
    url,
    fplay,
):
    mystic = await message.reply_text(_["play_1"])
    plist_id = None
    slider = None
    plist_type = None
    spotify = None
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    audio_telegram = (
        (message.reply_to_message.audio or message.reply_to_message.voice)
        if message.reply_to_message else None
    )
    video_telegram = (
        (message.reply_to_message.video or message.reply_to_message.document)
        if message.reply_to_message else None
    )
    
    if audio_telegram:
        if audio_telegram.file_size > 104857600:
            return await mystic.edit_text(_["play_5"])
        if (audio_telegram.duration) > config.DURATION_LIMIT:
            return await mystic.edit_text(_["play_6"].format(config.DURATION_LIMIT_MIN, app.mention))
        file_path = await Telegram.get_filepath(audio=audio_telegram)
        if await Telegram.download(_, message, mystic, file_path):
            message_link = await Telegram.get_link(message)
            file_name = await Telegram.get_filename(audio_telegram, audio=True)
            dur = await Telegram.get_duration(audio_telegram, file_path)
            details = {
                "title": file_name,
                "link": message_link,
                "path": file_path,
                "dur": dur,
            }

            try:
                await stream(_, mystic, user_id, details, chat_id, user_name, message.chat.id, streamtype="telegram", forceplay=fplay)
            except Exception as e:
                ex_type = type(e).__name__
                err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
                return await mystic.edit_text(err)
            return await mystic.delete()
        return
        
    elif video_telegram:
        if message.reply_to_message.document:
            try:
                ext = video_telegram.file_name.split(".")[-1]
                if ext.lower() not in formats:
                    return await mystic.edit_text(_["play_7"].format(f"{' | '.join(formats)}"))
            except:
                return await mystic.edit_text(_["play_7"].format(f"{' | '.join(formats)}"))
        if video_telegram.file_size > config.TG_VIDEO_FILESIZE_LIMIT:
            return await mystic.edit_text(_["play_8"])
        file_path = await Telegram.get_filepath(video=video_telegram)
        if await Telegram.download(_, message, mystic, file_path):
            message_link = await Telegram.get_link(message)
            file_name = await Telegram.get_filename(video_telegram)
            dur = await Telegram.get_duration(video_telegram, file_path)
            details = {
                "title": file_name,
                "link": message_link,
                "path": file_path,
                "dur": dur,
            }
            try:
                await stream(_, mystic, user_id, details, chat_id, user_name, message.chat.id, video=True, streamtype="telegram", forceplay=fplay)
            except Exception as e:
                ex_type = type(e).__name__
                err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
                return await mystic.edit_text(err)
            return await mystic.delete()
        return
        
    elif url:
        if await YouTube.exists(url):
            if "playlist" in url:
                try:
                    details = await YouTube.playlist(url, config.PLAYLIST_FETCH_LIMIT, message.from_user.id)
                except:
                    return await mystic.edit_text(_["play_3"])
                if not details:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "yt"
                if "&" in url:
                    plist_id = (url.split("=")[1]).split("&")[0]
                else:
                    plist_id = url.split("=")[1]
                cap = _["play_9"]
            else:
                try:
                    details, track_id = await YouTube.track(url)
                except:
                    return await mystic.edit_text(_["play_3"])
                if not details:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "youtube"
                cap = _["play_10"].format(details["title"], details["duration_min"])
                
        elif await Spotify.valid(url):
            spotify = True
            if not config.SPOTIFY_CLIENT_ID and not config.SPOTIFY_CLIENT_SECRET:
                return await mystic.edit_text("» sᴘᴏᴛɪғʏ ɪs ɴᴏᴛ sᴜᴘᴘᴏʀᴛᴇᴅ ʏᴇᴛ.\n\nᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.")
            if "track" in url:
                try:
                    details, track_id = await Spotify.track(url)
                except:
                    return await mystic.edit_text(_["play_3"])
                if not details:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "youtube"
                cap = _["play_10"].format(details["title"], details["duration_min"])
            elif "playlist" in url:
                try:
                    details, plist_id = await Spotify.playlist(url)
                except Exception:
                    return await mystic.edit_text(_["play_3"])
                if not details:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "spplay"
                cap = _["play_11"].format(app.mention, message.from_user.mention)
            elif "album" in url:
                try:
                    details, plist_id = await Spotify.album(url)
                except:
                    return await mystic.edit_text(_["play_3"])
                if not details:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "spalbum"
                cap = _["play_11"].format(app.mention, message.from_user.mention)
            elif "artist" in url:
                try:
                    details, plist_id = await Spotify.artist(url)
                except:
                    return await mystic.edit_text(_["play_3"])
                if not details:
                    return await mystic.edit_text(_["play_3"])
                streamtype = "playlist"
                plist_type = "spartist"
                cap = _["play_11"].format(message.from_user.first_name)
            else:
                return await mystic.edit_text(_["play_15"])
        else:
            try:
                await Anony.stream_call(url)
            except NoActiveGroupCall:
                await mystic.edit_text(_["black_9"])
                return await app.send_message(chat_id=config.LOGGER_ID, text=_["play_17"])
            except Exception as e:
                return await mystic.edit_text(_["general_2"].format(type(e).__name__))
            await mystic.edit_text(_["str_2"])
            try:
                await stream(_, mystic, message.from_user.id, url, chat_id, message.from_user.first_name, message.chat.id, video=video, streamtype="index", forceplay=fplay)
            except Exception as e:
                ex_type = type(e).__name__
                err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
                return await mystic.edit_text(err)
            return await play_logs(message, streamtype="M3u8 or Index Link")
            
    else:
        if len(message.command) < 2:
            buttons = botplaylist_markup(_)
            return await mystic.edit_text(_["play_18"], reply_markup=InlineKeyboardMarkup(buttons))
        
        query = message.text.split(None, 1)[1]
        if "-v" in query:
            query = query.replace("-v", "").strip()

        # ==========================================
        # 🟢 PERSONAL PLAYLIST QUEUE SYSTEM
        # ==========================================
        user_data = await get_user_playlists(user_id)
        user_playlists = user_data.get("playlists", {})
        
        if query in user_playlists:
            tracks = user_playlists[query]
            if not tracks:
                return await mystic.edit_text(f"❌ Your playlist **{query}** is empty.")
            
            # FIX: We now pass ONLY the raw videoids to the queue system!
            playlist_vids = [t['videoid'] for t in tracks]
            
            try:
                await stream(
                    _, mystic, user_id, playlist_vids, chat_id, user_name, 
                    message.chat.id, video=video, streamtype="playlist", forceplay=fplay
                )
            except Exception as e:
                ex_type = type(e).__name__
                err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
                return await mystic.edit_text(err)
            
            try:
                await mystic.delete()
            except:
                pass
            return await play_logs(message, streamtype=f"Personal Playlist: {query}")
        # ==========================================
            
        slider = True
        try:
            details, track_id = await YouTube.track(query)
        except Exception as ex:
            return await mystic.edit_text(_["play_3"])
            
        if not details:
            return await mystic.edit_text(_["play_3"])
            
        streamtype = "youtube"

    if str(playmode) == "Direct":
        if not plist_type:
            if details["duration_min"]:
                duration_sec = time_to_seconds(details["duration_min"])
                if duration_sec > config.DURATION_LIMIT:
                    return await mystic.edit_text(_["play_6"].format(config.DURATION_LIMIT_MIN, app.mention))
            else:
                buttons = livestream_markup(_, track_id, user_id, "v" if video else "a", "g", "f" if fplay else "d")
                return await mystic.edit_text(_["play_13"], reply_markup=InlineKeyboardMarkup(buttons))
        try:
            await stream(_, mystic, user_id, details, chat_id, user_name, message.chat.id, video=video, streamtype=streamtype, spotify=spotify, forceplay=fplay)
        except Exception as e:
            ex_type = type(e).__name__
            err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
            return await mystic.edit_text(err)
        await mystic.delete()
        return await play_logs(message, streamtype=streamtype)
    else:
        if plist_type:
            ran_hash = "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
            lyrical[ran_hash] = plist_id
            buttons = playlist_markup(_, ran_hash, message.from_user.id, plist_type, "g", "f" if fplay else "d")
            await mystic.delete()
            await message.reply_text(text=cap, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
            return await play_logs(message, streamtype=f"Playlist : {plist_type}")
        else:
            if slider:
                buttons = slider_markup(_, track_id, message.from_user.id, query, 0, "g", "f" if fplay else "d")
                await mystic.delete()
                await message.reply_text(
                    text=_["play_10"].format(details["title"].title(), details["duration_min"]),
                    reply_markup=InlineKeyboardMarkup(buttons),
                    disable_web_page_preview=True
                )
                return await play_logs(message, streamtype=f"Searched on Youtube")
            else:
                buttons = track_markup(_, track_id, message.from_user.id, "g", "f" if fplay else "d")
                await mystic.delete()
                await message.reply_text(text=cap, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
                return await play_logs(message, streamtype=f"URL Searched Inline")


@app.on_callback_query(filters.regex("MusicStream"))
@languageCB
async def play_music(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    vidid, user_id, mode, cplay, fplay = callback_request.split("|")
    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except:
            return

    user_name = CallbackQuery.from_user.first_name
    try:
        await CallbackQuery.message.delete()
        await CallbackQuery.answer()
    except:
        pass
    mystic = await CallbackQuery.message.reply_text(_["play_1"])
    try:
        details, track_id = await YouTube.track(vidid, True)
    except:
        return await mystic.edit_text(_["play_3"])
        
    if not details:
        return await mystic.edit_text(_["play_3"])
        
    if details["duration_min"]:
        duration_sec = time_to_seconds(details["duration_min"])
        if duration_sec > config.DURATION_LIMIT:
            return await mystic.edit_text(_["play_6"].format(config.DURATION_LIMIT_MIN, app.mention))
    else:
        buttons = livestream_markup(_, track_id, CallbackQuery.from_user.id, mode, "g", "f" if fplay else "d")
        return await mystic.edit_text(_["play_13"], reply_markup=InlineKeyboardMarkup(buttons))
    video = True if mode == "v" else None
    ffplay = True if fplay == "f" else None
    try:
        await stream(_, mystic, CallbackQuery.from_user.id, details, CallbackQuery.message.chat.id, user_name, CallbackQuery.message.chat.id, video, streamtype="youtube", forceplay=ffplay)
    except Exception as e:
        ex_type = type(e).__name__
        err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
        return await mystic.edit_text(err)
    return await mystic.delete()


@app.on_callback_query(filters.regex("AnonymousAdmin"))
async def anonymous_check(client, CallbackQuery):
    try:
        await CallbackQuery.answer(
            "» ʀᴇᴠᴇʀᴛ ʙᴀᴄᴋ ᴛᴏ ᴜsᴇʀ ᴀᴄᴄᴏᴜɴᴛ :\n\nᴏᴘᴇɴ ʏᴏᴜʀ ɢʀᴏᴜᴘ sᴇᴛᴛɪɴɢs.\n-> ᴀᴅᴍɪɴɪsᴛʀᴀᴛᴏʀs\n-> ᴄʟɪᴄᴋ ᴏɴ ʏᴏᴜʀ ɴᴀᴍᴇ\n-> ᴜɴᴄʜᴇᴄᴋ ᴀɴᴏɴʏᴍᴏᴜs ᴀᴅᴍɪɴ ᴘᴇʀᴍɪssɪᴏɴs.",
            show_alert=True,
        )
    except:
        pass


@app.on_callback_query(filters.regex("AnonyPlaylists"))
@languageCB
async def play_playlists_command(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    videoid, user_id, ptype, mode, cplay, fplay = callback_request.split("|")
    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except:
            return

    user_name = CallbackQuery.from_user.first_name
    await CallbackQuery.message.delete()
    try:
        await CallbackQuery.answer()
    except:
        pass
    mystic = await CallbackQuery.message.reply_text(_["play_1"])
    videoid = lyrical.get(videoid)
    video = True if mode == "v" else None
    ffplay = True if fplay == "f" else None
    spotify = True
    
    if ptype == "yt":
        spotify = False
        try:
            result = await YouTube.playlist(videoid, config.PLAYLIST_FETCH_LIMIT, CallbackQuery.from_user.id, True)
        except:
            return await mystic.edit_text(_["play_3"])
    if ptype == "spplay":
        try:
            result, spotify_id = await Spotify.playlist(videoid)
        except:
            return await mystic.edit_text(_["play_3"])
    if ptype == "spalbum":
        try:
            result, spotify_id = await Spotify.album(videoid)
        except:
            return await mystic.edit_text(_["play_3"])
    if ptype == "spartist":
        try:
            result, spotify_id = await Spotify.artist(videoid)
        except:
            return await mystic.edit_text(_["play_3"])

    if not result:
        return await mystic.edit_text(_["play_3"])

    try:
        await stream(_, mystic, user_id, result, CallbackQuery.message.chat.id, user_name, CallbackQuery.message.chat.id, video, streamtype="playlist", spotify=spotify, forceplay=ffplay)
    except Exception as e:
        ex_type = type(e).__name__
        err = e if ex_type == "AssistantErr" else _["general_2"].format(ex_type)
        return await mystic.edit_text(err)
    return await mystic.delete()


@app.on_callback_query(filters.regex("slider"))
@languageCB
async def slider_queries(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    what, rtype, query, user_id, cplay, fplay = callback_request.split("|")
    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except:
            return
            
    what = str(what)
    rtype = int(rtype)
    query_type = int(rtype + 1) if what == "F" and rtype != 9 else (0 if what == "F" else (9 if rtype == 0 else int(rtype - 1)))
    
    try:
        await CallbackQuery.answer(_["playcb_2"])
    except:
        pass
        
    try:
        title, duration_min, thumbnail, vidid = await YouTube.slider(query, query_type)
    except:
        return await CallbackQuery.edit_message_text(_["play_3"])
        
    buttons = slider_markup(_, vidid, user_id, query, query_type, "g", fplay)
    
    return await CallbackQuery.edit_message_text(
        text=_["play_10"].format(title.title(), duration_min),
        reply_markup=InlineKeyboardMarkup(buttons)
    )
