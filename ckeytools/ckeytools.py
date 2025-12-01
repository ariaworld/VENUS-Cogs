#General imports
import logging, aiomysql, os, tomlkit, datetime
from unicodedata import name
from array import array
from tokenize import String
from typing import Optional
import asyncio

#discord imports
import discord

#tgcommon imports
from tgcommon.errors import TGUnrecoverableError
from tgcommon.models import DiscordLink

#Redbot imports
from redbot.core import commands, Config, checks
from redbot.core.utils import chat_formatting

log = logging.getLogger("red.oranges_tgdb")

class CkeyTools(commands.Cog):
    """
    Extension cog for TGDB/TGVerify
    """
    
    __author__ = "Goku"
    __version__ = "2.0.2"
    
    def __init__(self, bot):
        self.bot = bot
        self.config: Config = Config.get_conf(self, identifier=908039527271104513, force_registration=True)

        default_guild = {
            "forcestay_enabled": "off",
            "autodonator_enabled": "off",
            "config_folder": None,
            "donator_roles": [],
            "verified_role_id": None,
            "age_vetted_role_id": None,
            "leave_log_channel_id": None,
            "leave_log_enabled": False,
            "agetemplate_image_url": None,
            "agetemplate_message": None
        }
        
        default_role = {
            "donator_tier": "none"
        }
        
        self.config.register_guild(**default_guild)
        self.config.register_role(**default_role)
    
    #Listeners
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        guild = member.guild
        if guild is None:
            return
        
        enabled = await self.config.guild(guild).forcestay_enabled()
        prefix = await self.get_tgdb_prefix(guild)

        if enabled == "on":
            query = f"UPDATE {prefix}discord_links SET valid = FALSE WHERE discord_id = %s AND valid = TRUE"
            parameters = [member.id]
            results = await self.query_database(query, parameters)
        
        leave_log_enabled = await self.config.guild(guild).leave_log_enabled()
        if not leave_log_enabled:
            return
            
        verified_role_id = await self.config.guild(guild).verified_role_id()
        age_vetted_role_id = await self.config.guild(guild).age_vetted_role_id()
        log_channel_id = await self.config.guild(guild).leave_log_channel_id()
        
        if not (verified_role_id and age_vetted_role_id and log_channel_id):
            return
            
        member_role_ids = [role.id for role in member.roles]
        
        if verified_role_id in member_role_ids and age_vetted_role_id in member_role_ids:
            log_channel = guild.get_channel(log_channel_id)
            if log_channel and isinstance(log_channel, discord.TextChannel):
                try:
                    # Calculate time on server if join date is available
                    joined_at = member.joined_at
                    time_on_server = ""
                    if joined_at:
                        days_on_server = (discord.utils.utcnow() - joined_at).days
                        time_on_server = f"{days_on_server} days"
                    
                    # Check if the user was banned
                    try:
                        # This will raise discord.NotFound if the user wasn't banned
                        ban_entry = await guild.fetch_ban(member)
                        is_banned = True
                    except discord.NotFound:
                        is_banned = False
                    except Exception as e:
                        # If we can't determine ban status for some reason, assume not banned
                        log.error(f"Error checking ban status: {e}", exc_info=True)
                        is_banned = False
                    
                    # Create appropriate embed based on whether user was banned or left
                    if is_banned:
                        embed = discord.Embed(
                            title="Verified & Age-Vetted User Banned",
                            description=f"{member.mention} ({member}) has been banned from the server.",
                            color=discord.Color.red(),
                            timestamp=discord.utils.utcnow()
                        )
                    else:
                        embed = discord.Embed(
                            title="Verified & Age-Vetted User Left",
                            description=f"{member.mention} ({member}) has left the server.",
                            color=discord.Color.orange(),
                            timestamp=discord.utils.utcnow()
                        )
                    
                    # More detailed user information
                    embed.set_thumbnail(url=member.display_avatar.url)
                    embed.add_field(name="User ID", value=str(member.id), inline=True)
                    embed.add_field(name="Full User Tag", value=f"{member.name}#{member.discriminator}" if hasattr(member, "discriminator") and member.discriminator != "0" else member.name, inline=True)
                    
                    # Add server-specific information
                    if member.nick and member.nick != member.name:
                        embed.add_field(name="Server Nickname", value=member.nick, inline=True)
                    
                    # Add join date information
                    if time_on_server:
                        embed.add_field(name="Joined Server", value=f"<t:{int(joined_at.timestamp())}:F> (Was on server for {time_on_server})", inline=False)
                    
                    if is_banned:
                        embed.set_footer(text="User was banned. Review ban reason before considering re-age-vetting.")
                    else:
                        embed.set_footer(text="This user had been verified and age-vetted. Use this as proof for re-age-vetting if they rejoin.")
                    
                    await log_channel.send(embed=embed)
                    log.info(f"Logged verified+age-vetted user {'ban' if is_banned else 'leave'}: {member.id} in guild {guild.id}")
                except Exception as e:
                    log.error(f"Failed to send leave log message: {e}", exc_info=True)
    
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        enabled = await self.config.guild(after.guild).autodonator_enabled()
        if not (enabled == "on"):
            return
        await self.rebuild_donator_file(after.guild)

    #ckeytools Commands
    @commands.group()
    @checks.admin_or_permissions(kick_members=True, ban_members=True)
    async def ckeytools(self, ctx: commands.Context):
        """
        Main command for the ckeytools cog
        """
        pass
    

    @ckeytools.command()
    @checks.admin()
    async def forcestay(self, ctx: commands.Context, *, on_or_off: Optional[str]):
        """
        Turn on/off to deverify players who leave the discord server.

        Saves the context in which it was turned on to perform automatic actions.
        """
        current = await self.config.guild(ctx.guild).forcestay_enabled()
        if on_or_off is None:
            return await ctx.send(f"This option is currently set to {current}")
        
        on_or_off = on_or_off.lower()
        
        if on_or_off == "on":
            await ctx.send("Players will now be required to stay in the discord server to play.")
        elif on_or_off == "off":
            await ctx.send("Players will no longer be required to stay in the discord server to play.")
        else:
            return await ctx.send(f"This option is currently set to {current}")
        await self.config.guild(ctx.guild).forcestay_enabled.set(on_or_off)
    
    @ckeytools.command(name="devgone")
    async def mass_deverify_nonmembers(self, ctx: commands.Context):
        """
        Deverify all the linked ckeys not currently in the discord server.
        """
        enabled = await self.config.guild(ctx.guild).forcestay_enabled()
        if not (enabled == "on"):
            return await ctx.send("The requirement to stay in the discord is currently not enabled.")
        
        tgdb = self.get_tgdb()
        prefix = await self.get_tgdb_prefix(ctx.guild)

        deleted = 0

        async with ctx.typing():
            query = f"SELECT * FROM {prefix}discord_links WHERE discord_id IS NOT NULL AND valid = TRUE"
            parameters = []
            rawsults = await tgdb.query_database(ctx, query, parameters)
            results = [DiscordLink.from_db_record(raw) for raw in rawsults]
            for result in results:
                member_check = ctx.guild.get_member(result.discord_id)
                if not member_check:
                    deleted += 1
                    await tgdb.clear_all_valid_discord_links_for_discord_id(ctx, result.discord_id)
        
        return await ctx.send(f"**{deleted}** users have been deverified.")

    @ckeytools.command(name="ckeychange")
    @checks.is_owner()
    async def change_ckey(self, ctx: commands.Context, old_ckey: str, new_ckey: str):
        """
        Change a ckey in the database from one value to another.
        
        This will update all records of the old ckey to the new ckey in the discord_links table.
        Useful for correcting typos or handling name changes without manual database edits.
        
        Parameters:
        - old_ckey: The current ckey in the database
        - new_ckey: The new ckey to replace it with
        """
        # Sanitize inputs - convert to lowercase
        old_ckey = old_ckey.lower()
        new_ckey = new_ckey.lower()
        
        # Get the database prefix
        prefix = await self.get_tgdb_prefix(ctx.guild)
        
        # Let the user know we're processing
        async with ctx.typing():
            try:
                # First, check if the old ckey exists
                check_query = f"SELECT COUNT(*) as count FROM {prefix}discord_links WHERE ckey = %s"
                check_params = [old_ckey]
                check_result = await self.query_database(check_query, check_params)
                
                # If no records found
                if not check_result or check_result[0]["count"] == 0:
                    return await ctx.send(f"❌ No records found for ckey `{old_ckey}`.")
                
                # Check if new ckey already exists
                new_check_query = f"SELECT COUNT(*) as count FROM {prefix}discord_links WHERE ckey = %s"
                new_check_params = [new_ckey]
                new_check_result = await self.query_database(new_check_query, new_check_params)
                
                # Always show confirmation
                confirmation_text = f"Found ckey `{old_ckey}` with {check_result[0]['count']} record(s). Change to `{new_ckey}`?"
                
                # If new ckey already exists, add warning to confirmation
                if new_check_result and new_check_result[0]["count"] > 0:
                    confirmation_text = (
                        f"⚠️ Warning: Found ckey `{old_ckey}` with {check_result[0]['count']} record(s).\n"
                        f"The target ckey `{new_ckey}` already exists in the database with "
                        f"{new_check_result[0]['count']} record(s).\n"
                        f"Are you sure you want to continue?"
                    )
                
                # Show confirmation message
                confirmation = await ctx.send(
                    f"{confirmation_text}\n"
                    f"React with ✅ to confirm or ❌ to cancel."
                )
                
                # Add reactions for confirmation
                await confirmation.add_reaction("✅")
                await confirmation.add_reaction("❌")
                
                # Wait for user confirmation
                def check(reaction, user):
                    return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == confirmation.id
                
                try:
                    reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
                    if str(reaction.emoji) == "❌":
                        return await ctx.send("Operation cancelled.")
                except asyncio.TimeoutError:
                    return await ctx.send("Operation timed out - no changes were made.")
                
                # Update the ckey
                update_query = f"UPDATE {prefix}discord_links SET ckey = %s WHERE ckey = %s"
                update_params = [new_ckey, old_ckey]
                await self.query_database(update_query, update_params)
                
                # Confirmation message
                return await ctx.send(f"✅ Successfully updated all instances of `{old_ckey}` to `{new_ckey}` in the database.")
                
            except Exception as e:
                log.error(f"Error changing ckey: {e}", exc_info=True)
                return await ctx.send(f"❌ An error occurred while updating the ckey: {str(e)}")

    @commands.guild_only()
    @commands.group(name="agetemplate", invoke_without_command=True)
    @checks.mod_or_permissions(administrator=True)
    async def send_age_template(self, ctx: commands.Context):
        """
        Send the configured age template embed with the stored image and message.
        """
        if ctx.invoked_subcommand is not None:
            return
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        guild_conf = self.config.guild(ctx.guild)
        image_url = await guild_conf.agetemplate_image_url()
        message = await guild_conf.agetemplate_message()

        if not image_url:
            prefix = ctx.prefix or ""
            return await ctx.send(f"No template image set. Configure it with `{prefix}agetemplate image <url>`.")

        embed = discord.Embed(
            description=message or "Here is your template message.",
            color=await ctx.embed_color(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_image(url=image_url)

        await ctx.send(embed=embed)

    @send_age_template.command(name="image")
    async def set_agetemplate_image(self, ctx: commands.Context, image_url: str):
        """
        Set the image URL for the age template embed.
        """
        if not image_url.lower().startswith(("http://", "https://")):
            return await ctx.send("Please provide a direct image link that starts with http or https.")

        await self.config.guild(ctx.guild).agetemplate_image_url.set(image_url)
        await ctx.send("Saved the template image URL.")

    @send_age_template.command(name="message")
    async def set_agetemplate_message(self, ctx: commands.Context, *, message: Optional[str] = None):
        """
        Set the default message for the age template embed.
        """
        await self.config.guild(ctx.guild).agetemplate_message.set(message)
        await ctx.send("Saved the template message." if message else "Template message cleared (will use fallback).")

    @send_age_template.command(name="show")
    async def show_agetemplate_config(self, ctx: commands.Context):
        """
        Show the current template configuration.
        """
        guild_conf = self.config.guild(ctx.guild)
        image_url = await guild_conf.agetemplate_image_url()
        message = await guild_conf.agetemplate_message()

        embed = discord.Embed(
            title="Age template configuration",
            color=await ctx.embed_color(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Image URL", value=image_url or "Not set", inline=False)
        embed.add_field(name="Message", value=chat_formatting.box(message or "Not set", "md"), inline=False)
        await ctx.send(embed=embed)

    @send_age_template.command(name="clear")
    async def clear_agetemplate_config(self, ctx: commands.Context):
        """
        Clear the stored image and message for the age template embed.
        """
        guild_conf = self.config.guild(ctx.guild)
        await guild_conf.agetemplate_image_url.clear()
        await guild_conf.agetemplate_message.clear()
        await ctx.send("Cleared the age template image and message.")

    #autodonator Commands
    @commands.group()
    @checks.is_owner()
    async def autodonator(self, ctx: commands.Context):
        """
        Commands for the automatic management of donator roles and perks in-game
        
        Creates and edits a TOML file in the server static files. Made specifically for SPLURT's donator system. 
        Needs configuration on the game itself to properly work.
        """
        pass

    @autodonator.command(name="update")
    async def update_donators(self, ctx: commands.Context):
        """
        Manually create a new donator tier toml file
        """
        await self.rebuild_donator_file(ctx.guild)
        await ctx.tick()
    
    @autodonator.command("check")
    async def check_file(self, ctx: commands.Context):
        """
        Debug command. Prints the current donator file.
        """
        
        folder = await self.config.guild(ctx.guild).config_folder()
        if(folder is None):
            folder = os.path.abspath(os.getcwd())
        folder = os.path.abspath(os.path.join(folder, "donator.toml"))
        
        with open(folder, "r") as donator_file:
            await ctx.send(chat_formatting.box(donator_file.read(), "toml"))

    @autodonator.group()
    async def config(self, ctx: commands.Context):
        """
        Configuration commands for autodonator
        """
        pass
    
    @config.command(name="folder")
    async def set_folder(self, ctx: commands.Context, *, new_repo: str):
        """
        Set the folder of the instance to set donator info in
        
        Please select the __FULL PATH__ of the __FOLDER__ where you want to send the TOML file to
        """
        new_repo = os.path.abspath(new_repo)
        if not (os.path.exists(new_repo) and os.path.isdir(new_repo)):
            return await ctx.send("This path is not a valid folder!")
        
        await self.config.guild(ctx.guild).config_folder.set(new_repo)
        await ctx.tick()
    
    @config.command()
    async def toggle(self, ctx: commands.Context, *, on_or_off: Optional[str]):
        """
        Toggle automatic donator updates (will update whenever user roles are changed)
        """
        current = await self.config.guild(ctx.guild).autodonator_enabled()
        if on_or_off is None:
            return await ctx.send(f"This option is currently set to {current}")
        
        on_or_off = on_or_off.lower()
        
        if on_or_off == "on":
            await ctx.send("Donators will be updated whenever users are updated.")
        elif on_or_off == "off":
            await ctx.send("Donators will no longer be automatically updated.")
        else:
            return await ctx.send(f"This option is currently set to {current}")
        await self.config.guild(ctx.guild).autodonator_enabled.set(on_or_off)
    
    @config.command()
    async def tier(self, ctx: commands.Context, role: discord.Role, *, tier: Optional[str]):
        """
        Edit which roles add what tiers of benefits
        
        Currently available tiers:
            - none
            - first
            - second
            - third
        """
        current_roles: array = await self.config.guild(ctx.guild).donator_roles()
        
        #Safety checks
        if(ctx.guild.get_role(role.id) is None):
            return await ctx.send_help()
        
        if(tier is None):
            return await ctx.send(f"{role.name} currently awards the {await self.config.role(role).donator_tier()} donator tier")
        elif(not (tier.lower() in ["first", "second", "third", "none"])):
            return await ctx.send_help()
        elif(tier.lower() == "none"):
            current_roles.remove(role.id)
        elif(not (role.id in current_roles)):
            current_roles.append(role.id)
        
        await self.config.guild(ctx.guild).donator_roles.set(current_roles)
        await self.config.role(role).donator_tier.set(tier.lower())
        await ctx.send(f"The role {role.name} will now award the {tier.lower()} donator tier")
        await self.rebuild_donator_file(ctx.guild)
    
    @config.command(name="current")
    async def current_roles(self, ctx: commands.Context):
        """
        Shows the current role config for donator awards
        """
        roles = await self.config.guild(ctx.guild).donator_roles()
        roles = [ctx.guild.get_role(role) for role in roles]
        
        roledict = {}
        for role in roles:
            tier = await self.config.role(role).donator_tier()
            roletier = {role.name: tier}
            roledict.update(roletier)
        
        firstdict = {}
        seconddict = {}
        thirddict = {}
        for k, v in roledict.items():
            if v == "first":
                firstdict.update({k: v})
            elif v == "second":
                seconddict.update({k: v})
            elif v == "third":
                thirddict.update({k: v})
        
        embed = discord.Embed(
            title="Current donator roles:",
            color=await ctx.embed_color(),
            timestamp=discord.utils.utcnow()
        )
        firststring = "\n".join(["- {}: {}".format(k, v) for k, v in firstdict.items()])
        secondstring = "\n".join(["- {}: {}".format(k, v) for k, v in seconddict.items()])
        thirdstring = "\n".join(["- {}: {}".format(k, v) for k, v in thirddict.items()])
        
        embed.add_field(name="First tier", value=chat_formatting.box(firststring.strip(), "yaml"), inline=False)
        embed.add_field(name="Second tier", value=chat_formatting.box(secondstring.strip(), "yaml"), inline=False)
        embed.add_field(name="Third tier", value=chat_formatting.box(thirdstring.strip(), "yaml"), inline=False)
        
        await ctx.send("", embed=embed)
        
    
    async def rebuild_donator_file(self, guild: discord.Guild):
        folder = await self.config.guild(guild).config_folder()
        roles = await self.config.guild(guild).donator_roles()
        tgdb = self.get_tgdb()
        if(folder is None):
            folder = os.path.abspath(os.getcwd())
        folder = os.path.abspath(os.path.join(folder, "donator.toml"))
        
        roles = [guild.get_role(role) for role in roles]
        tier1 = []
        tier2 = []
        tier3 = []
        
        for role in roles:
            tier = await self.config.role(role).donator_tier()
            try:
                keys = await self.get_ckeys_from_role(role)
            except TGUnrecoverableError as exception:
                return
            if(tier == "first"):
                tier1 += keys
            if(tier == "second"):
                tier2 += keys
            if(tier == "third"):
                tier3 += keys
        
        with open(folder, mode="w") as donatorfile:
            new_info = {
                "donators": {
                    "tier_1": tier1,
                    "tier_2": tier2,
                    "tier_3": tier3
                }
                    }
            donatorfile.write(tomlkit.dumps(new_info))
    
    #Functions to get cogs and info from the cogs
    async def get_tgdb_prefix(self, guild):
        """
        Gets the prefix for the database linked to tgdb
        """
        tgdb = self.get_tgdb()
        prefix = await tgdb.config.guild(guild).mysql_prefix()
        return prefix

    def get_tgdb(self):
        """
        Gets the TGDB cog if it is installed
        """
        tgdb = self.bot.get_cog("TGDB")
        if not tgdb:
            raise TGUnrecoverableError(
                "TGDB must exist and be configured for ckeytools to work"
            )
        return tgdb
    
    def get_tgverify(self):
        """
        Gets the TGverify cog if it is installed
        """
        tgver = self.bot.get_cog("TGverify")
        if not tgver:
            raise TGUnrecoverableError(
                "TGVerify must exist and be configured for ckeytools to work"
            )
        return tgver
    
    #Miscellaneous functions
    async def query_database(self, query, parameters):
        """
        Use TGDB's active pool to access the database
        """
        tgdb = self.get_tgdb()
        pool = tgdb.pool
        if not pool:
            raise TGUnrecoverableError(
                "The database was not connected. Please reconnect it using [p]tgdb reconnect"
            )
        log.debug(f"Executing query {query}, with parameters {parameters}")
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, parameters)
                rows = cur.fetchall()
                # WRITE TO STORAGE LOL
                await conn.commit()
                return rows.result()
    
    async def get_ckeys_from_role(self, role: discord.Role):
        """
        Get all ckeys from members that have a specific role
        """
        ckeys = []
        for member in role.members:
            link: DiscordLink = await self.link_from_member(member)
            if(not link is None):
                ckeys.append(link.ckey)
        return ckeys
    
    async def link_from_member(self, member: discord.Member):
        """
        Given a valid discord member, return the latest record linked to that user
        """
        prefix = await self.get_tgdb_prefix(member.guild)
        query = f"SELECT * FROM {prefix}discord_links WHERE discord_id = %s AND ckey IS NOT NULL ORDER BY timestamp DESC LIMIT 1"
        parameters = [member.id]
        results = await self.query_database(query, parameters)
        if len(results):
            return DiscordLink.from_db_record(results[0])

        return None

    # New commands for leave logging
    @ckeytools.group(name="leavelog")
    @checks.is_owner()
    async def leave_log_config(self, ctx: commands.Context):
        """
        Configure logging for verified & age-vetted users leaving.
        """
        pass
    
    @leave_log_config.command(name="verified")
    async def set_verified_role(self, ctx: commands.Context, role: discord.Role):
        """Sets the role that is considered 'Verified' for leave logging."""
        await self.config.guild(ctx.guild).verified_role_id.set(role.id)
        await ctx.send(f"Leave logging will track the '{role.name}' role as the verified role.")
    
    @leave_log_config.command(name="agevetted")
    async def set_age_vetted_role(self, ctx: commands.Context, role: discord.Role):
        """Sets the role that is considered 'Age-Vetted' for leave logging."""
        await self.config.guild(ctx.guild).age_vetted_role_id.set(role.id)
        await ctx.send(f"Leave logging will track the '{role.name}' role as the age-vetted role.")
    
    @leave_log_config.command(name="channel")
    async def set_leave_log_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Sets the channel where leave logs will be sent."""
        await self.config.guild(ctx.guild).leave_log_channel_id.set(channel.id)
        await ctx.send(f"Leave logs will now be sent to {channel.mention}.")
    
    @leave_log_config.command(name="toggle")
    async def toggle_leave_log(self, ctx: commands.Context, enable: bool):
        """Enables or disables leave logging."""
        await self.config.guild(ctx.guild).leave_log_enabled.set(enable)
        status = "enabled" if enable else "disabled"
        await ctx.send(f"Leave logging is now {status}.")
    
    @leave_log_config.command(name="status")
    async def show_leave_log_status(self, ctx: commands.Context):
        """Shows the current leave logging configuration."""
        settings = {}
        settings["enabled"] = await self.config.guild(ctx.guild).leave_log_enabled()
        settings["verified_role_id"] = await self.config.guild(ctx.guild).verified_role_id()
        settings["age_vetted_role_id"] = await self.config.guild(ctx.guild).age_vetted_role_id()
        settings["log_channel_id"] = await self.config.guild(ctx.guild).leave_log_channel_id()
        
        verified_role = ctx.guild.get_role(settings["verified_role_id"]) if settings["verified_role_id"] else None
        age_vetted_role = ctx.guild.get_role(settings["age_vetted_role_id"]) if settings["age_vetted_role_id"] else None
        log_channel = ctx.guild.get_channel(settings["log_channel_id"]) if settings["log_channel_id"] else None
        
        embed = discord.Embed(
            title="Leave Logging Configuration",
            color=await ctx.embed_color(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Enabled", value=str(settings["enabled"]), inline=False)
        embed.add_field(
            name="Verified Role", 
            value=f"{verified_role.mention} ({verified_role.id})" if verified_role else "Not set", 
            inline=False
        )
        embed.add_field(
            name="Age-Vetted Role", 
            value=f"{age_vetted_role.mention} ({age_vetted_role.id})" if age_vetted_role else "Not set", 
            inline=False
        )
        embed.add_field(
            name="Log Channel", 
            value=f"{log_channel.mention} ({log_channel.id})" if log_channel else "Not set", 
            inline=False
        )
        
        await ctx.send(embed=embed)
        
    @leave_log_config.command(name="simulate")
    async def simulate_leave_log(self, ctx: commands.Context, member: discord.Member = None):
        """
        Simulates a leave log message for testing purposes.
        
        If no member is specified, uses the command invoker as the test subject.
        """
        # This is a test function to simulate the leave log embed
        # Use the command invoker if no member specified
        if member is None:
            member = ctx.author
            
        # Check if feature is properly configured
        verified_role_id = await self.config.guild(ctx.guild).verified_role_id()
        age_vetted_role_id = await self.config.guild(ctx.guild).age_vetted_role_id()
        log_channel_id = await self.config.guild(ctx.guild).leave_log_channel_id()
        
        if not all([verified_role_id, age_vetted_role_id, log_channel_id]):
            missing = []
            if not verified_role_id:
                missing.append("Verified role")
            if not age_vetted_role_id:
                missing.append("Age-vetted role")
            if not log_channel_id:
                missing.append("Log channel")
            
            missing_str = ", ".join(missing)
            return await ctx.send(f"⚠️ Cannot simulate: {missing_str} not configured. Use `{ctx.prefix}ckeytools leavelog status` to check your configuration.")
        
        # Get the log channel
        log_channel = ctx.guild.get_channel(log_channel_id)
        if not log_channel or not isinstance(log_channel, discord.TextChannel):
            return await ctx.send(f"⚠️ Cannot simulate: Log channel not found or is not a text channel.")
        
        # Create the embed exactly as it would appear when a user leaves
        try:
            # Calculate time on server if join date is available
            joined_at = member.joined_at
            time_on_server = ""
            if joined_at:
                days_on_server = (discord.utils.utcnow() - joined_at).days
                time_on_server = f"{days_on_server} days"
            
            embed = discord.Embed(
                title="Verified & Age-Vetted User Left",
                description=f"{member.mention} ({member}) has left the server.",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow()
            )
            
            # More detailed user information
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="User ID", value=str(member.id), inline=True)
            embed.add_field(name="Full User Tag", value=f"{member.name}#{member.discriminator}" if hasattr(member, "discriminator") and member.discriminator != "0" else member.name, inline=True)
            
            # Add server-specific information
            if member.nick and member.nick != member.name:
                embed.add_field(name="Server Nickname", value=member.nick, inline=True)
            
            # Add join date information
            if time_on_server:
                embed.add_field(name="Joined Server", value=f"<t:{int(joined_at.timestamp())}:F> (Was on server for {time_on_server})", inline=False)
            
            # Add simulation notice and vetting guidance
            embed.set_footer(text="This is a simulation - the user has not actually left | Use this as proof for re-age-vetting if they rejoin.")
            
            # Send the embed to the log channel
            await log_channel.send(embed=embed)
            await ctx.send(f"✅ Simulation completed. Check {log_channel.mention} to view the test message.")
            
        except Exception as e:
            await ctx.send(f"❌ Error during simulation: {str(e)}")
            log.error(f"Error in leave log simulation: {e}", exc_info=True)

    @leave_log_config.command(name="simulateban")
    async def simulate_ban_log(self, ctx: commands.Context, member: discord.Member = None):
        """
        Simulates a ban log message for testing purposes.
        
        Parameters:
        - member: The member to simulate as banned (defaults to yourself)
        """
        # Use the command invoker if no member specified
        if member is None:
            member = ctx.author
            
        # Check if feature is properly configured
        verified_role_id = await self.config.guild(ctx.guild).verified_role_id()
        age_vetted_role_id = await self.config.guild(ctx.guild).age_vetted_role_id()
        log_channel_id = await self.config.guild(ctx.guild).leave_log_channel_id()
        
        if not all([verified_role_id, age_vetted_role_id, log_channel_id]):
            missing = []
            if not verified_role_id:
                missing.append("Verified role")
            if not age_vetted_role_id:
                missing.append("Age-vetted role")
            if not log_channel_id:
                missing.append("Log channel")
            
            missing_str = ", ".join(missing)
            return await ctx.send(f"⚠️ Cannot simulate: {missing_str} not configured. Use `{ctx.prefix}ckeytools leavelog status` to check your configuration.")
        
        # Get the log channel
        log_channel = ctx.guild.get_channel(log_channel_id)
        if not log_channel or not isinstance(log_channel, discord.TextChannel):
            return await ctx.send(f"⚠️ Cannot simulate: Log channel not found or is not a text channel.")
        
        # Create the embed for a ban
        try:
            # Calculate time on server if join date is available
            joined_at = member.joined_at
            time_on_server = ""
            if joined_at:
                days_on_server = (discord.utils.utcnow() - joined_at).days
                time_on_server = f"{days_on_server} days"
            
            embed = discord.Embed(
                title="Verified & Age-Vetted User Banned",
                description=f"{member.mention} ({member}) has been banned from the server.",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            
            # More detailed user information
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="User ID", value=str(member.id), inline=True)
            embed.add_field(name="Full User Tag", value=f"{member.name}#{member.discriminator}" if hasattr(member, "discriminator") and member.discriminator != "0" else member.name, inline=True)
            
            # Add server-specific information
            if member.nick and member.nick != member.name:
                embed.add_field(name="Server Nickname", value=member.nick, inline=True)
            
            # Add join date information
            if time_on_server:
                embed.add_field(name="Joined Server", value=f"<t:{int(joined_at.timestamp())}:F> (Was on server for {time_on_server})", inline=False)
            
            # Add simulation notice
            embed.set_footer(text="This is a simulation - the user has not actually been banned | Review ban reason before considering re-age-vetting.")
            
            # Send the embed to the log channel
            await log_channel.send(embed=embed)
            await ctx.send(f"✅ Ban simulation completed. Check {log_channel.mention} to view the test message.")
            
        except Exception as e:
            await ctx.send(f"❌ Error during ban simulation: {str(e)}")
            log.error(f"Error in ban log simulation: {e}", exc_info=True)
