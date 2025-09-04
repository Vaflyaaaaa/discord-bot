import disnake
from disnake.ext import commands
from disnake import FFmpegPCMAudio, ui, ButtonStyle
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import yt_dlp
import asyncio
import datetime
from loguru import logger
from dotenv import load_dotenv
import config


class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.current_embeds = {}
        self.play_lock = asyncio.Lock()
        self.replay_states = {}
        self.current_tracks = {}
        
        load_dotenv()
        
        self.sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
            client_id=config.SPOTIFY_CLIENT_ID,
            client_secret=config.SPOTIFY_CLIENT_SECRET
        ))
        
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0',
            'extractor_args': {
                'youtube': {
                    'player_client': ['android_embedded'],
                    'skip': ['dash', 'hls']
                }
            }
        }
        
        self.ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin',
            'options': '-vn -b:a 128k -threads 1'
        }
    
    class MusicButton(ui.Button):
        def __init__(self, callback_func, **kwargs):
            super().__init__(**kwargs)
            self.callback_func = callback_func

        async def callback(self, interaction: disnake.MessageInteraction):
            try:
                await self.callback_func(interaction)
            except Exception as e:
                logger.error(f"Button error: {e}")
                try:
                    await interaction.response.send_message(
                        "⚠️ Произошла ошибка при обработке запроса",
                        ephemeral=True
                    )
                except disnake.InteractionResponded:
                    await interaction.followup.send(
                        "⚠️ Произошла ошибка при обработке запроса",
                        ephemeral=True
                    )
    
    class MusicControls(ui.View):
        def __init__(self, cog, guild_id):
            super().__init__(timeout=None)
            self.cog = cog
            self.guild_id = guild_id
            self.paused = False
            self.replay = cog.replay_states.get(guild_id, False)
            
            self.pause_button = MusicCog.MusicButton(
                self.pause_resume, 
                style=ButtonStyle.blurple, 
                emoji="▶️" if self.paused else "⏸️"
            )
            self.skip_button = MusicCog.MusicButton(
                self.skip, 
                style=ButtonStyle.grey, 
                emoji="⏭️"
            )
            self.stop_button = MusicCog.MusicButton(
                self.stop_bot, 
                style=ButtonStyle.red, 
                emoji="⏹️"
            )
            self.replay_button = MusicCog.MusicButton(
                self.toggle_replay,
                style=ButtonStyle.green if self.replay else ButtonStyle.grey,
                emoji="🔁"
            )
            
            self.add_item(self.pause_button)
            self.add_item(self.skip_button)
            self.add_item(self.stop_button)
            self.add_item(self.replay_button)

        async def toggle_replay(self, interaction: disnake.MessageInteraction):
            try:
                self.replay = not self.replay
                self.cog.replay_states[self.guild_id] = self.replay
                self.replay_button.style = ButtonStyle.green if self.replay else ButtonStyle.grey
                
                await interaction.response.edit_message(view=self)
                
                status = "включен" if self.replay else "выключен"
                await interaction.followup.send(
                    f"🔁 Режим повтора: **{status}**!",
                    ephemeral=True,
                    delete_after=3
                )
            except Exception as e:
                logger.error(f"Replay error: {e}")

        async def create_context(self, interaction):
            return await self.cog.bot.get_context(await interaction.original_message())
        
        async def skip(self, interaction: disnake.MessageInteraction):
            try:
                await interaction.response.defer(with_message=False)
                voice = interaction.guild.voice_client
                if voice and voice.is_connected():
                    voice.stop()
                    await asyncio.sleep(0.5)
                    await self.cog.play_next(await self.create_context(interaction))
            except Exception as e:
                logger.error(f"Skip error: {e}")

        async def stop_bot(self, interaction: disnake.MessageInteraction):
            try:
                await interaction.response.defer(with_message=False)
                if interaction.guild.voice_client:
                    await interaction.guild.voice_client.disconnect()
                self.cog.queues.pop(interaction.guild.id, None)
                await interaction.delete_original_message()
            except Exception as e:
                logger.error(f"Stop error: {e}")

        async def pause_resume(self, interaction: disnake.MessageInteraction):
            try:
                voice = interaction.guild.voice_client
                if not voice or not voice.is_connected():
                    return

                if voice.is_playing():
                    voice.pause()
                    self.paused = True
                    self.pause_button.emoji = "▶️"
                elif voice.is_paused():
                    voice.resume()
                    self.paused = False
                    self.pause_button.emoji = "⏸️"
                
                await interaction.response.edit_message(view=self)
            except Exception as e:
                logger.error(f"Pause error: {e}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member == self.bot.user and not after.channel:
            self.queues.pop(member.guild.id, None)
            if member.guild.id in self.current_embeds:
                try:
                    await self.current_embeds[member.guild.id].delete()
                except Exception as e:
                    logger.warning(f"Ошибка удаления сообщения: {e}")

    def get_queue(self, guild_id):
        return self.queues.setdefault(guild_id, [])

    async def create_embed(self, track_info, ctx):
        embed = disnake.Embed(
            title="Сейчас играет",
            description=f"[{track_info['title']}]({track_info['url']})",
            color=0x1DB954
        )
        embed.add_field(name="Автор", value=track_info['artist'], inline=True)
        embed.add_field(name="Длительность", value=track_info['duration'], inline=True)
        embed.set_thumbnail(url=track_info['album_cover'])
        embed.set_footer(
            text=f"Запросил: {ctx.author.display_name} | {config.MUSIC_VERSION}",
            icon_url=ctx.author.avatar.url
        )
        return embed

    async def play_next(self, ctx):
        async with self.play_lock:
            try:
                voice = ctx.guild.voice_client
                if not voice or not voice.is_connected():
                    return

                while voice.is_playing() or voice.is_paused():
                    await asyncio.sleep(0.1)

                guild_id = ctx.guild.id
                queue = self.get_queue(guild_id)

                if self.replay_states.get(guild_id, False) and guild_id in self.current_tracks:
                    next_track = self.current_tracks[guild_id]
                elif queue:
                    next_track = queue.pop(0)
                    self.current_tracks[guild_id] = next_track
                else:
                    await voice.disconnect()
                    self.replay_states.pop(guild_id, None)
                    self.current_tracks.pop(guild_id, None)
                    return await ctx.send("🎶 Очередь пуста!")

                with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                    info = ydl.extract_info(f"ytsearch:{next_track['query']}", download=False)
                    
                    if not info or 'entries' not in info or not info['entries']:
                        raise ValueError("Не удалось получить информацию о треке")
                    
                    url = info['entries'][0]['url']

                if voice.is_playing():
                    voice.stop()

                voice.play(
                FFmpegPCMAudio(url, **config.FFMPEG_OPTIONS),
                after=lambda e: self.bot.loop.create_task(self.play_next(ctx))
            )
                embed = await self.create_embed(next_track, ctx)
                if guild_id in self.current_embeds:
                    message = self.current_embeds[guild_id]
                    controls = self.MusicControls(self, guild_id)
                    await message.edit(embed=embed, view=controls)
            except Exception as e:
                logger.error(f"Play error: {e}")
                await self.play_next(ctx)

    @commands.command()
    async def play(self, ctx, *, query):
        try:
            if not ctx.author.voice:
                return await ctx.send("❗ Подключитесь к голосовому каналу!")
            
            voice = ctx.voice_client or await ctx.author.voice.channel.connect()
            
            if "open.spotify.com" in query:
                if "/playlist/" in query:
                    await self.process_spotify_playlist(ctx, query)
                else:
                    await self.process_spotify_track(ctx, query)
            else:
                await self.process_youtube_query(ctx, query)
            
            if not voice.is_playing() and self.get_queue(ctx.guild.id):
                view = self.MusicControls(self, ctx.guild.id)
                embed = await self.create_embed(self.get_queue(ctx.guild.id)[0], ctx)
                message = await ctx.send(embed=embed, view=view)
                self.current_embeds[ctx.guild.id] = message
                await self.play_next(ctx)

        except Exception as e:
            logger.error(f"Command error: {e}")
            await ctx.send(f"❌ Ошибка: {str(e)}")

    async def process_spotify_playlist(self, ctx, url):
        playlist_id = url.split("/playlist/")[1].split("?")[0]
        results = self.sp.playlist_tracks(playlist_id)
        
        for item in results['items']:
            track = item['track']
            self.get_queue(ctx.guild.id).append(self.create_track_info(track))
        
        await ctx.send(f"✅ Добавлено {len(results['items'])} треков!")

    async def process_spotify_track(self, ctx, query):
        if "/track/" in query:
            track_id = query.split("/track/")[1].split("?")[0]
            track = self.sp.track(track_id)
        else:
            track = self.sp.search(query, limit=1, type='track')['tracks']['items'][0]
        
        self.get_queue(ctx.guild.id).append(self.create_track_info(track))
        await ctx.send(f"✅ Трек **{track['name']}** добавлен!")

    async def process_youtube_query(self, ctx, query):
        with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            track = {
                'title': info.get('title', 'Неизвестный трек'),
                'artist': info.get('uploader', 'Неизвестный исполнитель'),
                'url': info.get('webpage_url', ''),
                'duration': str(datetime.timedelta(seconds=info.get('duration', 0))),
                'album_cover': info.get('thumbnail'),
                'query': query
            }
            self.get_queue(ctx.guild.id).append(track)
            await ctx.send(f"✅ Трек **{track['title']}** добавлен!")

    def create_track_info(self, track):
        return {
            'title': track['name'],
            'artist': track['artists'][0]['name'],
            'url': track['external_urls']['spotify'],
            'duration': str(datetime.timedelta(seconds=track['duration_ms']//1000)),
            'album_cover': track['album']['images'][0]['url'] if track['album']['images'] else "",
            'query': f"{track['name']} {track['artists'][0]['name']}"
        }

    @commands.command()
    async def queue(self, ctx):
        if queue := self.get_queue(ctx.guild.id):
            embed = disnake.Embed(title="Очередь воспроизведения", color=0x1DB954)
            for i, track in enumerate(queue[:10], 1):
                embed.add_field(
                    name=f"{i}. {track['title']}",
                    value=f"Автор: {track['artist']} | Длительность: {track['duration']}",
                    inline=False
                )
            await ctx.send(embed=embed)
        else:
            await ctx.send("Очередь пуста!")

    @commands.command()
    async def skip(self, ctx):
        voice = ctx.voice_client
        if not voice:
            return await ctx.send("❌ Бот не подключен к голосовому каналу.")
        
        if voice.is_playing() or voice.is_paused():
            voice.stop()
            await ctx.send("⏭️ Трек пропущен!")
        elif queue := self.get_queue(ctx.guild.id):
            await self.play_next(ctx)
            await ctx.send("⏭️ Запущен следующий трек!")
        else:
            await ctx.send("🎶 Очередь пуста!")

    @commands.command()
    async def stop(self, ctx):
        guild_id = ctx.guild.id
        
        if guild_id in self.queues:
            self.queues.pop(guild_id)
        
        if guild_id in self.current_embeds:
            try:
                await self.current_embeds[guild_id].delete()
            except:
                pass
            finally:
                del self.current_embeds[guild_id]
        
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("⏹️ Воспроизведение остановлено!")
        else:
            await ctx.send("❌ Бот не подключен к голосовому каналу.")

    @commands.command()
    async def toggle(self, ctx):
        voice = ctx.voice_client
        
        if not voice or not voice.is_connected():
            return await ctx.send("❌ Бот не подключен к голосовому каналу.")
        
        if voice.is_playing():
            voice.pause()
            await ctx.send("⏸️ Воспроизведение приостановлено!")
        elif voice.is_paused():
            voice.resume()
            await ctx.send("▶️ Воспроизведение возобновлено!")
        else:
            await ctx.send("🎶 Сейчас ничего не играет!")

def setup(bot):
    bot.add_cog(MusicCog(bot))