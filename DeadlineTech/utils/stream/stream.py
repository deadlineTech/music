from typing import Union

from pyrogram.types import InlineKeyboardMarkup

import config
from DeadlineTech import YouTube, app
from DeadlineTech.core.call import Anony
from DeadlineTech.misc import db
from DeadlineTech.utils.database import add_active_video_chat, is_active_chat
from DeadlineTech.utils.exceptions import AssistantErr
from DeadlineTech.utils.inline import aq_markup, close_markup, stream_markup
from DeadlineTech.utils.pastebin import AnonyBin
from DeadlineTech.utils.stream.queue import put_queue, put_queue_index


async def stream(
    _,
    mystic,
    user_id,
    result,
    chat_id,
    user_name,
    original_chat_id,
    video: Union[bool, str] = None,
    streamtype: Union[bool, str] = None,
    spotify: Union[bool, str] = None,
    forceplay: Union[bool, str] = None,
):
    if not result:
        return
    if forceplay:
        await Anony.force_stop_stream(chat_id)
        
    if streamtype == "playlist":
        msg = f"{_['play_19']}\n\n"
        count = 0
        for search in result:
            if int(count) == config.PLAYLIST_FETCH_LIMIT:
                continue
            try:
                (title, duration_min, duration_sec, _, vidid) = await YouTube.details(search, False if spotify else True)
            except:
                continue
            if str(duration_min) == "None":
                continue
            if duration_sec > config.DURATION_LIMIT:
                continue
                
            if await is_active_chat(chat_id):
                await put_queue(
                    chat_id, original_chat_id, f"vid_{vidid}", title, duration_min, user_name, vidid, user_id, "video" if video else "audio"
                )
                position = len(db.get(chat_id)) - 1
                count += 1
                msg += f"{count}. {title[:70]}\n"
                msg += f"{_['play_20']} {position}\n\n"
            else:
                if not forceplay:
                    db[chat_id] = []
                status = True if video else None
                try:
                    file_path, direct = await YouTube.download(vidid, mystic, video=status, videoid=True)
                except:
                    # 🟢 FIX: If the 1st song of the Personal Playlist fails to download, 
                    # DON'T crash the playlist! Just skip it and try the next song!
                    continue
                    
                if not file_path:
                    continue # 🟢 FIX: Skip broken 1st song and try the next!
                    
                await Anony.join_call(chat_id, original_chat_id, file_path, video=status)
                await put_queue(
                    chat_id, original_chat_id, file_path if direct else f"vid_{vidid}", title, duration_min, user_name, vidid, user_id, "video" if video else "audio", forceplay=forceplay
                )
                
                button = stream_markup(_, chat_id)
                run = await app.send_message(
                    original_chat_id,
                    text=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{vidid}", title[:23], duration_min, user_name),
                    reply_markup=InlineKeyboardMarkup(button),
                    disable_web_page_preview=True
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
                count += 1
                
        if count == 0:
            # If literally EVERY song in the personal playlist failed to download
            try:
                await mystic.edit_text(_["play_14"])
            except:
                pass
            return
        else:
            link = await AnonyBin(msg)
            upl = close_markup(_)
            return await app.send_message(
                original_chat_id,
                text=_["play_21"].format(count, link),
                reply_markup=upl,
                disable_web_page_preview=True
            )
            
    elif streamtype == "youtube":
        link = result["link"]
        vidid = result["vidid"]
        title = (result["title"]).title()
        duration_min = result["duration_min"]
        status = True if video else None
        try:
            file_path, direct = await YouTube.download(vidid, mystic, videoid=True, video=status)
        except Exception as ex:
            raise AssistantErr(_["play_14"])
            
        if not file_path:
            raise AssistantErr(_["play_14"])
            
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id, original_chat_id, file_path if direct else f"vid_{vidid}", title, duration_min, user_name, vidid, user_id, "video" if video else "audio"
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
                disable_web_page_preview=True
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await Anony.join_call(chat_id, original_chat_id, file_path, video=status)
            await put_queue(
                chat_id, original_chat_id, file_path if direct else f"vid_{vidid}", title, duration_min, user_name, vidid, user_id, "video" if video else "audio", forceplay=forceplay
            )
            
            button = stream_markup(_, chat_id)
            run = await app.send_message(
                original_chat_id,
                text=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{vidid}", title[:23], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
                disable_web_page_preview=True
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"
            
    elif streamtype == "telegram":
        file_path = result["path"]
        link = result["link"]
        title = (result["title"]).title()
        duration_min = result["dur"]
        status = True if video else None
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id, original_chat_id, file_path, title, duration_min, user_name, streamtype, user_id, "video" if video else "audio"
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
                disable_web_page_preview=True
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await Anony.join_call(chat_id, original_chat_id, file_path, video=status)
            await put_queue(
                chat_id, original_chat_id, file_path, title, duration_min, user_name, streamtype, user_id, "video" if video else "audio", forceplay=forceplay
            )
            if video:
                await add_active_video_chat(chat_id)
            button = stream_markup(_, chat_id)
            run = await app.send_message(
                original_chat_id,
                text=_["stream_1"].format(link, title[:23], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
                disable_web_page_preview=True
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
            
    elif streamtype == "live":
        link = result["link"]
        vidid = result["vidid"]
        title = (result["title"]).title()
        duration_min = "Live Track"
        status = True if video else None
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id, original_chat_id, f"live_{vidid}", title, duration_min, user_name, vidid, user_id, "video" if video else "audio"
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
                disable_web_page_preview=True
            )
        else:
            if not forceplay:
                db[chat_id] = []
            n, file_path = await YouTube.video(link)
            if n == 0:
                raise AssistantErr(_["str_3"])
            await Anony.join_call(chat_id, original_chat_id, file_path, video=status)
            await put_queue(
                chat_id, original_chat_id, f"live_{vidid}", title, duration_min, user_name, vidid, user_id, "video" if video else "audio", forceplay=forceplay
            )
            button = stream_markup(_, chat_id)
            run = await app.send_message(
                original_chat_id,
                text=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{vidid}", title[:23], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
                disable_web_page_preview=True
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
