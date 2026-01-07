# General imports
import os
import tempfile
import zipfile

# Discord imports
import discord

# Redbot imports
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from redbot.core.data_manager import cog_data_path


class GameLogs(commands.Cog):
    """
    Zip and upload game logs from a configured GameStaticFiles directory.
    """

    __author__ = "Goku"
    __version__ = "1.0.0"

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=908039527271104513, force_registration=True)
        self.config.register_guild(gamestaticfiles_path=None)

    def _find_round_dir(self, logs_root: str, round_number: int):
        target = f"round-{round_number}"
        matches = []
        for root, dirs, _ in os.walk(logs_root):
            if target in dirs:
                matches.append(os.path.join(root, target))
        return matches

    def _zip_round_dir(self, round_dir: str, zip_path: str):
        round_name = os.path.basename(os.path.normpath(round_dir))
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(round_dir):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(file_path, round_dir)
                    arcname = os.path.join(round_name, rel_path)
                    zipf.write(file_path, arcname)

    @commands.command(name="setgamestaticfiles")
    @commands.guild_only()
    @checks.admin_or_permissions(administrator=True)
    async def set_gamestaticfiles(self, ctx: commands.Context, *, path: str):
        """
        Set the GameStaticFiles root path for log retrieval.
        """
        root_path = os.path.abspath(path)
        if not os.path.isdir(root_path):
            return await ctx.send(f"That path does not exist: `{root_path}`")
        await self.config.guild(ctx.guild).gamestaticfiles_path.set(root_path)
        await ctx.tick()
        await ctx.send(f"GameStaticFiles path set to `{root_path}`")

    @commands.command(name="getlogs")
    @commands.guild_only()
    @checks.admin_or_permissions(administrator=True)
    async def get_logs(self, ctx: commands.Context, round_number: int):
        """
        Zip and upload logs for a specific round from the configured GameStaticFiles path.
        """
        root_path = await self.config.guild(ctx.guild).gamestaticfiles_path()
        if not root_path:
            return await ctx.send("GameStaticFiles path not set. Use `!setgamestaticfiles <path>` first.")
        if not os.path.isdir(root_path):
            return await ctx.send(f"Configured GameStaticFiles path does not exist: `{root_path}`")

        logs_root = os.path.join(root_path, "data", "logs")
        if not os.path.isdir(logs_root):
            return await ctx.send(f"No logs directory found under `{root_path}`.")

        matches = self._find_round_dir(logs_root, round_number)
        if not matches:
            return await ctx.send(f"No folder named `round-{round_number}` found under `{logs_root}`.")

        round_dir = sorted(matches, key=lambda p: os.path.getmtime(p), reverse=True)[0]
        if len(matches) > 1:
            await ctx.send(f"Multiple `round-{round_number}` folders found; using the most recently modified one.")

        temp_dir = cog_data_path(self)
        os.makedirs(temp_dir, exist_ok=True)
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(dir=temp_dir, suffix=".zip", delete=False) as tmp:
                temp_file = tmp.name

            async with ctx.typing():
                await self.bot.loop.run_in_executor(None, self._zip_round_dir, round_dir, temp_file)

            zip_size = os.path.getsize(temp_file)
            size_limit = ctx.guild.filesize_limit
            if zip_size > size_limit:
                os.remove(temp_file)
                return await ctx.send(
                    f"Logs archive is too large to upload ({zip_size / 1024 / 1024:.2f} MB)."
                )

            await ctx.send(file=discord.File(temp_file, filename=f"round-{round_number}-logs.zip"))
        finally:
            if temp_file and os.path.exists(temp_file):
                os.remove(temp_file)
