HELP_1 = """
<b><u>𝖡𝖠𝖲𝖨𝖢 & 𝖯𝖫𝖠𝖸 𝖢𝖮𝖬𝖬𝖠𝖭𝖣𝖲</u></b> 🎵

📌 <b>Core Commands:</b>
🔸 <b>/start</b> – Initiates the music bot and verifies if it's active.
🔸 <b>/help</b> – Opens this detailed help menu.
🔸 <b>/ping</b> – Displays the bot’s current ping and basic system status.
🔸 <b>/stats</b> – Shows overall system statistics and uptime.

🎶 <b>Playback Commands:</b>
▶️ <b>/play</b> or <b>/vplay</b> – Starts streaming the requested track in the voice (or video) chat.
⏩ <b>/playforce</b> or <b>/vplayforce</b> – Instantly stops the ongoing stream and forces the new requested track to play.
"""

HELP_2 = """
<b><u>𝖯𝖫𝖠𝖸𝖤𝖱 & 𝖰𝖴𝖤𝖴𝖤 𝖢𝖮𝖭𝖳𝖱𝖮𝖫𝖲</u></b> 🎧

🛠️ <b>Control the ongoing stream:</b>
🔸 <b>/pause</b> – Pause the currently playing stream.
🔸 <b>/resume</b> – Resume the paused stream.
🔸 <b>/skip</b> – Skip the current track and play the next one in the queue.
🔸 <b>/end</b> or <b>/stop</b> – Clear the entire queue and stop the stream.
🔸 <b>/player</b> – Display an interactive player panel for the current song.

🔀 <b>Queue & Track Modification:</b>
🔸 <b>/queue</b> – Show the list of all queued tracks.
🔸 <b>/shuffle</b> – Randomly reshuffles the current playback queue.
🔸 <b>/loop [enable/disable/1,2,3...]</b> – Loop the currently playing stream a specific number of times.
🔸 <b>/seek [seconds]</b> – Jumps forward in the stream.
🔸 <b>/seekback [seconds]</b> – Rewinds the stream.
🔸 <b>/speed [0.5, 1, 1.5, 2]</b> – Adjust the playback speed of the ongoing stream.
"""

HELP_3 = """
<b><u>𝖯𝖤𝖱𝖲𝖮𝖭𝖠𝖫 𝖯𝖫𝖠𝖸𝖫𝖨𝖲𝖳𝖲</u></b> 📁

💾 <b>Save your favorite songs to custom folders and play them anytime!</b>
<i>💡 How to save: Click the "➕" button on any playing song's interactive player panel.</i>

🔹 <b>/playlists</b> or <b>/playlist</b> – View all your saved folders, manage tracks, or set a folder as "⭐ Active" for instant 1-click saving.
🔹 <b>/del_playlist [FolderName]</b> – Delete an entire saved playlist folder. (Must be used in the bot's Private Messages).

▶️ <b>How to Play your Playlist:</b>
Simply use the normal play command followed by your folder's exact name! All songs inside will be instantly queued.
📝 Example: <code>/play Music1234</code> or <code>/play Workout</code>
"""

HELP_4 = """
<b><u>𝖠𝖴𝖳𝖧 𝖴𝖲𝖤𝖱𝖲</u></b> 🔐

👤 <b>Auth users</b> can use admin-level commands (like pause, skip, stop, speed) in the bot <i>without</i> needing to be actual Telegram chat administrators.

🔹 <b>/auth [username/user_id]</b> – Add a user to the bot's auth list for the current chat.
🔹 <b>/unauth [username/user_id]</b> – Remove a user from the chat's auth list.
🔹 <b>/authusers</b> – Show the list of currently authorized users in the group.
"""

HELP_5 = """
<b><u>𝖲𝖴𝖣𝖮 & 𝖠𝖣𝖵𝖠𝖭𝖢𝖤𝖣 𝖳𝖮𝖮𝖫𝖲</u></b> 👨‍💻

⚠️ <i>These commands are restricted to Bot Owners and Sudo Users only.</i>

🔹 <b>/activecalls</b> or <b>/acalls</b> – Shows a complete list of ongoing voice and video calls across all groups.
🔹 <b>/logs</b> – Fetch the latest error and system logs from your bot’s backend.
🔹 <b>/logger [enable/disable]</b> – Turn activity logging on or off.
🔹 <b>/maintenance [enable/disable]</b> – Switch the bot to maintenance mode (ignores standard users while you run updates).
🔹 <b>/broadcast [message]</b> – Send a global message to users/chats.
  • Supported Flags: <code>-users</code>, <code>-chats</code>, <code>-all</code>, <code>-forward</code>
"""
