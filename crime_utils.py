"""
crime_utils.py
--------------
Small shared helpers used by all four notebooks:
  * file paths
  * MySQL connection settings (read from environment variables / .env)
  * SQLAlchemy engine  (used for bulk loading + pd.read_sql)
  * mysql-connector connection (used in Use Case 4, as the assignment asks)
  * a consistent plotting style
"""
import os
from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns

# ----------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("CRIME_DATA_DIR", PROJECT_DIR / "data"))
OUTPUT_DIR = PROJECT_DIR / "output"
FIG_DIR = OUTPUT_DIR / "figures"
SQL_DIR = PROJECT_DIR / "sql"
CLEAN_CRIME_FILE = OUTPUT_DIR / "chicago_crime_clean.pkl"   # pickle keeps dtypes (datetime, bool, Int64)

for _d in (OUTPUT_DIR, FIG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# accepted file names for each dataset (the delivered IUCR file is named "iucr_codes.csv.csv")
FILES = {
    "crime": ["chicago_crime_dataset.csv"],
    "iucr": ["iucr_codes.csv", "iucr_codes.csv.csv"],
    "district": ["chicago_district_ps_info.csv"],
    "ward": ["chicago_ward_offices.csv"],
    "community": ["chicago_city_community.csv"],
    "beat": ["chicago_police_beat_info.csv"],
}


def data_file(key):
    """Return the path of a dataset, accepting any of its known file names."""
    for name in FILES[key]:
        path = DATA_DIR / name
        if path.exists():
            return path
    raise FileNotFoundError(f"None of {FILES[key]} found in {DATA_DIR}")


def read_csv_repaired(path, **kwargs):
    """Read a CSV where some lines may have an unclosed double quote (e.g. a truncated export).

    An unclosed quote makes the parser swallow the next line(s) into one field, so that record
    ends up with the wrong number of fields. Only records like that get repaired: a quote is
    closed at the end of each of their lines that has an odd number of '"'. A properly quoted
    field that spans several lines still has the right field count, so it is left alone.
    Returns (DataFrame, list_of_repaired_line_numbers)."""
    import csv
    import io
    import pandas as pd

    text = Path(path).read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    n_fields = len(next(csv.reader([lines[0]])))

    reader = csv.reader(io.StringIO(text, newline=""))
    to_fix, start = set(), 1
    for record in reader:
        end = reader.line_num                      # physical lines start..end make up this record
        if len(record) != n_fields:
            to_fix.update(n for n in range(start, end + 1) if lines[n - 1].count('"') % 2 == 1)
        start = end + 1

    fixed = [l + '"' if (i + 1) in to_fix else l for i, l in enumerate(lines)]
    frame = pd.read_csv(io.StringIO("\n".join(fixed)), **kwargs)
    bad = [r for r in csv.reader(io.StringIO("\n".join(fixed), newline="")) if len(r) != n_fields]
    if bad:
        raise ValueError(f"{len(bad)} record(s) still have the wrong number of fields after repair")
    return frame, sorted(to_fix)


# ----------------------------------------------------------------------------
# Dates
# ----------------------------------------------------------------------------
DATE_FORMATS = [
    "%m/%d/%Y %H:%M",          # 5/3/2016 23:40         (expected)
    "%m/%d/%Y %I:%M:%S %p",    # 05/03/2016 11:40:00 PM (Chicago data-portal export)
    "%m/%d/%Y %H:%M:%S",       # 05/03/2016 23:40:00
    "%Y-%m-%d %H:%M:%S",       # 2016-05-03 23:40:00    (ISO)
    "%Y-%m-%d %H:%M",
    "%m/%d/%Y",                # date only
]
DATE_ONLY_FORMATS = {"%m/%d/%Y"}


def parse_mixed_dates(series):
    """Parse a text column that may contain several date formats.
    Tries DATE_FORMATS in order. Returns (parsed_datetimes, format_used_per_row)."""
    import pandas as pd

    s = series.astype("string").str.strip()
    parsed = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    fmt_used = pd.Series(pd.NA, index=s.index, dtype="string")
    for fmt in DATE_FORMATS:
        todo = parsed.isna() & s.notna()
        if not todo.any():
            break
        attempt = pd.to_datetime(s[todo], format=fmt, errors="coerce")
        ok = attempt.dropna().index
        parsed.loc[ok] = attempt.loc[ok]
        fmt_used.loc[ok] = fmt
    return parsed, fmt_used


# ----------------------------------------------------------------------------
# Confidence intervals (small counts need them)
# ----------------------------------------------------------------------------
def wilson_ci(successes, n, z=1.96):
    """95% Wilson score interval for a proportion, returned as (low, high) in 0..1.
    Works well for small n and for rates near 0% or 100%, unlike the plain p ± 1.96·SE."""
    import numpy as np

    successes, n = np.asarray(successes, dtype=float), np.asarray(n, dtype=float)
    p = successes / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return centre - half, centre + half


def poisson_ci(count, alpha=0.05):
    """Exact (Garwood) 95% interval for a Poisson count, returned as (low, high)."""
    import numpy as np
    from scipy.stats import chi2

    count = np.asarray(count, dtype=float)
    low = np.where(count > 0, chi2.ppf(alpha / 2, 2 * count) / 2, 0.0)
    high = chi2.ppf(1 - alpha / 2, 2 * (count + 1)) / 2
    return low, high

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ----------------------------------------------------------------------------
# Database settings – edit .env (or set environment variables), never hard-code
# passwords in notebooks.
# ----------------------------------------------------------------------------
def _load_dotenv():
    env_file = PROJECT_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                v = v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":   # MYSQL_PASSWORD="abc" -> abc
                    v = v[1:-1]
                os.environ.setdefault(k.strip(), v)


_load_dotenv()

DB = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "chicago_crime_db"),
}


def get_engine(with_db: bool = True):
    """SQLAlchemy engine using the PyMySQL driver."""
    from sqlalchemy import create_engine
    from urllib.parse import quote_plus

    db = f"/{DB['database']}" if with_db else "/"
    url = (f"mysql+pymysql://{DB['user']}:{quote_plus(DB['password'])}"
           f"@{DB['host']}:{DB['port']}{db}?charset=utf8mb4")
    return create_engine(url, pool_pre_ping=True)


def get_mysql_connection():
    """Plain mysql-connector-python connection (Use Case 4 requirement)."""
    import mysql.connector

    return mysql.connector.connect(**DB)


def run_sql_file(engine, path):
    """Execute a .sql file statement by statement (statements end with ';')."""
    from sqlalchemy import text

    sql = Path(path).read_text()
    # drop comment lines, then split on ';'
    body = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))
    statements = [s.strip() for s in body.split(";") if s.strip()]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
    return len(statements)


# ----------------------------------------------------------------------------
# Plot style
# ----------------------------------------------------------------------------
def set_style():
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams.update({
        "figure.figsize": (11, 5),
        "figure.dpi": 110,
        "axes.titleweight": "bold",
        "axes.titlesize": 13,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })


def save_fig(fig, name):
    path = FIG_DIR / f"{name}.png"
    fig.savefig(path, bbox_inches="tight")
    return path
