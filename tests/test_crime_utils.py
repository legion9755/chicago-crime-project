"""Tests for the helpers in crime_utils.py.  Run with:  python -m pytest -q"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import crime_utils as cu  # noqa: E402


# --- read_csv_repaired ------------------------------------------------------------
def test_repairs_truncated_last_lines(tmp_path):
    # the last two lines each open a quote that never closes (a cut-off export)
    f = tmp_path / "trunc.csv"
    f.write_text('id,name,loc\n1,a,"(1, 2)"\n2,b,"(3, 4)\n3,c,"(5, 6)\n', encoding="utf-8")
    df, fixed = cu.read_csv_repaired(f)
    assert fixed == [3, 4]
    assert len(df) == 3
    assert df["loc"].tolist() == ["(1, 2)", "(3, 4)", "(5, 6)"]


def test_leaves_valid_multiline_field_alone(tmp_path):
    # a correctly quoted field that spans two lines: each line has an odd number of quotes,
    # but the record has the right number of fields, so nothing should be "fixed"
    f = tmp_path / "multi.csv"
    f.write_text('id,note,x\n1,"line one\nline two",7\n2,plain,8\n', encoding="utf-8")
    df, fixed = cu.read_csv_repaired(f)
    assert fixed == []
    assert df.loc[0, "note"] == "line one\nline two"
    assert df["x"].tolist() == [7, 8]


# --- parse_mixed_dates ------------------------------------------------------------
def test_parse_mixed_dates_tries_each_format():
    s = pd.Series(["5/3/2016 23:40", "05/03/2016 11:40:00 PM", "2016-05-03 23:40:00",
                   "5/10/2016", "not a date", None])
    parsed, fmt = cu.parse_mixed_dates(s)
    assert parsed.iloc[0] == pd.Timestamp("2016-05-03 23:40")
    assert parsed.iloc[1] == pd.Timestamp("2016-05-03 23:40")
    assert parsed.iloc[2] == pd.Timestamp("2016-05-03 23:40")
    assert parsed.iloc[3] == pd.Timestamp("2016-05-10")
    assert fmt.iloc[3] in cu.DATE_ONLY_FORMATS
    assert pd.isna(parsed.iloc[4]) and pd.isna(parsed.iloc[5])


def test_date_only_values_sort_correctly():
    # the bug this guards against: parsing a date-only column with a date+time format
    # turns everything into NaT, so "keep the latest update" silently does nothing
    parsed, _ = cu.parse_mixed_dates(pd.Series(["5/10/2016", "5/2/2016", "12/1/2015"]))
    assert parsed.notna().all()
    assert parsed.idxmax() == 0


# --- confidence intervals ---------------------------------------------------------
def test_wilson_ci_matches_known_values():
    low, high = cu.wilson_ci(10, 105)           # theft: 10 arrests out of 105
    assert low == pytest.approx(0.0526, abs=1e-3)
    assert high == pytest.approx(0.1665, abs=1e-3)
    low, high = cu.wilson_ci(0, 5)              # 0% must not give a zero-width interval
    assert low == pytest.approx(0, abs=1e-12) and high > 0.4


def test_poisson_ci_matches_known_values():
    low, high = cu.poisson_ci(np.array([0, 3]))
    assert low[0] == 0
    assert low[1] == pytest.approx(0.6187, abs=1e-3)
    assert high[1] == pytest.approx(8.7673, abs=1e-3)
