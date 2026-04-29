"""Rich-based prompt helpers with defaults and validation."""

from __future__ import annotations

from rich.prompt import Confirm, Prompt

from platformforge.ui.console import console


def ask(
    prompt: str,
    default: str = "",
    password: bool = False,
) -> str:
    """Prompt for text input.  Returns *default* if the user presses Enter."""
    display_default = default if not password else ("[stored]" if default else None)
    result = Prompt.ask(
        prompt,
        console=console,
        default=display_default,
        password=password,
    )
    # Rich returns the default display string if the user hits Enter.
    # If it was a password with "[stored]", map it back to the real default.
    if password and result == "[stored]":
        return default
    return result.strip() if result else default


def ask_confirm(prompt: str, default: bool = True) -> bool:
    """Prompt for a yes/no confirmation."""
    return Confirm.ask(prompt, console=console, default=default)


def ask_choice(prompt: str, choices: list[str], default: str = "") -> str:
    """Prompt for a choice from a list.  Returns the chosen string."""
    result = Prompt.ask(
        prompt,
        console=console,
        choices=choices,
        default=default or choices[0],
    )
    return result
