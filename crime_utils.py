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
    """Read a CSV whose lines may have an unclosed double quote (e.g. a truncated export).

    A line with an odd number of '"' characters makes the CSV parser swallow the following
    line(s) into one field. We close the quote at the end of such lines before parsing.
    Returns (DataFrame, list_of_repaired_line_numbers)."""
    import io
    import pandas as pd

    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    repaired = [i + 1 for i, l in enumerate(lines) if l.count('"') % 2 == 1]
    fixed = [l + '"' if l.count('"') % 2 == 1 else l for l in lines]
    return pd.read_csv(io.StringIO("\n".join(fixed)), **kwargs), repaired

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
