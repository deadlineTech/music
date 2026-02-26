# ==========================================================
# 🔒 All Rights Reserved © Team DeadlineTech
# 📁 This file is part of the DeadlineTech Project.
# ==========================================================

import time
import asyncio

from pyrogram import filters
from pyrogram.enums import ChatMembersFilter
from pyrogram.errors import FloodWait, RPCError
from pyrogram.types import Message

from DeadlineTech import app
from DeadlineTech.misc import SUDOERS
from DeadlineTech.utils.database import (
    get_active_chats,
    get_authuser_names,
    get_client,
    get_served_chats,
    get_served_users,
)
from DeadlineTech.utils.decorators.language import language
from DeadlineTech.utils.formatters import alpha_to_int
from config import adminlist

# --- Configuration & Constants ---
from DeadlineTech.logging import LOGGER
LOG = LOGGER(__name__)

SEMAPHORE = asyncio.Semaphore(30)  # Increased concurrency

# Standard Emoji Configuration
class EMOJI:
    INFO = "ℹ️"
    ERROR = "❌"
    WARN = "⚠️"
    STOP = "🚫"
    CHECK = "✅"
    BROADCAST = "📢"
    ARROW = "➡️"
    USER = "👤"
    CHATS = "👥"
    PACKAGE = "📦"
    TIMER = "⏳"
    NOTE = "📝"

@app.on_message(filters.command("broadcast") & SUDOERS)
async def broadcast_command(client, message: Message):
    try:
        LOG.info(f"/broadcast triggered by user: {message.from_user.id}")

        command = message.text.lower()
        mode = "forward" if "-forward" in command else "copy"

        # Determine targets
        if "-all" in command:
            users = await get_served_users()
            chats = await get_served_chats()
            target_users = [u["user_id"] for u in users]
            target_chats = [c["chat_id"] for c in chats]
        elif "-users" in command:
            users = await get_served_users()
            target_users = [u["user_id"] for u in users]
            target_chats = []
        elif "-chats" in command:
            chats = await get_served_chats()
            target_users = []
            target_chats = [c["chat_id"] for c in chats]
        else:
            LOG.warning("Incorrect broadcast format used.")
            return await message.reply_text(
                f"{EMOJI.WARN} <b>Usage:</b>\n"
                "/broadcast -all/-users/-chats [-forward]\n"
                f"{EMOJI.NOTE} <b>Example:</b> /broadcast -all Hello!"
            )

        if not target_users and not target_chats:
            LOG.info("No target recipients found.")
            return await message.reply_text(f"{EMOJI.WARN} No recipients found.")

        # Extract content
        if message.reply_to_message:
            content = message.reply_to_message
        else:
            text = message.text
            for kw in ["/broadcast", "-forward", "-all", "-users", "-chats"]:
                text = text.replace(kw, "")
            text = text.strip()

            if not text:
                return await message.reply_text(f"{EMOJI.NOTE} Reply to a message or add content after the command.")
            content = text

        # Summary
        total = len(target_users + target_chats)
        sent_users = 0
        sent_chats = 0
        failed = 0

        LOG.info(f"Broadcast mode: {mode}")
        LOG.info(f"Targets - Users: {len(target_users)}, Chats: {len(target_chats)}, Total: {total}")

        await message.reply_text(
            f"{EMOJI.BROADCAST} <b>Broadcast Started</b>\n\n"
            f"{EMOJI.ARROW} Mode: <code>{mode}</code>\n"
            f"{EMOJI.USER} Users: <code>{len(target_users)}</code>\n"
            f"{EMOJI.CHATS} Chats: <code>{len(target_chats)}</code>\n"
            f"{EMOJI.PACKAGE} Total: <code>{total}</code>\n"
            f"{EMOJI.TIMER} Please wait while messages are being sent..."
        )

        # Define delivery function
        async def deliver(chat_id, is_user, retries=3):
            nonlocal sent_users, sent_chats, failed
            async with SEMAPHORE:
                try:
                    if isinstance(content, str):
                        await app.send_message(chat_id, content)
                    elif mode == "forward":
                        await app.forward_messages(chat_id, message.chat.id, [content.id])
                    else:
                        try:
                            await content.copy(chat_id)
                        except Exception as e:
                            LOG.warning(f"Copy failed to {chat_id}: {e}")
                            failed += 1
                            return

                    if is_user:
                        sent_users += 1
                    else:
                        sent_chats += 1

                except FloodWait as e:
                    wait_time = min(e.value, 120)
                    LOG.warning(f"FloodWait {e.value}s in chat {chat_id}, waiting {wait_time}s")
                    await asyncio.sleep(wait_time)
                    if retries > 0:
                        return await deliver(chat_id, is_user, retries - 1)
                    failed += 1

                except RPCError as e:
                    LOG.warning(f"RPCError in chat {chat_id}: {e}")
                    failed += 1

                except Exception as e:
                    LOG.error(f"Error delivering to {chat_id}: {e}")
                    failed += 1

        # Combine all targets
        targets = [(uid, True) for uid in target_users] + [(cid, False) for cid in target_chats]

        for i in range(0, len(targets), 100):
            batch = targets[i:i + 100]
            await asyncio.gather(*[deliver(chat_id, is_user) for chat_id, is_user in batch])
            await asyncio.sleep(2.5)  # Throttle between batches

        # Final summary
        await message.reply_text(
            f"{EMOJI.CHECK} <b>Broadcast Completed</b>\n\n"
            f"{EMOJI.ARROW} Mode: <code>{mode}</code>\n"
            f"{EMOJI.USER} Users Sent: <code>{sent_users}</code>\n"
            f"{EMOJI.CHATS} Chats Sent: <code>{sent_chats}</code>\n"
            f"{EMOJI.PACKAGE} Total Delivered: <code>{sent_users + sent_chats}</code>\n"
            f"{EMOJI.ERROR} Failed: <code>{failed}</code>"
        )
        LOG.info(f"Broadcast finished. Success: {sent_users + sent_chats}, Failed: {failed}")

    except Exception as e:
        LOG.exception("Unhandled error in broadcast_command")
        await message.reply_text(f"{EMOJI.STOP} Broadcast failed: {str(e)}")


# Adminlist Auto-cleaner
async def auto_clean():
    while True:
        await asyncio.sleep(10)
        try:
            chats = await get_active_chats()
            for chat_id in chats:
                if chat_id not in adminlist:
                    adminlist[chat_id] = []

                async for member in app.get_chat_members(chat_id, filter=ChatMembersFilter.ADMINISTRATORS):
                    if getattr(member, "privileges", None) and member.privileges.can_manage_video_chats:
                        adminlist[chat_id].append(member.user.id)

                for username in await get_authuser_names(chat_id):
                    user_id = await alpha_to_int(username)
                    adminlist[chat_id].append(user_id)

        except Exception as e:
            LOG.warning(f"AutoClean error: {e}")
#auto clean task
asyncio.create_task(auto_clean())

