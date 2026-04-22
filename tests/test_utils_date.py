from utils.date import extract_year


def test_extract_year_basic():
    assert extract_year(None) == ""
    assert extract_year("") == ""
    assert extract_year("Born 12 APR 1980") == "1980"
    assert extract_year("d. 5 May 2005") == "2005"


def test_extract_year_multiple():
    assert extract_year("Between 1890 and 1910") == "1890"  # first match
    assert extract_year("no year here") == ""
