"""
LateNight Music Selfbot
Plays music through your user account via Lavalink v4 + FluxWave.
"""

import os
import logging
import time
import datetime
from dotenv import load_dotenv

load_dotenv()  # loads TOKEN from .env file

import discord
from discord.ext import commands
import fluxwave

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("latenight.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("latenight")
logging.getLogger("discord").setLevel(logging.WARNING)
logging.getLogger("fluxwave").setLevel(logging.INFO)
# ──────────────────────────────────────────────────────────────────────────────

# ── Config ────────────────────────────────────────────────────────────────────
# Add as many owner IDs as you want here
OWNER_IDS = {
    901487880067776524,   # primary owner
    # 123456789012345678, # add more owners below
}
TOKEN = os.environ.get("DISCORD_TOKEN")  # set this in .env
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN not set — add it to your .env file")

LAVALINK_HOST   = "lava-v4.ajieblogs.eu.org"
LAVALINK_PORT   = 80
LAVALINK_PASS   = "https://dsc.gg/ajidevserver"
LAVALINK_SECURE = False
LAVALINK_URI    = f"{'https' if LAVALINK_SECURE else 'http'}://{LAVALINK_HOST}:{LAVALINK_PORT}"

PREFIX = ">"
# ──────────────────────────────────────────────────────────────────────────────


def is_owner():
    """Command check: silently ignore anyone who isn't an owner."""
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.author.id not in OWNER_IDS:
            log.debug(f"[check] Ignored non-owner {ctx.author.id}")
            return False
        return True
    return commands.check(predicate)


class LateNightBot(commands.Bot):
    _cog_loaded = False  # guard so on_ready doesn't double-load on reconnects

    def __init__(self) -> None:
        super().__init__(
            command_prefix=PREFIX,
            self_bot=True,
            help_command=None,  # disable default help so our >help can register
        )
        self._start_time = time.time()

    async def on_ready(self) -> None:
        log.info(f"[ready] Logged in as {self.user} (ID: {self.user.id})")
        log.info(f"[ready] Prefix={PREFIX!r}  Owners={OWNER_IDS}")

        if not self._cog_loaded:
            # add_cog is a coroutine in discord.py-self — must be awaited
            await self.add_cog(Music(self))
            self._cog_loaded = True
            log.info(f"[ready] Music cog loaded. Commands: {[c.name for c in self.commands]}")

        # Connect Lavalink here — self.user.id is guaranteed available
        log.info("[setup] Connecting to Lavalink...")
        try:
            node = fluxwave.Node(
                uri=LAVALINK_URI,
                password=LAVALINK_PASS,
                user_id=self.user.id,
                identifier="latenight-main",
                validate_version=False,
            )
            await fluxwave.Pool.connect(nodes=[node], cache_capacity=256)
            log.info(f"[setup] Lavalink connected → {LAVALINK_URI}")
        except Exception:
            log.exception("[setup] FAILED to connect to Lavalink!")

    async def on_message(self, message: discord.Message) -> None:
        # Log every incoming message for debugging
        log.debug(
            f"[msg] author={message.author.id} channel={message.channel.id} "
            f"content={message.content!r:.80}"
        )

        # Only process messages from owners (any channel)
        if message.author.id not in OWNER_IDS:
            return

        log.info(f"[msg] ✅ Owner command: {message.content!r}")

        # get_context() is broken in discord.py-self selfbot mode (always returns
        # prefix=None, ctx.valid=False). Bypass it entirely: parse the command
        # name and args ourselves, look up the command, and invoke it directly.
        text = message.content.strip()
        if not text.startswith(PREFIX):
            return

        # Split off the command name and the rest
        parts = text[len(PREFIX):].split(None, 1)
        if not parts:
            return
        cmd_name = parts[0].lower()
        arg_string = parts[1] if len(parts) > 1 else ""

        command = self.get_command(cmd_name)
        log.debug(f"[msg] cmd_name={cmd_name!r}  command={command}  arg_string={arg_string!r}")
        if command is None:
            log.warning(f"[msg] Unknown command: {cmd_name!r}")
            return

        ctx = await self.get_context(message)
        # Force-populate the fields get_context fails to set on selfbots
        ctx.prefix = PREFIX
        ctx.command = command
        ctx.invoked_with = cmd_name
        ctx.view = discord.ext.commands.view.StringView(arg_string)
        await self.invoke(ctx)

    async def on_command(self, ctx: commands.Context) -> None:
        log.info(f"[cmd] → {ctx.command}  args={ctx.args[1:]}  kwargs={ctx.kwargs}")

    async def on_command_completion(self, ctx: commands.Context) -> None:
        log.info(f"[cmd] ✅ Done: {ctx.command}")

    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.CheckFailure):
            log.debug(f"[cmd] CheckFailure (non-owner) for {ctx.command}")
            return  # silent — don't reply
        if isinstance(error, commands.MissingRequiredArgument):
            log.warning(f"[cmd] MissingArg: {error.param.name}")
            await ctx.reply(f"❌ Missing argument: `{error.param.name}`", mention_author=False)
        elif isinstance(error, commands.CommandNotFound):
            log.debug(f"[cmd] CommandNotFound: {ctx.invoked_with!r}")
        else:
            log.error(f"[cmd] Unhandled error in {ctx.command}:", exc_info=error)
            try:
                await ctx.reply(f"❌ Error: {error}", mention_author=False)
            except Exception:
                log.exception("[cmd] Also failed to send error reply")

    async def on_error(self, event_method: str, *args, **kwargs) -> None:
        log.exception(f"[error] Unhandled exception in event: {event_method}")


