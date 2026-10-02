from scripts.collect_periodicals import publisher_for

def test_publisher_mapping():
    assert publisher_for("Guardian Weekly - 1 October 2026.pdf") == "هفته‌نامه گاردین"
    assert publisher_for("WSJ_0210.pdf") == "وال‌استریت ژورنال"
    assert publisher_for("The Economist October 2026.pdf") == "اکونومیست"
    assert publisher_for("unknown.pdf") is None
