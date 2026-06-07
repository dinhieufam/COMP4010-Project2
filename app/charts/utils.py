from __future__ import annotations

import math
from collections.abc import Iterable

import pandas as pd


ISO2_TO_ISO3 = {
    "AD": "AND",
    "AE": "ARE",
    "AM": "ARM",
    "AR": "ARG",
    "AT": "AUT",
    "AU": "AUS",
    "BE": "BEL",
    "BG": "BGR",
    "BR": "BRA",
    "CA": "CAN",
    "CH": "CHE",
    "CL": "CHL",
    "CN": "CHN",
    "CO": "COL",
    "CY": "CYP",
    "CZ": "CZE",
    "DE": "DEU",
    "DK": "DNK",
    "DZ": "DZA",
    "EE": "EST",
    "ES": "ESP",
    "ET": "ETH",
    "FI": "FIN",
    "FR": "FRA",
    "GB": "GBR",
    "GR": "GRC",
    "HK": "HKG",
    "HR": "HRV",
    "HU": "HUN",
    "IE": "IRL",
    "IL": "ISR",
    "IN": "IND",
    "IQ": "IRQ",
    "IR": "IRN",
    "IS": "ISL",
    "IT": "ITA",
    "JP": "JPN",
    "KR": "KOR",
    "KZ": "KAZ",
    "LB": "LBN",
    "LK": "LKA",
    "LT": "LTU",
    "LU": "LUX",
    "MO": "MAC",
    "MX": "MEX",
    "MY": "MYS",
    "NL": "NLD",
    "NO": "NOR",
    "NZ": "NZL",
    "PA": "PAN",
    "PK": "PAK",
    "PL": "POL",
    "PT": "PRT",
    "QA": "QAT",
    "RO": "ROU",
    "RS": "SRB",
    "RU": "RUS",
    "SA": "SAU",
    "SE": "SWE",
    "SG": "SGP",
    "SI": "SVN",
    "TH": "THA",
    "TR": "TUR",
    "TW": "TWN",
    "UA": "UKR",
    "US": "USA",
    "UY": "URY",
    "VN": "VNM",
    "ZA": "ZAF",
}

COUNTRY_NAMES = {
    "AND": "Andorra",
    "ARE": "United Arab Emirates",
    "ARG": "Argentina",
    "ARM": "Armenia",
    "AUS": "Australia",
    "AUT": "Austria",
    "BEL": "Belgium",
    "BGR": "Bulgaria",
    "BRA": "Brazil",
    "CAN": "Canada",
    "CHE": "Switzerland",
    "CHL": "Chile",
    "CHN": "China",
    "COL": "Colombia",
    "CYP": "Cyprus",
    "CZE": "Czechia",
    "DEU": "Germany",
    "DNK": "Denmark",
    "DZA": "Algeria",
    "ESP": "Spain",
    "EST": "Estonia",
    "ETH": "Ethiopia",
    "FIN": "Finland",
    "FRA": "France",
    "GBR": "United Kingdom",
    "GRC": "Greece",
    "HKG": "Hong Kong",
    "HRV": "Croatia",
    "HUN": "Hungary",
    "IND": "India",
    "IRL": "Ireland",
    "IRN": "Iran",
    "IRQ": "Iraq",
    "ISL": "Iceland",
    "ISR": "Israel",
    "ITA": "Italy",
    "JPN": "Japan",
    "KAZ": "Kazakhstan",
    "KOR": "South Korea",
    "LBN": "Lebanon",
    "LKA": "Sri Lanka",
    "LTU": "Lithuania",
    "LUX": "Luxembourg",
    "MAC": "Macau",
    "MEX": "Mexico",
    "MYS": "Malaysia",
    "NLD": "Netherlands",
    "NOR": "Norway",
    "NZL": "New Zealand",
    "PAK": "Pakistan",
    "PAN": "Panama",
    "POL": "Poland",
    "PRT": "Portugal",
    "QAT": "Qatar",
    "ROU": "Romania",
    "RUS": "Russia",
    "SAU": "Saudi Arabia",
    "SGP": "Singapore",
    "SRB": "Serbia",
    "SVN": "Slovenia",
    "SWE": "Sweden",
    "THA": "Thailand",
    "TUR": "Turkey",
    "TWN": "Taiwan",
    "UKR": "Ukraine",
    "URY": "Uruguay",
    "USA": "United States",
    "VNM": "Vietnam",
    "ZAF": "South Africa",
}
COUNTRY_NAME_TO_ISO3 = {name.upper(): iso3 for iso3, name in COUNTRY_NAMES.items()}
COUNTRY_NAME_TO_ISO3.update(
    {
        "UNITED STATES OF AMERICA": "USA",
        "UNITED KINGDOM": "GBR",
        "SOUTH KOREA": "KOR",
        "CZECH REPUBLIC": "CZE",
    }
)


def split_tokens(value: object, sep: str = ",") -> list[str]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    tokens = [part.strip() for part in str(value).split(sep)]
    return [token for token in tokens if token and token != "Unknown"]


def explode_tokens(papers: pd.DataFrame, source_column: str, output_column: str) -> pd.DataFrame:
    """Explode a delimited text column into one row per token.

    Uses '|' as separator for institutions_text (to handle institution names
    that contain commas), and ',' for all other columns.
    """
    if papers.empty or source_column not in papers.columns:
        return pd.DataFrame(columns=list(papers.columns) + [output_column])
    sep = " | " if source_column == "institutions_text" else ","
    data = papers.copy()
    data[output_column] = data[source_column].apply(lambda v: split_tokens(v, sep))
    data = data.explode(output_column)
    data[output_column] = data[output_column].fillna("")
    return data[data[output_column].ne("")].copy()


def country_iso3(value: object) -> str | None:
    text = str(value).strip().upper()
    if not text or text == "UNKNOWN":
        return None
    if len(text) == 3:
        return text
    return ISO2_TO_ISO3.get(text) or COUNTRY_NAME_TO_ISO3.get(text)


def country_display(value: object) -> str:
    iso3 = country_iso3(value)
    return COUNTRY_NAMES.get(iso3 or "", str(value).strip())


def format_delta(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}"


def first_known(values: Iterable[str]) -> str:
    for value in values:
        if value and value != "Unknown":
            return value
    return "None"
