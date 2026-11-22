# Chicago Crime Analytics — Pandas · NumPy · Matplotlib · Seaborn · MySQL

An end-to-end data project for the four use cases:

| # | Notebook | What it does |
|---|---|---|
| 1 | `01_load_and_clean.ipynb` | Load CSVs → inspect → clean → new features → NumPy quality checks → load into MySQL |
| 2 | `02_eda_visualization.ipynb` | Yearly trend, top categories, arrest rate, month × weekday heatmap, top community areas |
| 3 | `03_statistical_insights.ipynb` | Hourly pattern, community-area stats + IQR outliers, correlation heatmap |
| 4 | `04_mysql_reporting.ipynb` | Summary tables via mysql-connector, SQL queries, views, `pd.read_sql`, charts from MySQL |

---

## 1. Project structure

```
chicago_crime_project/
├── data/                          ← your 6 CSV files (already included)
│   ├── chicago_crime_dataset.csv      (master / fact data, 498 crimes)
│   ├── iucr_codes.csv.csv             (crime code → primary_type; .csv or .csv.csv both accepted)
│   ├── chicago_city_community.csv
│   ├── chicago_district_ps_info.csv
│   ├── chicago_ward_offices.csv
│   └── chicago_police_beat_info.csv
├── sql/
│   └── 01_create_schema.sql       ← tables, primary/foreign keys, indexes
├── output/                        ← created automatically
│   ├── chicago_crime_clean.pkl        cleaned data (used by notebooks 2 & 3)
│   ├── data_quality_report.csv        every anomaly found + action taken
│   └── figures/*.png                  all charts
├── 01_load_and_clean.ipynb
├── 02_eda_visualization.ipynb
├── 03_statistical_insights.ipynb
├── 04_mysql_reporting.ipynb
├── crime_utils.py                 ← paths, DB connections, CSV repair, date parser, confidence intervals, plot style
├── tests/test_crime_utils.py      ← pytest tests for the helpers in crime_utils.py
├── requirements.txt               ← exact versions used for the committed outputs
├── requirements-lock.txt          ← full pip freeze
└── .env.example                   ← copy to .env and add your MySQL password
```

> **About the data.** `data/` contains the dataset you supplied. All answers in the notebooks are
> *computed* from it (nothing is typed in), so if you receive a bigger extract, drop it into
> `data/` and re-run 01 → 04. Section 4 below summarises the results **and the limits of this
> particular extract** — read it before presenting conclusions.

---

## 2. How to run

```bash
# 1. install libraries (a virtual environment is recommended)
#    The committed outputs were made with Python 3.14.7 and the exact versions in requirements.txt
pip install -r requirements.txt
python -m pytest -q          # optional: tests for the helper functions

# 2. MySQL 8.0+ must be running. Copy the settings file and add your password
cp .env.example .env          # Windows: copy .env.example .env
#    then edit .env -> MYSQL_PASSWORD=your_password
#    (the database chicago_crime_db is created automatically)

# 3. CSVs are already in data/  (or point CRIME_DATA_DIR at another folder)

# 4. run the notebooks IN ORDER: 01 → 02 → 03 → 04
jupyter notebook
```

Notebook 01 must run first: it creates the clean data file and fills MySQL. Notebooks 02 and 03
read the clean file, and 04 reads only from MySQL. Before committing, use **Restart & Run All** on
each notebook so the saved outputs come from one clean top-to-bottom run. To run all four from
the command line:

```bash
for nb in 01_load_and_clean 02_eda_visualization 03_statistical_insights 04_mysql_reporting; do
  jupyter nbconvert --to notebook --execute --inplace "$nb.ipynb" || break
done
```

**Common problems**

| Error | Fix |
|---|---|
| `Access denied for user` | wrong user/password in `.env` |
| `Can't connect to MySQL server` | MySQL service isn't running, or wrong host/port |
| `FileNotFoundError: None of [...] found` | CSV not in `data/` or a different file name; add the name to `FILES` in `crime_utils.py` |
| `ParserError: Expected 20 fields in line 498` | you used plain `pd.read_csv`; use `cu.read_csv_repaired` (see UC1 notes) |
| `Data too long for column` | a text value is longer than the schema allows; widen that `VARCHAR` in `01_create_schema.sql` |
| `window function` syntax error | MySQL older than 8.0; upgrade (5.7 has no `OVER()`) |
| `Cannot add or update a child row: a foreign key constraint fails` | a lookup file is missing rows; notebook 01 already nulls orphans, so make sure you re-ran it from the top |
| `Duplicate entry '0110' for key 'iucr.PRIMARY'` | an older version of the load cell only appended. The current one empties the tables first; pull the latest notebook 01 |

