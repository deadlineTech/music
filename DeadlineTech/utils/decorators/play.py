# DeadlineTech/utils/decorators/play.py

import asyncio
import logging
import traceback

from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import (
    ChatAdminRequired,
    InviteRequestSent,
    UserAlreadyParticipant,
    UserNotParticipant,
    ChannelsTooMuch,
    RPCError,
)
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from DeadlineTech import YouTube, app
from DeadlineTech.misc import SUDOERS
from DeadlineTech.utils.database import (
    get_assistant,
    get_lang,
    get_playmode,
    get_playtype,
    is_active_chat,
    is_maintenance,
)
from DeadlineTech.utils.inline import botplaylist_markup
from config import SUPPORT_CHAT, adminlist
from strings import get_string

logger = logging.getLogger(__name__)

links = {}

def PlayWrapper(command):
    async def wrapper(client, message):
        try:
            language = await get_lang(message.chat.id)
            _ = get_string(language)

            if message.sender_chat:
                return await message.reply_text(
                    _["general_3"],
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton(text="ʕᵒˡ ᴛʏ ꟾɪʏ ?", callback_data="AnonymousAdmin")]]
                    )
                )

            if await is_maintenance() is False and message.from_user.id not in SUDOERS:
                return await message.reply_text(
                    f"{app.mention} is under maintenance.\nPlease visit <a href={SUPPORT_CHAT}>support chat</a>.",
                    disable_web_page_preview=True
                )

            # SILENCED MESSAGE DELETION ERROR
            try:
                await message.delete()
            except Exception:
                pass

            audio = (message.reply_to_message.audio or message.reply_to_message.voice) if message.reply_to_message else None
            video = (message.reply_to_message.video or message.reply_to_message.document) if message.reply_to_message else None
            url = await YouTube.url(message)

            if not audio and not video and not url:
                if len(message.command) < 2:
                    if "stream" in message.command:
                        return await message.reply_text(_["str_1"])
                    return await message.reply_text(
                        _["play_18"],
                        reply_markup=InlineKeyboardMarkup(botplaylist_markup(_)),
                    )

            # REMOVED CHANNEL CHECK
            chat_id = message.chat.id

            playmode = await get_playmode(message.chat.id)
            playty = await get_playtype(message.chat.id)
            if playty != "Everyone" and message.from_user.id not in SUDOERS:
                admins = adminlist.get(message.chat.id)
                if not admins or message.from_user.id not in admins:
                    return await message.reply_text(_["play_4"])

            is_video = (
                True if message.command[0][0] == "v" or "-v" in message.text
                else (True if len(message.command[0]) > 1 and message.command[0][1] == "v" else None)
            )
            fplay = True if message.command[0][-1] == "e" else None

            # CHECK ASSISTANT MEMBERSHIP
            if not await is_active_chat(chat_id):
                userbot = await get_assistant(chat_id)
                try:
                    member = await app.get_chat_member(chat_id, userbot.id)
                    if member.status in [ChatMemberStatus.BANNED, ChatMemberStatus.RESTRICTED]:
                        return await message.reply_text(
                            _["call_2"].format(app.mention, userbot.id, userbot.name, userbot.username)
                        )
                except ChatAdminRequired:
                    pass
                except UserNotParticipant:
                    invite_link = links.get(chat_id)
                    if not invite_link:
                        if message.chat.username:
                            invite_link = message.chat.username
                        else:
                            try:
                                invite_link = await app.export_chat_invite_link(chat_id)
                            except ChatAdminRequired:
                                return await message.reply_text(_["call_1"])
                            except Exception as e:
                                return await message.reply_text(_["call_3"].format(app.mention, type(e).__name__))

                    if invite_link.startswith("https://t.me/+"):
                        invite_link = invite_link.replace("https://t.me/+", "https://t.me/joinchat/")

                    links[chat_id] = invite_link
                    msg = await message.reply_text(_["call_4"].format(app.mention))
                    try:
                        await userbot.join_chat(invite_link)
                    except InviteRequestSent:
                        try:
                            await app.approve_chat_join_request(chat_id, userbot.id)
                        except Exception as e:
                            return await message.reply_text(_["call_3"].format(app.mention, type(e).__name__))
                        await asyncio.sleep(3)
                        await msg.edit(_["call_5"].format(app.mention))
                    except UserAlreadyParticipant:
                        pass
                    except ChannelsTooMuch:
                        return await message.reply_text("🚫 Assistant has joined too many chats.")
                    except ChatAdminRequired:
                        return await message.reply_text(_["call_1"])
                    except RPCError as e:
                        return await message.reply_text(f"🚫 <b>RPC Error:</b> <code>{type(e).__name__}</code>")
                except Exception:
                    pass

            return await command(client, message, _, chat_id, is_video, playmode, url, fplay)

        except Exception as ex:
            logger.exception(f"Unhandled exception in PlayWrapper: {ex}")
            try:
                await message.reply_text(
                    f"🚫 <b>Unexpected Error:</b>\n<pre>{str(ex)}</pre>",
                    disable_web_page_preview=True,
                )
            except:
                pass

    return wrapper
