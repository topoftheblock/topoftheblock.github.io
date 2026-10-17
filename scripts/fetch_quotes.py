"""Fetch DAX quotes, intraday series and market headlines into data/quotes.json.

Runs in GitHub Actions on a schedule (see .github/workflows/quotes.yml). Standard library only.
Quotes come from Yahoo Finance's public chart endpoint and are delayed; headlines from Google News RSS.
If a fetch fails, the previous file is kept.
"""
import datetime as dt
import email.utils
import html
import json
import re
import sys
import urllib.parse
import urllib.request

OUT = sys.argv[1] if len(sys.argv) > 1 else "data/quotes.json"
UA = {"User-Agent": "Mozilla/5.0 (night-desk market data)"}
INDEX = ("^GDAXI", "DAX", "DAX Index")
STOCKS = [
    ("SAP.DE", "SAP", "SAP"), ("SIE.DE", "SIE", "Siemens"), ("ALV.DE", "ALV", "Allianz"),
    ("DTE.DE", "DTE", "Dt. Telekom"), ("MBG.DE", "MBG", "Mercedes-Benz"), ("BMW.DE", "BMW", "BMW"),
    ("DBK.DE", "DBK", "Deutsche Bank"), ("CBK.DE", "CBK", "Commerzbank"), ("BAS.DE", "BAS", "BASF"),
    ("AIR.DE", "AIR", "Airbus"), ("MUV2.DE", "MUV2", "Munich Re"), ("IFX.DE", "IFX", "Infineon"),
]
NEWS = "https://news.google.com/rss/search?q=DAX+B%C3%B6rse+Frankfurt&hl=de&gl=DE&ceid=DE:de"


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read().decode("utf-8")


def chart(symbol, rng, interval):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range={rng}&interval={interval}"
    res = json.loads(get(url))["chart"]["result"][0]
    return res["meta"], res.get("timestamp") or [], res["indicators"]["quote"][0]


def quote(symbol, tick, name):
    meta, _, q = chart(symbol, "1d", "5m")
    series = [round(c, 4) for c in q["close"] if c is not None]
    return {"sym": tick, "name": name, "price": meta["regularMarketPrice"],
            "prev": meta.get("chartPreviousClose") or meta.get("previousClose"),
            "time": meta.get("regularMarketTime"), "series": series}


def index():
    q1 = quote(*INDEX)
    meta, ts, q = chart(INDEX[0], "5d", "15m")
    candles = [[t, round(o, 2), round(h, 2), round(l, 2), round(c, 2)]
               for t, o, h, l, c in zip(ts, q["open"], q["high"], q["low"], q["close"])
               if None not in (o, h, l, c)]
    q1["candles"] = candles[-64:]
    return q1


def news(limit=10):
    items = re.findall(r"<item>.*?<title>(.*?)</title>.*?<pubDate>(.*?)</pubDate>.*?<source[^>]*>(.*?)</source>", get(NEWS), re.S)
    out = []
    for title, date, source in items[: limit * 2]:
        title, source = html.unescape(title), html.unescape(source)
        title = re.sub(r"\s+-\s+[^-]+$", "", title).strip()   # Google appends " - Source"
        when = email.utils.parsedate_to_datetime(date).astimezone(dt.timezone.utc).isoformat()
        out.append({"title": title, "source": source, "time": when})
    out.sort(key=lambda n: n["time"], reverse=True)
    return out[:limit]


def main():
    try:
        data = {"index": index(), "stocks": []}
        for s in STOCKS:
            try:
                data["stocks"].append(quote(*s))
            except Exception as e:  # one bad symbol shouldn't stop the update
                print("skip", s[0], e, file=sys.stderr)
        if len(data["stocks"]) < 8:
            raise RuntimeError("too few quotes")
        try:
            data["news"] = news()
        except Exception as e:
            print("news failed", e, file=sys.stderr)
            data["news"] = []
        data["updated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    except Exception as e:
        print("keeping previous data:", e, file=sys.stderr)
        return
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print("wrote", OUT, len(data["stocks"]), "stocks,", len(data["news"]), "headlines")


if __name__ == "__main__":
    main()
