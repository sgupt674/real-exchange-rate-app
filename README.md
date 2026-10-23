# Real Exchange Rate Explorer

A Streamlit application for comparing monthly CPI and exchange-rate data from the IMF SDMX 3.0 API.

## Files

- `app.py` — Streamlit app and RER calculations.
- `requirements.txt` — Python dependencies.
- `README.md` — setup and assignment notes.

## Run on Streamlit Community Cloud

1. Keep all three files at the top level of the public GitHub repository.
2. In Streamlit Community Cloud, deploy the repository's `main` branch and set the main file path to `app.py`.
3. Select Python 3.12 in Advanced settings if prompted.
4. No IMF API key is normally required.

## Economic definition used

The assignment defines `S(t)` as units of Country 2 currency per one unit of Country 1 currency:

`RER(t) = S(t) × CPI_1(t) / CPI_2(t)`

IMF exchange-rate series are quoted as local-currency units per USD. If `FX_1` is Country 1 currency per USD and `FX_2` is Country 2 currency per USD, then:

`S(t) = FX_2(t) / FX_1(t)`

The app calculates the average `RER*` over valid months within the selected date range, then:

`Real_Index(t) = 100 × RER(t) / RER*`

The index average should equal 100 over the valid observations in the selected sample (subject to rounding).

## Data coverage

The requested start date defaults to January 1976. IMF coverage varies by country and series; the app reports the first and last available month and uses only months with valid data for both countries. It does not fabricate or fill missing observations. The IMF uses `G163` for the Euro area.

Series keys used:
- CPI: `{country_code}.CPI._T.IX.M`
- Exchange rate: `{country_code}.XDC_USD.PA_RT.M`

The app includes a broad country list. If a country/series code is not accepted by the IMF API, try a shorter date range or another country and retain the displayed error for troubleshooting.

## CSV upload fallback

CSV columns must be `date,country,cpi,fx`. Use one row per country per month. The `fx` column must be local-currency units per USD. The country column should contain the exact selected country name or its IMF code.

## Required checks before submitting

1. Select United Kingdom as Country 1 and United States as Country 2. The nominal exchange rate must be quoted as USD per GBP.
2. Change the sample dates and verify the real-index mean is 100 over valid sample months.
3. Test Real, Nominal, and Both chart modes.
4. Use the manual verification expander to verify one row from the CSV.
5. Download the CSV and include it with the Streamlit URL, GitHub URL, prompt/model/date information, and a manual calculation in the assignment submission.

## Prompt/model record

Record the actual prompt(s), model name(s), and date(s) used to develop and revise the app in your assignment submission. Do not claim an earlier prompt or model was used if you did not save that record.
