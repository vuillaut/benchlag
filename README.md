# ia-bench-compare

Estimates how many months a model lags behind a reference line of models (by default: Mistral Large 4 vs Claude Opus), using Epoch AI's public benchmarks.

```sh
uv run benchlag            # download the latest data and recompute
uv run benchlag --offline  # recompute from the last snapshot
uv run benchlag-ui         # graphical interface (http://localhost:8501)
uv run pytest              # tests for the date-matching logic
```

Outputs in `reports/`:

- `latest.md`: the readable report (result, per-benchmark breakdown, Opus trajectory)
- `eci_lag.png`: the chart
- `latest.json`, `per_benchmark.csv`: the same data, machine-readable
- `history.csv`: one row per run, to track how the answer changes

The interface has two tabs: one model in detail (chart, per-benchmark table, CSV export) and a comparison of several models against the same reference. The reference is chosen in the sidebar (preset lineage, organization or regex), and its list of models can be edited by hand.

If the target is not behind the reference (no version reaches its level, or the reference only reaches it after the target's release), the command exits with an error (code 1) and the interface shows a message instead of a figure.

Method: `PROTOCOLE.md`. Settings: `config.toml`.

## Online version (GitHub Pages)

The interface also runs as a static site, with no server: [stlite](https://github.com/whitphx/stlite) runs the Streamlit app in the browser via Pyodide. `uv run python scripts/build_site.py` builds it in `site/`.

The workflow `.github/workflows/update.yml` downloads the Epoch AI data, recomputes the report, runs the tests, commits `reports/` (including `history.csv`) and redeploys the site. It runs on the 1st and 15th of each month at 05:00 UTC, on every push to `main`, and by hand from the Actions tab.

Local update without GitHub: `scripts/update.sh`, to put in a crontab (example in the script).
