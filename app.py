from __future__ import annotations

from datetime import date
from io import StringIO

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

# Real Exchange Rate Explorer
# Assignment specification:
# S(t) = units of Country 2 currency per one unit of Country 1 currency
# RER(t) = S(t) * CPI_1(t) / CPI_2(t)
# Real_Index(t) = 100 * RER(t) / average(RER) over selected valid months
#
# IMF FX series are local-currency units per USD. Therefore:
# S = FX_2 / FX_1 (not FX_1 / FX_2).

st.set_page_config(
    page_title="Real Exchange Rate Explorer",
    page_icon="📈",
    layout="wide",
)

st.title("Real Exchange Rate Explorer")
st.caption(
    "Monthly IMF CPI and exchange-rate data, nominal exchange rates, "
    "real exchange rates, and a sample-normalized real index."
)

# Country labels are paired with IMF codes. G163 is the IMF Euro area code.
# This list is a broad set of IMF economies; availability varies by series.
COUNTRIES = {
    "Euro area": "G163",
    "United States": "USA",
    "United Kingdom": "GBR",
    "Japan": "JPN",
    "Canada": "CAN",
    "Australia": "AUS",
    "New Zealand": "NZL",
    "India": "IND",
    "China": "CHN",
    "South Korea": "KOR",
    "Singapore": "SGP",
    "Switzerland": "CHE",
    "Sweden": "SWE",
    "Norway": "NOR",
    "Denmark": "DNK",
    "Iceland": "ISL",
    "Mexico": "MEX",
    "Brazil": "BRA",
    "Chile": "CHL",
    "Colombia": "COL",
    "Peru": "PER",
    "Argentina": "ARG",
    "South Africa": "ZAF",
    "Israel": "ISR",
    "Saudi Arabia": "SAU",
    "United Arab Emirates": "ARE",
    "Thailand": "THA",
    "Indonesia": "IDN",
    "Malaysia": "MYS",
    "Philippines": "PHL",
    "Vietnam": "VNM",
    "Pakistan": "PAK",
    "Bangladesh": "BGD",
    "Sri Lanka": "LKA",
    "Poland": "POL",
    "Czechia": "CZE",
    "Hungary": "HUN",
    "Romania": "ROU",
    "Bulgaria": "BGR",
    "Croatia": "HRV",
    "Serbia": "SRB",
    "Ukraine": "UKR",
    "Russia": "RUS",
    "Türkiye": "TUR",
    "Morocco": "MAR",
    "Egypt": "EGY",
    "Nigeria": "NGA",
    "Kenya": "KEN",
    "Ghana": "GHA",
    "Ethiopia": "ETH",
    "Costa Rica": "CRI",
    "Uruguay": "URY",
    "Paraguay": "PRY",
    "Panama": "PAN",
    "Afghanistan": "AFG",
    "Albania": "ALB",
    "Algeria": "DZA",
    "Angola": "AGO",
    "Antigua and Barbuda": "ATG",
    "Armenia": "ARM",
    "Aruba": "ABW",
    "Azerbaijan": "AZE",
    "Bahamas": "BHS",
    "Bahrain": "BHR",
    "Barbados": "BRB",
    "Belarus": "BLR",
    "Belgium": "BEL",
    "Belize": "BLZ",
    "Benin": "BEN",
    "Bhutan": "BTN",
    "Bolivia": "BOL",
    "Bosnia and Herzegovina": "BIH",
    "Botswana": "BWA",
    "Brunei Darussalam": "BRN",
    "Burkina Faso": "BFA",
    "Burundi": "BDI",
    "Cabo Verde": "CPV",
    "Cambodia": "KHM",
    "Cameroon": "CMR",
    "Central African Republic": "CAF",
    "Chad": "TCD",
    "Comoros": "COM",
    "Congo": "COG",
    "Democratic Republic of the Congo": "COD",
    "Côte d'Ivoire": "CIV",
    "Cyprus": "CYP",
    "Djibouti": "DJI",
    "Dominica": "DMA",
    "Ecuador": "ECU",
    "El Salvador": "SLV",
    "Equatorial Guinea": "GNQ",
    "Eritrea": "ERI",
    "Estonia": "EST",
    "Eswatini": "SWZ",
    "Fiji": "FJI",
    "Finland": "FIN",
    "France": "FRA",
    "Gabon": "GAB",
    "Gambia": "GMB",
    "Georgia": "GEO",
    "Germany": "DEU",
    "Grenada": "GRD",
    "Guatemala": "GTM",
    "Guinea": "GIN",
    "Guinea-Bissau": "GNB",
    "Guyana": "GUY",
    "Haiti": "HTI",
    "Honduras": "HND",
    "Iran": "IRN",
    "Iraq": "IRQ",
    "Ireland": "IRL",
    "Italy": "ITA",
    "Jordan": "JOR",
    "Kazakhstan": "KAZ",
    "Kiribati": "KIR",
    "Kosovo": "XKX",
    "Kuwait": "KWT",
    "Kyrgyz Republic": "KGZ",
    "Lao P.D.R.": "LAO",
    "Latvia": "LVA",
    "Lebanon": "LBN",
    "Lesotho": "LSO",
    "Liberia": "LBR",
    "Libya": "LBY",
    "Liechtenstein": "LIE",
    "Lithuania": "LTU",
    "Luxembourg": "LUX",
    "Madagascar": "MDG",
    "Malawi": "MWI",
    "Maldives": "MDV",
    "Mali": "MLI",
    "Malta": "MLT",
    "Marshall Islands": "MHL",
    "Mauritania": "MRT",
    "Mauritius": "MUS",
    "Micronesia": "FSM",
    "Moldova": "MDA",
    "Monaco": "MCO",
    "Mongolia": "MNG",
    "Montenegro": "MNE",
    "Mozambique": "MOZ",
    "Myanmar": "MMR",
    "Namibia": "NAM",
    "Nauru": "NRU",
    "Nepal": "NPL",
    "Netherlands": "NLD",
    "Nicaragua": "NIC",
    "Niger": "NER",
    "North Macedonia": "MKD",
    "Oman": "OMN",
    "Palau": "PLW",
    "Papua New Guinea": "PNG",
    "Portugal": "PRT",
    "Qatar": "QAT",
    "Rwanda": "RWA",
    "Samoa": "WSM",
    "San Marino": "SMR",
    "São Tomé and Príncipe": "STP",
    "Senegal": "SEN",
    "Seychelles": "SYC",
    "Sierra Leone": "SLE",
    "Slovak Republic": "SVK",
    "Slovenia": "SVN",
    "Solomon Islands": "SLB",
    "Somalia": "SOM",
    "South Sudan": "SSD",
    "Sudan": "SDN",
    "Suriname": "SUR",
    "Syria": "SYR",
    "Tajikistan": "TJK",
    "Tanzania": "TZA",
    "Timor-Leste": "TLS",
    "Togo": "TGO",
    "Tonga": "TON",
    "Tunisia": "TUN",
    "Turkmenistan": "TKM",
    "Tuvalu": "TUV",
    "Uganda": "UGA",
    "Uzbekistan": "UZB",
    "Vanuatu": "VUT",
    "Venezuela": "VEN",
    "Yemen": "YEM",
    "Zambia": "ZMB",
    "Zimbabwe": "ZWE",
    "Dominican Republic": "DOM",
    "Jamaica": "JAM",
    "Trinidad and Tobago": "TTO",
    "Hong Kong SAR": "HKG",
    "Taiwan Province of China": "TWN",
}

