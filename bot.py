import disnake
from disnake.ext import commands, tasks
import os
from loguru import logger
import random
import config

logger.add("log/logging.log", rotation="80 MB")

class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_levels = {}

intents = disnake.Intents.default()
intents.members = True
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.presences = True

bot = MyBot(command_prefix='!', intents=intents)

for filename in os.listdir("cogs"):
    if filename.endswith(".py"):
        bot.load_extension(f"cogs.{filename[:-3]}")


@bot.event
async def on_ready():
    await bot.change_presence(activity=disnake.Activity(type= disnake.ActivityType.watching, name="Файлы логов",))
    logger.info(f'Бот {bot.user} подключен к Discord!')


last_pinged_user = None

@tasks.loop(seconds=900)
async def reset_ping():
    global last_pinged_user
    last_pinged_user = None

@bot.event
async def on_message(message):
    global last_pinged_user

    if message.author.bot:
        return

    if '@here' in message.content or '@everyone' in message.content:
        return

    if bot.user.mentioned_in(message) and not any(role.mentionable for role in message.role_mentions):
        if not reset_ping.is_running():
            reset_ping.start()  

        if message.reference and message.reference.resolved.author == bot.user:
            return

        if message.author.id == last_pinged_user:
            await message.channel.send("Да чё тебе от меня надо? /info напиши уже и не пингуй меня, бездарь")
        else: 
            phrases = ["Чо нада?", "Чо хотел?"]
            random_phrase = random.choice(phrases)
            await message.channel.send(random_phrase)

        last_pinged_user = message.author.id 

    await bot.process_commands(message)

reset_ping.start()

bot.run(config.TOKEN_BOT)