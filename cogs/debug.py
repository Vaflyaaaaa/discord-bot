import disnake
from disnake.ext import commands
import time
import config
from loguru import logger
import json
import datetime
import os
import aiofiles


user_data_file = 'data/user_data.json'


def load_user_data():
    try:
        with open(user_data_file, 'r') as f:
            data = json.load(f)

            for guild_id, user_data in data.items():
                for user_id, user_info in user_data.items():
                    if 'last_bonus' in user_info and user_info['last_bonus']:
                        user_info['last_bonus'] = datetime.datetime.fromisoformat(user_info['last_bonus'])
            logger.info("Данные пользователей успешно загружены")
            return data
    except FileNotFoundError:
        logger.warning("Файл с данными пользователей не найден. Будет создан новый файл.")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка декодирования JSON: {e}")
        return {}


user_data = load_user_data()


def save_user_data(data):
    for guild_id, user_data in data.items():
        for user_id, user_info in user_data.items():
            if 'last_bonus' in user_info:
                if isinstance(user_info['last_bonus'], datetime.datetime):
                    user_info['last_bonus'] = user_info['last_bonus'].isoformat()

    with open(user_data_file, 'w') as f:
        json.dump(data, f, indent=4)
    logger.info("Данные пользователей сохранены")


class Debug(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()
        self.all_modules = [
            "cogs.debug",
            "cogs.etc",
            "cogs.logging",
            "cogs.moderation",
            "cogs.music",
            "cogs.tickets",
            "cogs.user"
        ]
        self.user_levels = {}

    async def cog_load(self):
        await self.load_levels()
        
    async def load_levels(self):
        try:
            async with aiofiles.open('data/user_levels.json', 'r', encoding='utf-8') as f:
                content = await f.read()
                self.user_levels = json.loads(content)
        except Exception:
            self.user_levels = {}

    def save_levels(self):
        with open(os.path.join(os.getcwd(), "data/user_levels.json"), "w", encoding="utf-8") as f:
            json.dump(self.user_levels, f, indent=4)

    @commands.command(name="modules")
    @commands.is_owner()
    async def modules(self, ctx, module_name: str = None, action: str = None):
        if not module_name:
            embed = disnake.Embed(
                title="Ошибка!",
                description="Укажите модуль, с которым хотите взаимодействовать.",
                color=disnake.Color.red()
                )
            embed.set_footer(text=f"{config.BOT_VERSION}")
            await ctx.send(embed=embed)
            return

        module_name = module_name.lower()
        if action is None:
            embed = disnake.Embed(
                title="Ошибка!",
                description="Пожалуйста, укажи действие: `on` или `off`",
                color=disnake.Color.red()
                )
            embed.set_footer(text=f"{config.BOT_VERSION}")
            await ctx.send(embed=embed)
            return

        action = action.lower()
        full_module_name = None

        for mod in self.all_modules:
            if mod.endswith(module_name):
                full_module_name = mod
                break

        if full_module_name is None:
            embed = disnake.Embed(
                title="Ошибка!",
                description=f"Модуль `{module_name}` не найден в списке известных модулей.",
                color=disnake.Color.red()
                )
            embed.set_footer(text=f"{config.BOT_VERSION}")
            await ctx.send(embed=embed)
            return

        if action == "on":
            if full_module_name in self.bot.extensions:
                embed = disnake.Embed(
                    title="Ошибка!",
                    description=f"Модуль `{module_name}` уже загружен.",
                    color=disnake.Color.red()
                    )
                embed.set_footer(text=f"{config.BOT_VERSION}")
                await ctx.send(embed=embed)
                return
            try:
                self.bot.load_extension(full_module_name)
                embed = disnake.Embed(
                    title="Отладка",
                    description=f"Модуль `{module_name}` успешно загружен."
                    )
                embed.set_footer(text=f"{config.BOT_VERSION}")
                await ctx.send(embed=embed)
            except Exception as e:
                embed = disnake.Embed(
                    title="Ошибка!",
                    description=f"Ошибка при загрузке модуля `{module_name}`:\n```{e}```",
                    color=disnake.Color.red()
                    )
                embed.set_footer(text=f"{config.BOT_VERSION}")
                await ctx.send(embed=embed)

        elif action == "off":
            if full_module_name not in self.bot.extensions:
                embed = disnake.Embed(
                    title="Ошибка!",
                    description=f"Модуль `{module_name}` уже отключён.",
                    color=disnake.Color.red()
                    )
                embed.set_footer(text=f"{config.BOT_VERSION}")
                await ctx.send(embed=embed)
                return
            try:
                self.bot.unload_extension(full_module_name)
                embed = disnake.Embed(
                    title="Отладка",
                    description=f"Модуль `{module_name}` успешно выгружен."
                    )
                embed.set_footer(text=f"{config.BOT_VERSION}")
                await ctx.send(embed=embed)
            except Exception as e:
                embed = disnake.Embed(
                    title="Ошибка!",
                    description=f"Ошибка при загрузке модуля `{module_name}`:\n```{e}```",
                    color=disnake.Color.red()
                    )
                embed.set_footer(text=f"{config.BOT_VERSION}")
                await ctx.send(embed=embed)
        else:
            embed = disnake.Embed(
                    title="Ошибка!",
                    description="Действие должно быть `on` либо `off`.",
                    color=disnake.Color.red()
                    )
            embed.set_footer(text=f"{config.BOT_VERSION}")
            await ctx.send(embed=embed)


    @commands.command(name="indata")
    @commands.is_owner()
    async def indata(self, ctx, member: disnake.Member):
        guild_id = str(member.guild.id)
        member_id = str(member.id)

        if guild_id not in user_data:
            user_data[guild_id] = {}

        if member_id not in user_data[guild_id]:
            user_data[guild_id][member_id] = {'balance': 0, 'last_bonus': None}
            save_user_data(user_data)

            embed = disnake.Embed(
                title="Отладка",
                description=f"Пользователь {member.mention} был добавлен в базу данных"
                )
            embed.set_footer(text=f"{config.BOT_VERSION}")
            await ctx.send(embed=embed)
        else:
            embed = disnake.Embed(
                title="Ошибка!",
                description=f"Пользователь {member.mention} уже находится в базе данных",
                color=disnake.Color.red()
                )
            embed.set_footer(text=f"{config.BOT_VERSION}")
            await ctx.send(embed=embed)
        
    
    @commands.command(name="setcoins")
    @commands.is_owner()
    async def setcoins(self, ctx, member: disnake.Member, coins: int):
        guild_id = str(member.guild.id)
        member_id = member.id

        if guild_id not in user_data:
            user_data[guild_id] = {}

        if member_id not in user_data[guild_id]:
            user_data[guild_id][member_id] = {'balance': 0, 'last_bonus': None}

        user_data[guild_id][member_id]['balance'] = coins
        save_user_data(user_data)
        
        embed = disnake.Embed(
            title="Отладка",
            description=f"Баланс пользователя {member} был изменён"
            )
        embed.set_footer(text=f"{config.BOT_VERSION}")
        await ctx.send(embed=embed)


    @commands.command(name="приказ")
    async def приказ(self, ctx, num: int, channel_id: int):
        server_id = str(ctx.guild.id)
        user_level = self.user_levels.get(server_id, {}).get(str(ctx.author.id), 0)

        if user_level < 2:
            await ctx.send("У вас нет прав для выполнения этой команды.")
            return

        if num != 66:
            await ctx.send("Неверный номер приказа. Используйте 66.")
            return
        
        channel = ctx.guild.get_channel(channel_id)
        if channel and isinstance(channel, disnake.VoiceChannel):
            for member in channel.members:
                try:
                    await member.move_to(None, reason="Команда 66: отключение от голосового")
                except Exception as e:
                    await ctx.send(f"Не удалось кикнуть {member.name}: {e}")
        else:
            await ctx.send("Указанный канал не найден или не является голосовым.")


    @commands.command(name="debug")
    @commands.is_owner()
    async def debug(self, ctx, debug_type: str):
        debug_type = debug_type.lower()
        embed = disnake.Embed(color=disnake.Color.blue())
        uptime = time.time() - self.start_time
        
        if debug_type == "stats":
            embed = disnake.Embed(
                title = "Информация о боте",
                description = (
                    f"Количество серверов: {len(self.bot.guilds)}\n"
                    f"Состояние бота: {self.bot.status}\n"
                    f"Задержка: {round(self.bot.latency * 1000)} ms\n"
                    f"Время работы: {self.format_uptime(uptime)}\n"
                ))
            embed.set_footer(text=f"{config.BOT_VERSION}")
        
        elif debug_type == "guild_info":
            embed = disnake.Embed(
                title = "Информация о сервере",
                description = (
                    f"Название: {ctx.guild.name}\n"
                    f"Количество членов: {ctx.guild.member_count}\n"
                    f"Создан: {ctx.guild.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
                ))
            embed.set_footer(text=f"{config.BOT_VERSION}")
            
        elif debug_type == "modules":
            embed.title = f"{config.BOT_VERSION}"
            description_lines = []
            for mod in self.all_modules:
                short_name = mod.split('.')[-1]
                status = "Включен ✅" if mod in self.bot.extensions else "Выключен ❌"
                description_lines.append(f"{short_name}: {status}")
            embed.description = f"Список модулей бота: {len(description_lines)}\n" + "```" + "\n\n".join(description_lines) + "```"
            embed.set_footer(text="Статус модулей — включен/выключен")
        else:
            embed = disnake.Embed(
                title = "Ошибка!",
                description = "Такого типа не существует. Возможно опечатка, попробуйте снова.",
                color= disnake.Color.red()
                )
            embed.set_footer(text=f"{config.BOT_VERSION}")
        await ctx.send(embed=embed)


    def format_uptime(self, uptime):
        hours, remainder = divmod(int(uptime), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}ч {minutes}м {seconds}с"
    
def setup(bot):
    bot.add_cog(Debug(bot))