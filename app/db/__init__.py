"""
All database interactions return a tuple (Success, Message)
"""
import aiosqlite

DB_NAME = "app/db/elo.db"

async def initialize():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id INTEGER UNIQUE NOT NULL,
            username TEXT NOT NULL,
            rating INTEGER DEFAULT 1200
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player1_id INTEGER NOT NULL,
            player2_id INTEGER NOT NULL,
            result TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(player1_id) REFERENCES players(id),
            FOREIGN KEY(player2_id) REFERENCES players(id)
        )
        """)
        await db.commit()

async def register(discord_id, username):
    async with aiosqlite.connect(DB_NAME) as db:
        try:
            await db.execute(
                "INSERT INTO players (discord_id, username) VALUES (?, ?)",
                (discord_id, username)
            )
            await db.commit()
            return (True, f"Player {username} is now registered!")
        except aiosqlite.IntegrityError:
            return (False, f"Player {username} is already registered!")

async def leaderboard():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT username, rating FROM players ORDER BY rating DESC LIMIT 10") as cursor:
            rows = await cursor.fetchall()
    if not rows:
        return (False, "No players registered yet.")
    else:
        leaderboard = "\n".join([f"{i+1}. {row[0]}: {row[1]}" for i, row in enumerate(rows)])
        return (True, leaderboard)

async def rating(discord_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, username, rating FROM players WHERE discord_id = ?", (discord_id,)) as cursor:
            player = await cursor.fetchone()
    if not player:
        return (False, "Player isn't registered")
    return (True, f"Player {player[1]} has rating {player[2]}!")

async def record(discord_id1, discord_id2, outcome):
    async with aiosqlite.connect(DB_NAME) as db:
        # Fetch players
        async with db.execute("SELECT id, username, rating FROM players WHERE discord_id = ?", (discord_id1,)) as cursor:
            player1 = await cursor.fetchone()
        async with db.execute("SELECT id, username, rating FROM players WHERE discord_id = ?", (discord_id2,)) as cursor:
            player2 = await cursor.fetchone()

        if not player1 or not player2:
            print(discord_id1, player1, discord_id2, player2)
            return (False, "At least one of the players is not registered.")

        # Calculate Elo
        rating1, rating2 = player1[2], player2[2]
        k = 32
        expected1 = 1 / (1 + 10 ** ((rating2 - rating1) / 400))
        expected2 = 1 / (1 + 10 ** ((rating1 - rating2) / 400))

        if outcome == "win":
            score1, score2 = 1, 0
        elif outcome == "loss":
            score1, score2 = 0, 1
        else:  # draw
            score1, score2 = 0.5, 0.5

        new_rating1 = round(rating1 + k * (score1 - expected1))
        new_rating2 = round(rating2 + k * (score2 - expected2))

        # Update ratings and log the game
        await db.execute("UPDATE players SET rating = ? WHERE id = ?", (new_rating1, player1[0]))
        await db.execute("UPDATE players SET rating = ? WHERE id = ?", (new_rating2, player2[0]))
        await db.execute(
            "INSERT INTO games (player1_id, player2_id, result) VALUES (?, ?, ?)",
            (player1[0], player2[0], outcome)
        )
        await db.commit()

        username1, username2 = player1[1], player2[1]
        return (True, f"Game recorded! New ratings: {username1} ({new_rating1}), {username2} ({new_rating2})")

