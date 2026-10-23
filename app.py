import io
from datetime import date

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# ------------------------------------------------------------
# Real Exchange Rate Explorer
# ------------------------------------------------------------
# CSV upload format:
# date,country,cpi,fx
# 1999-01-01,Euro area,75.2,0.86
# 1999-01-01,United States,166.6,1.00
#
# FX must be expressed as local-currency units per USD.
# Example: for the euro area, USD/EUR quoted as EUR per USD.
# The app calculates:
# Nominal_S = FX_1 / FX_2
# RER = Nominal_S * CPI_1 / CPI_2
#
# Important: IMF SDMX dataflow identifiers and dimensions can change.
# If the IMF request is rejected, use the CSV upload option. The app
# displays the failing URL and IMF's response to help diagnose it.

st.set_page_config(
    page_title="Real Exchange Rate Explorer",
    page_icon="📈",
    layout="wide",
)

st.title("📈 Real Exchange Rate Explorer")
st.write(
    "Compare monthly consumer prices and exchange rates, calculate a "
    "bilateral real exchange rate (RER), and inspect its movement over time."
)

with st.expander("How the calculation works", expanded=False):
    st.markdown(
        """
        The app uses the following convention:

        - **FX** = local-currency units per US dollar.
        - **Nominal exchange-rate ratio** = FX for Country 1 divided by FX for Country 2.
        - **RER** = nominal exchange-rate ratio × CPI of Country 1 ÷ CPI of Country 2.
        - **Real index** = RER divided by its average over the selected sample, multiplied by 100.

        An index above 100 means the calculated RER is above its own sample average;
        below 100 means it is below its sample average. Interpretation depends on
        the exchange-rate quotation and CPI series used.
        """
    )

st.warning(
    "For meaningful comparisons, use compatible CPI measures and the same "
    "frequency for both countries. Exchange rates must be local-currency units "
    "per USD. If the IMF API does not return the requested series, upload a CSV."
)

# -------------------- Sidebar controls --------------------

st.sidebar.header("Selection")

country_options = {
    "Euro area": "G163",
    "United States": "USA",
    "United Kingdom": "GBR",
    "Japan": "JPN",
    "Canada": "CAN",
    "Australia": "AUS",
    "India": "IND",
    "China": "CHN",
    "Switzerland": "CHE",
    "Mexico": "MEX",
    "Brazil": "BRA",
    "South Korea": "KOR",
    "New Zealand": "NZL",
    "Sweden": "SWE",
    "Norway": "NOR",
    "Denmark": "DNK",
    "Singapore": "SGP",
    "South Africa": "ZAF",
}

country_names = list(country_options.keys())
default_country_1 = country_names.index("Euro area")
default_country_2 = country_names.index("United States")

country_1 = st.sidebar.selectbox(
    "Country 1",
    country_names,
    index=default_country_1,
)
country_2 = st.sidebar.selectbox(
    "Country 2",
    country_names,
    index=default_country_2,
)

start_date = st.sidebar.date_input(
    "Start date",
    value=date(1999, 1, 1),
    min_value=date(1947, 1, 1),
    max_value=date.today(),
)
end_date = st.sidebar.date_input(
    "End date",
    value=date.today().replace(day=1),
    min_value=date(1947, 1, 1),
    max_value=date.today(),
)

data_source = st.sidebar.radio(
    "Data source",
    ["Try IMF API", "Upload CSV"],
    index=0,
)

st.sidebar.caption(
    "The country list is illustrative. IMF coverage and identifiers vary by series."
)

# -------------------- Data retrieval helpers --------------------

# IMF SDMX 3.0 API root. Individual dataflows / keys may vary.
IMF_API_BASE = "https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA"


