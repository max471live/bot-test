import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import json
import os
import random
import sqlite3
from datetime import datetime
from io import BytesIO
import requests
from PIL import Image, ImageDraw, ImageFont

# Configuration
DEEPINFRA_API_KEY = "1lO8eP244oEOuuxz5oDMBCGD6ljCzIef"
TOKEN = os.getenv("TOKEN")  # Replace the hardcoded token


# With these direct values (replace with your actual IDs)

DALIBI_CHANNEL_ID = 1371121385661010040  # Replace with your channel ID for Da Li Bi
KALADONT_CHANNEL_ID = 1371121376257380402  # Replace with your channel ID for Kaladont
SHIP_CHANNEL_ID = 1371121393634119831  # Replace with your channel ID for Ship
KISS_MARRY_KILL_CHANNEL_ID = 1371122036600082552  # Replace with your channel ID for Kiss Marry Kill
WELCOME_CHANNEL_ID = 1349448358900535372  # Replace with your welcome channel ID
WELCOME_ROLE_ID = 1349448358439419973  # Replace with your welcome role ID

# Game configurations
KALADONT_POINTS_PER_WIN = 10
KALADONT_POINTS_PER_WORD = 5
KALADONT_GAME_TIMEOUT = 300
SHIP_BACKGROUND_URL = "https://cdn.discordapp.com/attachments/935570892535251004/1371095597561548920/Untitled_design_7.png?ex=6821e3c8&is=68209248&hm=232aa66f4eab0ede4dc585b6f11e4c409ede6535d2fccc0b639c4a13e78cd92b&"
WELCOME_BACKGROUND_URL = "https://cdn.discordapp.com/attachments/1355936211734102101/1370911765449150534/discord.ggfoxara_4.png?ex=68228a13&is=68213893&hm=cbe999bcf389b896d94422e271500f261ee59f522bbbb212664c4b56905d80e0&"

# Initialize bot
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Database setup for Kaladont
def init_kaladont_db():
    conn = sqlite3.connect("kaladont.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            points INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            last_played TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Helper function to check channel restrictions
async def check_channel(interaction: discord.Interaction, channel_id: int) -> bool:
    if channel_id == 0:  # No restriction set
        return True
    return interaction.channel_id == channel_id

# --- Da Li Bi Cog ---
class DalibiView(discord.ui.View):
    def __init__(self, question, user):
        super().__init__(timeout=60)
        self.question = question
        self.user = user

        question_text = question.replace("Da li bi radije ", "").rstrip("?")
        options = [opt.strip() for opt in question_text.split(" ili ") if opt.strip()]

        def format_option(option):
            trimmed = option if len(option) <= 23 else option[:22].rsplit(' ', 1)[0]
            return f"🟠 {trimmed}"

        if len(options) >= 2:
            self.option1, self.option2 = options[:2]

            self.add_item(discord.ui.Button(
                style=discord.ButtonStyle.primary,
                label=format_option(self.option1),
                custom_id="option1"
            ))
            self.add_item(discord.ui.Button(
                style=discord.ButtonStyle.primary,
                label=format_option(self.option2),
                custom_id="option2"
            ))

        self.add_item(discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Ne želim da odgovorim",
            emoji="❌",
            custom_id="skip",
            row=1
        ))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user.id

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except:
            pass

class DalibiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_views = {}
        self.used_questions = set()
        self.questions_file = "used_questions.json"
        
        if os.path.exists(self.questions_file):
            with open(self.questions_file, 'r') as f:
                self.used_questions = set(json.load(f))

    def save_questions(self):
        with open(self.questions_file, 'w') as f:
            json.dump(list(self.used_questions), f)

    async def generate_ai_question(self):
        prompt = """Generiši kratko i jedinstveno "Da li bi radije?" pitanje na srpskom. 
        Pitanje mora biti maksimalno kratko i jednostavno. 
        Format: "Da li bi radije [opcija1] ili [opcija2]?" 
        Bez ikakvih dodatnih teksta, samo tačno pitanje u traženom formatu.
        Pitanje mora biti dužine najviše 10 reči."""

        headers = {
            "Authorization": f"Bearer {DEEPINFRA_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "meta-llama/Meta-Llama-3-70B-Instruct",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 50
        }

        try:
            async with aiohttp.ClientSession() as session:
                for attempt in range(3):
                    async with session.post(
                        "https://api.deepinfra.com/v1/openai/chat/completions",
                        headers=headers,
                        json=payload
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            question = data["choices"][0]["message"]["content"].strip()
                            
                            question = question.replace('"', '')
                            if not question.startswith("Da li bi radije"):
                                question = "Da li bi radije " + question
                            if not question.endswith("?"):
                                question += "?"
                            
                            if question not in self.used_questions:
                                self.used_questions.add(question)
                                self.save_questions()
                                return question
            return None
        except Exception as e:
            print(f"Error generating question: {e}")
            return None

    @app_commands.command(name="dalibi", description="Igraj igru da li bi radije!🦊")
    async def dalibi(self, interaction: discord.Interaction):
        if not await check_channel(interaction, DALIBI_CHANNEL_ID):
            return await interaction.response.send_message(
                f"Ova komanda se može koristiti samo u odgovarajućem kanalu!", 
                ephemeral=True
            )

        await interaction.response.defer()
        question = await self.generate_ai_question()
        if not question:
            return await interaction.followup.send("Došlo je do greške pri generisanju pitanja. Pokušajte ponovo.")

        if len(question.split()) > 15 or "Here are some" in question or "some short" in question:
            return await interaction.followup.send("Došlo je do greške pri generisanju pitanja. Pokušajte ponovo.")

        embed = discord.Embed(
            title="Da li bi radije?",
            description=question,
            color=discord.Color.orange()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)

        view = DalibiView(question, interaction.user)
        message = await interaction.followup.send(embed=embed, view=view)
        view.message = message
        self.active_views[message.id] = view

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return

        if not interaction.data or "custom_id" not in interaction.data:
            return

        custom_id = interaction.data["custom_id"]

        if custom_id in ["option1", "option2", "skip"]:
            view = self.active_views.get(interaction.message.id)
            if not view:
                return

            if custom_id == "option1":
                answer = f"Odgovor: {view.option1}"
            elif custom_id == "option2":
                answer = f"Odgovor: {view.option2}"
            else:
                answer = "Odgovor: Ne želi da odgovori"

            new_embed = discord.Embed(
                title="Da li bi radije?",
                description=f"{view.question}\n\n{answer}",
                color=discord.Color.orange()
            )
            new_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)

            for item in view.children:
                item.disabled = True

            await interaction.response.edit_message(embed=new_embed, view=view)
            del self.active_views[interaction.message.id]