---

## 3. Explanation, step by step

### Use Case 1 — Load and clean

**1. Load.** `pd.read_csv` reads the file into a DataFrame. The supplied crime file's last two
lines have an unclosed quote, so `cu.read_csv_repaired` closes the quote first; otherwise pandas
raises `ParserError`. Code columns (`iucr_code`,
`fbi_code`, `case_number`) are forced to text. If pandas thought they were numbers, it would turn
`0486` into `486` and fail on `031A`. Column names are normalised to `snake_case`, and the same
names are used in MySQL.

* `df.head(10)`: first 10 rows
* `df.info()` plus a schema table: dtype, non-null count, nulls, distinct values
* `df.shape`: (rows, columns)

**2. Clean.**

* **Duplicates:** exact duplicate rows are dropped. `case_number` is the primary key, so if it
  repeats we keep the most recently updated record. `date_of_update` is parsed with the same
  multi-format parser as `date` (it's date-only here, so a fixed `%m/%d/%Y %H:%M` format would
  turn it all into NaT and the "keep the latest" sort would do nothing). Four near-duplicate
  pairs (same date, block, crime code and coordinates, different case numbers, e.g. HZ251540 and
  HZ251541) are kept: they're most likely several victims of one incident. They're logged as
  checked.
* **Date to datetime:** instead of a single `pd.to_datetime` call, which silently turns any value
  in an unexpected format into `NaT`, we try a list of known formats in order and record which one
  matched each row. That gives a direct answer to "are there date-format anomalies?". Logical
  checks follow: future dates, update-before-occurrence, and a `year` column that disagrees with
  the date.
* **Missing values:** each key field gets its own decision, following the rule "never invent
  data":

  | Field | Action | Reason |
  |---|---|---|
  | date, case_number, iucr_code | drop row | unusable without them |
  | district_code | derived from `beat_num` | each beat belongs to exactly one district, so the beat lookup gives the real answer. If a beat isn't in the lookup, the fallback `beat // 100` is a guess, and it's logged separately (0 rows needed either in this file) |
  | hour | NULL when the source has no time | a date-only value would otherwise become `hour = 0`, a fake midnight |
  | location_desc | `"UNKNOWN"` | keeps the row and makes the gap visible |
  | ward_no, community_code, lat/long | left NULL | guessing would distort area-level results |
  | arrest, domestic | False if missing | no record of an arrest |

* **Standardising categories:** `.str.strip()`, collapsing repeated spaces, and `.str.upper()`.
  For example, "Apartment" / " APARTMENT " / "apartment" become one value. IUCR codes are padded
  to 4 characters (`zfill(4)`) in both files so the join works.
* **Coordinates:** a positive longitude of the right size is a missing minus sign, so it gets
  flipped. Points outside Chicago's bounding box are set to NULL.
* **Join:** `primary_type` (the crime category) comes from `iucr_codes.csv` through a left merge
  on `iucr_code`. Codes that aren't in the lookup become `UNKNOWN` and are reported.

**3. New features.** `df['date'].dt.year / .dt.month / .dt.day_name() / .dt.hour`. The `.dt`
accessor only works once the column is a real datetime, which is why step 2 comes first. `hour`
is only filled when the source value had a time; otherwise it's NULL (in MySQL too, the column is
nullable). In this file that's every row.

**4. NumPy.** `df.isna().to_numpy()` is a True/False matrix. `np.mean(mask, axis=0) * 100` is
the percentage missing per column, because the mean of 1s and 0s is the share of 1s. Columns over
50% are selected with `pct > 50` and dropped, except protected key fields: losing `date` would
destroy the analysis, so that case needs investigating rather than deleting.

**5. MySQL.** `sql/01_create_schema.sql` builds a **star schema**: one fact table
(`chicago_crime`) and five lookup tables connected by **foreign keys**, as in the data model.
`primary_type` is stored only in `iucr` (normalisation), while year/month/day/hour are stored on
the fact table for fast reporting (a deliberate denormalisation). Data is written with
SQLAlchemy + PyMySQL `df.to_sql(...)`: **lookup tables first, fact table last**, otherwise the
foreign keys reject rows. The load cell empties the tables first (fact table first), so it can be
run again on its own. The notebook then verifies that the MySQL row counts equal the DataFrame.

