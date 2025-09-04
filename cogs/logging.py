import disnake
from disnake.ext import commands
import datetime
import config
from datetime import datetime, timezone
from disnake.utils import utcnow

class LoggerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    async def log(self, message: str):
        channel = self.bot.get_channel(config.LOG_CHANNEL_ID)
        if channel:
            now = datetime.utcnow()
            formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
            mes = f"`{formatted_time}` | {message}"
            await channel.send(mes)
        else:
            print("Лог-канал не найден!")


    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot:
            return
        text = f"🗑 Пользователь {message.author} (ID: {message.author.id}) удалил сообщение: {message.content}"
        await self.log(text)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot:
            return
        
        if before.content == after.content:
            return
        
        text = (f"✏️ Пользователь {before.author} (ID: {before.author.id}) отредактировал сообщение в {before.channel.mention}:\n"
                f"До:\n" f"> {before.content}" + f"\nПосле:\n" f"> {after.content}")
        await self.log(text)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        text = f"🤝 Пользователь {member} (ID: {member.id}) присоединился к серверу"
        await self.log(text)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        text = f"👋 Пользователь {member} (ID: {member.id}) покинул сервер"
        await self.log(text)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.bot:
            return
        
        changes = []
        if before.nick != after.nick:
            changes.append(f"Смена никнейма с '{before.nick}' на '{after.nick}'")

        if before.roles != after.roles:
            removed = set(before.roles) - set(after.roles)
            added = set(after.roles) - set(before.roles)
            if removed:
                changes.append("> Была удалена роль: " + ", ".join(r.name for r in removed))
            if added:
                changes.append("> Была добавлена роль: " + ", ".join(r.name for r in added))
        if changes:
            text = f"⚙️ Данные пользователя {after} (ID: {after.id}) были обновлены:\n{', '.join(changes)}"
            await self.log(text)
    
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        text = f"📥 Создан канал {channel.name} ({channel.mention})"
        await self.log(text)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        text = f"📤 Удалён канал {channel.name}"
        await self.log(text)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return

        guild = member.guild
        event_time = disnake.utils.utcnow()

        mute_changed = (before.mute != after.mute) or (before.self_mute != after.self_mute)
        deaf_changed = (before.deaf != after.deaf) or (before.self_deaf != after.self_deaf)

        admin_user = None
        async for entry in guild.audit_logs(limit=20, action=disnake.AuditLogAction.member_update):
            if entry.target.id != member.id:
                continue

            changes = entry.changes
            before_attrs = changes.before
            after_attrs = changes.after

            mute_change = False
            deaf_change = False
            voice_state_change = False

            if before_attrs and after_attrs:
                if hasattr(before_attrs, 'mute') and hasattr(after_attrs, 'mute'):
                    mute_change = before_attrs.mute != after_attrs.mute
                if hasattr(before_attrs, 'deaf') and hasattr(after_attrs, 'deaf'):
                    deaf_change = before_attrs.deaf != after_attrs.deaf
                if hasattr(before_attrs, 'channel') and hasattr(after_attrs, 'channel'):
                    voice_state_change = before_attrs.channel != after_attrs.channel

            time_diff = abs((event_time - entry.created_at).total_seconds())
            if (mute_change or deaf_change or voice_state_change) and time_diff < 10:
                admin_user = entry.user
                break

        changes_list = []
        if mute_changed:
            if before.self_mute != after.self_mute:
                changes_list.append("локально отключил микрофон" if after.self_mute else "локально включил микрофон")
            elif before.mute != after.mute:
                changes_list.append("админ отключил микрофон" if after.mute else "админ включил микрофон")

        if deaf_changed:
            if before.self_deaf != after.self_deaf:
                changes_list.append("локально отключил звук на наушниках" if after.self_deaf else "локально включил звук на наушниках")
            elif before.deaf != after.deaf:
                changes_list.append("админ отключил звук на наушниках" if after.deaf else "админ включил звук на наушниках")

        if before.channel != after.channel:
            if before.channel is None and after.channel is not None:
                text = f"🎙 Пользователь {member} (ID: {member.id}) подключился к каналу {after.channel.name}"
                await self.log(text)

            elif before.channel is not None and after.channel is None:
                if admin_user:
                    text = (f"🎙 Администратор {admin_user} (ID: {admin_user.id}) кикнул "
                            f"пользователя {member} (ID: {member.id}) из канала {before.channel.name}")
                else:
                    text = f"🎙 Пользователь {member} (ID: {member.id}) вышел из канала {before.channel.name}"
                await self.log(text)

            else:
                if admin_user:
                    text = (f"🎙 Администратор {admin_user} (ID: {admin_user.id}) перекинул пользователя "
                            f"{member} (ID: {member.id}) из канала {before.channel.name} в канал {after.channel.name}")
                else:
                    text = (f"🎙 Пользователь {member} (ID: {member.id}) переместился из канала "
                            f"{before.channel.name} в канал {after.channel.name}")
                await self.log(text)

        if changes_list:
            if admin_user:
                text = (f"🎙 Администратор {admin_user} (ID: {admin_user.id}) изменил голосовой статус пользователя "
                        f"{member} (ID: {member.id}) : {', '.join(changes_list)}")
            else:
                text = (f"🎙 Пользователь {member} (ID: {member.id}) изменил свой голосовой статус: {', '.join(changes_list)}")

            await self.log(text)


def setup(bot):
    bot.add_cog(LoggerCog(bot))