IMF_API_ROOT = "https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA"


def month_start(value) -> pd.Timestamp:
    """Parse SDMX monthly periods such as 1976-01 or 1976-M01."""
    text = str(value).strip()
    if len(text) == 8 and text[4:6] == "-M":
        text = f"{text[:4]}-{text[6:]}-01"
    elif len(text) == 7 and text[4] == "-":
        text = f"{text}-01"
    return pd.to_datetime(text, errors="coerce")


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_imf_monthly_series(
    country_code: str,
    dataflow: str,
    key: str,
    start_period: str,
    end_period: str,
) -> pd.Series:
    """Fetch an IMF SDMX 3.0 monthly series as CSV and normalize its dates."""
    url = f"{IMF_API_ROOT}/{dataflow}/~/{key}"
    params = {
        "startPeriod": start_period,
        "endPeriod": end_period,
    }
    headers = {"Accept": "text/csv"}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=60)
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not connect to the IMF API: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text[:600].replace("\n", " ")
        raise RuntimeError(
            f"IMF returned HTTP {response.status_code} for {country_code} "
            f"{dataflow}.\nURL: {response.url}\nResponse: {detail}"
        )

    try:
        raw = pd.read_csv(StringIO(response.text))
    except Exception as exc:
        raise RuntimeError(
            f"Could not parse IMF response as CSV for {country_code} {dataflow}. "
            f"Response starts: {response.text[:250]!r}"
        ) from exc

    raw.columns = [str(c).strip().upper() for c in raw.columns]
    time_col = next(
        (c for c in ("TIME_PERIOD", "TIME", "PERIOD") if c in raw.columns),
        None,
    )
    value_col = next(
        (c for c in ("OBS_VALUE", "OBSERVED_VALUE", "VALUE") if c in raw.columns),
        None,
    )
    if time_col is None or value_col is None:
        raise RuntimeError(
            f"Unexpected IMF CSV columns for {country_code} {dataflow}: "
            f"{list(raw.columns)}. Response starts: {response.text[:250]!r}"
        )

    raw["month"] = raw[time_col].map(month_start)
    raw["value"] = pd.to_numeric(raw[value_col], errors="coerce")
    raw = raw.dropna(subset=["month", "value"])
    raw = raw[
        (raw["month"] >= pd.Timestamp(start_period + "-01"))
        & (raw["month"] <= pd.Timestamp(end_period + "-01"))
    ]

    # Guarantee exactly one observation per month. IMF monthly CPI/FX should
    # already be monthly; duplicate records are consolidated rather than
    # represented as artificial seconds on the same date.
    if not raw.empty:
        raw = raw.groupby("month", as_index=False)["value"].last()

    if raw.empty:
        raise RuntimeError(
            f"No usable monthly observations for {country_code} {dataflow} "
            f"from {start_period} to {end_period}. The series may not cover "
            "the requested dates or the IMF identifier may not be available."
        )

    result = raw.set_index("month")["value"].sort_index().astype(float)
    result.name = f"{country_code}_{dataflow}"
    return result