**Questions answered in the notebook:** number of unique crime types (`primary_type.nunique()`),
and a full anomaly table (`output/data_quality_report.csv`).

### Use Case 2 — EDA and visualisation

* **Yearly trend:** `groupby('year').size()` plotted as a line. The rising/falling verdict comes
  from the slope of `np.polyfit(year, count, 1)`, not from eyeballing. Incomplete years are
  flagged, because a year with 3 months of data looks like a crash.
* **Top 10 categories:** `value_counts()` and `value_counts(normalize=True) * 100` give counts
  and percentages.
* **Arrest rate:** `df['arrest'].mean() * 100`, since the mean of booleans is the share that are
  True. It's also broken down by category, with a 95% Wilson confidence interval on each rate
  (`cu.wilson_ci`). The notebook also compares the extract days (3–4 May 2016) with the older,
  late-arriving records, because those older records have a much higher arrest rate.
* **Heatmap:** `pivot_table(index='month', columns='day_of_week', aggfunc='count')`, with the
  columns re-ordered Monday to Sunday and drawn with `sns.heatmap`.
* **Top community areas:** counts joined to community names, shown as a bar chart.
* **Q: most frequent category.** The first row of `value_counts()`.
* **Q: is the arrest rate consistent?** The per-year rate plus its standard deviation, range and
  trend slope. A range of more than about 3 percentage points counts as not consistent.
* **Q: highest month.** Both the total and **crimes per day** are shown, because months have
  different lengths (February). Per day means divided by the calendar days of that month, summed
  over every year the month appears in.

### Use Case 3 — Statistics and patterns

* **Hourly:** counts per known hour as a line plot, with peak and low hours and time-of-day
  bands. As a bonus, a heatmap shows the hourly *shape* of each crime type. With this file the
  chart is empty and says so, because no row has a time.
* **NumPy community stats:** `np.mean`, `np.median`, `np.std`, `np.percentile` over the 77
  per-area counts. Mean > median means the distribution is right-skewed (a few areas dominate).
  Crimes per 1,000 residents gives a fairer comparison, but most areas have only a few crimes, so
  each rate gets an exact Poisson 95% interval (`cu.poisson_ci`) and a second ranking only
  includes areas with at least 10 crimes.
* **Outliers:** IQR = Q3 − Q1, and the fences are Q1 − 1.5×IQR and Q3 + 1.5×IQR. The box plot
  uses this same rule for its dots, so the plot shows the outliers and the IQR code lists them.
  Each outlier is printed with its population rank and per-resident rate, because a high count is
  often just a big population.
* **Correlation:** `.corr()` (Pearson, −1 to +1) drawn as a masked heatmap, as the assignment
  asks. Pearson on ID codes (district, ward, community) is meaningless, so the useful part is the
  chi-square test with Cramér's V on the categorical pairs (arrest vs crime type, arrest vs
  domestic, domestic vs crime type).

### Use Case 4 — MySQL reporting

* **Summary tables** (`summary_crime_yearly`, `summary_crime_category`, `summary_community`) are
  created and loaded with **mysql-connector-python**: `cursor.execute()`, `INSERT … SELECT` so
  MySQL computes the aggregates itself, and `commit()` / `rollback()`. There is also an
  `executemany` example with `%s` placeholders, the safe way to insert Python data (it prevents
  SQL injection).
* **Queries:** crimes per year (`GROUP BY year`), top 5 types with percentages
  (`SUM(COUNT(*)) OVER ()` is a window function that gives the grand total on every row), and
  arrests per year (`SUM(arrest)`, since arrest is 0/1).
* **Views:** `vw_crime_yearly` and `vw_crime_by_category`. A view is a saved query that stores
  no data and is always up to date.
* **Pandas integration:** `pd.read_sql("SELECT * FROM vw_crime_yearly", conn)`, where `conn` is a
  SQLAlchemy connection (pandas warns when given a raw mysql-connector connection). MySQL
  `DECIMAL` values arrive as Python `Decimal` and are converted to numbers.
* **`summary_community`** starts from `city_community` and LEFT JOINs the crimes, so all 77 areas
  are there (areas with no crimes get 0). An INNER JOIN would keep only 70 and bias any average.
