import discord # type: ignore
from discord.ext import commands, tasks # type: ignore
import uuid
import os
from datetime import datetime, timedelta
import aiohttp # type: ignore

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='.', intents=intents, help_command=None)

yourrole = '| Client'
txt = 'data.txt'
blacklist_ids = []  # Leeg laten om te beginnen met een lege blacklist
lookup_channel = 1234567891011121314  # Vervang dit met het ID van je lookup kanaal

key_durations = {
    'dag': timedelta(days=1),
    'week': timedelta(days=7),
    'maand': timedelta(days=30),
    'lifetime': None
}

key_creators = {}  # Dictionary om Key Creators op te slaan
fixed_number = 0  # Vaste nummer voor .db command

def has_role_check(ctx):
    role = discord.utils.get(ctx.guild.roles, name=yourrole)
    return role in ctx.author.roles

def is_lookup_channel(ctx):
    return ctx.channel.id == lookup_channel

@commands.check(has_role_check)
async def role_check(ctx):
    return has_role_check(ctx)

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name=".find"))
    print("Bot is online and ready")
    check_expired_roles.start()

@bot.command()
@commands.has_permissions(administrator=True)
async def gen(ctx, amount: int, duration: str):
    if duration not in key_durations:
        await ctx.send("Ongeldige duur! Gebruik 'dag', 'week', 'maand' of 'lifetime'.")
        return
    
    keys = [f"{str(uuid.uuid4())}_{duration}" for _ in range(amount)]

    with open("keys.txt", "a") as f:
        for key in keys:
            f.write(key + "\n")
            key_creators[key] = ctx.author.name  # Opslaan van Key Creator

    show_key = "\n".join(keys)
    await ctx.send(f"Keys:\n{show_key}")

@bot.command()
async def redeem(ctx, key):
    if not any(key.endswith(f"_{k}") for k in key_durations.keys()):
        em = discord.Embed(color=0xff0000, description="Deze key is niet geldig of al gebruikt")
        await ctx.send(embed=em)
        return

    # Controleer of de gebruiker op de blacklist staat
    if str(ctx.author.id) in blacklist_ids:
        await ctx.send("Je staat op de blacklist en kunt geen keys inwisselen.")
        return

    # Controleer of de gebruiker al de | Client rol heeft
    role = discord.utils.get(ctx.guild.roles, name=yourrole)
    if role in ctx.author.roles:
        em = discord.Embed(color=0xff0000, description="Je hebt al de Client rol en kunt geen nieuwe key claimen.")
        await ctx.send(embed=em)
        return

    with open("used_keys.txt", "r") as f:
        if key in f.read():
            em = discord.Embed(color=0xff0000, description="Deze key is niet geldig of al gebruikt")
            await ctx.send(embed=em)
            return

    with open("keys.txt", "r") as f:
        if key in f.read():
            duration = key.split('_')[-1]
            await ctx.author.add_roles(role)
            em = discord.Embed(color=0xe37300, description="De key is succesvol ingewisseld")
            await ctx.send(embed=em)

            with open("used_keys.txt", "a") as uf:
                uf.write(key + '\n')

            if key_durations[duration] is not None:
                expiry_date = datetime.utcnow() + key_durations[duration]
                with open("role_expiry.txt", "a") as ef:
                    ef.write(f"{ctx.author.id},{expiry_date.isoformat()}\n")

            # Verstuur informatie naar webhook met de naam van de Key Creator
            await send_webhook_info(ctx.author, key)

        else:
            em = discord.Embed(color=0xff0000, description="Deze key is niet geldig of al gebruikt!")
            await ctx.send(embed=em)

async def countt():
    count = 0
    try:
        with open(txt, 'r', encoding='utf-8', errors='replace') as file:
            lines = [line.replace('\x00', '.') for line in file if line.strip()]
            count = len(lines)
    except Exception as e:
        print(f"Error reading file: {e}")
    return count

async def lookup(query):
    found = []
    if os.path.exists(txt):
        try:
            with open(txt, 'r', encoding='utf-8', errors='replace') as file:
                lines = file.readlines()
                for line in lines:
                    if query in line and not any(nig in line for nig in blacklist_ids):
                        found.append(line.strip())
        except Exception as e:
            print(f"Error reading file: {e}")
    return found

async def send_webhook_info(member, key):
    webhook_url = ''  # Vervang dit met je eigen webhook URL
    if webhook_url:
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        amsterdam_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Vervang door correcte tijdzone

        embed = {
            'embeds': [
                {
                    'title': 'Gebruiker Redeemed Key',
                    'color': 15105570,
                    'fields': [
                        {'name': 'Discord', 'value': str(member), 'inline': True},
                        {'name': 'Naam', 'value': member.name, 'inline': True},
                        {'name': 'ID', 'value': str(member.id), 'inline': True},
                        {'name': 'Key Creator', 'value': key_creators.get(key, 'Onbekend'), 'inline': True},  # Naam van Key Creator toegevoegd
                        {'name': 'Datum', 'value': current_time, 'inline': True},
                    ],
                    'footer': {
                        'text': f'Uitgevoerd door: {member.id}'  # Gebruik de ID van de gebruiker in de footer
                    }
                }
            ]
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=embed) as response:
                if response.status != 204:
                    print(f"Failed to send webhook: {response.status}")

