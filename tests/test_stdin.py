"""Channel names from Home Assistant (hassio.addon_stdin) on the add-on's stdin."""

import importlib.util
import io
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "mirtvonline" / "mirtv_stdin.py"
spec = importlib.util.spec_from_file_location("mirtv_stdin", SCRIPT)
mirtv_stdin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mirtv_stdin)


class Chunks(io.RawIOBase):
    """A pipe that hands the data over in small pieces, as stdin does."""

    def __init__(self, data: bytes, size: int = 5):
        self.parts = [data[i:i + size] for i in range(0, len(data), size)]

    def read(self, n=-1):
        return self.parts.pop(0) if self.parts else b""


def test_json_values_without_newlines_between_them():
    data = '{"play": "Первый канал", "tv": ""}"Матч ТВ"\n{"play": "x"}'.encode()
    assert list(mirtv_stdin.values(Chunks(data))) == [
        {"play": "Первый канал", "tv": ""}, "Матч ТВ", {"play": "x"}]


def test_command_takes_a_name_and_only_a_media_player():
    assert mirtv_stdin.command({"play": " Первый ", "tv": "media_player.tv"}) == {
        "channel": "Первый", "tv": "media_player.tv"}
    assert mirtv_stdin.command({"play": "A", "tv": "light.x"}) == {"channel": "A", "tv": None}
    assert mirtv_stdin.command("Матч ТВ") == {"channel": "Матч ТВ", "tv": None}
    assert mirtv_stdin.command({"tv": "media_player.tv"}) is None
    assert mirtv_stdin.command(42) is None