def fetch_country_data(
    country_code: str, start_period: str, end_period: str
) -> pd.DataFrame:
    """Fetch monthly CPI and FX series for a country/area."""
    cpi_key = f"{country_code}.CPI._T.IX.M"
    fx_key = f"{country_code}.XDC_USD.PA_RT.M"

    cpi = fetch_imf_monthly_series(
        country_code, "CPI", cpi_key, start_period, end_period
    ).rename("CPI")
    fx = fetch_imf_monthly_series(
        country_code, "ER", fx_key, start_period, end_period
    ).rename("FX_LOCAL_PER_USD")

    frame = pd.concat([cpi, fx], axis=1).sort_index()
    frame.index.name = "date"
    return frame.reset_index()


def validate_uploaded_csv(file, country_1: str, country_2: str) -> pd.DataFrame:
    """CSV upload format: date,country,cpi,fx."""
    try:
        data = pd.read_csv(file)
    except Exception as exc:
        raise ValueError(f"Could not read the uploaded CSV: {exc}") from exc

    data.columns = [str(c).strip().lower() for c in data.columns]
    required = {"date", "country", "cpi", "fx"}
    missing = required - set(data.columns)
    if missing:
        raise ValueError(
            "CSV must contain columns date,country,cpi,fx. Missing: "
            + ", ".join(sorted(missing))
        )

    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["month"] = data["date"].dt.to_period("M").dt.to_timestamp()
    data["country"] = data["country"].astype(str).str.strip().str.casefold()
    data["cpi"] = pd.to_numeric(data["cpi"], errors="coerce")
    data["fx"] = pd.to_numeric(data["fx"], errors="coerce")
    data = data.dropna(subset=["month", "country", "cpi", "fx"])
    data = data[(data["cpi"] > 0) & (data["fx"] > 0)]

    if data.empty:
        raise ValueError("The CSV contains no valid positive CPI/FX observations.")

    def select_country(name: str) -> pd.DataFrame:
        aliases = {name.casefold(), COUNTRIES[name].casefold()}
        selected = data[data["country"].isin(aliases)]
        if selected.empty:
            raise ValueError(
                f"CSV has no rows for {name}. Use either '{name}' or "
                f"'{COUNTRIES[name]}' in the country column."
            )
        return selected.groupby("month", as_index=False).last()

    first = select_country(country_1)[["month", "cpi", "fx"]].rename(
        columns={"cpi": "CPI_1", "fx": "FX_1"}
    )
    second = select_country(country_2)[["month", "cpi", "fx"]].rename(
        columns={"cpi": "CPI_2", "fx": "FX_2"}
    )
    return pd.merge(first, second, on="month", how="inner").rename(
        columns={"month": "date"}
    )


