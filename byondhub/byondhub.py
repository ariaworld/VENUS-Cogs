# General imports
import logging
import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import Optional

# Discord imports
import discord

# Redbot imports
from redbot.core import commands, Config, checks
from redbot.core.utils.chat_formatting import box
from redbot.core import tasks

log = logging.getLogger("red.byondhub")

class ByondHub(commands.Cog):
    """
    Monitor BYOND Hub status and send notifications
    """
    
    __author__ = "Goku"
    __version__ = "1.0.0"
    
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=908039527271104514, force_registration=True)
        
        default_guild = {
            "enabled": False,
            "channel_id": None,
            "role_id": None,
            "check_interval": 300,  # 5 minutes default
            "heartbeat_interval": 3600,  # 1 hour default
            "last_status": None,
            "last_heartbeat": None,
            "url": "byond.com"
        }
        
        self.config.register_guild(**default_guild)
        self.status_check_task.start()
    
    def cog_unload(self):
        self.status_check_task.cancel()
    
    async def check_byond_status(self, url: str) -> tuple[bool, str]:
        """
        Check if BYOND Hub is up using downforeveryoneorjustme.com API
        Returns (is_up, status_message)
        """
        try:
            # Use downforeveryoneorjustme.com to check the status
            check_url = f"https://downforeveryoneorjustme.com/{url}"
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            ) as session:
                async with session.get(check_url) as response:
                    if response.status == 200:
                        text = await response.text()
                        text_lower = text.lower()
                        
                        # Check for common "down" indicators in the response
                        if "it's not just you" in text_lower or "down for everyone" in text_lower:
                            return False, "Site appears to be down for everyone"
                        elif "it's just you" in text_lower or "up and running" in text_lower:
                            return True, "Site is up and running"
                        elif "looks down" in text_lower:
                            return False, "Site looks down"
                        else:
                            # Fallback: if we can't determine from text, assume it's a connectivity issue
                            return False, f"Unable to determine status (HTTP {response.status})"
                    else:
                        return False, f"Status check failed (HTTP {response.status})"
                        
        except asyncio.TimeoutError:
            return False, "Connection timed out"
        except aiohttp.ClientError as e:
            return False, f"Connection error: {str(e)}"
        except Exception as e:
            log.error(f"Unexpected error checking BYOND status: {e}")
            return False, f"Unexpected error: {str(e)}"
    
    @tasks.loop(minutes=1)
    async def status_check_task(self):
        """Background task to check BYOND status"""
        try:
            for guild in self.bot.guilds:
                guild_config = self.config.guild(guild)
                
                if not await guild_config.enabled():
                    continue
                
                channel_id = await guild_config.channel_id()
                if not channel_id:
                    continue
                
                channel = guild.get_channel(channel_id)
                if not channel:
                    continue
                
                # Check if it's time for a status check
                check_interval = await guild_config.check_interval()
                last_check = getattr(self, f'_last_check_{guild.id}', None)
                
                if last_check and (datetime.now() - last_check).total_seconds() < check_interval:
                    continue
                
                setattr(self, f'_last_check_{guild.id}', datetime.now())
                
                # Get current status
                url = await guild_config.url()
                is_up, status_msg = await self.check_byond_status(url)
                
                # Get last known status
                last_status = await guild_config.last_status()
                
                # Check if status changed
                if last_status != is_up:
                    await guild_config.last_status.set(is_up)
                    await self.send_status_notification(guild, channel, is_up, status_msg, url)
                
                # Check if it's time for heartbeat
                heartbeat_interval = await guild_config.heartbeat_interval()
                last_heartbeat = await guild_config.last_heartbeat()
                
                if not last_heartbeat:
                    await guild_config.last_heartbeat.set(datetime.now().timestamp())
                else:
                    time_since_heartbeat = datetime.now().timestamp() - last_heartbeat
                    if time_since_heartbeat >= heartbeat_interval:
                        await guild_config.last_heartbeat.set(datetime.now().timestamp())
                        await self.send_heartbeat_notification(guild, channel, is_up, status_msg, url)
                        
        except Exception as e:
            log.error(f"Error in status check task: {e}")
    
    @status_check_task.before_loop
    async def before_status_check_task(self):
        await self.bot.wait_until_ready()
    
    async def send_status_notification(self, guild, channel, is_up: bool, status_msg: str, url: str):
        """Send status change notification"""
        try:
            role_id = await self.config.guild(guild).role_id()
            role_mention = f"<@&{role_id}>" if role_id else ""
            
            color = discord.Color.green() if is_up else discord.Color.red()
            status_text = "🟢 UP" if is_up else "🔴 DOWN"
            title = f"BYOND Hub Status Change - {status_text}"
            
            embed = discord.Embed(
                title=title,
                description=f"**URL:** {url}\n**Status:** {status_msg}",
                color=color,
                timestamp=datetime.now()
            )
            
            embed.set_footer(text="BYOND Hub Monitor")
            
            content = f"{role_mention}\n" if role_mention else ""
            await channel.send(content=content, embed=embed)
            
        except Exception as e:
            log.error(f"Error sending status notification: {e}")
    
    async def send_heartbeat_notification(self, guild, channel, is_up: bool, status_msg: str, url: str):
        """Send heartbeat notification"""
        try:
            color = discord.Color.blue()
            status_text = "🟢 UP" if is_up else "🔴 DOWN"
            title = f"BYOND Hub Heartbeat - {status_text}"
            
            embed = discord.Embed(
                title=title,
                description=f"**URL:** {url}\n**Status:** {status_msg}\n**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                color=color,
                timestamp=datetime.now()
            )
            
            embed.set_footer(text="BYOND Hub Monitor - Heartbeat")
            
            await channel.send(embed=embed)
            
        except Exception as e:
            log.error(f"Error sending heartbeat notification: {e}")
    
    @commands.group(name="byondhub", aliases=["bh"])
    @checks.admin_or_permissions(manage_guild=True)
    async def byondhub(self, ctx):
        """BYOND Hub monitoring commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)
    
    @byondhub.command(name="enable")
    async def enable_monitoring(self, ctx):
        """Enable BYOND Hub monitoring"""
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send("✅ BYOND Hub monitoring enabled!")
    
    @byondhub.command(name="disable")
    async def disable_monitoring(self, ctx):
        """Disable BYOND Hub monitoring"""
        await self.config.guild(ctx.guild).enabled.set(False)
        await ctx.send("❌ BYOND Hub monitoring disabled!")
    
    @byondhub.command(name="channel")
    async def set_channel(self, ctx, channel: discord.TextChannel = None):
        """Set the notification channel"""
        if channel is None:
            channel = ctx.channel
        
        await self.config.guild(ctx.guild).channel_id.set(channel.id)
        await ctx.send(f"📢 Notifications will be sent to {channel.mention}")
    
    @byondhub.command(name="role")
    async def set_role(self, ctx, role: discord.Role = None):
        """Set the role to ping (optional)"""
        if role is None:
            await self.config.guild(ctx.guild).role_id.set(None)
            await ctx.send("🔕 Role pinging disabled")
        else:
            await self.config.guild(ctx.guild).role_id.set(role.id)
            await ctx.send(f"📢 Will ping {role.mention} on status changes")
    
    @byondhub.command(name="interval")
    async def set_interval(self, ctx, seconds: int):
        """Set check interval in seconds (60-3600)"""
        if not 60 <= seconds <= 3600:
            await ctx.send("❌ Interval must be between 60 and 3600 seconds (1 minute to 1 hour)")
            return
        
        await self.config.guild(ctx.guild).check_interval.set(seconds)
        await ctx.send(f"⏱️ Check interval set to {seconds} seconds")
    
    @byondhub.command(name="heartbeat")
    async def set_heartbeat(self, ctx, seconds: int):
        """Set heartbeat interval in seconds (300-86400)"""
        if not 300 <= seconds <= 86400:
            await ctx.send("❌ Heartbeat interval must be between 300 and 86400 seconds (5 minutes to 24 hours)")
            return
        
        await self.config.guild(ctx.guild).heartbeat_interval.set(seconds)
        await ctx.send(f"💓 Heartbeat interval set to {seconds} seconds")
    
    @byondhub.command(name="url")
    async def set_url(self, ctx, url: str = "byond.com"):
        """Set the URL to monitor
        
        Default: byond.com
        """
        # Clean the URL (remove protocol if present)
        url = url.replace("https://", "").replace("http://", "").replace("www.", "")
        
        await self.config.guild(ctx.guild).url.set(url)
        await ctx.send(f"🌐 Monitoring URL set to: {url}")
    
    @byondhub.command(name="status")
    async def show_status(self, ctx):
        """Show current configuration and status"""
        guild_config = self.config.guild(ctx.guild)
        
        enabled = await guild_config.enabled()
        channel_id = await guild_config.channel_id()
        role_id = await guild_config.role_id()
        check_interval = await guild_config.check_interval()
        heartbeat_interval = await guild_config.heartbeat_interval()
        last_status = await guild_config.last_status()
        url = await guild_config.url()
        
        channel = ctx.guild.get_channel(channel_id) if channel_id else None
        role = ctx.guild.get_role(role_id) if role_id else None
        
        embed = discord.Embed(
            title="BYOND Hub Monitor Configuration",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="Status",
            value="🟢 Enabled" if enabled else "🔴 Disabled",
            inline=True
        )
        
        embed.add_field(
            name="URL",
            value=url,
            inline=True
        )
        
        embed.add_field(
            name="Channel",
            value=channel.mention if channel else "Not set",
            inline=True
        )
        
        embed.add_field(
            name="Role",
            value=role.mention if role else "None",
            inline=True
        )
        
        embed.add_field(
            name="Check Interval",
            value=f"{check_interval}s",
            inline=True
        )
        
        embed.add_field(
            name="Heartbeat Interval",
            value=f"{heartbeat_interval}s",
            inline=True
        )
        
        if last_status is not None:
            embed.add_field(
                name="Last Known Status",
                value="🟢 UP" if last_status else "🔴 DOWN",
                inline=True
            )
        
        await ctx.send(embed=embed)
    
    @byondhub.command(name="check")
    async def manual_check(self, ctx):
        """Manually check BYOND Hub status"""
        url = await self.config.guild(ctx.guild).url()
        
        embed = discord.Embed(
            title="Checking BYOND Hub Status...",
            description="Please wait...",
            color=discord.Color.yellow()
        )
        
        msg = await ctx.send(embed=embed)
        
        is_up, status_msg = await self.check_byond_status(url)
        
        color = discord.Color.green() if is_up else discord.Color.red()
        status_text = "🟢 UP" if is_up else "🔴 DOWN"
        
        embed = discord.Embed(
            title=f"BYOND Hub Status - {status_text}",
            description=f"**URL:** {url}\n**Status:** {status_msg}",
            color=color,
            timestamp=datetime.now()
        )
        
        embed.set_footer(text="Manual Status Check")
        
        await msg.edit(embed=embed) 
# test