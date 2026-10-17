# Night Desk · Christian Block

An empty trading floor at night, 45 floors above Frankfurt, built with three.js in a single HTML file.
The terminal on the desk holds the site: about, projects, publications and contact.

Live: https://topoftheblock.github.io

- `index.html` – the whole site. Page text lives in the `<section data-page="…">` blocks near the bottom.
- `data/quotes.json` – DAX quotes, intraday series and headlines shown on the desk screens.
- `scripts/fetch_quotes.py` – refreshes that file (Yahoo Finance quotes, delayed; Google News headlines).
- `.github/workflows/quotes.yml` – runs the script every 15 minutes in Xetra trading hours.
