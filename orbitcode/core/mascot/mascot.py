"""OrbitCode Animated Pixel Space-Orb Mascot Widget"""
from enum import Enum
from typing import Optional
from dataclasses import dataclass
import random
import asyncio
from textual.widget import Widget
from textual.reactive import reactive
from textual.timer import Timer


class MascotState(Enum):
    """Mascot animation states"""
    IDLE = "idle"
    IDLE_RAINBOW = "idle_rainbow"
    THINKING = "thinking"
    THINKING_COSMIC = "thinking_cosmic"
    TOOL_RUNNING = "tool_running"
    HACKER = "hacker"
    HAPPY = "happy"
    CELEBRATION = "celebration"
    DANCING = "dancing"
    LOADING = "loading"
    ERROR = "error"
    SLEEPING = "sleeping"


@dataclass
class MascotFrameSet:
    """Container for mascot animation frames"""
    frames: list[str]
    frame_duration: float = 0.5


# Default mascot frames - pixel space-orb with orbital ring (CRAZY EDITION)
ORBIT_MASCOT_FRAMES = {
    "idle": MascotFrameSet([
        """    [bold #22d3ee]╭── ✦ ──╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #22d3ee] ▀ [/][bold #a855f7]███[/][bold #22d3ee] ▀ [/][bold #a855f7]██[/]
  [bold #a855f7]▀█████████▀[/]
    [bold #f472b6]▀█▀ ▀█▀[/]""",
        """    [bold #22d3ee]╭── ✦ ──╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #22d3ee] ● [/][bold #a855f7]███[/][bold #22d3ee] ● [/][bold #a855f7]██[/]
  [bold #a855f7]▀█████████▀[/]
    [bold #f472b6]▀█▀ ▀█▀[/]""",
        """    [bold #22d3ee]╭── ✦ ──╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #22d3ee] ○ [/][bold #a855f7]███[/][bold #22d3ee] ○ [/][bold #a855f7]██[/]
  [bold #a855f7]▀█████████▀[/]
    [bold #f472b6]▀█▀ ▀█▀[/]""",
        """    [bold #22d3ee]╭── ✦ ──╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #f472b6] ★ [/][bold #a855f7]███[/][bold #f472b6] ★ [/][bold #a855f7]██[/]
  [bold #a855f7]▀█████████▀[/]
    [bold #f472b6]▀█▀ ▀█▀[/]""",
        """    [bold #22d3ee]╭── ✧ ──╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #22d3ee] ✦ [/][bold #a855f7]███[/][bold #22d3ee] ✦ [/][bold #a855f7]██[/]
  [bold #a855f7]▀█████████▀[/]
    [bold #f472b6]▀█▀ ▀█▀[/]""",
    ], frame_duration=1.5),

    # Rainbow cycling idle frames
    "idle_rainbow": MascotFrameSet([
        """    [bold #ff0000]╭── ✦ ──╮[/]
   [bold #ff7700]▄█████████▄[/]
  [bold #ffcc00]██[/][bold #00ff00] ▀ [/][bold #ffcc00]███[/][bold #00ff00] ▀ [/][bold #ffcc00]██[/]
  [bold #00ffff]▀█████████▀[/]
    [bold #8800ff]▀█▀ ▀█▀[/]""",
        """    [bold #8800ff]╭── ✦ ──╮[/]
   [bold #ff0000]▄█████████▄[/]
  [bold #ff7700]██[/][bold #ffcc00] ● [/][bold #ff7700]███[/][bold #ffcc00] ● [/][bold #ff7700]██[/]
  [bold #00ff00]▀█████████▀[/]
    [bold #00ffff]▀█▀ ▀█▀[/]""",
        """    [bold #00ffff]╭── ✦ ──╮[/]
   [bold #8800ff]▄█████████▄[/]
  [bold #ff0000]██[/][bold #ff7700] ○ [/][bold #ff0000]███[/][bold #ff7700] ○ [/][bold #ff0000]██[/]
  [bold #ffcc00]▀█████████▀[/]
    [bold #00ff00]▀█▀ ▀█▀[/]""",
        """    [bold #00ff00]╭── ✦ ──╮[/]
   [bold #00ffff]▄█████████▄[/]
  [bold #8800ff]██[/][bold #ff0000] ★ [/][bold #8800ff]███[/][bold #ff0000] ★ [/][bold #8800ff]██[/]
  [bold #ff7700]▀█████████▀[/]
    [bold #ffcc00]▀█▀ ▀█▀[/]""",
    ], frame_duration=0.2),
    "thinking": MascotFrameSet([
        """   [bold #f472b6]✦ ╭─────╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #22d3ee] ◠ [/][bold #a855f7]███[/][bold #22d3ee] ◠ [/][bold #a855f7]██[/]
  [bold #a855f7]▀█████████▀[/]
   [bold #f472b6]▀█▀   ▀█▀[/]""",
        """   [bold #f472b6]✦ ╭─────╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #22d3ee] ◡ [/][bold #a855f7]███[/][bold #22d3ee] ◡ [/][bold #a855f7]██[/]
  [bold #a855f7]▀█████████▀[/]
   [bold #f472b6]▀█▀   ▀█▀[/]""",
        """   [bold #f472b6]✦ ╭─────╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #22d3ee] ◐ [/][bold #a855f7]███[/][bold #22d3ee] ◑ [/][bold #a855f7]██[/]
  [bold #a855f7]▀█████████▀[/]
   [bold #f472b6]▀█▀   ▀█▀[/]""",
        """   [bold #f472b6]✦ ╭─────╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #22d3ee] ◓ [/][bold #a855f7]███[/][bold #22d3ee] ◒ [/][bold #a855f7]██[/]
  [bold #a855f7]▀█████████▀[/]
   [bold #f472b6]▀█▀   ▀█▀[/]""",
        """   [bold #f472b6]✦ ╭─────╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #f59e0b] ⚡ [/][bold #a855f7]███[/][bold #f59e0b] ⚡ [/][bold #a855f7]██[/]
  [bold #a855f7]▀█████████▀[/]
   [bold #f472b6]▀█▀   ▀█▀[/]""",
        """   [bold #f472b6]✦ ╭─────╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #22d3ee] 💡 [/][bold #a855f7]███[/][bold #22d3ee] 💡 [/][bold #a855f7]██[/]
  [bold #a855f7]▀█████████▀[/]
   [bold #f472b6]▀█▀   ▀█▀[/]""",
        """   [bold #f472b6]✦ ╭─────╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #a855f7] 🧠 [/][bold #a855f7]███[/][bold #a855f7] 🧠 [/][bold #a855f7]██[/]
  [bold #a855f7]▀█████████▀[/]
   [bold #f472b6]▀█▀   ▀█▀[/]""",
    ], frame_duration=0.3),

    # Crazy thinking with orbital particles
    "thinking_cosmic": MascotFrameSet([
        """   [bold #f472b6]✦ ╭─────╮[/]  [dim]✧[/]
   [bold #a855f7]▄█████████▄[/]  [dim]✦[/]
  [bold #a855f7]██[/][bold #22d3ee] ◠ [/][bold #a855f7]███[/][bold #22d3ee] ◠ [/][bold #a855f7]██[/]  [dim]✧[/]
  [bold #a855f7]▀█████████▀[/]  [dim]✦[/]
   [bold #f472b6]▀█▀   ▀█▀[/]  [dim]✧[/]""",
        """   [bold #f472b6]✦ ╭─────╮[/]  [dim]  ✧[/]
   [bold #a855f7]▄█████████▄[/]  [dim] ✦[/]
  [bold #a855f7]██[/][bold #22d3ee] ◡ [/][bold #a855f7]███[/][bold #22d3ee] ◡ [/][bold #a855f7]██[/]  [dim]  ✧[/]
  [bold #a855f7]▀█████████▀[/]  [dim] ✦[/]
   [bold #f472b6]▀█▀   ▀█▀[/]  [dim]  ✧[/]""",
        """   [bold #f472b6]✦ ╭─────╮[/] [dim]✧   [/]
   [bold #a855f7]▄█████████▄[/] [dim]✦   [/]
  [bold #a855f7]██[/][bold #22d3ee] ◐ [/][bold #a855f7]███[/][bold #22d3ee] ◑ [/][bold #a855f7]██[/] [dim]✧   [/]
  [bold #a855f7]▀█████████▀[/] [dim]✦   [/]
   [bold #f472b6]▀█▀   ▀█▀[/] [dim]✧   [/]""",
    ], frame_duration=0.25),
    "tool_running": MascotFrameSet([
        """   [bold #f59e0b]✦ ╭─────╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #f59e0b] ● [/][bold #a855f7]███[/][bold #f59e0b] ● [/][bold #a855f7]██[/]
  [bold #a855f7]▀█████████▀[/]
   [bold #f59e0b]▀█▀   ▀█▀[/]""",
        """   [bold #f59e0b]✦ ╭─────╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #f59e0b] ◐ [/][bold #a855f7]███[/][bold #f59e0b] ◑ [/][bold #a855f7]██[/]
  [bold #a855f7]▀█████████▀[/]
   [bold #f59e0b]▀█▀   ▀█▀[/]""",
        """   [bold #f59e0b]✦ ╭─────╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #f59e0b] ◓ [/][bold #a855f7]███[/][bold #f59e0b] ◒ [/][bold #a855f7]██[/]
  [bold #a855f7]▀█████████▀[/]
   [bold #f59e0b]▀█▀   ▀█▀[/]""",
        """   [bold #f59e0b]✦ ╭─────╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #22d3ee] ⚙ [/][bold #a855f7]███[/][bold #22d3ee] ⚙ [/][bold #a855f7]██[/]
  [bold #a855f7]▀█████████▀[/]
   [bold #f59e0b]▀█▀   ▀█▀[/]""",
        """   [bold #f59e0b]✦ ╭─────╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #f472b6] 🔧 [/][bold #a855f7]███[/][bold #f472b6] 🔧 [/][bold #a855f7]██[/]
  [bold #a855f7]▀█████████▀[/]
   [bold #f59e0b]▀█▀   ▀█▀[/]""",
    ], frame_duration=0.2),

    # Hacker mode - matrix-style
    "hacker": MascotFrameSet([
        """   [bold #00ff00]✦ ╭─────╮[/]
   [bold #00cc00]▄█████████▄[/]
  [bold #00cc00]██[/][bold #00ff00] 0 [/][bold #00cc00]███[/][bold #00ff00] 1 [/][bold #00cc00]██[/]
  [bold #00cc00]▀█████████▀[/]
   [bold #00ff00]▀█▀   ▀█▀[/]  [dim]INJECTING...[/]""",
        """   [bold #00ff00]✦ ╭─────╮[/]
   [bold #00cc00]▄█████████▄[/]
  [bold #00cc00]██[/][bold #00ff00] 1 [/][bold #00cc00]███[/][bold #00ff00] 0 [/][bold #00cc00]██[/]
  [bold #00cc00]▀█████████▀[/]
   [bold #00ff00]▀█▀   ▀█▀[/]  [dim]BYPASSING...[/]""",
        """   [bold #00ff00]✦ ╭─────╮[/]
   [bold #00cc00]▄█████████▄[/]
  [bold #00cc00]██[/][bold #00ff00] █ [/][bold #00cc00]███[/][bold #00ff00] █ [/][bold #00cc00]██[/]
  [bold #00cc00]▀█████████▀[/]
   [bold #00ff00]▀█▀   ▀█▀[/]  [dim]ROOT ACCESS[/]""",
        """   [bold #00ff00]✦ ╭─────╮[/]
   [bold #00cc00]▄█████████▄[/]
  [bold #00cc00]██[/][bold #00ff00] @ [/][bold #00cc00]███[/][bold #00ff00] @ [/][bold #00cc00]██[/]
  [bold #00cc00]▀█████████▀[/]
   [bold #00ff00]▀█▀   ▀█▀[/]  [dim]PWNED ![/]""",
    ], frame_duration=0.15),

    # Celebration mode
    "celebration": MascotFrameSet([
        """    [bold #f472b6]✦ ╭─★─╮ ✦[/]
   [bold #a855f7]▄█████████▄[/]  [bold #22d3ee]🎉[/]
  [bold #a855f7]██[/][bold #f472b6] ^ [/][bold #a855f7]███[/][bold #f472b6] ^ [/][bold #a855f7]██[/]  [bold #f59e0b]🎊[/]
  [bold #a855f7]▀█████████▀[/]  [bold #22d3ee]✨[/]
    [bold #f472b6]▀█▀ ▀█▀[/]  [bold #f59e0b]🎈[/]""",
        """    [bold #f472b6]✦ ╭─★─╮ ✦[/]
   [bold #a855f7]▄█████████▄[/]  [bold #f59e0b]🎊[/]
  [bold #a855f7]██[/][bold #22d3ee] ♡ [/][bold #a855f7]███[/][bold #22d3ee] ♡ [/][bold #a855f7]██[/]  [bold #22d3ee]✨[/]
  [bold #a855f7]▀█████████▀[/]  [bold #f472b6]🎉[/]
    [bold #f472b6]▀█▀ ▀█▀[/]  [bold #f59e0b]🎈[/]""",
        """    [bold #f472b6]✦ ╭─★─╮ ✦[/]
   [bold #a855f7]▄█████████▄[/]  [bold #22d3ee]✨[/]
  [bold #a855f7]██[/][bold #f59e0b] ★ [/][bold #a855f7]███[/][bold #f59e0b] ★ [/][bold #a855f7]██[/]  [bold #f472b6]🎊[/]
  [bold #a855f7]▀█████████▀[/]  [bold #f59e0b]🎉[/]
    [bold #f472b6]▀█▀ ▀█▀[/]  [bold #22d3ee]🎈[/]""",
    ], frame_duration=0.3),

    # Dancing mode
    "dancing": MascotFrameSet([
        """    [bold #22d3ee]╭── ✦ ──╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #f472b6] < [/][bold #a855f7]███[/][bold #f472b6] > [/][bold #a855f7]██[/]  [dim]♪[/]
  [bold #a855f7]▀█████████▀[/]
    [bold #f472b6]▀█▀ ▀█▀[/]  [dim]~♫[/]""",
        """    [bold #22d3ee]╭── ✦ ──╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #f59e0b] > [/][bold #a855f7]███[/][bold #f59e0b] < [/][bold #a855f7]██[/]  [dim]~♫[/]
  [bold #a855f7]▀█████████▀[/]
    [bold #f472b6]▀█▀ ▀█▀[/]  [dim]♪[/]""",
        """    [bold #22d3ee]╭── ✦ ──╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #22d3ee] ∨ [/][bold #a855f7]███[/][bold #22d3ee] ∨ [/][bold #a855f7]██[/]  [dim]♪[/]
  [bold #a855f7]▀█████████▀[/]
    [bold #f472b6]▀█▀ ▀█▀[/]  [dim]~♫[/]""",
        """    [bold #22d3ee]╭── ✦ ──╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #f472b6] ∧ [/][bold #a855f7]███[/][bold #f472b6] ∧ [/][bold #a855f7]██[/]  [dim]~♫[/]
  [bold #a855f7]▀█████████▀[/]
    [bold #f472b6]▀█▀ ▀█▀[/]  [dim]♪[/]""",
    ], frame_duration=0.25),

    # Loading/processing
    "loading": MascotFrameSet([
        """   [bold #f59e0b]✦ ╭─────╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #22d3ee] █ [/][bold #a855f7]███[/][bold #22d3ee] ░ [/][bold #a855f7]██[/]  [dim]████████████[/]
  [bold #a855f7]▀█████████▀[/]
   [bold #f59e0b]▀█▀   ▀█▀[/]  [dim]10%[/]""",
        """   [bold #f59e0b]✦ ╭─────╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #22d3ee] █ [/][bold #a855f7]███[/][bold #22d3ee] █ [/][bold #a855f7]██[/]  [dim]████████████[/]
  [bold #a855f7]▀█████████▀[/]
   [bold #f59e0b]▀█▀   ▀█▀[/]  [dim]33%[/]""",
        """   [bold #f59e0b]✦ ╭─────╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #22d3ee] █ [/][bold #a855f7]███[/][bold #22d3ee] █ [/][bold #a855f7]██[/]  [dim]████████████[/]
  [bold #a855f7]▀█████████▀[/]
   [bold #f59e0b]▀█▀   ▀█▀[/]  [dim]66%[/]""",
        """   [bold #f59e0b]✦ ╭─────╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #22d3ee] █ [/][bold #a855f7]███[/][bold #22d3ee] █ [/][bold #a855f7]██[/]  [dim]████████████[/]
  [bold #a855f7]▀█████████▀[/]
   [bold #f59e0b]▀█▀   ▀█▀[/]  [dim]100%[/]""",
    ], frame_duration=0.4),
    "happy": MascotFrameSet([
        """    [bold #22d3ee]✦ ╭─★─╮ ✦[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #f472b6] ^ [/][bold #a855f7]███[/][bold #f472b6] ^ [/][bold #a855f7]██[/]
  [bold #a855f7]▀█████████▀[/]
    [bold #f472b6]▀█▀ ▀█▀[/]""",
        """    [bold #22d3ee]✦ ╭─★─╮ ✦[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #f472b6] ^ [/][bold #a855f7]███[/][bold #f472b6] ^ [/][bold #a855f7]██[/]
  [bold #a855f7]▀█████████▀[/]
    [bold #f472b6]▀█▀ ▀█▀[/]""",
        """    [bold #22d3ee]✦ ╭─★─╮ ✦[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #f472b6] ♡ [/][bold #a855f7]███[/][bold #f472b6] ♡ [/][bold #a855f7]██[/]
  [bold #a855f7]▀█████████▀[/]
    [bold #f472b6]▀█▀ ▀█▀[/]""",
    ], frame_duration=0.5),
    "error": MascotFrameSet([
        """   [bold #ef4444]✦ ╭─────╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #ef4444] ✕ [/][bold #a855f7]███[/][bold #ef4444] ✕ [/][bold #a855f7]██[/]
  [bold #a855f7]▀█████████▀[/]
   [bold #ef4444]▀█▀   ▀█▀[/]""",
        """   [bold #ef4444]✦ ╭─────╮[/]
   [bold #a855f7]▄█████████▄[/]
  [bold #a855f7]██[/][bold #ef4444] ✘ [/][bold #a855f7]███[/][bold #ef4444] ✘ [/][bold #a855f7]██[/]
  [bold #a855f7]▀█████████▀[/]
   [bold #ef4444]▀█▀   ▀█▀[/]""",
    ], frame_duration=0.5),
    "sleeping": MascotFrameSet([
        """    [bold #6b7280]╭─────────╮[/]
   [bold #4b5563]▄█████████▄[/]
  [bold #4b5563]██[/][bold #6b7280] - [/][bold #4b5563]███[/][bold #6b7280] - [/][bold #4b5563]██[/]
  [bold #4b5563]▀█████████▀[/]
    [bold #9ca3af]▀█▀   ▀█▀[/]
   [dim]z z z[/]""",
        """    [bold #6b7280]╭─────────╮[/]
   [bold #4b5563]▄█████████▄[/]
  [bold #4b5563]██[/][bold #6b7280] - [/][bold #4b5563]███[/][bold #6b7280] - [/][bold #4b5563]██[/]
  [bold #4b5563]▀█████████▀[/]
    [bold #9ca3af]▀█▀   ▀█▀[/]
    [dim]z z z[/]""",
    ], frame_duration=2.0),
}