def calculate_results(
    data: pd.DataFrame, start_period: str, end_period: str
) -> pd.DataFrame:
    """Calculate S, RER and the index using only valid selected-sample months."""
    result = data.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    result = result.dropna(subset=["date", "CPI_1", "CPI_2", "FX_1", "FX_2"])
    result["date"] = result["date"].dt.to_period("M").dt.to_timestamp()
    result = result[
        (result["date"] >= pd.Timestamp(start_period + "-01"))
        & (result["date"] <= pd.Timestamp(end_period + "-01"))
    ]
    result = result.drop_duplicates("date", keep="last")
    result = result[
        (result[["CPI_1", "CPI_2", "FX_1", "FX_2"]] > 0).all(axis=1)
    ].sort_values("date")

    if result.empty:
        raise ValueError(
            "No overlapping monthly observations with positive CPI and FX "
            "values exist within the selected sample."
        )

    # IMF FX: local currency units per USD.
    # Required S: Country 2 currency units per Country 1 currency unit.
    # Thus S = FX_2 / FX_1.
    result["Nominal_S"] = result["FX_2"] / result["FX_1"]
    result["RER"] = result["Nominal_S"] * result["CPI_1"] / result["CPI_2"]

    rer_star = result["RER"].mean()
    if pd.isna(rer_star) or rer_star == 0:
        raise ValueError("The selected-sample average RER is invalid.")
    result["RER_star"] = rer_star
    result["Real_Index"] = 100.0 * result["RER"] / rer_star
    return result


# ------------------------------ User interface ------------------------------

country_names = list(COUNTRIES.keys())
left, right = st.columns(2)
with left:
    country_1 = st.selectbox(
        "Country 1", country_names,
        index=country_names.index("United Kingdom"),
    )
with right:
    country_2 = st.selectbox(
        "Country 2", country_names,
        index=country_names.index("United States"),
    )

date_col_1, date_col_2 = st.columns(2)
with date_col_1:
    start_date = st.date_input(
        "Start month",
        value=date(1976, 1, 1),
        min_value=date(1947, 1, 1),
        max_value=date.today(),
    )
with date_col_2:
    end_date = st.date_input(
        "End month",
        value=date.today().replace(day=1),
        min_value=date(1947, 1, 1),
        max_value=date.today(),
    )