def _monthly_date(value):
    """Convert common monthly SDMX period formats into a timestamp."""
    text = str(value).strip()
    if len(text) == 7 and text[4] == "-":
        # YYYY-MM
        text = f"{text}-01"
    elif len(text) == 8 and text[4] == "M":
        # YYYY-Mmm, e.g. 2020-M01
        text = f"{text[:4]}-{text[5:]}-01"
    return pd.to_datetime(text, errors="coerce")


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_imf_series(
    country_code: str,
    series_type: str,
    start_period: str,
    end_period: str,
) -> pd.Series:
    """
    Request one monthly IMF series using SDMX 3.0 and CSV output.

    NOTE: IMF series identifiers differ across dataflows. The CPI key below
    follows the dot-separated CPI example. The exchange-rate dataflow/key is
    a best-effort candidate and may need updating if IMF changes its catalogue.
    """
    if series_type == "CPI":
        flow = "CPI"
        key = f"{country_code}.CPI._T.IX.M"
    elif series_type == "FX":
        flow = "ER"
        key = f"{country_code}.XDC_USD.PA_RT.M"
    else:
        raise ValueError("series_type must be 'CPI' or 'FX'")

    url = f"{IMF_API_BASE}/{flow}/~/{key}"
    params = {
        "startPeriod": start_period,
        "endPeriod": end_period,
    }
    headers = {"Accept": "text/csv"}

    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=45,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not connect to the IMF API: {exc}") from exc

    if response.status_code >= 400:
        body = response.text[:700].replace("\n", " ")
        raise RuntimeError(
            f"IMF returned HTTP {response.status_code} for {country_code} {series_type}.\n\n"
            f"Request URL: {response.url}\n\n"
            f"Response: {body}"
        )

    try:
        raw = pd.read_csv(io.StringIO(response.text))
    except Exception as exc:
        raise RuntimeError(
            f"Could not parse the IMF response as CSV for {country_code} {series_type}. "
            f"The response may not be CSV. Response begins: {response.text[:300]!r}"
        ) from exc

    raw.columns = [str(column).strip().upper() for column in raw.columns]

    # IMF CSV output can vary by endpoint/version, so look for common names.
    time_candidates = ["TIME_PERIOD", "TIME", "PERIOD"]
    value_candidates = ["OBS_VALUE", "OBSERVED_VALUE", "VALUE"]

    time_col = next((c for c in time_candidates if c in raw.columns), None)
    value_col = next((c for c in value_candidates if c in raw.columns), None)

    if time_col is None or value_col is None:
        raise RuntimeError(
            f"Unexpected IMF CSV structure for {country_code} {series_type}. "
            f"Columns received: {list(raw.columns)}. "
            f"Response begins: {response.text[:300]!r}"
        )

    raw["date"] = raw[time_col].map(_monthly_date)
    raw["value"] = pd.to_numeric(raw[value_col], errors="coerce")
    raw = raw.dropna(subset=["date", "value"])

    start_ts = pd.Timestamp(start_period + "-01")
    end_ts = pd.Timestamp(end_period + "-01")
    raw = raw[(raw["date"] >= start_ts) & (raw["date"] <= end_ts)]

    if raw.empty:
        raise RuntimeError(
            f"The IMF API returned no usable monthly observations for "
            f"{country_code} {series_type} between {start_period} and {end_period}."
        )

    series = (
        raw.drop_duplicates("date", keep="last")
        .sort_values("date")
        .set_index("date")["value"]
        .astype(float)
    )
    series.name = f"{country_code}_{series_type}"
    return series


def load_imf_country(
    country_code: str,
    start_period: str,
    end_period: str,
) -> pd.DataFrame:
    """Load CPI and FX for one country and combine them by month."""
    cpi = fetch_imf_series(country_code, "CPI", start_period, end_period)
    fx = fetch_imf_series(country_code, "FX", start_period, end_period)

    frame = pd.concat(
        [cpi.rename("cpi"), fx.rename("fx")],
        axis=1,
    ).sort_index()
    frame.index.name = "date"
    frame["country_code"] = country_code
    return frame.reset_index()


