"""Tests for the detection of text invented by the OCR model (src/ncse/invented.py, D-017)."""

from ncse.invented import invented_reason, repeated_share

SETTINGS = {"token_limit": 2000, "repeat_ngram": 8, "repeat_share": 0.3}

REAL = ("Critics are not the legislators, but the judges and police of literature. They do not make laws; "
        "they interpret and try to enforce them. The volume before us is a pleasant one, written with care, "
        "and the author has a fine ear for the cadence of English prose, though his plot is somewhat thin.")
LOOP = "The poem is a very different kind of poem from the long-winded productions of the land. " * 12


def test_real_prose_has_no_repetition():
    assert repeated_share(REAL, 8) == 0.0


def test_loop_has_high_repetition():
    assert repeated_share(LOOP, 8) > 0.8


def test_dot_leaders_and_numbers_are_not_repetition():
    contents = "MAGAZINES. " + "... " * 200 + " ".join(str(i) for i in range(400, 600))
    assert repeated_share(contents, 8) == 0.0


def test_short_text_is_not_judged():
    assert repeated_share("a b c a b c", 8) == 0.0


def test_output_limit():
    assert invented_reason(REAL, 2000, 1, SETTINGS).startswith("output limit")
    assert invented_reason(REAL, 4000, 2, SETTINGS).startswith("output limit")
    assert invented_reason(REAL, 2500, 2, SETTINGS) is None  # only one of two parts may have reached the limit


def test_loop_reason():
    assert invented_reason(LOOP, 300, 1, SETTINGS).startswith("loop")


def test_real_text_passes():
    assert invented_reason(REAL, 120, 1, SETTINGS) is None
