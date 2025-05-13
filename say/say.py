#General imports
import discord
from typing import Optional

#Redbot imports
from redbot.core import commands, checks
from redbot.core.utils.chat_formatting import pagify

class Say(commands.Cog):
    """
    Make the bot say things in specific channels
    """
    
    __author__ = "Goku"
    __version__ = "1.0.0"
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.group(name="say")
    @checks.is_owner()
    async def say_commands(self, ctx: commands.Context):
        """
        Make the bot say things in specific channels
        """
        pass
    
    @say_commands.command(name="channel")
    async def say_in_channel(self, ctx: commands.Context, channel: discord.TextChannel, *, message: str):
        """
        Make the bot say something in a specific channel
        
        Parameters:
        - channel: The channel where the message should be sent (mention or ID)
        - message: The message to send
        """
        # Check if the bot has permissions to send messages in the target channel
        if not channel.permissions_for(ctx.guild.me).send_messages:
            return await ctx.send(f"❌ I don't have permission to send messages in {channel.mention}.")
        
        # Send the message to the specified channel
        try:
            await channel.send(message)
            # Send a confirmation to the command invoker
            await ctx.tick()
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to send messages in that channel.")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to send message: {str(e)}")
    
    @say_commands.command(name="embed")
    async def say_embed(self, ctx: commands.Context, channel: discord.TextChannel, title: str, *, content: str):
        """
        Make the bot say something in a specific channel as an embed
        
        Parameters:
        - channel: The channel where the message should be sent (mention or ID)
        - title: The title of the embed
        - content: The content of the embed
        """
        # Check if the bot has permissions to send messages in the target channel
        if not channel.permissions_for(ctx.guild.me).send_messages:
            return await ctx.send(f"❌ I don't have permission to send messages in {channel.mention}.")
        
        if not channel.permissions_for(ctx.guild.me).embed_links:
            return await ctx.send(f"❌ I don't have permission to send embeds in {channel.mention}.")
        
        # Create and send the embed
        try:
            embed = discord.Embed(
                title=title,
                description=content,
                color=await ctx.embed_color(),
                timestamp=discord.utils.utcnow()
            )
            
            await channel.send(embed=embed)
            # Send a confirmation to the command invoker
            await ctx.tick()
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to send embeds in that channel.")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to send embed: {str(e)}")
    
    @say_commands.command(name="here")
    async def say_here(self, ctx: commands.Context, *, message: str):
        """
        Make the bot say something in the current channel
        
        Parameters:
        - message: The message to send
        """
        # Delete the command message if the bot has permission
        if ctx.channel.permissions_for(ctx.guild.me).manage_messages:
            try:
                await ctx.message.delete()
            except:
                pass
        
        # Send the message
        try:
            await ctx.send(message)
        except discord.Forbidden:
            await ctx.author.send("❌ I don't have permission to send messages in that channel.")
        except discord.HTTPException as e:
            await ctx.author.send(f"❌ Failed to send message: {str(e)}")

async def setup(bot):
    await bot.add_cog(Say(bot)) 