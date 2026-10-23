# Real Exchange Rate Explorer

A Streamlit app for comparing the monthly real exchange rate (RER) of two economies using consumer price indices (CPI) and exchange rates.

## Files

- `app.py` — Streamlit app, data retrieval, calculations, charts, and CSV export.
- `requirements.txt` — Python dependencies for Streamlit Community Cloud.
- `README.md` — project description and setup instructions.

## Calculation used

The IMF exchange-rate series is expected to be expressed as local-currency units per US dollar.

- `S(t) = FX_1(t) / FX_2(t)` — units of Country 2 currency per unit of Country 1 currency.
- `RER(t) = S(t) * CPI_1(t) / CPI_2(t)`.
- `RER benchmark = arithmetic mean of RER over valid months in the selected sample`.
- `Real Index(t) = 100 * RER(t) / RER benchmark`.

The app calculates the benchmark over the selected date range and only uses months with valid, positive observations for all four input series. It does not interpolate missing values.

## Run locally

Python 3.12 is recommended.

```bash
python -m venv .venv
```

Activate the environment:

- Windows PowerShell: `.venv\\Scripts\\Activate.ps1`
- macOS/Linux: `source .venv/bin/activate`

Install dependencies and start the app:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Publish on Streamlit Community Cloud

1. Push `app.py`, `requirements.txt`, and `README.md` to the root of your public GitHub repository.
2. Go to <https://share.streamlit.io/> and sign in with GitHub.
3. Select **Create app**, choose your repository and branch (`main`), and set the main file path to `app.py`.
4. Select Python 3.12 in advanced settings if that option is offered, then deploy.
5. Open the deployed URL and test the country selectors, date range, chart options, and CSV download.

## IMF data and fallback

The app attempts to retrieve monthly CPI and exchange-rate series from the IMF SDMX 3.0 API. IMF dataset organization, series keys, and access rules may change, and series availability differs by economy. If the API does not return the requested series, choose **Upload CSV files** in the app and upload a long-format CSV with these columns:

| date | country | cpi | fx |
|---|---|---:|---:|
| 2020-01-01 | Euro area | 100.0 | 0.90 |
| 2020-01-01 | United States | 100.0 | 1.00 |

The example numbers above are illustrative only, not actual observations. Use the exact country names selected in the app. `date` should be monthly; `cpi` is the CPI index; and `fx` must be local-currency units per USD. The app does not treat illustrative examples as real data.

## Important interpretation note

An index above 100 means the calculated RER is above its mean over the selected sample; below 100 means it is below that mean. This does not, by itself, establish that a currency is objectively overvalued or undervalued. Results depend on the chosen sample, data definitions, quotation convention, and economic context.

## Project checklist

- [ ] Confirm IMF API data loads for your selected countries, or use a documented CSV data source.
- [ ] Verify at least one RER observation manually using `RER = (FX_1 / FX_2) * (CPI_1 / CPI_2)`.
- [ ] Test the real-index, nominal-rate, and both-axes chart modes.
- [ ] Download the CSV and confirm it contains raw inputs and calculated columns.
- [ ] Save the GitHub repository URL and deployed Streamlit URL for submission.
