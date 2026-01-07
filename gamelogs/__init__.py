from .gamelogs import GameLogs

async def setup(bot):
    await bot.add_cog(GameLogs(bot))
