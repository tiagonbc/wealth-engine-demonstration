# Wealth Engine Demonstration

**Live site: https://tiagonbc.github.io/wealth-engine-demonstration/** · system design: [/design](https://tiagonbc.github.io/wealth-engine-demonstration/design/)

**Preliminary version, mock data.** I built this to show how I would approach RBC's
Senior Software Quantitative Engineer role (req. R-0000186840), which I intend to apply for.
It is independent work: not affiliated with, reviewed or endorsed by RBC. The site's colours
follow RBC's public website; no RBC logo, product, data or methodology is used.

It is the computational core of a digital wealth platform, working end to end:

| Posting asks for | Where it is |
|---|---|
| Portfolio optimization | `wealth_engine/optimize.py`: efficient frontier, five model portfolios (max return for a volatility budget, weight bounds, equity cap), risk parity, resampling and input-sensitivity tests |
| Monte Carlo simulations | `wealth_engine/simulate.py`: correlated lognormal returns for nine asset classes, plans in today's dollars, probability of success, spending at 90% success, what-if grid |
| Financial health scores | `wealth_engine/health.py`: 0-100 score from six components, each with its rule and ranked next step |
| Probability assessment models | `wealth_engine/validation.py`: convergence, calibration (Brier score, reliability by bin) under three "true" worlds, stress tests |
| Trading algorithms | `wealth_engine/rebalance.py`: 5/25 tolerance bands, cash-flow investing, whole-unit orders, six pre-trade checks |
| Back tests | `wealth_engine/backtest.py`: four rebalancing policies on 500 synthetic 25-year histories |
| API services | `api/app.py`: Flask REST API, JSON Schema validation, RFC 9457 problem+json errors, request IDs, OpenAPI 3.1 |
| Data from various sources | `wealth_engine/data.py`: mock inputs plus data-quality checks run before any model |
| Best practices | `tests/`: 65 pytest tests; standard risk metrics (Sharpe, Sortino, VaR/CVaR, drawdown, Calmar) in `wealth_engine/risk.py`; model inventory shaped like OSFI Guideline E-23 |

## Run it

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest                       # 65 tests
python -m flask --app api.app run      # http://127.0.0.1:5000/api/v1/status
python build_site.py                   # runs every model, writes docs/data/engine.json (~25 s)
python -m http.server 8794 -d docs     # the site: http://localhost:8794

docker build -t wealth-engine .
docker run -p 8000:8000 wealth-engine  # API under gunicorn on port 8000
```

## Layout

```
wealth_engine/   the libraries (NumPy, SciPy)
api/             Flask REST API over the libraries
tests/           pytest suite
build_site.py    runs the engine and writes docs/data/engine.json
docs/            static site (plain HTML/JS, no framework) that reads engine.json
```

## What is mock

Everything. Capital market assumptions are round illustrative numbers, not forecasts and not
RBC's. Households, accounts, funds and prices are fictional. Health-score thresholds and
rebalancing rules are common rules of thumb. Nothing here is investment advice.

Built with an AI coding agent (Claude Code) working under tests; the design, checks and review are mine.

Tiago Costa · [linkedin.com/in/tiagonbc](https://www.linkedin.com/in/tiagonbc)