def validate_csv(uploaded_file, country_1_name, country_2_name):
    """Validate and standardize the uploaded CSV."""
    try:
        data = pd.read_csv(uploaded_file)
    except Exception as exc:
        raise ValueError(f"Could not read the CSV file: {exc}") from exc

    data.columns = [str(c).strip().lower() for c in data.columns]
    required = {"date", "country", "cpi", "fx"}
    missing = required - set(data.columns)
    if missing:
        raise ValueError(
            "CSV is missing required column(s): "
            + ", ".join(sorted(missing))
            + ". Required columns are date, country, cpi, fx."
        )

    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["country"] = data["country"].astype(str).str.strip()
    data["cpi"] = pd.to_numeric(data["cpi"], errors="coerce")
    data["fx"] = pd.to_numeric(data["fx"], errors="coerce")
    data = data.dropna(subset=["date", "country", "cpi", "fx"])

    if data.empty:
        raise ValueError("The CSV contains no usable rows after parsing.")

    if (data["cpi"] <= 0).any():
        raise ValueError("CPI values must be greater than zero.")
    if (data["fx"] <= 0).any():
        raise ValueError("FX values must be greater than zero.")

    data["month"] = data["date"].dt.to_period("M").dt.to_timestamp()
    data["country_key"] = data["country"].str.casefold()

    aliases_1 = {country_1_name.casefold(), country_options[country_1_name].casefold()}
    aliases_2 = {country_2_name.casefold(), country_options[country_2_name].casefold()}

    # Also permit the full country name as entered in the file.
    available = set(data["country_key"].unique())
    match_1 = next((x for x in aliases_1 if x in available), None)
    match_2 = next((x for x in aliases_2 if x in available), None)

    if match_1 is None or match_2 is None:
        raise ValueError(
            f"CSV must include rows for '{country_1_name}' (or code "
            f"{country_options[country_1_name]}) and '{country_2_name}' "
            f"(or code {country_options[country_2_name]}). "
            f"Country values found: {', '.join(sorted(data['country'].unique())[:20])}"
        )

    d1 = data[data["country_key"] == match_1][["month", "cpi", "fx"]].rename(
        columns={"cpi": "CPI_1", "fx": "FX_1"}
    )
    d2 = data[data["country_key"] == match_2][["month", "cpi", "fx"]].rename(
        columns={"cpi": "CPI_2", "fx": "FX_2"}
    )

    d1 = d1.groupby("month", as_index=False).last()
    d2 = d2.groupby("month", as_index=False).last()
    merged = pd.merge(d1, d2, on="month", how="inner").sort_values("month")
    return merged


def calculate_rer(data: pd.DataFrame) -> pd.DataFrame:
    """Calculate nominal ratio, RER and sample-normalized real index."""
    out = data.copy()
    out = out.dropna(subset=["CPI_1", "CPI_2", "FX_1", "FX_2"])
    out = out[
        (out["CPI_1"] > 0)
        & (out["CPI_2"] > 0)
        & (out["FX_1"] > 0)
        & (out["FX_2"] > 0)
    ].copy()

    if out.empty:
        raise ValueError("No overlapping, positive CPI and FX observations were available.")

    out["Nominal_S"] = out["FX_1"] / out["FX_2"]
    out["RER"] = out["Nominal_S"] * out["CPI_1"] / out["CPI_2"]
    rer_mean = out["RER"].mean()

    if pd.isna(rer_mean) or rer_mean == 0:
        raise ValueError("Could not normalize the RER because its mean is zero or invalid.")

    out["Real_Index"] = 100 * out["RER"] / rer_mean
    return out.sort_values("date" if "date" in out.columns else "month")


# -------------------- Main app --------------------

if start_date > end_date:
    st.error("Start date must be earlier than or equal to end date.")
    st.stop()

start_period = start_date.strftime("%Y-%m")
end_period = end_date.strftime("%Y-%m")

if data_source == "Upload CSV":
    st.subheader("Upload monthly data")
    st.write(
        "Upload a CSV with columns `date`, `country`, `cpi`, and `fx`. "
        "Use one row per country per month. The `fx` field must be local-currency "
        "units per US dollar."
    )
    st.code(
        "date,country,cpi,fx\n"
        "1999-01-01,Euro area,75.2,0.86\n"
        "1999-01-01,United States,166.6,1.00\n"
        "1999-02-01,Euro area,75.4,0.87\n"
        "1999-02-01,United States,166.8,1.00",
        language="csv",
    )
    uploaded_file = st.file_uploader("Choose CSV file", type=["csv"])
