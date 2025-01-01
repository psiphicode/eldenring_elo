# builtin libs
import os

# pip installed libs
from dotenv import load_dotenv
import discord
from discord import app_commands
from discord.ext import commands

# locally defined libs
import db # location: app/db/__init__.py

# read environment variables from .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = int(os.getenv("SERVER_ID"))

# channels
channels = {
    "the-protocols": 1323799794690556045,
    "bingo-results": 1322399416648470579,
    "elo-register": 1323800968898412624,
}
channel_names = { v:k for k,v in channels.items() }

# exceptions: discord roles/channels permissions
class MissingRoleError(app_commands.CheckFailure):
    """Raised when the user does not have the required role."""
    def __init__(self, role_names: str):
        self.role_names = role_names
        super().__init__(f"User lacks one of the required roles: {', '.join(role_names)}")

class IncorrectChannelError(app_commands.CheckFailure):
    """Raised when the command is used in the wrong channel."""
    def __init__(self, channel_ids: int):
        self.channel_ids = channel_ids
        self.allowed_channels = ', '.join([channel_names[channel_id] for channel_id in channel_ids])
        super().__init__(f"Command must be used in one of the channels: {self.allowed_channels}")

# restrict a command to a list of roles
def is_allowed_roles(role_names: list[str]):
    def predicate(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            return False
        # Get all role names, or default to an empty list if no roles
        allowed_roles = [role.name for role in getattr(interaction.user, "roles", [])]
        if any(role in allowed_roles for role in role_names):
            return True
        else:
            raise MissingRoleError(role_names)
    return app_commands.check(predicate)

# restrict a command to a list of channels
def is_allowed_channel(channel_ids: list[int]):
    def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.channel.id in channel_ids:
            raise IncorrectChannelError(channel_ids)
        return True
    return app_commands.check(predicate)

# command interactions follow a pattern
async def wrap_interaction(interaction, callback, *args):
    try:
        result = await callback(*args)
        await interaction.response.send_message(result[1], ephemeral=not result[0])
    except Exception as e:
        print(f"Exception occured: {e}")
        await interaction.response.send_message("Whoops! There was an internal server error.", ephemeral=True)

outcome_choices = [
    app_commands.Choice(name="Win", value="win"),
    app_commands.Choice(name="Loss", value="loss"),
    app_commands.Choice(name="Draw", value="draw"),
]

class EloBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="register", description="Register for Elo tracking")
    @is_allowed_channel([channels["elo-register"]])
    async def register(self, interaction: discord.Interaction):
        discord_id = interaction.user.id
        username = interaction.user.name
        await wrap_interaction(interaction, db.register, discord_id, username)

    @app_commands.command(name="register_player", description="Register another player for Elo tracking")
    @is_allowed_roles(["Core", "Contributor"])
    async def register_player(self, interaction: discord.Interaction, player: discord.Member):
        discord_id = player.id
        username = player.name
        await wrap_interaction(interaction, db.register, discord_id, username)

    @app_commands.command(name="record", description="Record a game result")
    @app_commands.choices(outcome=outcome_choices)
    @is_allowed_roles(["Core", "Contributor"])
    @is_allowed_channel([channels["bingo-results"]])
    async def record(self, interaction: discord.Interaction, player1: discord.Member, player2: discord.Member,
                     outcome: app_commands.Choice[str]):
        discord_id1, discord_id2 = player1.id, player2.id
        if discord_id1 == discord_id2:
            await interaction.response.send_message("Whoops! player1 must be different than player2", ephemeral=True)
        else:
            await wrap_interaction(interaction, db.record, discord_id1, discord_id2, outcome.value)

    @app_commands.command(name="leaderboard", description="View the current leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        await wrap_interaction(interaction, db.leaderboard)

    @app_commands.command(name="rating", description="View your Elo rating")
    async def rating(self, interaction: discord.Interaction):
        discord_id = interaction.user.id
        await wrap_interaction(interaction, db.rating, discord_id)

bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

# Error handling for inaccessible commands
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, MissingRoleError):
        await interaction.response.send_message(
            f"You do not have one of the required roles: {', '.join(error.role_names)}.", ephemeral=True
        )
    elif isinstance(error, IncorrectChannelError):
        await interaction.response.send_message(
            f"This command must be used in one of the following channels: {error.allowed_channels}.",
            ephemeral=True
        )
    elif isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message(
            "You do not meet the requirements to use this command.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"An unexpected error occurred: {str(error)}", ephemeral=True
        )

@bot.event
async def on_ready():
    try:
        # add commands to the bot
        await bot.add_cog(EloBot(bot))
        # sync commands to the discord server
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)  # Sync commands to Discord
        print(f"Succeeded in syncing commands in server: {GUILD_ID}")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

    try:
        # setup database
        await db.initialize()
        print("Database initialized")
    except:
        print("Database initialization failed")

    print(f"Logged in as {bot.user}!")

# run the discord bot
bot.run(BOT_TOKEN)
