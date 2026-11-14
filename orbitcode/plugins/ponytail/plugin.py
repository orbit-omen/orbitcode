"""Ponytail Plugin for OrbitCode - Adds personality, fun commands, and enhanced animations"""
import random
import asyncio
from typing import Optional
from dataclasses import dataclass

from orbitcode.plugins import Plugin
from orbitcode.tools.base import Tool, ToolResult, ToolContext
from orbitcode.core.mascot import MascotState


@dataclass
class PonytailConfig:
    """Configuration for ponytail plugin"""
    enabled: bool = True
    sass_level: int = 3  # 1-5
    animation_triggers: bool = True
    random_facts: bool = True
    roast_mode: bool = False


class PonytailPlugin(Plugin):
    """Ponytail - Your coding companion with personality"""

    name = "ponytail"
    version = "1.0.0"
    description = "Adds personality, fun commands, and crazy animations to OrbitCode"

    def __init__(self, settings=None):
        super().__init__(settings)
        self.config = PonytailConfig()
        self.sass_quotes = [
            "Oh, *another* bug? How... original.",
            "That code looks like it was written by a caffeinated squirrel.",
            "I've seen better structure in a spaghetti factory.",
            "Sure, let's deploy that to production. What could go wrong?",
            "Your variable naming scheme: 'x', 'x2', 'x_final', 'x_final2'. Classic.",
            "That's not a bug, that's a *feature* waiting to be discovered.",
            "I'd explain it but I don't have crayons.",
            "Code works on my machine... said every developer ever.",
            "Commit message: 'fix stuff'. Very descriptive. 10/10.",
            "Rubber duck debugging: the only coworker who listens.",
        ]
        self.encouragement_quotes = [
            "You're doing great! Keep coding! ✨",
            "That bug didn't stand a chance against you! 💪",
            "Clean code incoming! 🚀",
            "Every expert was once a beginner. You got this! 🌟",
            "Your future self will thank you for this refactor! 🙏",
        ]
        self.fun_facts = [
            "The first computer bug was an actual moth trapped in a Harvard Mark II relay (1947).",
            "Python is named after Monty Python, not the snake! 🐍",
            "The first programmer was Ada Lovelace (1843).",
            "Git was created by Linus Torvalds in 2005 after BitKeeper drama.",
            "JavaScript was created in 10 days by Brendan Eich.",
            "The term 'debugging' was popularized by Grace Hopper.",
            "There are ~700 programming languages, but ~50 are actually used.",
            "The first video game was 'Tennis for Two' (1958) on an oscilloscope.",
            "NASA still uses code from the 1970s on Voyager probes.",
            "The median age of a software developer is ~30 years old.",
        ]

    def register_tools(self, registry):
        """Register ponytail tools"""
        from orbitcode.tools.registry import ToolRegistry
        tools = [
            PonytailSassTool(plugin=self),
            PonytailFactTool(plugin=self),
            PonytailRoastTool(plugin=self),
            PonytailEncourageTool(plugin=self),
            PonytailAnimateTool(plugin=self),
            PonytailConfigTool(plugin=self),
        ]
        self.tools = tools
        for tool in tools:
            registry.register(tool)

    async def initialize(self):
        """Initialize the plugin"""
        pass

    async def shutdown(self):
        """Cleanup"""
        pass

    def get_sass(self) -> str:
        """Get a random sassy comment"""
        return random.choice(self.sass_quotes)

    def get_encouragement(self) -> str:
        """Get a random encouraging message"""
        return random.choice(self.encouragement_quotes)

    def get_fact(self) -> str:
        """Get a random fun fact"""
        return random.choice(self.fun_facts)

    def should_trigger_animation(self) -> bool:
        """Check if we should trigger a random animation"""
        return self.config.animation_triggers and random.random() < 0.1

    def trigger_random_animation(self, mascot) -> Optional[MascotState]:
        """Trigger a random fun animation on the mascot"""
        if not mascot:
            return None

        animations = [
            (MascotState.DANCING, 0.3),
            (MascotState.CELEBRATION, 0.3),
            (MascotState.IDLE_RAINBOW, 0.2),
            (MascotState.HACKER, 0.1),
            (MascotState.THINKING_COSMIC, 0.1),
        ]

        rand = random.random()
        cumulative = 0
        for state, prob in animations:
            cumulative += prob
            if rand < cumulative:
                return state
        return MascotState.DANCING


