"""Real Exchange Rate Explorer — International Finance project.

Calculations follow the project specification:
  S(t) = X1(t) / X2(t), where X1 and X2 are local-currency units per USD.
  RER(t) = S(t) * CPI1(t) / CPI2(t).
  Real Index(t) = 100 * RER(t) / mean(RER over the selected sample).

IMF API availability and series identifiers can change. The app supports IMF SDMX
JSON responses and CSV upload as a fallback if an IMF series is unavailable.
"""
from __future__ import annotations

from io import BytesIO, StringIO
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

APP_TITLE = "Real Exchange Rate Explorer"
START_DATE = pd.Timestamp("1976-01-01")
IMF_API_BASE = "https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA"

# ISO3 values are used by the IMF series keys. Euro area is included as requested.
COUNTRIES = {
    "United States": "USA",
    "Euro area": "G163",
    "United Kingdom": "GBR",
    "Japan": "JPN",
    "Canada": "CAN",
    "Australia": "AUS",
    "China": "CHN",
    "India": "IND",
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
    "Turkey": "TUR",
    "Indonesia": "IDN",
}

st.set_page_config(page_title=APP_TITLE, page_icon="📈", layout="wide")


def _extract_sdmx_json(payload: dict[str, Any]) -> pd.DataFrame:
    """Extract time/value observations from common SDMX-JSON layouts."""
    # SDMX-JSON 2.0-ish data structure
    data = payload.get("data", payload)
    if isinstance(data, dict) and "dataSets" in data:
        structure = data.get("structure", {})
        dimensions = structure.get("dimensions", {}).get("observation", [])
        time_dim = next((d for d in dimensions if d.get("id", "").lower() in {"time_period", "time", "period"}), None)
        time_values = [v.get("id") for v in (time_dim or {}).get("values", [])]
        observations = data["dataSets"][0].get("observations", {})
        rows = []
        for key, value in observations.items():
            try:
                idx = int(key.split(":")[-1])
                rows.append((time_values[idx], value[0] if isinstance(value, list) else value))
            except (ValueError, IndexError, TypeError):
                continue
        if rows:
            return pd.DataFrame(rows, columns=["date", "value"])

    # SDMX-JSON 1.0-ish structure
    data_sets = payload.get("DataSet") or payload.get("dataSet")
    structure = payload.get("Structure") or payload.get("structure") or {}
    if isinstance(data_sets, list) and data_sets:
        ds = data_sets[0]
        series_block = ds.get("Series") or ds.get("series") or {}
        rows = []
        def walk(node: Any) -> None:
            if not isinstance(node, dict):
                return
            obs = node.get("Obs") or node.get("observations")
            if isinstance(obs, list):
                for item in obs:
                    if not isinstance(item, dict):
                        continue
                    time_val = item.get("TIME_PERIOD") or item.get("TIME_PERIOD_LABEL") or item.get("time")
                    value = item.get("OBS_VALUE") or item.get("value")
                    if time_val is not None and value is not None:
                        rows.append((time_val, value))
            for val in node.values():
                if isinstance(val, dict):
                    walk(val)
        walk(series_block)
        if rows:
            return pd.DataFrame(rows, columns=["date", "value"])

    # Some IMF responses expose observations as a flat array.
    for key in ("observations", "Observations", "values"):
        obs = payload.get(key)
        if isinstance(obs, list) and obs and isinstance(obs[0], dict):
            rows = []
            for item in obs:
                date = item.get("TIME_PERIOD") or item.get("time") or item.get("period")
                value = item.get("OBS_VALUE") or item.get("value")
                if date is not None and value is not None:
                    rows.append((date, value))
            if rows:
                return pd.DataFrame(rows, columns=["date", "value"])
    raise ValueError("The IMF response format was not recognized. Try uploading a CSV file instead.")


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_imf_series(iso3: str, series_type: str, start_date: str, end_date: str) -> pd.Series:
    """Fetch one monthly series from IMF SDMX API; raise a useful error if unavailable."""
    if series_type == "CPI":
        flow, key = "CPI", f"{iso3}.CPI._T.IX_M"
    else:
        flow, key = "ER", f"{iso3}.XDC_USD.PA_RT.M"
    url = f"{IMF_API_BASE}/{flow}/1.0/{key}"
    params = {"startPeriod": start_date[:7], "endPeriod": end_date[:7], "format": "json"}
    response = requests.get(url, params=params, timeout=30)
    if response.status_code >= 400:
        raise RuntimeError(
            f"IMF returned HTTP {response.status_code} for {iso3} {series_type}. "
            "The series key or endpoint may differ for this country. You can upload a CSV instead."
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("IMF did not return JSON data. Please try CSV upload.") from exc
    raw = _extract_sdmx_json(payload)
    raw["date"] = pd.to_datetime(raw["date"].astype(str).str.replace(r"(\d{4})-(\d{2})$", r"\1-\2-01", regex=True), errors="coerce")
    raw["value"] = pd.to_numeric(raw["value"], errors="coerce")
    raw = raw.dropna(subset=["date", "value"]).sort_values("date")
    raw = raw[(raw["date"] >= pd.Timestamp(start_date)) & (raw["date"] <= pd.Timestamp(end_date))]
    if raw.empty:
        raise RuntimeError(f"No usable monthly observations returned for {iso3} {series_type}. Try CSV upload.")
    result = raw.drop_duplicates("date", keep="last").set_index("date")["value"].astype(float)
    result.name = f"{iso3}_{series_type}"
    return result


def parse_upload(uploaded_file: Any) -> pd.DataFrame:
    """Accept long or wide CSV. Expected columns include date, country, cpi, fx."""
    try:
        df = pd.read_csv(uploaded_file)
    except Exception as exc:
        raise ValueError(f"Could not read the CSV: {exc}") from exc
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    date_col = next((c for c in ["date", "time", "period", "observation_date"] if c in df.columns), None)
    if not date_col:
        raise ValueError("CSV needs a date column named date, time, period, or observation_date.")
    df["date"] = pd.to_datetime(df[date_col].astype(str).str.replace(r"(\d{4})-(\d{2})$", r"\1-\2-01", regex=True), errors="coerce")
    if "country" in df.columns and {"cpi", "fx"}.issubset(df.columns):
        df["country"] = df["country"].astype(str).str.strip()
        return df[["date", "country", "cpi", "fx"]].copy()
    # Wide format: date, country1_cpi, country1_fx, country2_cpi, country2_fx
    return df


def prepare_data(cpi1: pd.Series, fx1: pd.Series, cpi2: pd.Series, fx2: pd.Series,
                 country1: str, country2: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    frame = pd.concat([
        cpi1.rename("CPI_1"), fx1.rename("FX_1"),
        cpi2.rename("CPI_2"), fx2.rename("FX_2"),
    ], axis=1).sort_index()
    frame.index.name = "Date"
    frame = frame.loc[(frame.index >= start) & (frame.index <= end)].copy()
    frame = frame.dropna(subset=["CPI_1", "FX_1", "CPI_2", "FX_2"])
    frame = frame[(frame[["CPI_1", "CPI_2", "FX_1", "FX_2"]] > 0).all(axis=1)]
    if frame.empty:
        raise ValueError("No overlapping valid monthly data in the selected date range.")
    # IMF exchange-rate series are local currency units per US dollar.
    frame["Nominal_S"] = frame["FX_1"] / frame["FX_2"]
    frame["RER"] = frame["Nominal_S"] * frame["CPI_1"] / frame["CPI_2"]
    benchmark = frame["RER"].mean()
    frame["RER_Benchmark_Mean"] = benchmark
    frame["Real_Index"] = 100.0 * frame["RER"] / benchmark
    frame["Country_1"] = country1
    frame["Country_2"] = country2
    return frame.reset_index()


st.title("📈 Real Exchange Rate Explorer")
st.caption("Monthly IMF data • Relative purchasing power • Real and nominal exchange rates")
st.markdown(
    "Compare two economies using consumer price indices (CPI) and exchange rates. "
    "This tool is for academic analysis; a real exchange-rate index is a relative measure, not a definitive verdict on fair value."
)

with st.sidebar:
    st.header("1. Choose countries")
    country1 = st.selectbox("Country 1 (numerator)", list(COUNTRIES.keys()), index=list(COUNTRIES.keys()).index("Euro area"))
    country2 = st.selectbox("Country 2 (denominator)", list(COUNTRIES.keys()), index=list(COUNTRIES.keys()).index("United States"))
    st.header("2. Choose sample")
    min_date = START_DATE.date()
    today = pd.Timestamp.today().date().replace(day=1)
    start = st.date_input("Start month", value=min_date, min_value=min_date, max_value=today)
    end = st.date_input("End month", value=today, min_value=min_date, max_value=today)
    st.header("3. Data source")
    source_mode = st.radio("Load data from", ["Try IMF API", "Upload CSV files"], index=0)

if country1 == country2:
    st.warning("Choose two different countries to compare.")
    st.stop()
if start > end:
    st.error("The start date must be on or before the end date.")
    st.stop()

uploaded = None
if source_mode == "Upload CSV files":
    st.subheader("Upload monthly data")
    st.write("Upload one CSV containing columns `date`, `country`, `cpi`, and `fx`, with one row per country/month. The `fx` column must be local-currency units per USD. Country values must match the country names selected in the sidebar.")
    uploaded = st.file_uploader("Choose CSV", type=["csv"])

run = st.button("Load data and calculate RER", type="primary", use_container_width=True)
if run:
    try:
        if source_mode == "Try IMF API":
            iso1, iso2 = COUNTRIES[country1], COUNTRIES[country2]
            with st.spinner("Requesting monthly CPI and exchange-rate data from the IMF…"):
                cpi1 = fetch_imf_series(iso1, "CPI", str(start), str(end))
                fx1 = fetch_imf_series(iso1, "FX", str(start), str(end))
                cpi2 = fetch_imf_series(iso2, "CPI", str(start), str(end))
                fx2 = fetch_imf_series(iso2, "FX", str(start), str(end))
        else:
            if uploaded is None:
                st.error("Please upload a CSV file first.")
                st.stop()
            loaded = parse_upload(uploaded)
            required = {"date", "country", "cpi", "fx"}
            if not required.issubset(loaded.columns):
                st.error("CSV must be in long format with columns: date, country, cpi, fx.")
                st.stop()
            loaded["cpi"] = pd.to_numeric(loaded["cpi"], errors="coerce")
            loaded["fx"] = pd.to_numeric(loaded["fx"], errors="coerce")
            loaded = loaded.dropna(subset=["date", "cpi", "fx"])
            loaded = loaded[(loaded["date"] >= pd.Timestamp(start)) & (loaded["date"] <= pd.Timestamp(end))]
            def series_for(country: str, col: str) -> pd.Series:
                part = loaded[loaded["country"].str.casefold() == country.casefold()]
                if part.empty:
                    raise ValueError(f"CSV has no rows for '{country}'. Check the country column spelling.")
                out = part.drop_duplicates("date", keep="last").set_index("date")[col].sort_index()
                out.name = f"{country}_{col}"
                return out
            cpi1, fx1 = series_for(country1, "cpi"), series_for(country1, "fx")
            cpi2, fx2 = series_for(country2, "cpi"), series_for(country2, "fx")
        result = prepare_data(cpi1, fx1, cpi2, fx2, country1, country2, pd.Timestamp(start), pd.Timestamp(end))
        st.session_state["rer_result"] = result
        st.session_state["rer_country1"] = country1
        st.session_state["rer_country2"] = country2
        st.session_state["rer_start"] = str(start)
        st.session_state["rer_end"] = str(end)
    except Exception as exc:
        st.error(f"Could not calculate the RER: {exc}")
        st.info("If the IMF API does not recognize a series key, switch to **Upload CSV files**. Use IMF monthly CPI and exchange-rate series, with exchange rates expressed as local-currency units per USD.")

if "rer_result" in st.session_state:
    result = st.session_state["rer_result"].copy()
    c1 = st.session_state["rer_country1"]
    c2 = st.session_state["rer_country2"]
    latest = result.iloc[-1]
    c1a, c2a, c3a, c4a = st.columns(4)
    c1a.metric("Valid monthly observations", f"{len(result):,}")
    c2a.metric("Latest nominal S (C2 per C1)", f"{latest['Nominal_S']:,.4f}")
    c3a.metric("Latest real index", f"{latest['Real_Index']:,.2f}")
    c4a.metric("Sample mean RER", f"{latest['RER_Benchmark_Mean']:,.4f}")

    st.subheader("Exchange rate and purchasing-power comparison")
    chart_mode = st.radio("Chart view", ["Real index", "Nominal exchange rate", "Both (separate axes)"], horizontal=True)
    fig = go.Figure()
    if chart_mode in ("Real index", "Both (separate axes)"):
        fig.add_trace(go.Scatter(x=result["Date"], y=result["Real_Index"], name="Real index (sample mean = 100)", mode="lines", yaxis="y1"))
        fig.add_hline(y=100, line_dash="dash", line_color="gray", annotation_text="Sample mean = 100", yref="y")
    if chart_mode in ("Nominal exchange rate", "Both (separate axes)"):
        fig.add_trace(go.Scatter(x=result["Date"], y=result["Nominal_S"], name=f"Nominal S: {c2} currency per {c1} currency", mode="lines", yaxis="y2" if chart_mode == "Both (separate axes)" else "y1"))
    fig.update_layout(
        template="plotly_white", height=520, hovermode="x unified",
        xaxis_title="Month", yaxis_title="Real index (100 = sample mean)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    if chart_mode == "Both (separate axes)":
        fig.update_layout(yaxis=dict(title="Real index (100 = sample mean)"), yaxis2=dict(title="Nominal S (C2 currency per C1 currency)", overlaying="y", side="right"))
    elif chart_mode == "Nominal exchange rate":
        fig.update_layout(yaxis_title=f"{c2} currency per {c1} currency")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Data and calculations")
    st.caption("RER = (FX₁ / FX₂) × (CPI₁ / CPI₂). The benchmark is the arithmetic mean RER over valid months in the selected sample. Real Index = 100 × RER / benchmark.")
    display_cols = ["Date", "CPI_1", "FX_1", "CPI_2", "FX_2", "Nominal_S", "RER", "RER_Benchmark_Mean", "Real_Index"]
    st.dataframe(result[display_cols].sort_values("Date", ascending=False), use_container_width=True, hide_index=True)
    csv_bytes = result.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8")
    st.download_button("Download all observations and calculations (CSV)", data=csv_bytes,
                       file_name=f"rer_{COUNTRIES[c1]}_vs_{COUNTRIES[c2]}.csv", mime="text/csv", type="primary")

    with st.expander("How to interpret the result"):
        st.markdown(
            "- **Real index above 100:** the calculated RER is above its selected-sample mean.\n"
            "- **Real index below 100:** the calculated RER is below its selected-sample mean.\n"
            "- This is a relative benchmark, not proof by itself that a currency is overvalued or undervalued. Interpretation depends on the CPI definitions, exchange-rate quotation, benchmark period, and economic context.\n"
            "- Confirm that both countries' CPI series use compatible index concepts and that FX is quoted as local-currency units per USD."
        )

st.divider()
st.caption("Data source: International Monetary Fund (IMF), where available. The app does not interpolate missing observations; calculations use months with valid data for all four input series.")
