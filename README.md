# Christian Block · Personal Homepage

An empty trading floor at night on the 45th floor of a Frankfurt tower, built with three.js in a single HTML file.
The Bloomberg-style terminal on the desk holds the site: about, projects, publications and contact. Through the glass: the Roßmarkt
and the Hauptwache below, FOUR ahead, the Commerzbank Tower round the corner, in the rain.

Live: https://topoftheblock.github.io

- `index.html` – the whole site. Page text lives in the `<section data-page="…">` blocks near the bottom.
- `data/city.json` – the city outside: every building, street, tram line, tree, street lamp and traffic signal within 2.7 km, from OpenStreetMap.
- `scripts/bake_city.py` – rebuilds that file from OpenStreetMap (standard library only; caches downloads in `.osm-cache/`).
- `video/recording.mp4` – the screen recording that plays when you click a tower from the glass (H.264, 1920 px, 30 fps, no audio).
- `img/` – the framed photos on the desk, and the Golf Club Hanau-Wilhelmsbad badge on the headcovers (from golfclub-hanau.de).
- `data/quotes.json` – DAX quotes, intraday series and headlines shown on the desk screens.
- `scripts/fetch_quotes.py` – refreshes that file (Yahoo Finance quotes, delayed; Google News headlines).
- `.github/workflows/quotes.yml` – runs the script every 15 minutes in Xetra trading hours.

Map data © OpenStreetMap contributors, available under the Open Database License (https://www.openstreetmap.org/copyright). The site credits it on the Contact page.
