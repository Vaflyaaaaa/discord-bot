import disnake
from disnake.ext import commands
import os
from loguru import logger
import asyncio
import json
import config

if not os.path.exists('data'):
    os.makedirs('data')

tdata_path = 'data/tickets.json'

if os.path.exists(tdata_path):
    with open(tdata_path, 'r') as f:
        ticket_data = json.load(f)
else:
    ticket_data = {'ticket_counter': 0, 'ticket_channels': {}}

def save_ticket_data():
    with open(tdata_path, 'w') as f:
        json.dump(ticket_data, f, indent=4, ensure_ascii=False)

class TicketView(disnake.ui.View):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @disnake.ui.button(label='Создать тикет', style=disnake.ButtonStyle.primary)
    async def create_ticket(self, button: disnake.ui.Button, interaction: disnake.Interaction):
        global ticket_data
        ticket_data['ticket_counter'] += 1
        ticket_id = ticket_data['ticket_counter']

        channel_name = f'ticket-{ticket_id}'
        guild = interaction.guild
        category = disnake.utils.get(guild.categories, name='Tickets')
        channel = await guild.create_text_channel(channel_name, category=category)

        ticket_data['ticket_channels'][str(channel.id)] = ticket_id
        
        save_ticket_data()
        await interaction.response.send_message(f'Ваш тикет {channel.mention} создан.', ephemeral=True)

        dev_mention = f"<@{config.DEVELOPER_ID}>"
        embed = disnake.Embed(
            title="Тикет был успешно создан",
            description="Напишите свой вопрос/улучшение и ожидайте ответ разработчика",
            color=disnake.Color.green()
        )

        try:
            await channel.send(content=dev_mention, embed=embed)
        except Exception as e:
            logger.error(f"Ошибка при отправке эмбеда в канал тикета: {e}")

        await self.schedule_ticket_deletion(channel)

        with open(tdata_path, 'w') as f:
            json.dump(ticket_data, f)

    async def schedule_ticket_deletion(self, channel):
        await asyncio.sleep(86400)
        await channel.delete()
        ticket_data['ticket_channels'].pop(str(channel.id), None)
        with open(tdata_path, 'w') as f:
            json.dump(ticket_data, f)
        logger.info(f"Тикет был удалён")


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        guild = self.bot.get_guild(config.GUILD_ID)
        channel = guild.get_channel(config.TICKET_CHANNEL_ID)
        embed = disnake.Embed(title='Обращение к разработчику', description='Чтобы подать обращение, нажмите кнопку ниже.')
        view = TicketView(self.bot)
        if channel:
            try:
                await channel.send(embed=embed, view=view)
                logger.info(f"Эмбед создания тикета успешно отправлен")
            except disnake.Forbidden:
                logger.error(f"Ошибка: Недостаточно прав для отправки сообщения в канал {channel.name}.")
        else:
            logger.error("Ошибка: Канал не найден.")

def setup(bot):
    bot.add_cog(Tickets(bot))