* **Charts from MySQL:** crimes and arrest rate on two y-axes (each year labelled with its n;
  years under 30 crimes drawn hollow and marked unreliable), category share vs arrest rate, and a
  per-capita community ranking limited to areas with at least 10 crimes, with 95% intervals.

---

## 4. Results on the supplied dataset (and what they can / can't tell you)

### Data-quality findings (Use Case 1, Q2: "anomalies in date formats or outliers?")

| Finding | Rows | Action |
|---|---|---|
| Crime CSV ends with **2 truncated lines** (unclosed `"` on the `location` field) — plain `pd.read_csv` crashes | 2 | quote closed before parsing (`read_csv_repaired`) |
| `date` has **no time of day** (`5/3/2016`), and one consistent format | 498 (all) | parsed as `%m/%d/%Y`; `hour` stored as NULL, hour analysis impossible |
| File looks Excel-saved: `m/d/yyyy` dates with no time, upper-case `TRUE`/`FALSE`. The data-portal export normally includes times, so they were most likely lost before the file was handed over | – | noted; the raw export would bring back the hourly analysis |
| Near-duplicates: same date, block, crime code and coordinates, different case numbers | 8 (4 pairs) | kept, most likely several victims of one incident |
| Data concentrated in time: **89% of crimes on 3–4 May 2016**; the rest go back to 2012 (late reports); every `date_of_update` is May 2016 | 443 | flagged — this is a snapshot, not a history |
| Missing `location_desc` | 4 | `'UNKNOWN'` |
| Missing coordinates / location | 29 (5.8%) | kept NULL |
| IUCR file: named `iucr_codes.csv.csv`; header `IUCR`, `PRIMARY_TYPE␣` (trailing space), `INDEX CODE` | – | file name accepted; headers normalised |
| IUCR codes stored without leading zero (`486` vs `0486`) | – | `zfill(4)` on both sides; 100% matched |
| Ward file: key column `ward` (not `ward_no`), extra `location_*` columns, **8 wards listed twice** (old + new office/alderman) | 8 | renamed; kept the last (newest) record. Caveat: several newer aldermen (Cruz, ward 30; Hall, ward 6; Quezada, ward 35) took office in 2023, after these 2016 crimes, so "newest" is not "in office on the crime date". Ward 27's two rows are the same person spelled two ways |
| Beat file: beat `3100` appears 3 times (identical) | 2 | de-duplicated |
| Duplicates, future dates, out-of-Chicago coordinates, `year` mismatches | 0 | checked — none found |
| Columns > 50% missing | none (max 5.8%) | nothing dropped |

**Unique crime types:** 23 `primary_type` categories (97 distinct IUCR sub-codes).

### Analysis answers

