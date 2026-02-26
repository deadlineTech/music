# Powered By Team DeadlineTech
from DeadlineTech.core.bot import Anony
from DeadlineTech.core.dir import dirr
from DeadlineTech.core.git import git
from DeadlineTech.core.userbot import Userbot
from DeadlineTech.misc import dbb, heroku

from .logging import LOGGER

dirr()
git()
dbb()
heroku()

app = Anony()
userbot = Userbot()


from .platforms import *

Spotify = SpotifyAPI()
Telegram = TeleAPI()
YouTube = YouTubeAPI()
