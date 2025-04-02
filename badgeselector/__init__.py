from .badgeselector import BadgeSelector

async def setup(bot):
    await bot.add_cog(BadgeSelector(bot)) 