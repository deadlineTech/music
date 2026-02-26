# Powered By Team DeadlineTech

import random
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from pyrogram.enums import ChatType

from DeadlineTech import app, YouTube
from DeadlineTech.misc import db
from DeadlineTech.utils.database import (
    get_user_playlists, create_playlist, add_to_playlist, 
    delete_playlist, remove_track_from_playlist
)
from config import BANNED_USERS

# ==========================================
# 1. THE ADD TRACK FLOW (Auto-Default Logic)
# ==========================================
@app.on_callback_query(filters.regex(r"^pl_menu\|") & ~BANNED_USERS)
async def pl_menu_cb(client, CallbackQuery):
    chat_id = int(CallbackQuery.data.split("|")[1])
    playing = db.get(chat_id)
    
    if not playing:
        return await CallbackQuery.answer("❌ Nothing is currently playing.", show_alert=True)
        
    videoid = playing[0]["vidid"]
    title = playing[0]["title"]
    user_id = CallbackQuery.from_user.id
    playlists = await get_user_playlists(user_id)
    
    # REQUIREMENT: If no playlist exists, create default and add track
    if not playlists:
        default_name = f"Music{random.randint(1000, 9999)}"
        await create_playlist(user_id, default_name)
        await add_to_playlist(user_id, default_name, videoid, title)
        return await CallbackQuery.answer(f"✅ Created default playlist '{default_name}' and saved track!", show_alert=True)

    # If playlists exist, show selection menu
    buttons = []
    row = []
    for name in playlists.keys():
        row.append(InlineKeyboardButton(text=f"📁 {name}", callback_data=f"pl_add|{name}|{videoid}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row: buttons.append(row)
    
    if len(playlists) < 5:
        buttons.append([InlineKeyboardButton(text="➕ Create New Folder", callback_data=f"pl_create|{videoid}")])
    
    buttons.append([InlineKeyboardButton(text="🗑 Close", callback_data="close")])
    await CallbackQuery.message.reply_text("**Select a folder to save this track:**", reply_markup=InlineKeyboardMarkup(buttons))

# ==========================================
# 2. MANAGEMENT COMMAND (/playlists)
# ==========================================
@app.on_message(filters.command(["playlists", "playlist"]) & filters.private & ~BANNED_USERS)
async def manage_playlists(client, message: Message):
    user_id = message.from_user.id
    playlists = await get_user_playlists(user_id)
    
    if not playlists:
        return await message.reply_text("❌ You don't have any playlists yet. Save a song from the player first!")
        
    buttons = []
    for name in playlists.keys():
        buttons.append([InlineKeyboardButton(text=f"📁 {name} ({len(playlists[name])}/25)", callback_data=f"pl_view|{name}")])
        
    await message.reply_text(
        f"**📚 Your Library ({len(playlists)}/5):**\nChoose a playlist to view or edit tracks.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex(r"^pl_view\|") & ~BANNED_USERS)
async def pl_view_cb(client, CallbackQuery):
    name = CallbackQuery.data.split("|")[1]
    user_id = CallbackQuery.from_user.id
    playlists = await get_user_playlists(user_id)
    
    if name not in playlists:
        return await CallbackQuery.answer("❌ Playlist not found.", show_alert=True)
        
    songs = playlists[name]
    text = f"**📁 Playlist: {name}**\n\n"
    if not songs:
        text += "_This folder is empty._"
    else:
        for i, song in enumerate(songs, 1):
            text += f"**{i}.** {song['title'][:45]}\n"
            
    buttons = [
        [InlineKeyboardButton(text="✏️ Edit Tracks", callback_data=f"pl_edit|{name}")],
        [InlineKeyboardButton(text="🗑 Delete Playlist", callback_data=f"pl_del|{name}")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="pl_home")]
    ]
    await CallbackQuery.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(r"^pl_edit\|") & ~BANNED_USERS)
async def pl_edit_cb(client, CallbackQuery):
    # Enforce Private Chat for editing
    if CallbackQuery.message.chat.type != ChatType.PRIVATE:
        return await CallbackQuery.answer("⚠️ You can only remove tracks in my Private Chat!", show_alert=True, url=f"https://t.me/{app.username}?start=playlist")

    name = CallbackQuery.data.split("|")[1]
    user_id = CallbackQuery.from_user.id
    playlists = await get_user_playlists(user_id)
    songs = playlists.get(name, [])
    
    text = f"**🛠 Editing: {name}**\nSelect a track number to remove it:\n\n"
    buttons = []
    row = []
    for i, _ in enumerate(songs, 1):
        row.append(InlineKeyboardButton(text=f"🗑 {i}", callback_data=f"pl_rem|{name}|{i-1}"))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row: buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data=f"pl_view|{name}")])
    
    await CallbackQuery.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(r"^pl_rem\|") & ~BANNED_USERS)
async def pl_rem_cb(client, CallbackQuery):
    data = CallbackQuery.data.split("|")
    name, index = data[1], int(data[2])
    await remove_track_from_playlist(CallbackQuery.from_user.id, name, index)
    await CallbackQuery.answer("✅ Track removed.", show_alert=True)
    await pl_edit_cb(client, CallbackQuery)