chart_mode = st.radio(
    "Chart display",
    ["Real", "Nominal", "Both"],
    horizontal=True,
    help="Both displays real and nominal series on separate y-axes.",
)
data_mode = st.radio(
    "Data source",
    ["IMF API", "Upload CSV"],
    horizontal=True,
)
uploaded_file = None
if data_mode == "Upload CSV":
    st.markdown(
        "Upload one row per country per month. Required columns: "
        "`date,country,cpi,fx`. FX must be local-currency units per USD."
    )
    st.code(
        "date,country,cpi,fx\n"
        "1976-01-01,United Kingdom,0.55,0.55\n"
        "1976-01-01,United States,56.4,1.00",
        language="csv",
    )
    uploaded_file = st.file_uploader("Choose CSV", type=["csv"])

with st.expander("Calculation and data notes"):
    st.markdown(
        """
        - IMF CPI key: `{IMF country code}.CPI._T.IX.M`
        - IMF exchange-rate key: `{IMF country code}.XDC_USD.PA_RT.M`
        - Euro area IMF code: `G163`
        - IMF exchange rates are local-currency units per USD.
        - Required nominal quote: **units of Country 2 currency per one unit of Country 1 currency**.
        - Formula: `S = FX_2 / FX_1`; `RER = S × CPI_1 / CPI_2`.
        - The real index is normalized to an average of 100 over valid observations in the selected dates.
        - Coverage differs across countries and series. The app uses the common valid months and reports the actual first/last month.
        """
    )

if start_date > end_date:
    st.error("Start month must be earlier than or equal to end month.")
    st.stop()
if country_1 == country_2:
    st.error("Choose two different countries.")
    st.stop()

start_period = start_date.strftime("%Y-%m")
end_period = end_date.strftime("%Y-%m")