else:
    uploaded_file = None
    st.info(
        "IMF API mode tries to retrieve CPI and exchange-rate series. "
        "The IMF API may reject a country/series if its dataflow or dimensions "
        "differ from the candidate identifiers used here."
    )

run = st.button("Load data and calculate RER", type="primary", use_container_width=True)

if run:
    if country_1 == country_2:
        st.error("Choose two different countries.")
        st.stop()

    try:
        with st.spinner("Loading data and calculating the real exchange rate..."):
            if data_source == "Upload CSV":
                if uploaded_file is None:
                    st.error("Please upload a CSV file first.")
                    st.stop()
                paired = validate_csv(uploaded_file, country_1, country_2)
                paired = paired.rename(columns={"month": "date"})
            else:
                code_1 = country_options[country_1]
                code_2 = country_options[country_2]

                data_1 = load_imf_country(code_1, start_period, end_period)
                data_2 = load_imf_country(code_2, start_period, end_period)

                data_1 = data_1[["date", "cpi", "fx"]].rename(
                    columns={"cpi": "CPI_1", "fx": "FX_1"}
                )
                data_2 = data_2[["date", "cpi", "fx"]].rename(
                    columns={"cpi": "CPI_2", "fx": "FX_2"}
                )
                paired = pd.merge(data_1, data_2, on="date", how="inner").sort_values("date")

            paired["date"] = pd.to_datetime(paired["date"], errors="coerce")
            paired = paired.dropna(subset=["date"])
            paired = paired[
                (paired["date"] >= pd.Timestamp(start_period + "-01"))
                & (paired["date"] <= pd.Timestamp(end_period + "-01"))
            ]

            if paired.empty:
                st.error("No overlapping monthly observations were found for the selected countries and dates.")
                st.stop()

            result = calculate_rer(paired)

        st.success(f"Calculated RER using {len(result):,} overlapping monthly observations.")

        c1, c2, c3 = st.columns(3)
        c1.metric("Observations", f"{len(result):,}")
        c2.metric("First month", result["date"].min().strftime("%b %Y"))
        c3.metric("Last month", result["date"].max().strftime("%b %Y"))

        st.subheader("Real exchange rate index")
        fig = px.line(
            result,
            x="date",
            y="Real_Index",
            title=f"Real Exchange Rate Index: {country_1} vs {country_2}",
            labels={"date": "Month", "Real_Index": "Real index (sample average = 100)"},
        )
        fig.add_hline(y=100, line_dash="dash", annotation_text="Sample average = 100")
        fig.update_layout(hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("Nominal exchange-rate ratio and unnormalized RER"):
            fig2 = px.line(
                result,
                x="date",
                y=["Nominal_S", "RER"],
                title="Nominal ratio and RER",
                labels={"date": "Month", "value": "Value", "variable": "Series"},
            )
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Calculated data")
        display_cols = ["date", "CPI_1", "CPI_2", "FX_1", "FX_2", "Nominal_S", "RER", "Real_Index"]
        st.dataframe(
            result[display_cols].round(6),
            use_container_width=True,
            hide_index=True,
        )

        csv_bytes = result[display_cols].to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download calculated data as CSV",
            data=csv_bytes,
            file_name="real_exchange_rate_results.csv",
            mime="text/csv",
            use_container_width=True,
        )

    except Exception as exc:
        st.error("Could not calculate the RER.")
        st.code(str(exc))
        if data_source == "Try IMF API":
            st.markdown(
                "If the IMF API reports HTTP 404 or an unexpected response, "
                "the selected IMF dataflow/key is not valid for that series. "
                "This is an API-series identifier issue, not necessarily a problem "
                "with the RER formula. Switch to **Upload CSV** to continue."
            )

st.caption(
    "Research/educational tool. Results depend on the definitions, units, coverage, "
    "and quality of the input CPI and exchange-rate series."
)
