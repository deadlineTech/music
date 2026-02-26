# Powered By Team DeadlineTech

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, Message

import config
from DeadlineTech import YouTube, app
from DeadlineTech.core.call import Anony
from DeadlineTech.misc import db
from DeadlineTech.utils.database import get_loop
from DeadlineTech.utils.decorators import AdminRightsCheck
from DeadlineTech.utils.inline import close_markup, stream_markup
from DeadlineTech.utils.stream.autoclear import auto_clean
from config import BANNED_USERS


@app.on_message(
    filters.command(["skip", "next"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck
async def skip(cli, message: Message, _, chat_id):
    if not len(message.command) < 2:
        loop = await get_loop(chat_id)
        if loop != 0:
            return await message.reply_text(_["admin_8"])
        state = message.text.split(None, 1)[1].strip()
        if state.isnumeric():
            state = int(state)
            check = db.get(chat_id)
            if check:
                count = len(check)
                if count > 2:
                    count = int(count - 1)
                    if 1 <= state <= count:
                        for x in range(state):
                            popped = None
                            try:
                                popped = check.pop(0)
                            except:
                                return await message.reply_text(_["admin_12"])
                            if popped:
                                await auto_clean(popped)
                            if not check:
                                try:
                                    await message.reply_text(
                                        text=_["admin_6"].format(
                                            message.from_user.mention,
                                            message.chat.title,
                                        ),
                                        reply_markup=close_markup(_),
                                    )
                                    await Anony.stop_stream(chat_id)
                                except:
                                    return
                                break
                    else:
                        return await message.reply_text(_["admin_11"].format(count))
                else:
                    return await message.reply_text(_["admin_10"])
            else:
                return await message.reply_text(_["queue_2"])
        else:
            return await message.reply_text(_["admin_9"])
    else:
        check = db.get(chat_id)
        popped = None
        try:
            popped = check.pop(0)
            if popped:
                await auto_clean(popped)
            if not check:
                await message.reply_text(
                    text=_["admin_6"].format(
                        message.from_user.mention, message.chat.title
                    ),
                    reply_markup=close_markup(_),
                )
                try:
                    return await Anony.stop_stream(chat_id)
                except:
                    return
        except:
            try:
                await message.reply_text(
                    text=_["admin_6"].format(
                        message.from_user.mention, message.chat.title
                    ),
                    reply_markup=close_markup(_),
                )
                return await Anony.stop_stream(chat_id)
            except:
                return
                
    queued = check[0]["file"]
    title = (check[0]["title"]).title()
    user = check[0]["by"]
    streamtype = check[0]["streamtype"]
    videoid = check[0]["vidid"]
    status = True if str(streamtype) == "video" else None
    db[chat_id][0]["played"] = 0
    exis = (check[0]).get("old_dur")
    if exis:
        db[chat_id][0]["dur"] = exis
        db[chat_id][0]["seconds"] = check[0]["old_second"]
        db[chat_id][0]["speed_path"] = None
        db[chat_id][0]["speed"] = 1.0
        
    if "live_" in queued:
        n, link = await YouTube.video(videoid, True)
        if n == 0:
            return await message.reply_text(_["admin_7"].format(title))
        try:
            await Anony.skip_stream(chat_id, link, video=status)
        except:
            return await message.reply_text(_["call_6"])
        button = stream_markup(_, chat_id)
        run = await message.reply_text(
            text=_["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{videoid}",
                title[:23],
                check[0]["dur"],
                user,
            ),
            reply_markup=InlineKeyboardMarkup(button),
            disable_web_page_preview=True
        )
        db[chat_id][0]["mystic"] = run
        db[chat_id][0]["markup"] = "tg"
        
    elif "vid_" in queued:
        mystic = await message.reply_text(_["call_7"], disable_web_page_preview=True)
        try:
            file_path, direct = await YouTube.download(
                videoid,
                mystic,
                videoid=True,
                video=status,
            )
        except:
            return await mystic.edit_text(_["call_6"])
        try:
            await Anony.skip_stream(chat_id, file_path, video=status)
        except:
            return await mystic.edit_text(_["call_6"])
        button = stream_markup(_, chat_id)
        run = await message.reply_text(
            text=_["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{videoid}",
                title[:23],
                check[0]["dur"],
                user,
            ),
            reply_markup=InlineKeyboardMarkup(button),
            disable_web_page_preview=True
        )
        db[chat_id][0]["mystic"] = run
        db[chat_id][0]["markup"] = "stream"
        await mystic.delete()
        
    elif "index_" in queued:
        try:
            await Anony.skip_stream(chat_id, videoid, video=status)
        except:
            return await message.reply_text(_["call_6"])
        button = stream_markup(_, chat_id)
        run = await message.reply_text(
            text=_["stream_2"].format(user),
            reply_markup=InlineKeyboardMarkup(button),
            disable_web_page_preview=True
        )
        db[chat_id][0]["mystic"] = run
        db[chat_id][0]["markup"] = "tg"
        
    else:
        try:
            await Anony.skip_stream(chat_id, queued, video=status)
        except:
            return await message.reply_text(_["call_6"])
            
        button = stream_markup(_, chat_id)
        if videoid == "telegram" or videoid == "soundcloud":
            run = await message.reply_text(
                text=_["stream_1"].format(
                    config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                ),
                reply_markup=InlineKeyboardMarkup(button),
                disable_web_page_preview=True
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
        else:
            run = await message.reply_text(
                text=_["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{videoid}",
                    title[:23],
                    check[0]["dur"],
                    user,
                ),
                reply_markup=InlineKeyboardMarkup(button),
                disable_web_page_preview=True
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"