# ── Music Cog ─────────────────────────────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot: LateNightBot) -> None:
        self.bot = bot

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_guild(self, ctx: commands.Context) -> discord.Guild | None:
        ch = self.bot.get_channel(ctx.channel.id)
        guild = getattr(ch, "guild", None)
        if guild is None:
            log.warning(f"[guild] Could not resolve guild from channel {ctx.channel.id}")
        return guild

    def _player(self, ctx: commands.Context) -> fluxwave.FluxPlayer | None:
        guild = self._get_guild(ctx)
        if guild is None:
            return None
        return guild.voice_client  # type: ignore[return-value]

    async def _ensure_connected(self, ctx: commands.Context) -> fluxwave.FluxPlayer | None:
        guild = self._get_guild(ctx)
        if guild is None:
            await ctx.reply("❌ This command only works in a server.", mention_author=False)
            return None

        # Selfbot: ctx.author IS the account, so voice state is directly available
        voice_state = ctx.author.voice
        log.debug(f"[connect] Voice state: {voice_state}")
        if voice_state is None or voice_state.channel is None:
            await ctx.reply("❌ You need to be in a voice channel first.", mention_author=False)
            return None

        player: fluxwave.FluxPlayer | None = guild.voice_client  # type: ignore[assignment]
        try:
            if player is None:
                log.info(f"[connect] Joining #{voice_state.channel.name}")
                player = await voice_state.channel.connect(cls=fluxwave.FluxPlayer)
            elif player.channel != voice_state.channel:
                log.info(f"[connect] Moving to #{voice_state.channel.name}")
                await player.move_to(voice_state.channel)
        except Exception:
            log.exception("[connect] Failed to connect to voice channel")
            await ctx.reply("❌ Failed to join your voice channel.", mention_author=False)
            return None

        return player

    @staticmethod
    def _fmt_duration(ms: int | None) -> str:
        if ms is None:
            return "∞"
        s = ms // 1000
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    @staticmethod
    def _progress_bar(position_ms: int, length_ms: int, width: int = 20) -> str:
        ratio = min(position_ms / max(length_ms, 1), 1.0)
        filled = int(ratio * width)
        bar = "▓" * filled + "░" * (width - filled)
        return f"[{bar}]"

    # ── Lavalink Events ───────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_fluxwave_track_start(self, event: fluxwave.TrackStartEvent) -> None:
        log.info(f"[track] ▶ Started: {event.track.title}")
        guild = self.bot.get_guild(event.guild_id)
        if guild is None:
            return
        player: fluxwave.FluxPlayer | None = guild.voice_client  # type: ignore[assignment]
        if player is None:
            return
        ch = getattr(player, "_text_channel", None)
        if ch is None:
            return
        t = event.track
        try:
            await ch.send(
                f"🎵 Now playing: **{t.title}** by `{t.author}`  "
                f"[`{self._fmt_duration(t.length)}`]",
            )
        except Exception:
            log.exception("[track] Failed to send now-playing message")

    @commands.Cog.listener()
    async def on_fluxwave_track_end(self, event: fluxwave.TrackEndEvent) -> None:
        log.info(f"[track] ⏹ Ended: reason={event.reason}")
        if event.reason in ("FINISHED", "LOAD_FAILED"):
            guild = self.bot.get_guild(event.guild_id)
            if guild is None:
                return
            player: fluxwave.FluxPlayer | None = guild.voice_client  # type: ignore[assignment]
            if player is None:
                return
            if player.queue.is_empty and player.current is None:
                ch = getattr(player, "_text_channel", None)
                if ch:
                    try:
                        await ch.send("✅ Queue finished. Use `!play` to add more tracks.")
                    except Exception:
                        log.exception("[track] Failed to send queue-end message")

    # ── Commands ──────────────────────────────────────────────────────────────

    @commands.command(name="play", aliases=["p"])
    @is_owner()
    async def play(self, ctx: commands.Context, *, query: str) -> None:
        """Play a song or add it to the queue. Supports YouTube, SoundCloud, URLs."""
        log.info(f"[play] Query: {query!r}")
        player = await self._ensure_connected(ctx)
        if player is None:
            return
        player._text_channel = ctx.channel  # type: ignore[attr-defined]
        try:
            async with ctx.typing():
                result = await player.enqueue(query)
        except Exception:
            log.exception("[play] enqueue() failed")
            await ctx.reply("❌ Failed to load track.", mention_author=False)
            return
        log.info(f"[play] Enqueued {result.added} track(s)")
        if result.added == 0:
            await ctx.reply("❌ No tracks found for that query.", mention_author=False)
            return
        if player.current is None:
            await player.skip(force=True)
        else:
            t = result.tracks[0]
            await ctx.reply(
                f"➕ Added to queue: **{t.title}** [`{self._fmt_duration(t.length)}`]",
                mention_author=False,
            )

    @commands.command(name="playnext", aliases=["pn"])
    @is_owner()
    async def playnext(self, ctx: commands.Context, *, query: str) -> None:
        """Add a track to the front of the queue (plays next)."""
        log.info(f"[playnext] Query: {query!r}")
        player = await self._ensure_connected(ctx)
        if player is None:
            return
        player._text_channel = ctx.channel  # type: ignore[attr-defined]
        try:
            async with ctx.typing():
                result = await player.play_next(query)
        except Exception:
            log.exception("[playnext] play_next() failed")
            await ctx.reply("❌ Failed to load track.", mention_author=False)
            return
        if result.added == 0:
            await ctx.reply("❌ No tracks found.", mention_author=False)
            return
        t = result.tracks[0]
        await ctx.reply(
            f"⏭ Playing next: **{t.title}** [`{self._fmt_duration(t.length)}`]",
            mention_author=False,
        )

    @commands.command(name="skip", aliases=["s", "next"])
    @is_owner()
    async def skip(self, ctx: commands.Context) -> None:
        """Skip the current track."""
        player = self._player(ctx)
        if player is None or player.current is None:
            await ctx.reply("❌ Nothing is playing.", mention_author=False)
            return
        title = player.current.title
        await player.skip(force=True)
        await ctx.reply(f"⏭ Skipped **{title}**.", mention_author=False)

    @commands.command(name="stop")
    @is_owner()
    async def stop(self, ctx: commands.Context) -> None:
        """Stop playback and clear the queue."""
        player = self._player(ctx)
        if player is None:
            await ctx.reply("❌ Not connected.", mention_author=False)
            return
        await player.stop(clear_queue=True)
        await ctx.reply("⏹ Stopped and queue cleared.", mention_author=False)

    @commands.command(name="pause")
    @is_owner()
    async def pause(self, ctx: commands.Context) -> None:
        """Pause the current track."""
        player = self._player(ctx)
        if player is None or player.current is None:
            await ctx.reply("❌ Nothing is playing.", mention_author=False)
            return
        await player.pause(True)
        await ctx.reply("⏸ Paused.", mention_author=False)

    @commands.command(name="resume", aliases=["unpause"])
    @is_owner()
    async def resume(self, ctx: commands.Context) -> None:
        """Resume a paused track."""
        player = self._player(ctx)
        if player is None:
            await ctx.reply("❌ Not connected.", mention_author=False)
            return
        await player.pause(False)
        await ctx.reply("▶️ Resumed.", mention_author=False)

    @commands.command(name="volume", aliases=["vol"])
    @is_owner()
    async def volume(self, ctx: commands.Context, vol: int) -> None:
        """Set volume (0–200). Default is 100."""
        if not 0 <= vol <= 200:
            await ctx.reply("❌ Volume must be between 0 and 200.", mention_author=False)
            return
        player = self._player(ctx)
        if player is None:
            await ctx.reply("❌ Not connected.", mention_author=False)
            return
        await player.set_volume(vol)
        bar = "🔊" if vol >= 50 else ("🔉" if vol > 0 else "🔇")
        await ctx.reply(f"{bar} Volume set to **{vol}%**.", mention_author=False)

    @commands.command(name="seek")
    @is_owner()
    async def seek(self, ctx: commands.Context, position: str) -> None:
        """Seek to a position. Format: `1:30` or `90` (seconds)."""
        player = self._player(ctx)
        if player is None or player.current is None:
            await ctx.reply("❌ Nothing is playing.", mention_author=False)
            return
        try:
            if ":" in position:
                parts = position.split(":")
                if len(parts) == 2:
                    ms = (int(parts[0]) * 60 + int(parts[1])) * 1000
                elif len(parts) == 3:
                    ms = (int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])) * 1000
                else:
                    raise ValueError
            else:
                ms = int(position) * 1000
        except ValueError:
            await ctx.reply("❌ Invalid position. Use `1:30` or `90` (seconds).", mention_author=False)
            return
        await player.seek(ms)
        await ctx.reply(f"⏩ Seeked to `{self._fmt_duration(ms)}`.", mention_author=False)

    @commands.command(name="queue", aliases=["q"])
    @is_owner()
    async def queue(self, ctx: commands.Context) -> None:
        """Show the current queue."""
        player = self._player(ctx)
        if player is None or (player.current is None and player.queue.is_empty):
            await ctx.reply("❌ Nothing is playing and the queue is empty.", mention_author=False)
            return
        lines: list[str] = []
        if player.current:
            pos = self._fmt_duration(player.position)
            dur = self._fmt_duration(player.current.length)
            bar = self._progress_bar(player.position, player.current.length or 1)
            lines.append("**Now Playing:**")
            lines.append(f"🎵 **{player.current.title}** — `{player.current.author}`")
            lines.append(f"{bar} `{pos} / {dur}`\n")
        if not player.queue.is_empty:
            lines.append("**Up Next:**")
            for i, track in enumerate(list(player.queue)[:10], start=1):
                lines.append(f"`{i}.` {track.title} — `{self._fmt_duration(track.length)}`")
            remaining = len(player.queue) - 10
            if remaining > 0:
                lines.append(f"…and **{remaining}** more track(s).")
            lines.append(f"\n⏱ Queue duration: `{self._fmt_duration(player.queue.total_duration)}`")
        await ctx.reply("\n".join(lines), mention_author=False)

    @commands.command(name="nowplaying", aliases=["np"])
    @is_owner()
    async def nowplaying(self, ctx: commands.Context) -> None:
        """Show what's currently playing."""
        player = self._player(ctx)
        if player is None or player.current is None:
            await ctx.reply("❌ Nothing is playing.", mention_author=False)
            return
        t = player.current
        pos = self._fmt_duration(player.position)
        dur = self._fmt_duration(t.length)
        bar = self._progress_bar(player.position, t.length or 1)
        paused = " *(paused)*" if player.paused else ""
        await ctx.reply(
            f"🎵 **{t.title}**{paused}\n"
            f"👤 Artist: `{t.author}`\n"
            f"🔗 Source: <{t.uri}>\n"
            f"{bar} `{pos} / {dur}`",
            mention_author=False,
        )

    @commands.command(name="shuffle")
    @is_owner()
    async def shuffle(self, ctx: commands.Context) -> None:
        """Shuffle the queue."""
        player = self._player(ctx)
        if player is None or player.queue.is_empty:
            await ctx.reply("❌ The queue is empty.", mention_author=False)
            return
        player.queue.shuffle()
        await ctx.reply("🔀 Queue shuffled.", mention_author=False)

    @commands.command(name="loop")
    @is_owner()
    async def loop(self, ctx: commands.Context, mode: str = "track") -> None:
        """Set loop mode: `track`, `queue`, or `off`."""
        mapping = {
            "track": fluxwave.QueueMode.loop,
            "queue": fluxwave.QueueMode.loop_all,
            "off":   fluxwave.QueueMode.normal,
        }
        if mode.lower() not in mapping:
            await ctx.reply("❌ Valid modes: `track`, `queue`, `off`.", mention_author=False)
            return
        player = self._player(ctx)
        if player is None:
            await ctx.reply("❌ Not connected.", mention_author=False)
            return
        player.queue.mode = mapping[mode.lower()]
        icons = {"track": "🔂", "queue": "🔁", "off": "➡️"}
        await ctx.reply(f"{icons[mode.lower()]} Loop mode: **{mode}**.", mention_author=False)

    @commands.command(name="remove")
    @is_owner()
    async def remove(self, ctx: commands.Context, index: int) -> None:
        """Remove a track from the queue by position (1-based)."""
        player = self._player(ctx)
        if player is None or player.queue.is_empty:
            await ctx.reply("❌ Queue is empty.", mention_author=False)
            return
        q_list = list(player.queue)
        if not 1 <= index <= len(q_list):
            await ctx.reply(f"❌ Index out of range (1–{len(q_list)}).", mention_author=False)
            return
        track = q_list[index - 1]
        player.queue.remove(track)
        await ctx.reply(f"🗑 Removed **{track.title}** from queue.", mention_author=False)

    @commands.command(name="clear")
    @is_owner()
    async def clear_queue(self, ctx: commands.Context) -> None:
        """Clear the queue without stopping current playback."""
        player = self._player(ctx)
        if player is None:
            await ctx.reply("❌ Not connected.", mention_author=False)
            return
        player.queue.clear()
        await ctx.reply("🧹 Queue cleared.", mention_author=False)

    @commands.command(name="join", aliases=["j"])
    @is_owner()
    async def join(self, ctx: commands.Context) -> None:
        """Join your current voice channel."""
        player = await self._ensure_connected(ctx)
        if player is not None:
            await ctx.reply(f"✅ Joined **{player.channel.name}**.", mention_author=False)

    @commands.command(name="disconnect", aliases=["dc", "leave"])
    @is_owner()
    async def disconnect(self, ctx: commands.Context) -> None:
        """Disconnect from the voice channel."""
        player = self._player(ctx)
        if player is None:
            await ctx.reply("❌ Not connected.", mention_author=False)
            return
        await player.disconnect()
        await ctx.reply("👋 Disconnected.", mention_author=False)

    # ── Filters ───────────────────────────────────────────────────────────────

    @commands.command(name="nightcore", aliases=["nc"])
    @is_owner()
    async def nightcore(self, ctx: commands.Context) -> None:
        """Apply nightcore filter (pitch + speed up)."""
        player = self._player(ctx)
        if player is None:
            await ctx.reply("❌ Not connected.", mention_author=False)
            return
        await player.set_filters(fluxwave.Filters().nightcore(), seek=True)
        await ctx.reply("🌙 Nightcore filter applied!", mention_author=False)

    @commands.command(name="bassboost", aliases=["bb"])
    @is_owner()
    async def bassboost(self, ctx: commands.Context) -> None:
        """Apply bass boost filter."""
        player = self._player(ctx)
        if player is None:
            await ctx.reply("❌ Not connected.", mention_author=False)
            return
        await player.set_filters(fluxwave.Filters().bass_boost(), seek=True)
        await ctx.reply("🔊 Bass boost applied!", mention_author=False)

    @commands.command(name="vaporwave", aliases=["vw"])
    @is_owner()
    async def vaporwave(self, ctx: commands.Context) -> None:
        """Apply vaporwave filter (slowed + reverb feel)."""
        player = self._player(ctx)
        if player is None:
            await ctx.reply("❌ Not connected.", mention_author=False)
            return
        await player.set_filters(fluxwave.Filters().vaporwave(), seek=True)
        await ctx.reply("🌊 Vaporwave filter applied!", mention_author=False)

    @commands.command(name="resetfilter", aliases=["rf", "clearfilter"])
    @is_owner()
    async def resetfilter(self, ctx: commands.Context) -> None:
        """Remove all active filters."""
        player = self._player(ctx)
        if player is None:
            await ctx.reply("❌ Not connected.", mention_author=False)
            return
        await player.set_filters(fluxwave.Filters(), seek=True)
        await ctx.reply("✨ Filters cleared.", mention_author=False)

    # ── Utility ───────────────────────────────────────────────────────────────

    @commands.command(name="ping")
    @is_owner()
    async def ping(self, ctx: commands.Context) -> None:
        """Show bot latency."""
        latency = round(self.bot.latency * 1000)
        await ctx.reply(f"🏓 Pong! `{latency}ms`", mention_author=False)

    @commands.command(name="uptime")
    @is_owner()
    async def uptime(self, ctx: commands.Context) -> None:
        """Show how long the bot has been running."""
        delta = datetime.timedelta(seconds=int(time.time() - self.bot._start_time))
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        await ctx.reply(f"⏱ Uptime: `{hours}h {minutes}m {seconds}s`", mention_author=False)

    @commands.command(name="node")
    @is_owner()
    async def node(self, ctx: commands.Context) -> None:
        """Show Lavalink node status."""
        try:
            # fluxwave.Pool.nodes can be a callable or a dict depending on version
            raw = fluxwave.Pool.nodes
            nodes_dict = raw() if callable(raw) else raw
            # normalise to a list of node objects
            if isinstance(nodes_dict, dict):
                node_list = list(nodes_dict.values())
            elif hasattr(nodes_dict, "__iter__"):
                node_list = list(nodes_dict)
            else:
                node_list = [nodes_dict]

            if not node_list:
                await ctx.reply("❌ No Lavalink nodes connected.", mention_author=False)
                return

            lines = ["**🔗 Lavalink Node Status**"]
            for n in node_list:
                stats = getattr(n, "stats", None)
                identifier = getattr(n, "identifier", "unknown")
                if stats:
                    players    = getattr(stats, "playing_players", "?")
                    cpu_obj    = getattr(stats, "cpu", None)
                    cpu        = round(getattr(cpu_obj, "lavalink_load", 0) * 100, 1) if cpu_obj else "?"
                    mem_obj    = getattr(stats, "memory", None)
                    mem_used   = round(getattr(mem_obj, "used", 0) / 1024 / 1024) if mem_obj else "?"
                    uptime_ms  = getattr(stats, "uptime", 0) or 0
                    uptime_s   = int(uptime_ms / 1000)
                    uh, ur     = divmod(uptime_s, 3600)
                    um, us     = divmod(ur, 60)
                    lines.append(
                        f"`{identifier}` — ✅ Connected\n"
                        f"  Players: `{players}` | CPU: `{cpu}%` | RAM: `{mem_used}MB` | Uptime: `{uh}h {um}m {us}s`"
                    )
                else:
                    lines.append(f"`{identifier}` — ✅ Connected (no stats yet)")
            await ctx.reply("\n".join(lines), mention_author=False)
        except Exception as e:
            log.exception("[node] Failed to fetch node info")
            await ctx.reply(f"❌ Error fetching node info: {e}", mention_author=False)

    # ── Help ──────────────────────────────────────────────────────────────────

    @commands.command(name="help", aliases=["mh"])
    @is_owner()
    async def help(self, ctx: commands.Context) -> None:
        """Show all LateNight music commands."""
        help_text = f"""
**🌙 LateNight Selfbot — Commands** `(prefix: {PREFIX})`

**Utility**
`{PREFIX}ping` — Bot latency
`{PREFIX}uptime` — How long bot has been running
`{PREFIX}node` — Lavalink node status

**Playback**
`{PREFIX}play <query/url>` — Play a song or add to queue
`{PREFIX}playnext <query>` — Play next (jumps queue)
`{PREFIX}skip` — Skip current track
`{PREFIX}stop` — Stop and clear queue
`{PREFIX}pause` — Pause playback
`{PREFIX}resume` — Resume playback
`{PREFIX}seek <1:30>` — Seek to timestamp

**Queue**
`{PREFIX}queue` — Show queue
`{PREFIX}nowplaying` — Show current track
`{PREFIX}shuffle` — Shuffle queue
`{PREFIX}loop <track|queue|off>` — Set loop mode
`{PREFIX}remove <#>` — Remove track by position
`{PREFIX}clear` — Clear queue

**Audio**
`{PREFIX}volume <0-200>` — Set volume
`{PREFIX}nightcore` — Nightcore filter
`{PREFIX}bassboost` — Bass boost filter
`{PREFIX}vaporwave` — Vaporwave filter
`{PREFIX}resetfilter` — Remove all filters

**Connection**
`{PREFIX}join` — Join your voice channel
`{PREFIX}disconnect` — Leave voice channel
        """.strip()
        await ctx.reply(help_text, mention_author=False)


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    bot = LateNightBot()
    log.info("[start] Starting LateNight Music Selfbot by yup-console...")
    try:
        bot.run(TOKEN, log_handler=None)
    except Exception:
        log.exception("[start] Fatal error running bot")
