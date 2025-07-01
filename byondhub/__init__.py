from .byondhub import ByondHub

async def setup(bot):
    await bot.add_cog(ByondHub(bot)) 