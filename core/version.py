from pathlib import Path

VERSION = Path(__file__).resolve().parent.parent.joinpath("VERSION").read_text().strip()
