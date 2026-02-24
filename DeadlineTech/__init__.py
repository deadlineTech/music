# Powered By Team DeadlineTech
from DeadlineTech.core.bot import damian
from DeadlineTech.core.dir import dirr
from DeadlineTech.core.git import git
from DeadlineTech.core.userbot import Userbot
from DeadlineTech.misc import dbb, heroku

from .logging import LOGGER

dirr()
git()
dbb()
heroku()

app = damian()
userbot = Userbot()


from .platforms import *

Apple = AppleAPI()
Carbon = CarbonAPI()
SoundCloud = SoundAPI()
Spotify = SpotifyAPI()
Resso = RessoAPI()
Telegram = TeleAPI()
YouTube = YouTubeAPI()
