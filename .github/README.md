<h1 align="center">
Arc Music Bot
</h1>

<p align="center">
    <img src="https://files.catbox.moe/4lkow5.jpg" width="400">
</p>

<p align="center">
    <a href="https://github.com/deadlineTech/Music/stargazers">
        <img src="https://img.shields.io/github/stars/deadlineTech/Music?color=ffd700&style=for-the-badge&logo=github" />
    </a>
    <a href="https://github.com/deadlineTech/Music/network/members">
        <img src="https://img.shields.io/github/forks/deadlineTech/Music?color=blue&style=for-the-badge&logo=github" />
    </a>
<img src="https://img.shields.io/github/license/deadlineTech/music?style=for-the-badge" alt="LICENSE">
<br>
<a href="https://www.python.org">
        <img src="https://img.shields.io/badge/Made%20With-Python-306998?style=for-the-badge&logo=python&logoColor=yellow" />
    </a>
<img src="http://ForTheBadge.com/images/badges/built-with-love.svg" alt="built-with-love">
</p>

---

## 🎧 Advanced Telegram Group Music Bot

> A modern Telegram bot for high-quality group music streaming using PyTgCalls and Arc Bots powerful Music API key.

---

## ✨ Features

- 🎵 Stream music in group voice/video chats
- 🚀 Lightning-fast, stable, and scalable performance
- 🖼️ Dynamic thumbnails with song metadata
- 🎛️ Admin dashboard and playback controls
- 🧠 Intelligent queue management system
- ⚙️ Simple deployment on Heroku or VPS
- 🔑 Powered by [Deadline API Key](https://deadlinetech.site) for smooth music delivery

---

## 🔑 What is the API Key?

> A **Music API Key** by Arc Bots gives you powerful music fetching, blazing-fast downloads, rich metadata, and seamless YouTube support.  
> Just buy it once and enjoy the best streaming experience on your Telegram groups!

- 🔗 [Buy API Key](https://deadlinetech.site)

---

## 📜 Command Guide

### 🎵 Music Controls
| Command | Description |
|--------|-------------|
| `/play <name/link>` | Play audio from YouTube/Spotify/etc |
| `/vplay <name/link>` | Play video in videochat |
| `/pause` | Pause current song |
| `/resume` | Resume playback |
| `/skip` | Skip current song |
| `/end` | End stream & clear queue |
| `/music` | for Downloading the music from Yt |

### 📋 Queue Commands
| Command | Description |
|--------|-------------|
| `/queue` | Show current song queue |
| `/loop` | Toggle loop |
| `/shuffle` | Shuffle queue order |

### 🛠 Admin Commands
| Command | Description |
|--------|-------------|
| `/auth` | Add user to admin list |
| `/unauth` | Remove user from admin list |
| `/authusers` | Show admin list |

### 🔧 Tools
| Command | Description |
|--------|-------------|
| `/start` | Welcome message |
| `/help` | Full command list |
| `/ping` | Ping check |
| `/stats` | Bot stats & system usage |

---

## 🚀 Deployment Options

<details>
<summary><b>🔹 Deploy to Heroku</b></summary>

[![Deploy](https://img.shields.io/badge/Deploy%20to-Heroku-4700f5?style=for-the-badge&logo=heroku)](https://dashboard.heroku.com/new?template=https://github.com/deadlineTech/Music)

</details>

<details>
<summary><b>🔸 Deploy on VPS / Localhost</b></summary>

**1. Install Dependencies**
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip ffmpeg -y
sudo pip3 install -U pip
```

**2. Install NodeJS**
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.38.0/install.sh | bash && source ~/.bashrc && nvm install v18
```

**3. Clone Project**
```bash
git clone https://github.com/deadlineTech/music
cd music
pip3 install -U -r requirements.txt
```

**4. Setup .env**
```bash
cp sample.env .env
vi .env
```

- Press `I` to edit, `Ctrl + C`, then `:wq` to save.

**5. Run Bot**
```bash
sudo apt install tmux && tmux
bash start
```
Detach with: `Ctrl + B`, then `D`

</details>

---

## 🔧 Environment Variables

```env
API_ID=123456
API_HASH=abcdef1234567890abcdef1234567890
BOT_TOKEN=YOUR_BOT_TOKEN
OWNER_ID=123456789
MONGO_DB_URI=mongodb+srv://username:password@cluster.mongodb.net/dbname
API_KEY=YOUR_API_KEY  # Get from @ApixhubBot
STRING_SESSION=YOUR_STRING_SESSION
```

---

## 🤝 Support & Community

- 📢 [Announcements Channel](https://t.me/ArcUpdates)
- 💬 [Support Group](https://t.me/ArcChatz)
- 🧑‍💻 [Developer Contact](https://t.me/Its_Damiann)

---

## ⚡ Credits

- Base Framework: [Anon Music](https://github.com/AnonymousX1025/AnonXMusic)
- Enhanced by: [Team Arc](https://telegram.me/ArcUpdates)
- Lead Dev: [𝘿𝙖𝙢𝙞𝙖𝙣❤‍🩹](https://telegram.me/Its_Damiann) 

---

## 📄 License

> Licensed under the <b>MIT License</b>.
See <a href="https://github.com/deadlineTech/Music/blob/master/LICENSE">LICENSE</a> for details.

---

<p align="center">
  - <b> sᴩᴇᴄɪᴀʟ ᴛʜᴀɴᴋs ᴛᴏ <a href="https://github.com/TeamYukki">[ᴛᴇᴀᴍ ʏᴜᴋᴋɪ]</a> ғᴏʀ <a href="https://github.com/TeamYukki/YukkiMusicBot">[ʏᴜᴋᴋɪ ᴍᴜsɪᴄ ʙᴏᴛ]</a></b>
</p>
