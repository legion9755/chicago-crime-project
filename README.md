# Chicago Crime Analytics: Pandas · NumPy · Matplotlib · Seaborn · MySQL

This project works through the four use cases of the assignment on the Chicago crime data: loading
and cleaning the data and inserting it into MySQL (UC1), exploring it with charts (UC2), finding
statistical patterns (UC3), and reporting from MySQL with summary tables, queries and views (UC4).

## Project structure

```
chicago_crime_project/
├── data/                          ← the 6 CSV files
│   ├── chicago_crime_dataset.csv      (fact data, 498 crimes)
│   ├── iucr_codes.csv.csv
│   ├── chicago_city_community.csv
│   ├── chicago_district_ps_info.csv
│   ├── chicago_ward_offices.csv
│   └── chicago_police_beat_info.csv
├── sql/
│   └── 01_create_schema.sql       ← tables, primary and foreign keys
├── output/                        ← created by the notebooks
│   ├── chicago_crime_clean.pkl        cleaned data (used by notebooks 02 and 03)
│   ├── community_lookup.pkl           community names (used by notebooks 02 and 03)
│   └── figures/*.png                  all charts
├── 01_load_and_clean.ipynb
├── 02_eda_visualization.ipynb
├── 03_statistical_insights.ipynb
├── 04_mysql_reporting.ipynb
├── crime_utils.py                 ← paths, CSV reading, date parsing, DB connections, plot style
├── requirements.txt
└── .env.example                   ← copy to .env and add your MySQL password
```

## How to run

```bash
pip install -r requirements.txt
cp .env.example .env          # Windows: copy .env.example .env
#   then set MYSQL_PASSWORD in .env (the database chicago_crime_db is created automatically)
jupyter notebook
```

Run the notebooks in order, 01 → 02 → 03 → 04, each with **Restart & Run All**. Notebook 01
creates the clean data files and fills MySQL; 02 and 03 read the clean files; 04 reads from MySQL.

## Use case → notebook

| Brief task | Where |
|---|---|
| UC1.1 Load CSV, first 10 rows, schema and dtypes, rows × columns | `01` sections 1a–1c |
| UC1.2 Date to datetime, missing values, standardise categorical fields | `01` sections 2a–2d |
| UC1.3 Year, Month, DayOfWeek | `01` section 3 |
| UC1.4 NumPy % missing per column, drop columns > 50% missing | `01` section 4 |
| UC1.5 MySQL schema, write with SQLAlchemy + PyMySQL | `01` section 5 + `sql/01_create_schema.sql` |
| UC1 Q1, Q2 | `01` Questions |
| UC2.1 Crimes per year, rising or falling | `02` section 1 |
| UC2.2 Top 10 categories with counts and % | `02` section 2 |
| UC2.3 Arrest rate | `02` section 3 |
| UC2.4 Month × DayOfWeek heatmap | `02` section 4 |
| UC2.5 Top 10 community areas | `02` section 5 |
| UC2 Q1–Q3 | `02` Questions |
| UC3.1 Crimes per hour | `03` section 1 |
| UC3.2 NumPy mean per community area, box plot, IQR outliers | `03` section 2 |
| UC3.3 `.corr()` heatmap | `03` section 3 |
| UC4.1 Summary tables with MySQL Connector | `04` section 1 |
| UC4.2 Crimes per year, top 5 types with %, arrests per year | `04` section 2 |
| UC4.3 Views `vw_crime_yearly`, `vw_crime_by_category` | `04` section 3 |
| UC4.4 `pd.read_sql` on the views | `04` section 4 |
| UC4.5 Charts from MySQL data | `04` section 5 |

## Answers to the brief's questions

- **UC1 Q1, unique crime types:** 23 (`primary_type`).
- **UC1 Q2, anomalies:** every date is `%m/%d/%Y` with no time of day; the last 2 lines of the
  CSV were truncated and had to be repaired; no unparseable or future dates, no year mismatches,
  no positive longitudes and no coordinates outside Chicago. 89% of the crimes fall on 3–4 May 2016,
  with a handful going back to 2012.
- **UC2 Q1, most frequent category:** THEFT, 105 crimes (21.08%).
- **UC2 Q2, arrest rate consistent across years?** Can't be judged: only 2016 has enough crimes;
  2012–2015 have 1–4 each.
- **UC2 Q3, month with the most crime:** May, 447 crimes (89.8%), because of when the extract was taken.
- **Overall arrest rate:** 24.90%.
- **UC3 community outliers (IQR):** Austin, Near North Side, Humboldt Park.
- **UC3 hourly pattern:** every crime is at 00:00, because the supplied file has dates only.
