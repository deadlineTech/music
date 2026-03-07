import os

from config import autoclean


async def auto_clean(popped):
    try:
        rem = popped["file"]
        autoclean.remove(rem)
        count = autoclean.count(rem)
        if count == 0:
            # Fixed: use 'and' instead of 'or' - file should be deleted only if it's NONE of these prefixes
            if "vid_" not in rem and "live_" not in rem and "index_" not in rem:
                try:
                    os.remove(rem)
                except:
                    pass
    except:
        pass
