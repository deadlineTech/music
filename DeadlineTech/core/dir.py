# ==========================================================
# 🎧 Public Open-Source VC Player Music Bot (Cookies Based)
# 🛠️ Maintained by Team DeadlineTech | Lead Developer: @Its_damiann
# 🔓 Licensed for Public Use — All Rights Reserved © Team DeadlineTech
# ❤️ Openly built for the community, but proudly protected by the passion of its creators.
# ==========================================================


import os

from ..logging import LOGGER

DOWNLOAD_DIR = "downloads"
CACHE_DIR = "cache"


def dirr():
    for file in os.listdir():
        if file.endswith(".jpg"):
            os.remove(file)
        elif file.endswith(".jpeg"):
            os.remove(file)
        elif file.endswith(".png"):
            os.remove(file)

    if DOWNLOAD_DIR not in os.listdir():
        os.mkdir(DOWNLOAD_DIR)
    if CACHE_DIR not in os.listdir():
        os.mkdir(CACHE_DIR)

    LOGGER(__name__).info("Directory structure successfully updated.")