class OrbitMascot(Widget):
    """Animated pixel space-orb mascot widget for OrbitCode TUI"""

    DEFAULT_CSS = """
    OrbitMascot {
        height: 7;
        width: 100%;
        content-align: center middle;
        background: transparent;
    }
    """

    # Reactive state for animation
    current_state: reactive[MascotState] = reactive(MascotState.IDLE)
    custom_frames: reactive[Optional[dict]] = reactive(None)
    style_variant: reactive[str] = reactive("full")  # full, compact, minimal
    enabled: reactive[bool] = reactive(True)

    def __init__(
        self,
        style_variant: str = "full",
        custom_frames: Optional[dict] = None,
        enabled: bool = True,
        **kwargs
    ):
        super().__init__(**kwargs)
        # Initialize all non-reactive attributes first
        self._animation_timer: Optional[Timer] = None
        self._frame_index = 0
        self._idle_timer: Optional[Timer] = None
        self._sleep_threshold = 30.0  # seconds of inactivity before sleeping
        self._last_activity = 0.0

        # Then set reactive attributes (these trigger watchers)
        self.style_variant = style_variant
        self.custom_frames = custom_frames
        # enabled is set last so watchers have all attributes available
        self.enabled = enabled

    def on_mount(self) -> None:
        """Start animation loop on mount"""
        if self.enabled:
            self._start_animation()
            self._start_idle_monitor()

    def on_unmount(self) -> None:
        """Clean up timers"""
        if self._animation_timer:
            self._animation_timer.stop()
        if self._idle_timer:
            self._idle_timer.stop()

    def _start_animation(self) -> None:
        """Start the frame animation timer"""
        self._animation_timer = self.set_interval(
            self._get_frame_duration(),
            self._animate_frame
        )

    def _start_idle_monitor(self) -> None:
        """Monitor for idle state to trigger sleeping animation"""
        self._last_activity = self.app._animation_time if hasattr(self.app, '_animation_time') else 0
        self._idle_timer = self.set_interval(5.0, self._check_idle)

    def _check_idle(self) -> None:
        """Check if we should enter sleeping state"""
        current_time = self.app._animation_time if hasattr(self.app, '_animation_time') else 0
        if current_time - self._last_activity > self._sleep_threshold:
            if self.current_state == MascotState.IDLE:
                self.current_state = MascotState.SLEEPING

    def record_activity(self) -> None:
        """Record user/agent activity to reset idle timer"""
        self._last_activity = self.app._animation_time if hasattr(self.app, '_animation_time') else 0
        if self.current_state == MascotState.SLEEPING:
            self.current_state = MascotState.IDLE

    def _get_frame_duration(self) -> float:
        """Get current frame duration based on state"""
        frames = self._get_current_frames()
        return frames.frame_duration if frames else 0.5

    def _get_current_frames(self) -> Optional[MascotFrameSet]:
        """Get frames for current state"""
        if self.custom_frames and self.current_state.value in self.custom_frames:
            return MascotFrameSet(self.custom_frames[self.current_state.value])
        return ORBIT_MASCOT_FRAMES.get(self.current_state.value)

    def _animate_frame(self) -> None:
        """Advance to next frame"""
        frames = self._get_current_frames()
        if not frames or not frames.frames:
            return

        self._frame_index = (self._frame_index + 1) % len(frames.frames)
        self.refresh()

        # Update timer interval if frame duration changed
        if self._animation_timer:
            self._animation_timer.stop()
            self._animation_timer = self.set_interval(
                self._get_frame_duration(),
                self._animate_frame
            )

    def watch_current_state(self, old_state: MascotState, new_state: MascotState) -> None:
        """React to state changes"""
        self._frame_index = 0
        if self._animation_timer:
            self._animation_timer.stop()
        if self.enabled:
            self._start_animation()
        self.refresh()

    def watch_enabled(self, enabled: bool) -> None:
        """React to enabled/disabled"""
        if enabled:
            if hasattr(self, '_animation_timer') and self._animation_timer:
                self._animation_timer.stop()
            if hasattr(self, '_idle_timer') and self._idle_timer:
                self._idle_timer.stop()
            self._start_animation()
            self._start_idle_monitor()
        else:
            if hasattr(self, '_animation_timer') and self._animation_timer:
                self._animation_timer.stop()
            if hasattr(self, '_idle_timer') and self._idle_timer:
                self._idle_timer.stop()
        self.refresh()

    def set_state(self, state: MascotState) -> None:
        """Set mascot state"""
        self.current_state = state
        self.record_activity()

    def render(self) -> str:
        """Render current frame"""
        if not self.enabled:
            return ""

        frames = self._get_current_frames()
        if not frames or not frames.frames:
            return ""

        # Get current frame
        frame = frames.frames[self._frame_index]

        # Apply style variant
        if self.style_variant == "compact":
            frame = self._make_compact(frame)
        elif self.style_variant == "minimal":
            frame = self._make_minimal(frame)

        return frame

    def _make_compact(self, frame: str) -> str:
        """Convert to compact (3-line) version"""
        lines = frame.strip().split('\n')
        if len(lines) <= 3:
            return frame
        # Keep top, middle, bottom
        return '\n'.join([lines[0], lines[len(lines)//2], lines[-1]])

    def _make_minimal(self, frame: str) -> str:
        """Convert to minimal (1-line) version"""
        lines = frame.strip().split('\n')
        if not lines:
            return ""
        # Just return the mascot face line
        for line in lines:
            if '██' in line and ('▀' in line or '●' in line or '◠' in line or '^' in line):
                return line
        return lines[0]

    # Convenience methods for state transitions
    def idle(self) -> None:
        self.set_state(MascotState.IDLE)

    def idle_rainbow(self) -> None:
        self.set_state(MascotState.IDLE_RAINBOW)

    def thinking(self) -> None:
        self.set_state(MascotState.THINKING)

    def thinking_cosmic(self) -> None:
        self.set_state(MascotState.THINKING_COSMIC)

    def tool_running(self) -> None:
        self.set_state(MascotState.TOOL_RUNNING)

    def hacker(self) -> None:
        self.set_state(MascotState.HACKER)

    def happy(self) -> None:
        self.set_state(MascotState.HAPPY)

    def celebration(self) -> None:
        self.set_state(MascotState.CELEBRATION)

    def dancing(self) -> None:
        self.set_state(MascotState.DANCING)

    def loading(self) -> None:
        self.set_state(MascotState.LOADING)

    def error(self) -> None:
        self.set_state(MascotState.ERROR)

    def sleep(self) -> None:
        self.set_state(MascotState.SLEEPING)

    # Fun personalized modes
    def go_crazy(self) -> None:
        """Activate rainbow mode - the ultimate personalized animation!"""
        self.set_state(MascotState.IDLE_RAINBOW)

    def hacker_mode(self) -> None:
        """Activate hacker/matrix mode"""
        self.set_state(MascotState.HACKER)

    def party_mode(self) -> None:
        """Activate celebration mode"""
        self.set_state(MascotState.CELEBRATION)

    def dance_mode(self) -> None:
        """Activate dancing mode"""
        self.set_state(MascotState.DANCING)


# Compact mascot frames for smaller terminals
COMPACT_MASCOT_FRAMES = {
    "idle": MascotFrameSet([
        "[bold #a855f7]▄█████████▄[/]  [bold #22d3ee]OrbitCode[/] [dim]by OrbitOmen[/]",
        "[bold #a855f7]██[/][bold #22d3ee] ● [/][bold #a855f7]███[/][bold #22d3ee] ● [/][bold #a855f7]██[/]",
        "[bold #a855f7]▀█████████▀[/]",
    ], frame_duration=1.5),
    "idle_rainbow": MascotFrameSet([
        "[bold #ff0000]▄█████████▄[/]  [bold #ff7700]OrbitCode[/] [dim]★[/]",
        "[bold #ffcc00]██[/][bold #00ff00] ● [/][bold #ffcc00]███[/][bold #00ff00] ● [/][bold #ffcc00]██[/]",
        "[bold #00ffff]▀█████████▀[/]",
        "[bold #8800ff]▄█████████▄[/]  [bold #ff0000]OrbitCode[/] [dim]✧[/]",
        "[bold #ff0000]██[/][bold #ff7700] ○ [/][bold #ff0000]███[/][bold #ff7700] ○ [/][bold #ff0000]██[/]",
        "[bold #ffcc00]▀█████████▀[/]",
    ], frame_duration=0.15),
    "thinking": MascotFrameSet([
        "[bold #a855f7]▄█████████▄[/]  [bold #22d3ee]Thinking...[/]",
        "[bold #a855f7]██[/][bold #22d3ee] ◠ [/][bold #a855f7]███[/][bold #22d3ee] ◠ [/][bold #a855f7]██[/]",
        "[bold #a855f7]▀█████████▀[/]",
    ], frame_duration=0.3),
    "thinking_cosmic": MascotFrameSet([
        "[bold #f472b6]▄█████████▄[/]  [dim]✧[/]",
        "[bold #a855f7]██[/][bold #22d3ee] ◐ [/][bold #a855f7]███[/][bold #22d3ee] ◑ [/][bold #a855f7]██[/]  [dim]✦[/]",
        "[bold #a855f7]▀█████████▀[/]  [dim]✧[/]",
    ], frame_duration=0.2),
    "tool_running": MascotFrameSet([
        "[bold #a855f7]▄█████████▄[/]  [bold #f59e0b]Running tool...[/]",
        "[bold #a855f7]██[/][bold #f59e0b] ● [/][bold #a855f7]███[/][bold #f59e0b] ● [/][bold #a855f7]██[/]",
        "[bold #a855f7]▀█████████▀[/]",
    ], frame_duration=0.2),
    "hacker": MascotFrameSet([
        "[bold #00cc00]▄█████████▄[/]  [bold #00ff00]HACKING[/]",
        "[bold #00cc00]██[/][bold #00ff00] 0 [/][bold #00cc00]███[/][bold #00ff00] 1 [/][bold #00cc00]██[/]",
        "[bold #00cc00]▀█████████▀[/]  [dim]INJECTING...[/]",
        "[bold #00cc00]▄█████████▄[/]  [bold #00ff00]ROOT[/]",
        "[bold #00cc00]██[/][bold #00ff00] @ [/][bold #00cc00]███[/][bold #00ff00] @ [/][bold #00cc00]██[/]",
        "[bold #00cc00]▀█████████▀[/]  [dim]PWNED ![/]",
    ], frame_duration=0.15),
    "happy": MascotFrameSet([
        "[bold #a855f7]▄█████████▄[/]  [bold #a855f7]Done![/]",
        "[bold #a855f7]██[/][bold #f472b6] ^ [/][bold #a855f7]███[/][bold #f472b6] ^ [/][bold #a855f7]██[/]",
        "[bold #a855f7]▀█████████▀[/]",
    ], frame_duration=0.5),
    "celebration": MascotFrameSet([
        "[bold #a855f7]▄█████████▄[/]  [bold #22d3ee]🎉[/]",
        "[bold #a855f7]██[/][bold #f472b6] ^ [/][bold #a855f7]███[/][bold #f472b6] ^ [/][bold #a855f7]██[/]  [bold #f59e0b]🎊[/]",
        "[bold #a855f7]▀█████████▀[/]  [bold #22d3ee]✨[/]",
    ], frame_duration=0.3),
    "dancing": MascotFrameSet([
        "[bold #a855f7]▄█████████▄[/]  [dim]♪[/]",
        "[bold #a855f7]██[/][bold #f472b6] < [/][bold #a855f7]███[/][bold #f472b6] > [/][bold #a855f7]██[/]  [dim]~♫[/]",
        "[bold #a855f7]▀█████████▀[/]  [dim]♪[/]",
    ], frame_duration=0.25),
    "loading": MascotFrameSet([
        "[bold #a855f7]▄█████████▄[/]  [dim]████████████ 10%[/]",
        "[bold #a855f7]██[/][bold #22d3ee] █ [/][bold #a855f7]███[/][bold #22d3ee] ░ [/][bold #a855f7]██[/]",
        "[bold #a855f7]▀█████████▀[/]  [dim]████████████ 100%[/]",
    ], frame_duration=0.4),
    "error": MascotFrameSet([
        "[bold #a855f7]▄█████████▄[/]  [bold #ef4444]Error![/]",
        "[bold #a855f7]██[/][bold #ef4444] ✕ [/][bold #a855f7]███[/][bold #ef4444] ✕ [/][bold #a855f7]██[/]",
        "[bold #a855f7]▀█████████▀[/]",
    ], frame_duration=0.5),
    "sleeping": MascotFrameSet([
        "[bold #4b5563]▄█████████▄[/]  [dim]Sleeping...[/]",
        "[bold #4b5563]██[/][bold #6b7280] - [/][bold #4b5563]███[/][bold #6b7280] - [/][bold #4b5563]██[/]  [dim]z z z[/]",
        "[bold #4b5563]▀█████████▀[/]",
    ], frame_duration=2.0),
}


# Minimal mascot frames (single line)
MINIMAL_MASCOT_FRAMES = {
    "idle": MascotFrameSet(["[bold #a855f7]●[/][bold #22d3ee]◌[/][bold #a855f7]●[/] OrbitCode"], frame_duration=0),
    "thinking": MascotFrameSet(["[bold #a855f7]◐[/][bold #22d3ee]◑[/][bold #a855f7]◐[/] Thinking..."], frame_duration=0.5),
    "tool_running": MascotFrameSet(["[bold #a855f7]●[/][bold #f59e0b]◉[/][bold #a855f7]●[/] Working..."], frame_duration=0.3),
    "happy": MascotFrameSet(["[bold #a855f7]^[/][bold #f472b6]♡[/][bold #a855f7]^[/] Done!"], frame_duration=0),
    "error": MascotFrameSet(["[bold #a855f7]✕[/][bold #ef4444]✘[/][bold #a855f7]✕[/] Error!"], frame_duration=0),
    "sleeping": MascotFrameSet(["[bold #4b5563]-[/][bold #6b7280]z[/][bold #4b5563]-[/] Sleeping"], frame_duration=0),
}


def get_mascot_frames(style: str) -> dict:
    """Get mascot frames for a given style variant"""
    if style == "compact":
        return COMPACT_MASCOT_FRAMES
    elif style == "minimal":
        return MINIMAL_MASCOT_FRAMES
    return ORBIT_MASCOT_FRAMES