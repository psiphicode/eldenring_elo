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
GUILD_ID = int(os.getenv("PSIPHI_SERVER_ID"))

# restrict a command to a list of roles
def is_allowed_roles(role_names: list[str]):
    def predicate(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            return False
        # Get all role names, or default to an empty list if no roles
        allowed_roles = [role.name for role in getattr(interaction.user, "roles", [])]
        return any(role in allowed_roles for role in role_names)
    return app_commands.check(predicate)

# db interactions follow a pattern
async def wrap_interaction(interaction, callback, *args):
    try:
        result = await callback(*args)
        await interaction.response.send_message(result[1], ephemeral=not result[0])
    except Exception as e:
        print(f"Exception occured: {e}")
        await interaction.response.send_message("There was an internal server error.", ephemeral=True)

outcome_choices = [
    app_commands.Choice(name="Win", value="win"),
    app_commands.Choice(name="Loss", value="loss"),
    app_commands.Choice(name="Draw", value="draw")
]

class EloBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="register", description="Register yourself for Elo tracking")
    async def register(self, interaction: discord.Interaction):
        discord_id = interaction.user.id
        username = interaction.user.name
        await wrap_interaction(interaction, db.register, discord_id, username)

    @app_commands.command(name="record", description="Record a game result")
    @app_commands.choices(outcome=outcome_choices)
    @is_allowed_roles(["Core", "Contributor"])
    async def record(self, interaction: discord.Interaction, player1: discord.Member, player2: discord.Member,
                     outcome: app_commands.Choice[str]):
        discord_id1, discord_id2 = player1.id, player2.id
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
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message(
            "You do not have the required role or permissions to use this command.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"An unexpected error occurred: {str(error)}",
            ephemeral=True
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