if st.button("Load data and calculate RER", type="primary", use_container_width=True):
    try:
        with st.spinner("Retrieving monthly observations and calculating RER..."):
            if data_mode == "IMF API":
                d1 = fetch_country_data(
                    COUNTRIES[country_1], start_period, end_period
                )
                d2 = fetch_country_data(
                    COUNTRIES[country_2], start_period, end_period
                )
                d1 = d1[["date", "CPI", "FX_LOCAL_PER_USD"]].rename(
                    columns={"CPI": "CPI_1", "FX_LOCAL_PER_USD": "FX_1"}
                )
                d2 = d2[["date", "CPI", "FX_LOCAL_PER_USD"]].rename(
                    columns={"CPI": "CPI_2", "FX_LOCAL_PER_USD": "FX_2"}
                )
                paired = pd.merge(d1, d2, on="date", how="inner")
            else:
                if uploaded_file is None:
                    st.error("Upload a CSV file before continuing.")
                    st.stop()
                paired = validate_uploaded_csv(uploaded_file, country_1, country_2)

            result = calculate_results(paired, start_period, end_period)

        st.success(
            f"Calculated using {len(result):,} valid monthly observations. "
            "The real index averages 100 over this selected valid sample."
        )
        m1, m2, m3 = st.columns(3)
        m1.metric("Valid monthly observations", f"{len(result):,}")
        m2.metric("First available month", result["date"].min().strftime("%b %Y"))
        m3.metric("Last available month", result["date"].max().strftime("%b %Y"))

        # Make gaps in the common monthly sample visible instead of silently
        # reporting only the count of valid rows.
        first_month = result["date"].min().to_period("M")
        last_month = result["date"].max().to_period("M")
        expected_months = pd.period_range(first_month, last_month, freq="M")
        observed_months = pd.PeriodIndex(result["date"].dt.to_period("M").unique(), freq="M")
        missing_months = expected_months.difference(observed_months)

        if len(missing_months):
            missing_text = ", ".join(str(month) for month in missing_months)
            st.warning(
                f"Data coverage check: {len(missing_months)} month(s) are missing "
                f"between the first and last available observations: {missing_text}. "
                "These months are excluded from the RER average and real index. "
                "Check source-series availability before interpreting the results."
            )
        else:
            st.info("Data coverage check: no missing months between the first and last available observations.")

        requested_last = pd.Period(end_period, freq="M")
        if last_month < requested_last:
            st.info(
                f"The requested end month is {requested_last}, but the latest "
                f"common valid observation is {last_month}. Later months are not "
                "included because both countries' required data are not available "
                "as a valid matched observation."
            )

        st.subheader(f"{country_1} vs {country_2}")
        if chart_mode == "Both":
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(
                go.Scatter(
                    x=result["date"], y=result["Real_Index"],
                    name="Real index (sample average = 100)", mode="lines",
                ),
                secondary_y=False,
            )
            fig.add_trace(
                go.Scatter(
                    x=result["date"], y=result["Nominal_S"],
                    name=f"Nominal S ({country_2} currency per {country_1} currency)",
                    mode="lines",
                ),
                secondary_y=True,
            )
            fig.update_yaxes(title_text="Real index (average = 100)", secondary_y=False)
            fig.update_yaxes(
                title_text=f"Nominal S ({country_2} currency per {country_1} currency)",
                secondary_y=True,
            )
            fig.update_layout(
                title="Real index and nominal exchange rate",
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            )
        else:
            fig = go.Figure()
            if chart_mode == "Real":
                fig.add_trace(
                    go.Scatter(
                        x=result["date"], y=result["Real_Index"],
                        name="Real index (sample average = 100)", mode="lines",
                    )
                )
                fig.add_hline(
                    y=100, line_dash="dash",
                    annotation_text="Selected-sample average = 100",
                )
                fig.update_layout(
                    title="Real exchange rate index",
                    yaxis_title="Real index (sample average = 100)",
                )
            else:
                fig.add_trace(
                    go.Scatter(
                        x=result["date"], y=result["Nominal_S"],
                        name="Nominal S", mode="lines",
                    )
                )
                fig.update_layout(
                    title="Nominal exchange rate",
                    yaxis_title=f"{country_2} currency per {country_1} currency",
                )
            fig.update_layout(hovermode="x unified")

        fig.update_layout(xaxis_title="Month")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Observations and calculations")
        export_columns = [
            "date", "CPI_1", "CPI_2", "FX_1", "FX_2",
            "Nominal_S", "RER", "RER_star", "Real_Index",
        ]
        st.dataframe(
            result[export_columns].round(6),
            use_container_width=True,
            hide_index=True,
        )
        csv_data = result[export_columns].to_csv(index=False, date_format="%Y-%m-%d")
        st.download_button(
            "Download all observations and calculations as CSV",
            data=csv_data.encode("utf-8"),
            file_name="real_exchange_rate_results.csv",
            mime="text/csv",
            use_container_width=True,
        )

        # Manual verification values to help the user document one calculation.
        sample = result.iloc[0]
        with st.expander("Manual verification of the first exported observation"):
            st.write(f"Month: {sample['date']:%Y-%m}")
            st.write(
                f"S = FX_2 / FX_1 = {sample['FX_2']:.6f} / "
                f"{sample['FX_1']:.6f} = {sample['Nominal_S']:.6f}"
            )
            st.write(
                f"RER = S × CPI_1 / CPI_2 = {sample['Nominal_S']:.6f} × "
                f"{sample['CPI_1']:.6f} / {sample['CPI_2']:.6f} = "
                f"{sample['RER']:.6f}"
            )
            st.write(
                f"Real Index = 100 × RER / RER* = 100 × "
                f"{sample['RER']:.6f} / {sample['RER_star']:.6f} = "
                f"{sample['Real_Index']:.6f}"
            )

    except Exception as exc:
        st.error("Could not calculate the RER.")
        st.code(str(exc))
        if data_mode == "IMF API":
            st.warning(
                "The IMF dataflow may not have the requested series for this "
                "country/date range, or the IMF service may be temporarily unavailable. "
                "The app will not fabricate missing data. Try a shorter date range or "
                "another country pair; if it still fails, share this exact error."
            )

st.caption(
    "Data source: IMF SDMX 3.0 API. Data availability and definitions vary by country. "
    "Check the exported FX units and manually verify one observation before submitting."
)
