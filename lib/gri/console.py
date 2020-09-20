from rich.terminal_theme import TerminalTheme

TERMINAL_THEME = TerminalTheme(
    (13, 21, 27),
    (220, 220, 220),
    [
        (60, 68, 77),  # black
        (175, 34, 55),  # red
        (62, 179, 131),  # green
        (255, 147, 0),  # yellow
        (38, 107, 133),  # blue
        (203, 62, 118),  # magenta
        (138, 150, 168),  # cyan
        (220, 220, 220),  # white
    ],
    [  # bright
        (81, 93, 104),  # black
        (189, 37, 61),  # red
        (83, 234, 168),  # green
        (253, 227, 129),  # yellow
        (50, 157, 204),  # blue
        (242, 74, 165),  # magenta
        (175, 2195, 219),  # cyan
        (255, 255, 255),  # white
    ],
)


def link(url: str, name: str) -> str:
    return f"[link={url}]{name}[/link]"
