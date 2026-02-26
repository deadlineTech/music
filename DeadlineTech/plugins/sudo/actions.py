# Powered by DeadlineTech

import logging
from pyrogram import Client, filters
from DeadlineTech import app
from pyrogram.types import Message, ChatMemberUpdated
from pyrogram.enums import ChatMemberStatus
from DeadlineTech.logging import LOGGER

@app.on_chat_member_updated()
async def handle_member_update(client: Client, update: ChatMemberUpdated):
    user = update.from_user
    chat = update.chat
    old = update.old_chat_member
    new = update.new_chat_member

    if not old or not new:
        return

    if old.status != new.status:
        if new.status == ChatMemberStatus.MEMBER:
            LOGGER(__name__).info(f"{user.id} joined {chat.id}")
        elif new.status == ChatMemberStatus.LEFT:
            LOGGER(__name__).info(f"{user.id} left {chat.id}")
        elif new.status == ChatMemberStatus.ADMINISTRATOR:
            LOGGER(__name__).info(f"{user.id} was promoted in {chat.id}")
        elif old.status == ChatMemberStatus.ADMINISTRATOR and new.status != ChatMemberStatus.ADMINISTRATOR:
            LOGGER(__name__).info(f"{user.id} was demoted in {chat.id}")

@app.on_message(filters.video_chat_started)
async def video_chat_started_handler(client: Client, message: Message):
    chat = message.chat
    LOGGER(__name__).info(f"Video chat started in {chat.id}")

@app.on_message(filters.video_chat_ended)
async def video_chat_ended_handler(client: Client, message: Message):
    chat = message.chat
    LOGGER(__name__).info(f" Video chat ended in {chat.id}")

@app.on_message(filters.pinned_message)
async def pinned_message_handler(client: Client, message: Message):
    chat = message.chat
    pinned = message.pinned_message

    if pinned:
        LOGGER(__name__).info(f"Message pinned in {chat.id} - Pinned Msg ID: {pinned.id}")
    else:
        LOGGER(__name__).info(f"A message was pinned in {chat.id}, but content is not accessible.")