@bot.command(name='find')
@commands.check(has_role_check)
async def find(ctx, *, query: str):
    if any(nig in query for nig in blacklist_ids):
        await ctx.send("Deze persoon is geblacklist")
        return
    
    if not is_lookup_channel(ctx):
        await ctx.send("In dit kanaal kan de command niet worden uitgevoerd. Probeer het in het lookup kanaal.")
        return
    
    results = await lookup(query)
    if results:
        for result in results:
            embed = discord.Embed(title="Result", description=f"```{result}```", color=0xe37300)
            embed.set_footer(text=f"discord.gg/limelookup > {ctx.author}")
            embed.set_thumbnail(url="CHANGE HERE") # VERANDER HIER EEN FOTO DIE JIJ WILT NAAST DE COMMAND
            await ctx.send(embed=embed)
    else:
        await ctx.send("Persoon zit niet in de database")

@find.error
async def find_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("Je bent nog niet bevoegd om deze command te gebruiken.")
    elif isinstance(error, commands.CheckFailure):
        await ctx.send(f"Je moet de rol '{yourrole}' hebben om deze command te gebruiken.")

@bot.command(name='lines')
async def count(ctx):
    lines = await countt()
    embed = discord.Embed(title="Lines Count", description=f"```{lines}```", color=0xe37300)
    embed.set_footer(text="By discord.gg/limelookup")
    embed.set_thumbnail(url="CHANGE HERE") # VERANDER HIER EEN FOTO DIE JIJ WILT NAAST DE COMMAND
    await ctx.send(embed=embed)

@bot.command(name='db')
async def db(ctx):
    embed = discord.Embed(
        title="Database Count",
        description=f"```{fixed_number}```",
        color=0xe37300
    )
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def blacklist(ctx, user_id: str):
    if user_id not in blacklist_ids:
        blacklist_ids.append(user_id)
        # Optioneel: Update de blacklist naar een tekstbestand
        with open("blacklist.txt", "a") as f:
            f.write(user_id + "\n")
        await ctx.send(f"<@{user_id}> is toegevoegd aan de blacklist.")
    else:
        await ctx.send(f"<@{user_id}> staat al in de blacklist.")

@bot.command()
@commands.has_permissions(administrator=True)
async def unblacklist(ctx, user_id: str):
    if user_id in blacklist_ids:
        blacklist_ids.remove(user_id)
        # Optioneel: Update de blacklist naar een tekstbestand
        with open("blacklist.txt", "w") as f:
            for id in blacklist_ids:
                f.write(id + "\n")
        await ctx.send(f"<@{user_id}> is verwijderd uit de blacklist.")
    else:
        await ctx.send(f"<@{user_id}> staat niet in de blacklist.")

@tasks.loop(minutes=1)
async def check_expired_roles():
    if not os.path.exists("role_expiry.txt"):
        return

    with open("role_expiry.txt", "r") as f:
        lines = f.readlines()

    with open("role_expiry.txt", "w") as f:
        for line in lines:
            user_id, expiry_date = line.strip().split(',')
            expiry_date = datetime.fromisoformat(expiry_date)

            if datetime.utcnow() >= expiry_date:
                guild = discord.utils.get(bot.guilds, name="Lime")  # Vervang met je guild naam
                member = guild.get_member(int(user_id))
                if member:
                    role = discord.utils.get(guild.roles, name=yourrole)
                    await member.remove_roles(role)
            else:
                f.write(line)

@bot.command(name='help')
async def custom_help(ctx):
    embed = discord.Embed(
        title="Help",
        description=(
            "Lijst van beschikbare commando's\n"
            "**.gen <aantal> <tijdsduur>** - `` Maak een key aan ``.\n"
            "**.redeem <key>** - `` Wissel een key in voor toegang. ``\n"
            "**.find <query>** - `` Zoek naar ip `` .\n"
            "**.blacklist <user_id>** - `` Voeg een gebruiker toe aan de blacklist `` .\n"
            "**.unblacklist <user_id>** - `` Verwijder een gebruiker van de blacklist `` .\n"
            "**.db** - `` Geeft het aantal records in de database `` .\n"
        ),
        color=0xe37300
    )
    embed.set_footer(text="By discord.gg/limelookup")
    await ctx.send(embed=embed)

bot.run('BOT TOKEN HERE')
