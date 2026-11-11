import asyncio

from eltorpedo.app import ElTorpedoApp, KeybindScreen
from eltorpedo.config import DEFAULT_KEYBINDS, Config, load_config, save_keybinds


def test_default_keybinds():
    cfg = Config()
    assert cfg.ui.action_for("q") == "request_quit"
    assert cfg.ui.action_for("question_mark") == "show_help"
    assert cfg.ui.action_for("k") == "show_keybinds"
    assert cfg.ui.action_for("nope") is None


def test_keybinds_override(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        '[ui.keybinds]\nrequest_quit = "w"\ntoggle_arm = "m"\n',
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg.ui.keybinds["request_quit"] == "w"
    assert cfg.ui.keybinds["show_help"] == DEFAULT_KEYBINDS["show_help"]
    assert cfg.ui.action_for("w") == "request_quit"
    assert cfg.ui.action_for("q") is None


def test_save_keybinds_preserves_other_sections(tmp_path):
    path = tmp_path / "config.toml"
    keybinds = dict(load_config(path).ui.keybinds)
    keybinds["request_quit"] = "w"

    save_keybinds(path, keybinds)

    text = path.read_text(encoding="utf-8")
    assert "[gamepad]" in text
    assert load_config(path).ui.keybinds["request_quit"] == "w"

    keybinds["request_quit"] = "y"
    save_keybinds(path, keybinds)

    assert [
        line for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() == "[ui.keybinds]"
    ] == ["[ui.keybinds]"]
    assert load_config(path).ui.keybinds["request_quit"] == "y"


def test_remapped_key_dispatches(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        '[ui.keybinds]\ntoggle_arm = "m"\n',
        encoding="utf-8",
    )
    app = ElTorpedoApp(load_config(path), sitl=True)

    async def scenario():
        async with app.run_test() as pilot:
            app._check_link = lambda now: None
            app.state.link_ok = True
            calls = []
            app.mav.arm = lambda value: calls.append(value)
            await pilot.press("z")
            assert calls == []
            await pilot.press("m")
            assert calls == [True]

    asyncio.run(scenario())


def test_keybind_screen_saves(tmp_path):
    path = tmp_path / "config.toml"
    app = ElTorpedoApp(load_config(path), sitl=True)

    async def scenario():
        async with app.run_test() as pilot:
            app.action_show_keybinds()
            await pilot.pause()
            assert isinstance(app.screen, KeybindScreen)
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("w")
            await pilot.pause()

    asyncio.run(scenario())

    assert app.cfg.ui.keybinds["request_quit"] == "w"
    assert 'request_quit = "w"' in path.read_text(encoding="utf-8")