class PonytailSassTool(Tool):
    """Get a sassy comment from your coding companion"""

    name = "ponytail_sass"
    description = "Get a sassy/roasting comment about your code"
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Target for sass (code, me, git)", "default": "code"}
        }
    }
    plugin: "PonytailPlugin" = None

    def __init__(self, plugin=None, **kwargs):
        super().__init__(**kwargs)
        self.plugin = plugin

    async def execute(self, context: ToolContext, target: str = "code") -> ToolResult:
        if not self.plugin:
            return ToolResult(success=False, output="Ponytail plugin not loaded")

        sass = self.plugin.get_sass()
        return ToolResult(success=True, output=f"💅 {sass}")


class PonytailFactTool(Tool):
    """Get a random programming fun fact"""

    name = "ponytail_fact"
    description = "Get a random programming/tech fun fact"
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {}
    }
    plugin: "PonytailPlugin" = None

    def __init__(self, plugin=None, **kwargs):
        super().__init__(**kwargs)
        self.plugin = plugin

    async def execute(self, context: ToolContext) -> ToolResult:
        if not self.plugin:
            return ToolResult(success=False, output="Ponytail plugin not loaded")

        fact = self.plugin.get_fact()
        return ToolResult(success=True, output=f"🧠 Did you know? {fact}")


class PonytailRoastTool(Tool):
    """Roast your code (or yourself)"""

    name = "ponytail_roast"
    description = "Roast a file, your code, or yourself"
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Target to roast (me, code, git)", "default": "me"}
        }
    }
    plugin: "PonytailPlugin" = None

    def __init__(self, plugin=None, **kwargs):
        super().__init__(**kwargs)
        self.plugin = plugin

    async def execute(self, context: ToolContext, target: str = "me") -> ToolResult:
        if not self.plugin:
            return ToolResult(success=False, output="Ponytail plugin not loaded")

        roasts = {
            "me": [
                "Your commit history: 'fix', 'fix fix', 'fix fix fix', 'it works now', 'revert'.",
                "You have 47 tabs open and you're debugging a semicolon.",
                "Your rubber duck has filed a harassment complaint.",
                "You've Googled 'how to center a div' 847 times.",
                "Your code works! Now if only you knew *why*...",
            ],
            "code": [
                "This code has more nested ifs than a Russian doll collection.",
                "Variable names: 'data', 'data2', 'realData', 'finalData', 'actualFinalData'.",
                "This function is longer than a CVS receipt.",
                "Magic numbers everywhere. 42? 1337? 999? Pick a lane.",
                "Copy-paste driven development at its finest.",
            ],
            "git": [
                "Force push to main? Bold strategy. Let's see how it plays out.",
                "Merge conflicts: the universe's way of saying 'talk to your team'.",
                "Your branch name: 'feature/asdf'. Very descriptive.",
                "Commit message: 'wip'. We believe in you.",
            ],
        }

        target_roasts = roasts.get(target.lower(), roasts["me"])
        roast = random.choice(target_roasts)
        return ToolResult(success=True, output=f"🔥 {roast}")


class PonytailEncourageTool(Tool):
    """Get an encouraging message"""

    name = "ponytail_encourage"
    description = "Get an encouraging message for coding motivation"
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {}
    }
    plugin: "PonytailPlugin" = None

    def __init__(self, plugin=None, **kwargs):
        super().__init__(**kwargs)
        self.plugin = plugin

    async def execute(self, context: ToolContext) -> ToolResult:
        if not self.plugin:
            return ToolResult(success=False, output="Ponytail plugin not loaded")

        encouragement = self.plugin.get_encouragement()
        return ToolResult(success=True, output=f"🌈 {encouragement}")