| Question | Answer from this data |
|---|---|
| Most frequent category | **THEFT** — 105 of 498 crimes (21.1%), then BATTERY (17.1%), CRIMINAL DAMAGE (9.8%) |
| Top 5 share | 63.5% of all crimes |
| Overall arrest rate | **24.9%** (124 / 498), but this is pulled up by how the extract was taken. Rows dated 3–4 May 2016 (443) have 22.3% (95% CI 18.7–26.5%); the 55 older, late-arriving rows have 45.5% (33.0–58.5%). 14 of those are dated the 1st of a month, a common stand-in for an unknown date. 22.3% is the better estimate for a typical day |
| Arrest rate by category (95% CI) | NARCOTICS 100% (89–100), CRIMINAL TRESPASS 88% (66–97), ASSAULT 28.6% (16.3–45.1), BATTERY 23.5% (15.8–33.6), ROBBERY 20.0% (9.5–37.3), THEFT 9.5% (5.3–16.6). Theft vs Battery is a real difference (Fisher's exact test p = 0.01, even though the intervals touch); Assault, Robbery, Battery and Other Offense can't be told apart (e.g. Assault vs Robbery p = 0.57) |
| Crime rising or falling over years? | **Cannot be determined.** 2016 holds 98.4% of rows and no year is complete; the upward-looking chart is an artefact of how the extract was taken |
| Arrest rate consistent across years? | **Cannot be judged.** Only 2016 has enough crimes (490); 2012–2015 have 1–4 crimes each, so their rates (0–100%) are noise |
| Month with highest frequency | **May** (447 crimes, 89.8%; 4.81 per calendar day), which reflects the extract date, not seasonality |
| Busiest heatmap cell | May / Wednesday (= 4 May 2016) |
| Hourly pattern | **Not available**: no times in the source, so `hour` is NULL for every crime |
| Top community areas | Austin (34), Near North Side (20), Humboldt Park (20), then South Shore, Englewood, South Lawndale (16 each) |
| Community outliers (IQR) | Q1 = 2, Q3 = 9, IQR = 7, upper fence 19.5 → **Austin, Near North Side, Humboldt Park**. Mostly a population effect: Near North Side is the most populous area in the lookup and Austin the 3rd; per resident they're 0.19 and 0.34 per 1,000 against a city-wide 0.18 |
| Crimes per 1,000 residents | Fuller Park tops the raw ranking on just 3 crimes (1.35, 95% CI 0.28–3.95), which overlaps most other areas. Among areas with ≥10 crimes: West Garfield Park 0.77 (0.40–1.34), Englewood 0.75 (0.43–1.21), East Garfield Park 0.58. The intervals overlap, so the order isn't reliable. Residents are the wrong denominator for the Loop and Near North Side (commuters and visitors) |
| Correlations | Pearson: arrest vs year r = −0.13 is weak, and comes entirely from the 8 pre-2016 rows (the same late-record effect), so it says nothing about time. Location codes correlate with each other (community vs latitude −0.74, district vs ward 0.72), which is geography. Chi-square / Cramér's V: arrest vs crime type V = 0.60 (strong), domestic vs crime type V = 0.58, arrest vs domestic V = 0.01 (no link) |

> **How to present this:** the pipeline, SQL and charts are complete. The honest conclusion is
> that this 498-row extract supports *composition* questions (which crimes, where, arrest
> rates by type) but not *time-trend* questions. That conclusion is itself a finding worth
> stating: spotting it is what separates analysis from charting.

---

## 5. Likely viva / interview questions

* **Why pickle instead of CSV between notebooks?** CSV loses dtypes. Datetimes come back as text
  and nullable ints as floats. Pickle keeps them exactly.
* **Why `Int64` (capital I)?** NumPy `int64` can't hold NaN, so pandas would turn the whole column
  into floats (`24.0`). `Int64` is pandas' nullable integer type.
* **Why load lookup tables before the fact table?** Foreign keys: a crime row can't reference a
  beat that doesn't exist yet.
* **Why both SQLAlchemy and mysql-connector?** The assignment asks for SQLAlchemy/PyMySQL in UC1
  (`to_sql` bulk load) and mysql-connector in UC4. SQLAlchemy is what `pandas.to_sql` /
  `read_sql` are built for, while mysql-connector is the plain DB-API driver.
* **Summary table vs view?** A summary table stores results (fast, but must be refreshed). A view
  stores only the query (always current, but recomputed on each read).
* **Why does the yearly chart say "can't determine" instead of "rising"?** A trend needs
  comparable collection each year. Here one year holds 98% of rows, so the slope measures the
  extract, not crime.
* **Why the IQR rule and not mean ± 3σ?** The IQR rule is based on quartiles, so the outliers
  themselves don't distort it. The mean and σ get pulled by extreme values.
* **Why is the overall arrest rate misleading?** Older records are only in the extract because
  something happened to them recently, and they end in arrest twice as often (45.5% vs 22.3%).
  It's the same selection effect that makes the yearly trend unreadable.
* **Why Wilson intervals and not p ± 1.96·SE?** With small n and rates near 0% or 100%, the plain
  formula gives intervals below 0 or above 100%, or zero width at 0%. Wilson behaves properly.
* **The ward file has two records for some wards. Which one is right?** Neither on its own. It's a
  slowly changing dimension: an alderman's office changes over time. The textbook fix (SCD Type
  2) keeps every record with valid-from / valid-to dates and joins each crime to the record valid
  on its date. The file has no term dates, so the notebook keeps the newest and says why that's
  imperfect.
* **Is it really a star schema?** Mostly. The fact table links to both `police_beat_info` and
  `district_ps_info`, and a beat already belongs to a district, so the district is stored twice
  (redundant, and a step towards a snowflake). It's kept because the district comes straight from
  the source file and queries by district don't need the extra join. `police_beat_info.district`
  has no foreign key to `district_ps_info`; adding one would be the next tidy-up.
