import pytest

from app import theme


def test_resolve_none_returns_default_preset() -> None:
    r = theme.resolve(None)
    assert r["preset"] == "default"
    assert r["font_family"] == "Inter"
    assert r["font_scale"] == 1.0
    assert r["border"] == "1px solid #000"
    assert r["cell_padding"] == "4px"


def test_resolve_empty_dict_returns_default_preset() -> None:
    r = theme.resolve({})
    assert r["preset"] == "default"


def test_resolve_known_preset() -> None:
    r = theme.resolve({"preset": "editorial"})
    assert r["preset"] == "editorial"
    assert r["font_family"] == "Source Serif 4"
    assert r["font_scale"] == 1.1
    assert r["border"] == "none"
    assert r["cell_padding"] == "8px"


def test_resolve_override_takes_precedence_over_preset() -> None:
    r = theme.resolve({"preset": "editorial", "font_family": "JetBrains Mono"})
    assert r["font_family"] == "JetBrains Mono"
    # Other axes still come from editorial preset
    assert r["font_scale"] == 1.1
    assert r["border"] == "none"


def test_resolve_null_override_falls_back_to_preset() -> None:
    r = theme.resolve({"preset": "terminal", "font_family": None, "density": None})
    assert r["font_family"] == "JetBrains Mono"
    assert r["cell_padding"] == "2px"  # terminal = dense


def test_resolve_unknown_preset_falls_back_to_default() -> None:
    r = theme.resolve({"preset": "nonsense"})
    assert r["preset"] == "default"


def test_resolve_includes_font_face_css() -> None:
    r = theme.resolve(None)
    assert "@font-face" in r["font_face_css"]
    assert "Inter" in r["font_face_css"]


def test_resolve_with_custom_font_url_injects_import() -> None:
    r = theme.resolve({"custom_font_url": "https://example.com/fonts.css"})
    assert "@import url('https://example.com/fonts.css');" in r["font_face_css"]


def test_validate_accepts_none() -> None:
    theme.validate(None)


def test_validate_accepts_empty() -> None:
    theme.validate({})


def test_validate_accepts_complete_object() -> None:
    theme.validate({
        "preset": "soft",
        "font_family": "Lora",
        "font_scale": 1.2,
        "border_style": "divider",
        "density": "roomy",
    })


def test_validate_rejects_unknown_key() -> None:
    with pytest.raises(theme.InvalidTheme, match="unknown theme keys"):
        theme.validate({"bogus": "x"})


def test_validate_rejects_unknown_preset() -> None:
    with pytest.raises(theme.InvalidTheme, match="unknown preset"):
        theme.validate({"preset": "nope"})


def test_validate_rejects_unknown_font_family() -> None:
    with pytest.raises(theme.InvalidTheme, match="unknown font_family"):
        theme.validate({"font_family": "Comic Sans"})


def test_validate_rejects_unknown_border_style() -> None:
    with pytest.raises(theme.InvalidTheme, match="unknown border_style"):
        theme.validate({"border_style": "double-dashed"})


def test_validate_rejects_unknown_density() -> None:
    with pytest.raises(theme.InvalidTheme, match="unknown density"):
        theme.validate({"density": "extreme"})


@pytest.mark.parametrize("bad", [0.4, 2.1, "1.0", True])
def test_validate_rejects_bad_font_scale(bad) -> None:
    with pytest.raises(theme.InvalidTheme):
        theme.validate({"font_scale": bad})


def test_list_presets_includes_all_four() -> None:
    names = [p["name"] for p in theme.list_presets()]
    assert set(names) == {"default", "editorial", "terminal", "soft"}
