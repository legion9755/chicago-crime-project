-- =====================================================================
-- 01_create_schema.sql
-- Chicago Crime - normalized schema that follows the assignment's data
-- model: one fact table (chicago_crime) + five lookup (dimension) tables.
-- Run order matters: lookup tables first, fact table last (foreign keys).
-- =====================================================================

-- Drop in reverse dependency order so the script can be re-run safely
DROP VIEW  IF EXISTS vw_crime_yearly;
DROP VIEW  IF EXISTS vw_crime_by_category;
DROP TABLE IF EXISTS chicago_crime;
DROP TABLE IF EXISTS iucr;
DROP TABLE IF EXISTS police_beat_info;
DROP TABLE IF EXISTS district_ps_info;
DROP TABLE IF EXISTS ward_office;
DROP TABLE IF EXISTS city_community;

-- ---------------------------------------------------------------------
-- Lookup: Illinois Uniform Crime Reporting codes
-- ---------------------------------------------------------------------
CREATE TABLE iucr (
    iucr_code     VARCHAR(4)   NOT NULL,
    primary_type  VARCHAR(64)  NOT NULL,
    description   VARCHAR(128),
    index_code    CHAR(1),
    PRIMARY KEY (iucr_code),
    INDEX idx_iucr_primary_type (primary_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- Lookup: community areas (77 in Chicago)
-- ---------------------------------------------------------------------
CREATE TABLE city_community (
    community_code    INT           NOT NULL,
    community_name    VARCHAR(64)   NOT NULL,
    population        INT,
    area_sqmile       DECIMAL(8,2),
    area_sqkm         DECIMAL(8,2),
    density_per_sqmi  DECIMAL(12,2),
    density_per_sqkm  DECIMAL(12,2),
    PRIMARY KEY (community_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- Lookup: police districts / stations
-- ---------------------------------------------------------------------
CREATE TABLE district_ps_info (
    district_code  INT           NOT NULL,
    district_name  VARCHAR(64)   NOT NULL,
    address        VARCHAR(128),
    city           VARCHAR(32),
    state          CHAR(2),
    zip            VARCHAR(10),
    website        VARCHAR(255),
    phone          VARCHAR(40),
    fax            VARCHAR(40),
    tty            VARCHAR(40),
    x_coordinate   DECIMAL(14,3),
    y_coordinate   DECIMAL(14,3),
    latitude       DECIMAL(11,8),
    longitude      DECIMAL(11,8),
    location       VARCHAR(64),
    PRIMARY KEY (district_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- Lookup: ward (city council) offices
-- (the delivered file also has location_address/city/state/zip columns)
-- ---------------------------------------------------------------------
CREATE TABLE ward_office (
    ward_no            INT           NOT NULL,
    alderman           VARCHAR(64),
    address            VARCHAR(128),
    city               VARCHAR(32),
    state              CHAR(2),
    zipcode            VARCHAR(10),
    ward_phone         VARCHAR(40),
    ward_fax           VARCHAR(40),
    email              VARCHAR(128),
    website            VARCHAR(255),
    location           VARCHAR(64),
    location_address   VARCHAR(128),
    location_city      VARCHAR(32),
    location_state     CHAR(2),
    location_zip       VARCHAR(10),
    city_hall_address  VARCHAR(128),
    city_hall_city     VARCHAR(32),
    city_hall_state    CHAR(2),
    city_hall_zipcode  VARCHAR(10),
    city_hall_phone    VARCHAR(40),
    PRIMARY KEY (ward_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- Lookup: police beats  (3-5 beats = sector, 3 sectors = district)
-- ---------------------------------------------------------------------
CREATE TABLE police_beat_info (
    beat_num  INT NOT NULL,
    district  INT,
    sector    INT,
    beat      INT,
    PRIMARY KEY (beat_num)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- Fact table: one row per reported incident
-- case_number is the PK (as in the data model); id is kept UNIQUE.
-- year / month / day_of_week / hour are derived columns stored for fast
-- reporting (a deliberate, documented denormalization).
-- ---------------------------------------------------------------------
CREATE TABLE chicago_crime (
    id              BIGINT        NOT NULL,
    case_number     VARCHAR(12)   NOT NULL,
    date            DATETIME      NOT NULL,
    block           VARCHAR(64),
    iucr_code       VARCHAR(4)    NOT NULL,
    location_desc   VARCHAR(80),
    arrest          TINYINT(1)    NOT NULL DEFAULT 0,
    domestic        TINYINT(1)    NOT NULL DEFAULT 0,
    beat_num        INT,
    district_code   INT,
    ward_no         INT,
    community_code  INT,
    fbi_code        VARCHAR(4),
    x_coordinate    INT,
    y_coordinate    INT,
    year            SMALLINT      NOT NULL,
    month           TINYINT       NOT NULL,
    day_of_week     VARCHAR(9)    NOT NULL,
    hour            TINYINT       NULL,      -- NULL when the source date has no time of day
    date_of_update  DATETIME,
    latitude        DECIMAL(11,8),
    longitude       DECIMAL(11,8),
    location        VARCHAR(64),
    PRIMARY KEY (case_number),
    UNIQUE KEY uq_crime_id (id),
    INDEX idx_crime_year (year),
    INDEX idx_crime_year_month (year, month),
    INDEX idx_crime_community (community_code),
    CONSTRAINT fk_crime_iucr      FOREIGN KEY (iucr_code)      REFERENCES iucr(iucr_code),
    CONSTRAINT fk_crime_beat      FOREIGN KEY (beat_num)       REFERENCES police_beat_info(beat_num),
    CONSTRAINT fk_crime_district  FOREIGN KEY (district_code)  REFERENCES district_ps_info(district_code),
    CONSTRAINT fk_crime_ward      FOREIGN KEY (ward_no)        REFERENCES ward_office(ward_no),
    CONSTRAINT fk_crime_community FOREIGN KEY (community_code) REFERENCES city_community(community_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