# --- Kaladont Cog ---
class KaladontCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}
        init_kaladont_db()

    async def get_player_data(self, user_id):
        conn = sqlite3.connect("kaladont.db")
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM players WHERE user_id = ?', (user_id,))
        data = cursor.fetchone()
        conn.close()
        return data

    async def update_player_score(self, user, points_to_add=0, win=False):
        conn = sqlite3.connect("kaladont.db")
        cursor = conn.cursor()
        
        current_data = await self.get_player_data(user.id)
        
        if current_data:
            new_points = current_data[2] + points_to_add
            new_wins = current_data[3] + (1 if win else 0)
            cursor.execute('''
                UPDATE players 
                SET points = ?, wins = ?, last_played = ?, username = ?
                WHERE user_id = ?
            ''', (new_points, new_wins, datetime.now().isoformat(), str(user), user.id))
        else:
            cursor.execute('''
                INSERT INTO players (user_id, username, points, wins, last_played)
                VALUES (?, ?, ?, ?, ?)
            ''', (user.id, str(user), points_to_add, 1 if win else 0, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        return new_points if current_data else points_to_add

    async def get_leaderboard(self, limit=10):
        conn = sqlite3.connect("kaladont.db")
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, username, points 
            FROM players 
            ORDER BY points DESC 
            LIMIT ?
        ''', (limit,))
        leaderboard = cursor.fetchall()
        conn.close()
        return leaderboard

    async def validate_serbian_word(self, word):
        word = word.lower().strip()
        if len(word) < 2:
            return False
        forbidden = {'kaladont', 'internet', 'facebook', 'instagram', 'twitter', 'youtube', 'google'}
        if word in forbidden:
            return False

        if len(word) <= 3 and word not in {'ja', 'ti', 'mi', 'vi', 'on', 'ona', 'ono'}:
            return False

        url = "https://api.deepinfra.com/v1/openai/chat/completions"
        headers = {
            "Authorization": f"Bearer {DEEPINFRA_API_KEY}",
            "Content-Type": "application/json"
        }

        prompt = (
            f"Da li je '{word}' validna reč u srpskom jeziku? "
            "Odgovori tačno samo sa 'da' ako je reč gramatički ispravna i postoji u srpskom jeziku. "
            "Odgovori sa 'ne' ako reč ne postoji, ne znači ništa, ili izgleda izmišljeno."
        )

        data = {
            "model": "meta-llama/Meta-Llama-3-70B-Instruct",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 3,
            "temperature": 0
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status != 200:
                        return False
                    result = await response.json()
                    return result['choices'][0]['message']['content'].strip().lower().startswith('da')
        except:
            return False

    def get_last_two_letters(self, word):
        word = word.lower().strip()
        return word if len(word) <= 2 else word[-2:]

    def can_follow(self, current_word, new_word):
        if not current_word:
            return True
        return new_word.lower().startswith(self.get_last_two_letters(current_word))

    async def end_game(self, channel, winner=None, ended_by=None):
        if channel.id not in self.active_games:
            return
        game = self.active_games[channel.id]
        if winner:
            new_points = await self.update_player_score(winner, KALADONT_POINTS_PER_WIN, win=True)
            embed = discord.Embed(
                title="Igra je završena!",
                description=f"🎉 {winner.mention} je upisao kaladont i pobedio/la! (+{KALADONT_POINTS_PER_WIN} poena)",
                color=discord.Color.orange()
            )
            embed.set_footer(text=f"Sada ima ukupno {new_points} bodova.")
            await channel.send(embed=embed)
        elif ended_by:
            embed = discord.Embed(
                title="Igra je završena!",
                description=f"Igra je završena od strane {ended_by.mention}",
                color=discord.Color.orange()
            )
            await channel.send(embed=embed)
        else:
            await channel.send("❌ Igra je završena zbog neaktivnosti.")
        del self.active_games[channel.id]

    @app_commands.command(name="kaladont", description="Igraj igru kaladont!🦊")
    async def kaladont(self, interaction: discord.Interaction):
        if not await check_channel(interaction, KALADONT_CHANNEL_ID):
            return await interaction.response.send_message(
                f"Ova komanda se može koristiti samo u odgovarajućem kanalu!", 
                ephemeral=True
            )

        if interaction.channel.id in self.active_games:
            await interaction.response.send_message("Već postoji aktivna igra u ovom kanalu!", ephemeral=True)
            return

        self.active_games[interaction.channel.id] = {
            'players': [interaction.user],
            'current_player': None,
            'current_word': '',
            'used_words': set(),
            'last_move_time': interaction.created_at.timestamp(),
            'creator': interaction.user,
            'last_player': None
        }

        embed = discord.Embed(
            description="✅ **Kaladont je započet!**\nNapišite bilo koju reč!",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="kaladont_top", description="Prikazi top 10 kaladont igraca!🦊")
    async def kaladont_top(self, interaction: discord.Interaction):
        leaderboard = await self.get_leaderboard()
        if not leaderboard:
            await interaction.response.send_message("Još nema igrača na listi!", ephemeral=True)
            return

        embed = discord.Embed(
            title="🏆 Top 10 Kaladont Igrača",
            description="Lista najboljih igrača prema broju bodova:",
            color=discord.Color.orange()
        )
        for idx, (user_id, username, points) in enumerate(leaderboard, 1):
            member = interaction.guild.get_member(user_id)
            display_name = member.display_name if member else username
            embed.add_field(
                name=f"{idx}. {display_name}",
                value=f"➡️ {points} bodova",
                inline=False
            )
        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        if message.content.startswith(self.bot.command_prefix):
            return
        if message.channel.id not in self.active_games:
            return

        game = self.active_games[message.channel.id]
        content = message.content.lower().strip()

        if content == 'zaustavi':
            if message.author == game['creator']:
                await self.end_game(message.channel, ended_by=message.author)
            else:
                await message.add_reaction("❌")
            return

        if content == 'kaladont':
            if not game.get('current_word', '').endswith('ka'):
                await message.add_reaction("❌")
                return
            await self.end_game(message.channel, winner=message.author)
            return

        if len(content) < 3 or content in game['used_words']:
            await message.add_reaction("❌")
            return

        if message.author not in game['players']:
            game['players'].append(message.author)

        if not game['current_word']:
            game['current_word'] = content
            game['used_words'].add(content)
            game['last_move_time'] = message.created_at.timestamp()
            game['last_player'] = message.author
            await self.update_player_score(message.author, KALADONT_POINTS_PER_WORD)
            last_two = self.get_last_two_letters(content)
            
            embed = discord.Embed(
                title=f"✅ __{content.capitalize()}__",
                description=f"**Iduća reč mora počinjati na slova:** `{last_two}`",
                color=discord.Color.orange()
            )
            embed.set_footer(text=f"Upiši 'zaustavi' za kraj igre | {message.author.display_name} +{KALADONT_POINTS_PER_WORD} poena")
            await message.channel.send(embed=embed)
            return

        if game['last_player'] == message.author or not self.can_follow(game['current_word'], content):
            await message.add_reaction("❌")
            return

        is_valid = await self.validate_serbian_word(content)
        if not is_valid:
            await message.add_reaction("❌")
            return

        game['current_word'] = content
        game['used_words'].add(content)
        game['last_move_time'] = message.created_at.timestamp()
        game['last_player'] = message.author
        await self.update_player_score(message.author, KALADONT_POINTS_PER_WORD)
        last_two = self.get_last_two_letters(content)
        
        embed = discord.Embed(
            title=f"✅ __{content.capitalize()}__",
            description=f"**Iduća reč mora počinjati na slova:** `{last_two}`",
            color=discord.Color.orange()
        )
        embed.set_footer(text=f"Upiši 'zaustavi' za kraj igre | {message.author.display_name} +{KALADONT_POINTS_PER_WORD} poena")
        await message.channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.loop.create_task(self.check_inactive_games())

    async def check_inactive_games(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            now = discord.utils.utcnow().timestamp()
            to_remove = [cid for cid, g in self.active_games.items() if now - g['last_move_time'] > KALADONT_GAME_TIMEOUT]
            for cid in to_remove:
                channel = self.bot.get_channel(cid)
                if channel:
                    await self.end_game(channel)
            await asyncio.sleep(60)

# --- Kiss Marry Kill Cog ---
class GameSession:
    def __init__(self, user, selected_users):
        self.user = user
        self.original_targets = selected_users
        self.targets = selected_users.copy()
        self.choices = {"kiss": None, "marry": None, "kill": None}

    def is_complete(self):
        return all(self.choices.values())

    def get_remaining_targets(self):
        return [target for target in self.targets if target not in self.choices.values()]

class TargetSelectView(discord.ui.View):
    def __init__(self, session: GameSession, action: str, original_msg: discord.InteractionMessage):
        super().__init__(timeout=60)
        self.session = session
        self.action = action
        self.original_msg = original_msg

        remaining_targets = self.session.get_remaining_targets()
        for target in remaining_targets:
            label = target.display_name
            self.add_item(TargetButton(label=label, target=target, action=action, view=self))

class TargetButton(discord.ui.Button):
    def __init__(self, label, target, action, view):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.target = target
        self.action = action
        self.custom_view = view

    async def callback(self, interaction: discord.Interaction):
        session = self.custom_view.session

        if interaction.user.id != session.user.id:
            await interaction.response.send_message("Samo ti možeš igrati svoju igru!", ephemeral=True)
            return

        if session.choices[self.action] is not None:
            await interaction.response.send_message(f"Već si izabrao nekoga za {self.action}.", ephemeral=True)
            return

        if self.target in session.choices.values():
            await interaction.response.send_message("Već si izabrao ovu osobu za neku drugu akciju!", ephemeral=True)
            return

        session.choices[self.action] = self.target
        session.targets.remove(self.target)

        if session.is_complete():
            embed = discord.Embed(
                title="Kiss/Marry/Kill",
                description=(
                    f"💋 Kiss: {session.choices['kiss'].mention} ({session.choices['kiss'].display_name})\n"
                    f"💍 Marry: {session.choices['marry'].mention} ({session.choices['marry'].display_name})\n"
                    f"🔪 Kill: {session.choices['kill'].mention} ({session.choices['kill'].display_name})"
                ),
                color=discord.Color.orange()
            )
            embed.set_author(name=session.user.display_name, icon_url=session.user.avatar.url)
            embed.set_footer(text="Želiš i ti koristiti komandu? Upiši /kissmarrykill")
            await self.custom_view.original_msg.edit(embed=embed, view=None)
            await interaction.response.send_message("Igra završena! ✅", ephemeral=True)
        else:
            remaining_targets = session.get_remaining_targets()
            description = "\n".join([f"{i+1}. {target.mention} ({target.display_name})" for i, target in enumerate(remaining_targets)])

            embed = discord.Embed(
                title="💋💍🔪 Kiss Marry Kill",
                description=description,
                color=discord.Color.orange()
            )
            embed.set_author(name=session.user.display_name, icon_url=session.user.avatar.url)
            embed.set_footer(text="Želiš i ti koristiti komandu? Upiši /kissmarrykill")
            await self.custom_view.original_msg.edit(embed=embed)

            await interaction.response.send_message(f"Izabrao si {self.target.mention} ({self.target.display_name}) za {self.action}.", ephemeral=True)

class ActionView(discord.ui.View):
    def __init__(self, session: GameSession, message: discord.InteractionMessage):
        super().__init__(timeout=60)
        self.session = session
        self.message = message

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.session.user.id:
            await interaction.response.send_message("Samo ti možeš igrati svoju igru!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Kiss", style=discord.ButtonStyle.primary, emoji="💋")
    async def kiss(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"Izaberi osobu za 💋 Kiss", view=TargetSelectView(self.session, "kiss", self.message), ephemeral=True)

    @discord.ui.button(label="Marry", style=discord.ButtonStyle.success, emoji="💍")
    async def marry(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"Izaberi osobu za 💍 Marry", view=TargetSelectView(self.session, "marry", self.message), ephemeral=True)

    @discord.ui.button(label="Kill", style=discord.ButtonStyle.danger, emoji="🔪")
    async def kill(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"Izaberi osobu za 🔪 Kill", view=TargetSelectView(self.session, "kill", self.message), ephemeral=True)

class KissMarryKillCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sessions = {}

    @app_commands.command(name="kissmarrykill", description="Igraj Kiss Marry Kill!🦊")
    async def kissmarrykill(self, interaction: discord.Interaction):
        if not await check_channel(interaction, KISS_MARRY_KILL_CHANNEL_ID):
            return await interaction.response.send_message(
                f"Ova komanda se može koristiti samo u odgovarajućem kanalu!", 
                ephemeral=True
            )

        members = [m for m in interaction.guild.members if not m.bot and m != interaction.user]
        if len(members) < 3:
            await interaction.response.send_message("Nema dovoljno korisnika za igru.", ephemeral=True)
            return

        selected = random.sample(members, 3)
        session = GameSession(interaction.user, selected)
        self.sessions[interaction.user.id] = session

        description = "\n".join([f"{i+1}. {selected[i].mention} ({selected[i].display_name})" for i in range(3)])

        embed = discord.Embed(
            title="💋💍🔪 Kiss Marry Kill",
            description=description,
            color=discord.Color.orange()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar.url)
        embed.set_footer(text="Želiš i ti koristiti komandu? Upiši /kissmarrykill")

        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        await message.edit(view=ActionView(session, message))

# --- Ship Cog ---
class ShipCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def download_image(self, url):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return Image.open(BytesIO(response.content)).convert("RGBA")
        except Exception as e:
            print(f"Error downloading image: {e}")
            response = requests.get("https://cdn.discordapp.com/embed/avatars/0.png")
            return Image.open(BytesIO(response.content)).convert("RGBA")

    def generate_ship_image(self, user1_avatar, user2_avatar, percentage):
        try:
            bg = Image.open(BytesIO(requests.get(SHIP_BACKGROUND_URL).content)).convert("RGBA")
            bg = bg.resize((800, 400))
        except:
            bg = Image.new('RGBA', (800, 400), (54, 57, 63, 255))
        
        avatar_size = 200
        def process_avatar(avatar):
            avatar = avatar.resize((avatar_size, avatar_size))
            mask = Image.new('L', (avatar_size, avatar_size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
            result = Image.new('RGBA', (avatar_size, avatar_size))
            result.paste(avatar, (0, 0), mask)
            return result
        
        user1_avatar = process_avatar(user1_avatar)
        user2_avatar = process_avatar(user2_avatar)
        
        bg.paste(user1_avatar, (50, 100), user1_avatar)
        bg.paste(user2_avatar, (550, 100), user2_avatar)
        
        draw = ImageDraw.Draw(bg)
        try:
            font = ImageFont.truetype("arial.ttf", 80)
        except:
            font = ImageFont.load_default(size=80)
        
        text = f"{percentage}%"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (800 - text_width) // 2
        y = (400 - text_height) // 2
        
        outline_width = 5
        for adj in range(-outline_width, outline_width + 1):
            for adj2 in range(-outline_width, outline_width + 1):
                if adj != 0 or adj2 != 0:
                    draw.text((x + adj, y + adj2), text, fill="black", font=font)
        
        draw.text((x, y), text, fill="white", font=font)
        
        return bg

    @app_commands.command(name="ship", description="Shipuj sebe sa odredjenom osobom ili random!🦊")
    @app_commands.describe(user="Ako zelis random ship ostavis samo polje prazno")
    async def ship(self, interaction: discord.Interaction, user: discord.Member = None):
        if not await check_channel(interaction, SHIP_CHANNEL_ID):
            return await interaction.response.send_message(
                f"Ova komanda se može koristiti samo u odgovarajućem kanalu!", 
                ephemeral=True
            )

        await interaction.response.defer()
        
        if user is None:
            try:
                members = [m for m in interaction.guild.members 
                          if not m.bot and m != interaction.user]
                if not members:
                    return await interaction.followup.send("Ne mogu pronaci nijednu odredjenu osobu")
                user = random.choice(members)
            except Exception as e:
                print(f"Error finding random user: {e}")
                return await interaction.followup.send("🚫 Ne mogu naci random osobu ili trazenu pokusaj ponovo")
        
        if user.bot:
            return await interaction.followup.send("Ne mozes shipovati bota jesi retardiran?")
        
        if user.id == interaction.user.id:
            return await interaction.followup.send("Nemoj biti sam shipuj nekog drugog")
        
        base_percentage = random.randint(0, 100)
        percentage = max(0, min(100, base_percentage + random.randint(-15, 15)))
        
        try:
            user1_avatar = await self.download_image(interaction.user.display_avatar.url)
            user2_avatar = await self.download_image(user.display_avatar.url)
            
            ship_image = self.generate_ship_image(user1_avatar, user2_avatar, percentage)
            
            with BytesIO() as buffer:
                ship_image.save(buffer, 'PNG')
                buffer.seek(0)
                file = discord.File(buffer, filename='ship.png')
                
                user1_name = interaction.user.display_name
                user2_name = user.display_name
                
                embed = discord.Embed(
                    title=f"💘 {user1_name} × {user2_name}",
                    color=discord.Color.from_rgb(255, 105, 180)
                )
                embed.set_image(url="attachment://ship.png")
                
                if percentage >= 90:
                    message = "Ma sudjeno vam je 💞"
                elif percentage >= 70:
                    message = "Ma gorite od ljubavi 💖"
                elif percentage >= 50:
                    message = "Zamalo 💕"
                elif percentage >= 30:
                    message = "Odustanite bolje vam je 💝"
                else:
                    message = "Jebes ljubav 💔"
                
                embed.description = f"**Šanse:** {percentage}%\n{message}"
                embed.set_footer(text=f" {user1_name}")
                
                await interaction.followup.send(embed=embed, file=file)
        
        except Exception as e:
            print(f"Shipping error: {e}")
            await interaction.followup.send("🚫 Failed to generate ship image. Please try again later!")

# --- Welcome Cog ---
class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def create_welcome_image(self, member_avatar_url, member_name):
        async with aiohttp.ClientSession() as session:
            async with session.get(member_avatar_url) as resp:
                if resp.status != 200:
                    return None
                avatar_data = await resp.read()

            async with session.get(WELCOME_BACKGROUND_URL) as resp:
                if resp.status != 200:
                    return None
                background_data = await resp.read()

        avatar = Image.open(BytesIO(avatar_data)).convert("RGBA")
        background = Image.open(BytesIO(background_data)).convert("RGBA")

        avatar_size = 140
        avatar = avatar.resize((avatar_size, avatar_size))

        border_thickness = 4
        border_color = (255, 165, 0)

        mask = Image.new('L', (avatar_size, avatar_size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)

        avatar_with_border = Image.new('RGBA',
                                       (avatar_size + border_thickness*2, avatar_size + border_thickness*2),
                                       (0, 0, 0, 0))
        draw = ImageDraw.Draw(avatar_with_border)
        draw.ellipse((0, 0,
                      avatar_size + border_thickness*2,
                      avatar_size + border_thickness*2),
                     fill=border_color)
        draw.ellipse((border_thickness, border_thickness,
                      avatar_size + border_thickness,
                      avatar_size + border_thickness),
                     fill=(0, 0, 0, 0))
        avatar_with_border.paste(avatar, (border_thickness, border_thickness), mask)

        position = (
            (background.width - (avatar_size + border_thickness*2)) // 2,
            (background.height - (avatar_size + border_thickness*2)) // 3
        )

        background.paste(avatar_with_border, position, avatar_with_border)

        draw = ImageDraw.Draw(background)
        try:
            font_path = "SpecialGothic-ExpandedOne.ttf"
            name_font = ImageFont.truetype(font_path, 30)
            welcome_font = ImageFont.truetype(font_path, 10)
        except:
            name_font = ImageFont.load_default()
            welcome_font = ImageFont.load_default()

        name_half = len(member_name) // 2
        first_half = member_name[:name_half]
        second_half = member_name[name_half:]

        full_text_width = draw.textlength(member_name, font=name_font)
        first_half_width = draw.textlength(first_half, font=name_font)

        text_x = (background.width - full_text_width) // 2
        text_y = position[1] + avatar_size + 5

        draw.text((text_x, text_y), first_half, font=name_font, fill=(255, 165, 0))
        draw.text((text_x + first_half_width, text_y), second_half, font=name_font, fill=(255, 255, 255))

        welcome_text = "-Dobrodosao/la-"
        welcome_width = draw.textlength(welcome_text, font=welcome_font)
        welcome_x = (background.width - welcome_width) // 2
        welcome_y = text_y + 30

        draw.text((welcome_x, welcome_y), welcome_text, font=welcome_font, fill=(255, 255, 255))

        final_image = BytesIO()
        background.save(final_image, format='PNG')
        final_image.seek(0)

        return final_image

    @commands.Cog.listener()
    async def on_member_join(self, member):
        welcome_channel = self.bot.get_channel(WELCOME_CHANNEL_ID)
        if not welcome_channel:
            print("Welcome channel not found!")
            return

        try:
            welcome_image = await self.create_welcome_image(member.display_avatar.url, member.display_name)

            if welcome_image:
                embed = discord.Embed(
                    title="Dobrodosao/la na server!",
                    description="Pogledaj nase igre, imamo gomilu unikatnih igara koje mozes igrati s prijateljima! Nadam se da ces se zabaviti. Uzivaj! ❤️🦊",
                    color=discord.Color.orange()
                )

                file = discord.File(welcome_image, filename="welcome.png")
                embed.set_image(url="attachment://welcome.png")
                await welcome_channel.send(file=file, embed=embed)

            welcome_role = member.guild.get_role(WELCOME_ROLE_ID)
            if welcome_role:
                await member.add_roles(welcome_role)

        except Exception as e:
            print(f"Error in welcome system: {e}")

# Bot setup
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.add_cog(DalibiCog(bot))
    await bot.add_cog(KaladontCog(bot))
    await bot.add_cog(KissMarryKillCog(bot))
    await bot.add_cog(ShipCog(bot))
    await bot.add_cog(WelcomeCog(bot))
    await bot.tree.sync()
    print("Bot is ready!")

bot.run(TOKEN)

