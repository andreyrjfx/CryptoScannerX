from app.core.symbol_normalizer import normalize_coin


def test_known_alias_is_normalized():
    assert normalize_coin("XBT") == "BTC"
    assert normalize_coin("BCC") == "BCH"
    assert normalize_coin("BCHABC") == "BCH"
    assert normalize_coin("LUNA2") == "LUNA"


def test_unknown_coin_is_returned_uppercased():
    assert normalize_coin("sol") == "SOL"
    assert normalize_coin("ETH") == "ETH"


def test_lowercase_alias_is_normalized():
    assert normalize_coin("xbt") == "BTC"