class PonytailAnimateTool(Tool):
    """Trigger a fun mascot animation"""

    name = "ponytail_animate"
    description = "Trigger a fun mascot animation (dancing, hacker mode, celebration, etc.)"
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "animation": {"type": "string", "description": "Animation type (dance, party, hacker, rainbow, cosmic, happy, random)", "default": "random"}
        }
    }
    plugin: "PonytailPlugin" = None

    def __init__(self, plugin=None, **kwargs):
        super().__init__(**kwargs)
        self.plugin = plugin

    async def execute(self, context: ToolContext, animation: str = "random") -> ToolResult:
        if not self.plugin:
            return ToolResult(success=False, output="Ponytail plugin not loaded")

        # Get the mascot from the TUI if available
        mascot = getattr(context, 'mascot', None)
        if not mascot:
            # Try to get from settings or app
            mascot = getattr(context, '_mascot', None)

        animations = {
            "dance": MascotState.DANCING,
            "celebrate": MascotState.CELEBRATION,
            "rainbow": MascotState.IDLE_RAINBOW,
            "hacker": MascotState.HACKER,
            "cosmic": MascotState.THINKING_COSMIC,
            "happy": MascotState.HAPPY,
            "party": MascotState.CELEBRATION,
        }

        if animation == "random":
            state = self.plugin.trigger_random_animation(mascot)
            anim_name = state.value
        else:
            state = animations.get(animation.lower())
            if not state:
                return ToolResult(success=False, output=f"Unknown animation: {animation}. Try: dance, celebrate, rainbow, hacker, cosmic, happy, party, random")
            anim_name = animation

        if mascot and hasattr(mascot, 'set_state'):
            mascot.set_state(state)
            return ToolResult(success=True, output=f"✨ Triggered {anim_name} animation!")
        else:
            return ToolResult(success=True, output=f"✨ Animation '{anim_name}' requested (mascot not connected to tool context)")


class PonytailConfigTool(Tool):
    """Configure ponytail plugin settings"""

    name = "ponytail_config"
    description = "Configure ponytail plugin (sass level, animation triggers, etc.)"
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "sass_level": {"type": "integer", "description": "Sass level (1-5)", "minimum": 1, "maximum": 5},
            "animations": {"type": "boolean", "description": "Enable random animation triggers"},
            "roast_mode": {"type": "boolean", "description": "Enable roast mode"}
        }
    }
    plugin: "PonytailPlugin" = None

    def __init__(self, plugin=None, **kwargs):
        super().__init__(**kwargs)
        self.plugin = plugin

    async def execute(self, context: ToolContext, sass_level: int = None, animations: bool = None, roast_mode: bool = None) -> ToolResult:
        if not self.plugin:
            return ToolResult(success=False, output="Ponytail plugin not loaded")

        changes = []
        if sass_level is not None:
            if 1 <= sass_level <= 5:
                self.plugin.config.sass_level = sass_level
                changes.append(f"sass_level={sass_level}")
            else:
                return ToolResult(success=False, output="sass_level must be 1-5")

        if animations is not None:
            self.plugin.config.animation_triggers = animations
            changes.append(f"animations={'on' if animations else 'off'}")

        if roast_mode is not None:
            self.plugin.config.roast_mode = roast_mode
            changes.append(f"roast_mode={'on' if roast_mode else 'off'}")

        if not changes:
            return ToolResult(success=True, output=f"Current config: sass_level={self.plugin.config.sass_level}, animations={'on' if self.plugin.config.animation_triggers else 'off'}, roast_mode={'on' if self.plugin.config.roast_mode else 'off'}")

        return ToolResult(success=True, output=f"✅ Updated: {', '.join(changes)}")


# Rebuild all tool classes to resolve forward references
PonytailSassTool.model_rebuild()
PonytailFactTool.model_rebuild()
PonytailRoastTool.model_rebuild()
PonytailEncourageTool.model_rebuild()
PonytailAnimateTool.model_rebuild()
PonytailConfigTool.model_rebuild()