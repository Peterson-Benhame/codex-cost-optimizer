from pathlib import Path


SKILL=Path(__file__).parents[1]/"SKILL.md"


def test_skill_frontmatter_and_core_contract():
    text=SKILL.read_text(encoding="utf-8")
    assert "name: codex-cost-optimizer" in text
    assert "description: Use when" in text
    lower=text.lower()
    assert "autorização explícita" in lower
    assert "zero-token" in lower
    assert "uma recomendação" in lower
    assert "configuração global" in lower
    assert "cco" in lower
