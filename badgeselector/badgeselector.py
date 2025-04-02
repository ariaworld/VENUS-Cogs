import discord
from redbot.core import commands, Config, checks
from redbot.core.utils.chat_formatting import box, pagify
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS
from redbot.core.bot import Red
from typing import Dict, List, Optional, Union
import asyncio

class BadgeSelector(commands.Cog):
    """
    Donator Badge Selection System
    
    Allows users to select badges based on their donator tier.
    """
    __author__ = "Goku"
    __version__ = "1.0.0"
    
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=113377331177, force_registration=True)
        
        default_guild = {
            "enabled": False,
            "tier_roles": {
                "1": None,  # "Tier 1 Donator" role ID
                "2": None,  # "Tier 2 Donator" role ID
                "3": None,  # "Tier 3 Donator" role ID
                "4": None,  # "Tier 4 Donator" role ID
                "5": None   # "Tier 5 Donator" role ID
            },
            "badge_roles": {
                "1": None,  # "Tier 1 Donator Badge" role ID
                "2": None,  # "Tier 2 Donator Badge" role ID
                "3": None,  # "Tier 3 Donator Badge" role ID
                "4": None,  # "Tier 4 Donator Badge" role ID
                "5": None   # "Tier 5 Donator Badge" role ID
            },
            "select_channel": None
        }
        
        self.config.register_guild(**default_guild)
    
    @commands.group(name="badge")
    @commands.guild_only()
    async def badge(self, ctx: commands.Context):
        """Commands for the donator badge selection system"""
        pass
    
    @badge.command(name="select")
    @commands.guild_only()
    async def badge_select(self, ctx: commands.Context, tier: int):
        """
        Select a badge based on your donator tier
        
        This command allows you to select a badge matching or below your donator tier level.
        
        Example:
        [p]badge select 2 - Select the Tier 2 badge
        """
        # Check if the system is enabled
        if not await self.config.guild(ctx.guild).enabled():
            return await ctx.send("The badge selection system is not enabled on this server.")
        
        # Check if user is in the correct channel
        select_channel_id = await self.config.guild(ctx.guild).select_channel()
        if select_channel_id and ctx.channel.id != select_channel_id:
            select_channel = ctx.guild.get_channel(select_channel_id)
            if select_channel:
                return await ctx.send(f"Please use this command in {select_channel.mention}")
        
        # Validate tier input
        if tier < 1 or tier > 5:
            return await ctx.send("Please select a tier between 1 and 5.")
        
        # Get tier and badge roles
        tier_roles = await self.config.guild(ctx.guild).tier_roles()
        badge_roles = await self.config.guild(ctx.guild).badge_roles()
        
        # Check if roles are configured
        if not all(tier_roles.values()) or not all(badge_roles.values()):
            return await ctx.send("The badge system has not been fully configured. Please contact an administrator.")
        
        # Get the member's highest tier role
        highest_tier = 0
        for t in range(5, 0, -1):
            role_id = tier_roles[str(t)]
            role = ctx.guild.get_role(role_id)
            if role and role in ctx.author.roles:
                highest_tier = t
                break
        
        if highest_tier == 0:
            return await ctx.send("You don't have any donator tier roles. Please contact an administrator if you believe this is an error.")
        
        # Check if the requested badge is allowed for their tier
        if tier > highest_tier:
            return await ctx.send(f"You can only select badges up to Tier {highest_tier} based on your donator status.")
        
        # Get the requested badge role
        requested_badge_id = badge_roles[str(tier)]
        requested_badge = ctx.guild.get_role(requested_badge_id)
        
        if not requested_badge:
            return await ctx.send(f"Error: Tier {tier} badge role not found. Please contact an administrator.")
        
        # Remove any existing badge roles
        badge_role_ids = [int(badge_id) for badge_id in badge_roles.values() if badge_id]
        roles_to_remove = [role for role in ctx.author.roles if role.id in badge_role_ids]
        
        if roles_to_remove:
            await ctx.author.remove_roles(*roles_to_remove, reason="Badge selection update")
        
        # Add the new badge role
        await ctx.author.add_roles(requested_badge, reason="Badge selection")
        
        # Feedback
        await ctx.send(f"✅ You're now displaying the **Tier {tier} Donator Badge**!")
    
    @badge.command(name="list")
    @commands.guild_only()
    async def badge_list(self, ctx: commands.Context):
        """List all available badges for your donator tier"""
        # Check if the system is enabled
        if not await self.config.guild(ctx.guild).enabled():
            return await ctx.send("The badge selection system is not enabled on this server.")
        
        # Get tier and badge roles
        tier_roles = await self.config.guild(ctx.guild).tier_roles()
        badge_roles = await self.config.guild(ctx.guild).badge_roles()
        
        # Check if roles are configured
        if not all(tier_roles.values()) or not all(badge_roles.values()):
            return await ctx.send("The badge system has not been fully configured. Please contact an administrator.")
        
        # Get the member's highest tier role
        highest_tier = 0
        for t in range(5, 0, -1):
            role_id = tier_roles[str(t)]
            role = ctx.guild.get_role(role_id)
            if role and role in ctx.author.roles:
                highest_tier = t
                break
        
        if highest_tier == 0:
            return await ctx.send("You don't have any donator tier roles. Please contact an administrator if you believe this is an error.")
        
        # Create a list of available badges
        available_badges = []
        for t in range(1, highest_tier + 1):
            badge_id = badge_roles[str(t)]
            badge_role = ctx.guild.get_role(badge_id)
            if badge_role:
                available_badges.append(f"Tier {t}: {badge_role.name}")
        
        # Find currently selected badge
        badge_role_ids = [int(badge_id) for badge_id in badge_roles.values() if badge_id]
        current_badge = None
        for role in ctx.author.roles:
            if role.id in badge_role_ids:
                for t, badge_id in badge_roles.items():
                    if badge_id == role.id:
                        current_badge = f"Tier {t}"
        
        # Create and send embed
        embed = discord.Embed(
            title="Available Donator Badges",
            description=f"Based on your **Tier {highest_tier} Donator** status, you can select from the following badges:",
            color=discord.Color.gold()
        )
        
        embed.add_field(name="Currently Selected", value=current_badge or "None", inline=False)
        embed.add_field(name="Available Badges", value="\n".join(available_badges), inline=False)
        embed.add_field(
            name="How to Select", 
            value=f"Use `{ctx.prefix}badge select <tier>` to choose a badge.\nExample: `{ctx.prefix}badge select 2`", 
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @badge.command(name="clear")
    @commands.guild_only()
    async def badge_clear(self, ctx: commands.Context):
        """Remove your current donator badge"""
        # Check if the system is enabled
        if not await self.config.guild(ctx.guild).enabled():
            return await ctx.send("The badge selection system is not enabled on this server.")
        
        # Get badge roles
        badge_roles = await self.config.guild(ctx.guild).badge_roles()
        
        # Check if roles are configured
        if not all(badge_roles.values()):
            return await ctx.send("The badge system has not been fully configured. Please contact an administrator.")
        
        # Remove any existing badge roles
        badge_role_ids = [int(badge_id) for badge_id in badge_roles.values() if badge_id]
        roles_to_remove = [role for role in ctx.author.roles if role.id in badge_role_ids]
        
        if not roles_to_remove:
            return await ctx.send("You don't have any donator badges to remove.")
        
        await ctx.author.remove_roles(*roles_to_remove, reason="Badge cleared")
        await ctx.send("✅ Your donator badge has been removed.")

    @commands.group(name="setbadge")
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def setbadge(self, ctx: commands.Context):
        """Configuration commands for the donator badge selection system"""
        pass
    
    @setbadge.command(name="toggle")
    async def setbadge_toggle(self, ctx: commands.Context, state: bool = None):
        """Toggle the badge selection system on or off"""
        current = await self.config.guild(ctx.guild).enabled()
        
        if state is None:
            state = not current
        
        await self.config.guild(ctx.guild).enabled.set(state)
        await ctx.send(f"Badge selection system is now {'enabled' if state else 'disabled'}.")
    
    @setbadge.command(name="channel")
    async def setbadge_channel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Set the channel for badge selection commands"""
        if channel:
            await self.config.guild(ctx.guild).select_channel.set(channel.id)
            await ctx.send(f"Badge selection channel set to {channel.mention}")
        else:
            await self.config.guild(ctx.guild).select_channel.set(None)
            await ctx.send("Badge selection can now be used in any channel.")
    
    @setbadge.command(name="tierrole")
    async def setbadge_tierrole(self, ctx: commands.Context, tier: int, role: discord.Role):
        """
        Set a donator tier role
        
        Example:
        [p]setbadge tierrole 1 "Tier 1 Donator"
        """
        if tier < 1 or tier > 5:
            return await ctx.send("Tier must be between 1 and 5.")
        
        tier_roles = await self.config.guild(ctx.guild).tier_roles()
        tier_roles[str(tier)] = role.id
        await self.config.guild(ctx.guild).tier_roles.set(tier_roles)
        
        await ctx.send(f"Tier {tier} donator role set to {role.name}")
    
    @setbadge.command(name="badgerole")
    async def setbadge_badgerole(self, ctx: commands.Context, tier: int, role: discord.Role):
        """
        Set a badge role for a specific tier
        
        Example:
        [p]setbadge badgerole 1 "Tier 1 Donator Badge"
        """
        if tier < 1 or tier > 5:
            return await ctx.send("Tier must be between 1 and 5.")
        
        badge_roles = await self.config.guild(ctx.guild).badge_roles()
        badge_roles[str(tier)] = role.id
        await self.config.guild(ctx.guild).badge_roles.set(badge_roles)
        
        await ctx.send(f"Tier {tier} badge role set to {role.name}")
    
    @setbadge.command(name="status")
    async def setbadge_status(self, ctx: commands.Context):
        """Check the current configuration of the badge system"""
        # Get current config
        config = await self.config.guild(ctx.guild).all()
        enabled = config["enabled"]
        tier_roles = config["tier_roles"]
        badge_roles = config["badge_roles"]
        select_channel_id = config["select_channel"]
        
        # Build status embed
        embed = discord.Embed(
            title="Badge Selection System Status",
            color=discord.Color.blue()
        )
        
        # System status
        embed.add_field(
            name="System Status", 
            value=f"{'✅ Enabled' if enabled else '❌ Disabled'}", 
            inline=False
        )
        
        # Select channel
        select_channel = ctx.guild.get_channel(select_channel_id) if select_channel_id else None
        embed.add_field(
            name="Selection Channel", 
            value=select_channel.mention if select_channel else "Any channel", 
            inline=False
        )
        
        # Tier roles
        tier_roles_text = ""
        for tier in range(1, 6):
            role_id = tier_roles.get(str(tier))
            role = ctx.guild.get_role(role_id) if role_id else None
            tier_roles_text += f"Tier {tier}: {role.name if role else '❌ Not set'}\n"
        
        embed.add_field(name="Donator Tier Roles", value=tier_roles_text, inline=False)
        
        # Badge roles
        badge_roles_text = ""
        for tier in range(1, 6):
            role_id = badge_roles.get(str(tier))
            role = ctx.guild.get_role(role_id) if role_id else None
            badge_roles_text += f"Tier {tier}: {role.name if role else '❌ Not set'}\n"
        
        embed.add_field(name="Badge Roles", value=badge_roles_text, inline=False)
        
        # Helper text for admins
        embed.add_field(
            name="Setup Commands", 
            value=(
                f"`{ctx.prefix}setbadge toggle <true/false>` - Enable/disable the system\n"
                f"`{ctx.prefix}setbadge channel <#channel>` - Set selection channel\n"
                f"`{ctx.prefix}setbadge tierrole <tier> <role>` - Set tier roles\n"
                f"`{ctx.prefix}setbadge badgerole <tier> <role>` - Set badge roles"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @setbadge.command(name="reset")
    @checks.is_owner()
    async def setbadge_reset(self, ctx: commands.Context, confirm: bool = False):
        """Reset the badge selection system configuration"""
        if not confirm:
            return await ctx.send("This will reset all badge system settings. To confirm, use `{ctx.prefix}setbadge reset true`")
        
        await self.config.guild(ctx.guild).clear()
        await ctx.send("Badge selection system configuration has been reset.") 