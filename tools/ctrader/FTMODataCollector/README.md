# FTMODataCollector (cTrader Python cBot)

Read-only collector for FTMO cTrader `BTCUSD` and `ETHUSD`. It exports M1 bars,
live bid/ask samples, and broker-specific symbol metadata. It contains no order
submission, modification, or position-management calls and uses
`AccessRights.None`.

## Install in cTrader Windows

1. Open **Algo** and select **cBots → New**.
2. Create a Python cBot named exactly `FTMODataCollector`.
3. Replace the generated Python source with `FTMODataCollector.py` from this
   directory.
4. Open the generated project folder. Its location is normally:
   `Documents/cAlgo/Sources/Robots/FTMODataCollector/FTMODataCollector/`.
5. Replace the generated `FTMODataCollector.cs` with the file from this directory.
6. Replace the generated `config.json` with `config.json` from this directory.
   Current cTrader Python projects declare UI parameters in this JSON file.
7. Build the cBot (`Ctrl+Shift+B` when using the external VS Code editor).
8. Add an instance on the FTMO Free Trial account. The chart symbol is not
   important because the collector explicitly requests both configured symbols.
9. Keep the defaults for the first run: 30 history days, quotes every 5 seconds,
   stop after 60 minutes.
10. Start the instance locally. No trading permission or Open API credentials are
   required.

## Output

With `AccessRights.None`, cTrader writes into the cBot's protected data folder:

`Documents/cAlgo/Data/cBots/FTMODataCollector/`

Expected files:

- `btcusd_m1.csv`
- `ethusd_m1.csv`
- `quotes_live.csv`
- `symbol_metadata.json`

Copy these four files into the framework only after the cTrader log reports both
M1 exports successfully. Do not copy cTrader credentials, account identifiers,
or unrelated platform files.

## Operational notes

- M1 bars are broker/server bars and do not contain a historical bid/ask spread.
  `quotes_live.csv` records real bid and ask snapshots for spread calibration.
- The collector loads older history in bounded batches. A warning is printed if
  `Max History Batches` is reached before the requested cutoff.
- Keep the instance local. Cloud instances do not provide a convenient local
  output-file workflow.
- The collector overwrites bar and metadata files at startup and starts a new
  live-quote file for each run.
