import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.intelligence.report_builder import ReportBuilder


def test_sanitize_report_content_replaces_empty_markers():
    builder = ReportBuilder()
    content = """
# 每日破圈赚钱情报

- 风险提醒：无
- 中国落地价值：无
#### 历史类比 / 成熟市场参照：/
#### 可执行动作：无
- 机会判断：N/A
- 其他字段：无。
- 另一个字段：/.
- 第三个字段：N/A。
"""

    cleaned = builder.sanitize_report_content(content)

    assert "：无" not in cleaned
    assert "：/" not in cleaned
    assert "：N/A" not in cleaned
    assert "风险提醒：暂无明显风险，但仍需核实来源、真实案例和交付能力。" in cleaned
    assert "中国落地价值：暂无直接落地路径，先作为趋势观察。" in cleaned
    assert "历史类比 / 成熟市场参照：暂无明确可比历史阶段，本条更适合作为趋势观察。" in cleaned
    assert "可执行动作：暂不建议行动，本条只做趋势观察。" in cleaned
    assert "机会判断：观察中。" in cleaned
    assert "其他字段：暂无明确价值，先作为趋势观察。" in cleaned


def test_remaining_empty_markers_detects_after_sanitize_only():
    builder = ReportBuilder()
    cleaned = builder.sanitize_report_content("- 风险提醒：无\n- 中国落地价值：N/A\n- 可执行动作：/.")
    assert builder._remaining_empty_markers(cleaned) == []


def test_sanitize_report_content_removes_bare_feishu_title_leaks():
    builder = ReportBuilder()
    content = "# 每日破圈赚钱情报\n\n## 二、今日赚钱机会雷达\n\n每日破圈赚钱情报\n\n- 机会名称：测试"

    cleaned = builder.sanitize_report_content(content)

    assert "每日破圈赚钱情报 (" not in cleaned
    assert not any(line.strip() == "每日破圈赚钱情报" for line in cleaned.splitlines())
    assert cleaned.startswith("# 每日破圈赚钱情报")
