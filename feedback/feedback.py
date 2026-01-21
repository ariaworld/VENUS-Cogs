# General imports
import re

# Discord imports
import discord

# Redbot imports
from redbot.core import commands, checks
from redbot.core.utils.chat_formatting import box


class Feedback(commands.Cog):
    """
    DM users about feedback status updates.
    """

    __author__ = "Goku"
    __version__ = "1.0.0"

    STATUS_ALIASES = {
        "to be completed": "To be completed/implemented soon",
        "to be implemented": "To be completed/implemented soon",
        "implemented soon": "To be completed/implemented soon",
        "to be done": "To be completed/implemented soon",
        "planned": "To be completed/implemented soon",
        "pending": "To be completed/implemented soon",
        "todo": "To be completed/implemented soon",
        "tbd": "To be completed/implemented soon",
        "tbc": "To be completed/implemented soon",
        "completed": "Completed/Implemented on the server",
        "implemented": "Completed/Implemented on the server",
        "done": "Completed/Implemented on the server",
        "finished": "Completed/Implemented on the server",
        "refused": "Refused",
        "rejected": "Refused",
        "declined": "Refused",
    }
    STATUS_MATCHES = tuple(sorted(STATUS_ALIASES.keys(), key=len, reverse=True))

    def __init__(self, bot):
        self.bot = bot

    def _extract_feedback_and_status(self, content: str):
        cleaned = re.sub(r"<@!?\d+>", "", content)
        cleaned = " ".join(cleaned.split())
        if not cleaned:
            return None, None

        tail_stripped = cleaned.rstrip(" \t\r\n.!?)]}'\"")
        lowered = tail_stripped.lower()
        for alias in self.STATUS_MATCHES:
            if lowered.endswith(alias):
                feedback_text = tail_stripped[: -len(alias)].rstrip()
                return feedback_text, self.STATUS_ALIASES[alias]
        return None, None

    @commands.guild_only()
    @checks.admin_or_permissions(manage_messages=True)
    @commands.command(name="feedback")
    async def feedback(self, ctx: commands.Context, *, content: str):
        """
        DM a user about their feedback status.

        Format: !feedback <feedback text> @user <completed/refused/to be completed>
        """
        if not ctx.message.mentions:
            return await ctx.send("Please mention the user who submitted the feedback.")
        if len(ctx.message.mentions) > 1:
            return await ctx.send("Please mention only one user.")

        member = ctx.message.mentions[0]
        feedback_text, status_label = self._extract_feedback_and_status(content)
        if not feedback_text or not status_label:
            return await ctx.send(
                "Please include feedback text and a status at the end "
                "(completed/refused/to be completed)."
            )

        dm_message = (
            "Hello! Your feedback:\n"
            f"{box(feedback_text, lang='text')}\n"
            f"Has been marked as: **{status_label}**"
        )

        try:
            await member.send(dm_message)
        except discord.Forbidden:
            return await ctx.send(f"I couldn't DM {member.mention}. They might have DMs disabled.")
        except discord.HTTPException:
            return await ctx.send(f"I couldn't DM {member.mention} due to a Discord error.")

        await ctx.tick()
        await ctx.send(f"Sent feedback update to {member.mention}.")
