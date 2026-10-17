#!/usr/bin/env python3
"""Bakes the view from OMNITURM into data/city.json.

Downloads OpenStreetMap data around the Frankfurt banking district (buildings with their heights and 3D parts,
streets, tram lines, trees, street lamps, traffic signals), then writes it in the room's own coordinates:
x to the right of the window, z towards the viewer (-z looks out), y up with the street at G.

    python3 scripts/bake_city.py               # downloads into .osm-cache/ (about 150 MB), writes data/city.json

Map data (c) OpenStreetMap contributors, ODbL. Uses only the standard library.
"""
import sys, os, json, math, time, collections, urllib.request, xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".osm-cache")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "city.json")

# --- download: the OSM API hands out small boxes, so fetch a grid of them -----------------------
def fetch_tiles():
    os.makedirs(CACHE, exist_ok=True)
    files = []
    for i in range(8):
        for j in range(5):
            x0, y0 = round(8.645 + 0.008 * i, 4), round(50.100 + 0.005 * j, 4)
            f = os.path.join(CACHE, "tile_%s_%s.xml" % (x0, y0))
            files.append(f)
            if os.path.exists(f) and open(f, "rb").read().rstrip().endswith(b"</osm>"): continue
            url = "https://api.openstreetmap.org/api/0.6/map?bbox=%s,%s,%s,%s" % (x0, y0, round(x0 + 0.008, 4), round(y0 + 0.005, 4))
            for attempt in range(4):
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "nd-terminal-site/1.0 (github.com/topoftheblock)"})
                    data = urllib.request.urlopen(req, timeout=120).read()
                    if data.rstrip().endswith(b"</osm>"):
                        open(f, "wb").write(data); print("tile", x0, y0, len(data)); break
                except Exception as e:
                    print("retry", url, e)
                time.sleep(5 * (attempt + 1))
            else:
                sys.exit("could not download " + url)
    return files

def load(files):
    nodes, ways, rels = {}, {}, {}
    for f in files:
        for ev, el in ET.iterparse(f):
            if el.tag == "node":
                nodes[int(el.get("id"))] = (float(el.get("lon")), float(el.get("lat")), {t.get("k"): t.get("v") for t in el.findall("tag")} or None); el.clear()
            elif el.tag == "way":
                ways[int(el.get("id"))] = ([int(n.get("ref")) for n in el.findall("nd")], {t.get("k"): t.get("v") for t in el.findall("tag")}); el.clear()
            elif el.tag == "relation":
                rels[int(el.get("id"))] = ([(m.get("type"), int(m.get("ref")), m.get("role")) for m in el.findall("member")], {t.get("k"): t.get("v") for t in el.findall("tag")}); el.clear()
    return nodes, ways, rels

nodes, ways, rels = load(fetch_tiles())

# --- local metres around OMNITURM ---------------------------------------------------------------
lon0, lat0 = 8.673312223076923, 50.11156132307693
kx = 111320*math.cos(math.radians(lat0)); ky = 110540
def L(lon, lat): return ((lon-lon0)*kx, (lat-lat0)*ky)
def ring(nd): return [L(*nodes[n][:2]) for n in nd if n in nodes]
def num(v):
    try: return float(v.split()[0].replace(",", ".").rstrip("m"))
    except: return None
def height(t):
    for k in ("height", "building:height"):
        if k in t and num(t[k]) is not None: return num(t[k])
    if "building:levels" in t and num(t["building:levels"]) is not None:
        return num(t["building:levels"]) * 3.4 + (num(t.get("roof:levels", "0") or "0") or 0) * 2.8
    return None
def minh(t):
    if "min_height" in t and num(t["min_height"]) is not None: return num(t["min_height"])
    if "building:min_level" in t and num(t["building:min_level"]) is not None: return num(t["building:min_level"]) * 3.4
    return 0.0
def pip(x, y, poly):
    c = False; n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i+1) % n]
        if (y1 > y) != (y2 > y) and x < (x2-x1)*(y-y1)/(y2-y1)+x1: c = not c
    return c
def area(p): return abs(sum(p[i][0]*p[(i+1)%len(p)][1]-p[(i+1)%len(p)][0]*p[i][1] for i in range(len(p))))/2

FLOOR = 166.0            # our floor above the street
G = -FLOOR
OMNI = 598133203

# --- the window: the east end of OMNITURM's north-east face --------------------------------
on = ways[OMNI][0]
pts = ring(on)
A = (-10.3, 27.2); B = (7.8, -0.5)      # north and east corners of the north-east face (checked against the outline)
A = min(pts, key=lambda p: math.hypot(p[0] - A[0], p[1] - A[1])); B = min(pts, key=lambda p: math.hypot(p[0] - B[0], p[1] - B[1]))
tx, ty = B[0] - A[0], B[1] - A[1]; tl = math.hypot(tx, ty); tx, ty = tx / tl, ty / tl   # along the face, towards the east corner = room +x
fx, fy = ty, -tx                                                                       # outward normal = room -z
if fx * (A[0] + B[0]) / 2 + fy * (A[1] + B[1]) / 2 < 0: fx, fy = -fx, -fy
bearing = math.degrees(math.atan2(fx, fy)) % 360
# the room is 17.2 m wide; its right wall (x = 8.6) sits 0.4 m inside the corner
px, py = B[0] - tx * 9.0, B[1] - ty * 9.0
ox, oy = px - fx * 0.65, py - fy * 0.65                                                # room origin: 0.65 m behind the glass
rx, ry = tx, ty

def P(e, n):
    dx, dy = e - ox, n - oy
    return (dx * rx + dy * ry, -(dx * fx + dy * fy))

def q(v): return int(round(v * 10))  # decimetres

def flat(r):
    out = []
    for e, n in r:
        x, z = P(e, n); out += [q(x), q(z)]
    return out

def simplify(r, tol):
    if len(r) < 4: return r
    def rdp(a):
        if len(a) < 3: return a
        (x1, y1), (x2, y2) = a[0], a[-1]; dx, dy = x2 - x1, y2 - y1; d = math.hypot(dx, dy) or 1e-9
        best, bi = -1, 0
        for i in range(1, len(a) - 1):
            x, y = a[i]; dist = abs(dy * x - dx * y + x2 * y1 - y2 * x1) / d
            if dist > best: best, bi = dist, i
        if best > tol: return rdp(a[:bi + 1])[:-1] + rdp(a[bi:])
        return [a[0], a[-1]]
    return rdp(r)

def visible(rr, margin=12):
    # anything wholly behind the window plane can't be seen
    zs = [P(e, n)[1] for e, n in rr]
    xs = [P(e, n)[0] for e, n in rr]
    # the room has glass on two sides: ahead (-z) and to the right (+x), round the building's east corner
    if min(zs) > margin and max(xs) < 8.6 - margin: return False
    if min(math.hypot(x, z) for x, z in zip(xs, zs)) > 2700: return False
    return True

# --- multipolygon rings ----------------------------------------------------------------------
def assemble(members, role="outer"):
    segs = [list(ways[r][0]) for (t, r, ro) in members if t == "way" and r in ways and (ro or "outer") == role]
    rings = []
    while segs:
        cur = segs.pop(0)
        changed = True
        while cur[0] != cur[-1] and changed:
            changed = False
            for i, s in enumerate(segs):
                if s[0] == cur[-1]: cur += s[1:]
                elif s[-1] == cur[-1]: cur += s[::-1][1:]
                elif s[-1] == cur[0]: cur = s[:-1] + cur
                elif s[0] == cur[0]: cur = s[::-1][:-1] + cur
                else: continue
                segs.pop(i); changed = True; break
        if cur[0] == cur[-1] and len(cur) > 3: rings.append(cur)
    return rings

# --- named buildings: label and a line about each ---------------------------------------------
INFO = {
    "Commerzbank Tower": "259 m, 300 m with the spire. Norman Foster, 1997. Commerzbank's head office: a triangle with sky gardens that wind up round a central atrium.",
    "Main Tower": "200 m, 240 m with the antenna. 1999. Helaba's head office, with the trading floor of a Landesbank and a public viewing terrace at 187 m.",
    "Turm 1": "FOUR Frankfurt, tower 1: 233 m, 2024. Offices, on the block between Große Gallusstraße and Junghofstraße.",
    "Turm 2": "FOUR Frankfurt, tower 2: 178 m, 2024. Flats and a hotel above, offices below.",
    "Turm 3": "FOUR Frankfurt, tower 3: 120 m, 2024. Flats.",
    "Turm 4": "FOUR Frankfurt, tower 4: 100 m, 2024. Flats.",
    "Garden Tower": "127 m, 1976, rebuilt 2010 with a garden behind a double glass skin.",
    "Japan Center": "115 m, 1996, after the shape of a Japanese stone lantern. Dark red granite.",
    "TaunusTurm": "170 m, 2014, at the edge of the Taunusanlage park.",
    "Eurotheum": "110 m, 1999. Offices below, a hotel above.",
    "Global Tower": "84 m, 1974. Former Commerzbank offices, rebuilt as flats.",
    "K26": "70 m. Offices at Kaiserstraße.",
    "Eurotower": "148 m, 1977. The seat of the European Central Bank until 2014, now the ECB's banking supervision.",
    "Gallileo Hochhaus": "136 m, 2003. Commerzbank offices; the Gallileo theatre is in the base.",
    "Silberturm": "166 m, 1978. Storey-high aluminium panels; Deutsche Bahn's offices for decades.",
    "Skyper": "154 m, 2004. DekaBank's offices, with the old Villa Rumpf at its foot.",
    "Turm A": "Deutsche Bank head office, tower A: 155 m, 1984. Mirror glass; with tower B, Soll und Haben.",
    "Turm B": "Deutsche Bank head office, tower B: 155 m, 1984. The trading floors are in the base.",
    "Trianon": "186 m, 1993. A triangle standing on one corner; DekaBank's head office.",
    "Marienturm": "155 m, 2019.",
    "OpernTurm": "170 m, 2009. Limestone and glass, next to the Alte Oper.",
    "Westend Tower": "208 m, 1993. DZ Bank. The ring on top is the crown.",
    "Messeturm": "257 m, Helmut Jahn, 1991. Red granite and glass, with a pyramid on top. Locals call it the pencil.",
    "Tower 185": "200 m, 2011. PwC's German head office.",
    "Nextower": "136 m, 2010. Offices and a hotel above the Thurn-und-Taxis-Palais.",
    "Europäische Zentralbank": "185 m, 2015. The European Central Bank: two towers of different heights twisted round an atrium.",
    "Hauptwache": "The baroque guardhouse of 1730, in the middle of the city's busiest square. Below it, the S- and U-Bahn hub.",
    "Katharinenkirche": "St. Catherine's, 1681. Goethe was baptised here.",
    "Bürohaus an der Alten Oper": "89 m, 1981.",
    "Parktower": "115 m, 1972, rebuilt 2007.",
    "FBC Hochhaus": "142 m, 1980. Frankfurter Büro Center.",
    "City Haus I": "142 m, 1974.",
    "Galeria": "The department store on the Zeil.",
    "Paulskirche": "1833. Germany's first freely elected parliament met here in 1848.",
    "Kaiserdom St. Bartholomäus": "Frankfurt Cathedral. Its 95 m red sandstone tower was finished in 1877.",
    "Römer": "The town hall since 1405.",
    "Alte Oper": "The old opera, 1880. Burnt out in the war, reopened as a concert hall in 1981.",
}
LABEL = {"Turm 1": "FOUR · Tower 1", "Turm 2": "FOUR · Tower 2", "Turm 3": "FOUR · Tower 3", "Turm 4": "FOUR · Tower 4",
         "Turm A": "Deutsche Bank · Tower A", "Turm B": "Deutsche Bank · Tower B", "Europäische Zentralbank": "European Central Bank",
         "Gallileo Hochhaus": "Gallileo", "TaunusTurm": "Taunusturm", "OpernTurm": "Opernturm", "Kaiserdom St. Bartholomäus": "Kaiserdom"}
# banks whose trading floors light up at night, in their own buildings
TRADING = {"Commerzbank Tower", "Main Tower", "Turm A", "Turm B", "Trianon", "Westend Tower", "Gallileo Hochhaus", "Skyper", "Eurotower"}
names, nameIdx = [], {}
def nid(n):
    if n not in nameIdx: nameIdx[n] = len(names); names.append([LABEL.get(n, n), INFO.get(n, "")])
    return nameIdx[n]

COLOURS = {"white": "#e8e6e0", "beige": "#c9b994", "ivory": "#e9e4d0", "lightgrey": "#c4c4c4", "lightgray": "#c4c4c4", "lightyellow": "#e8e2b8", "grey": "#8a8a8a",
           "gray": "#8a8a8a", "lemonchiffon": "#e6dfb5", "tan": "#b8996c", "whitesmoke": "#e6e6e6", "yellow": "#d8c060", "khaki": "#bfb07a", "wheat": "#d8c39a",
           "firebrick": "#8e3a2c", "lightgoldenrodyellow": "#e2dfb2", "maroon": "#5e2a24", "antiquewhite": "#e6dcc8", "brown": "#6a4434", "azure": "#d4e2e6",
           "orange": "#c8823c", "lightsalmon": "#d29a7e", "black": "#1a1a1a", "salmon": "#c0786a", "gainsboro": "#d0d0d0", "dimgrey": "#5a5a5a", "skyblue": "#86aac0",
           "sandybrown": "#c49060", "green": "#4a6a4a", "silver": "#b8bcc0", "red": "#8e3a2c"}
def colour(t):
    c = (t.get("building:colour") or t.get("colour") or "").strip().lower()
    if c.startswith("#") and len(c) == 7: return c
    return COLOURS.get(c)

def h32(s):
    x = 2166136261
    for ch in str(s): x = ((x ^ ord(ch)) * 16777619) & 0xffffffff
    return x / 4294967295.0

# --- buildings ------------------------------------------------------------------------------
cands = []   # (ring_nodes, tags, id, is_part)
for wid, (nd, t) in ways.items():
    if ("building" in t or "building:part" in t) and nd[0] == nd[-1] and len(nd) > 3:
        cands.append(([nd], t, "w%d" % wid, "building:part" in t and "building" not in t))
for rid, (mem, t) in rels.items():
    if t.get("type") in ("multipolygon", "building") and ("building" in t or "building:part" in t):
        rs = assemble(mem)
        if rs: cands.append((rs, t, "r%d" % rid, "building:part" in t and "building" not in t))
SKIP_B = {"underground", "construction", "no", "roof_underground"}
omni_poly = ring(on)[:-1]

# parts per outline: an outline that has parts inside it is drawn by its parts only
grid = collections.defaultdict(list)
parts = []
for rs, t, i, isp in cands:
    if isp:
        r = ring(rs[0]); cx = sum(p[0] for p in r) / len(r); cy = sum(p[1] for p in r) / len(r)
        parts.append((cx, cy)); grid[(int(cx // 50), int(cy // 50))].append((cx, cy))
def has_parts(r):
    xs = [p[0] for p in r]; ys = [p[1] for p in r]
    for gx in range(int(min(xs) // 50), int(max(xs) // 50) + 1):
        for gy in range(int(min(ys) // 50), int(max(ys) // 50) + 1):
            for cx, cy in grid.get((gx, gy), []):
                if pip(cx, cy, r): return True
    return False

def style(t, h, name):
    b = t.get("building") or t.get("building:part") or "yes"
    mat = (t.get("building:material") or "").lower()
    hist = "historic" in t or "heritage" in t or b in ("church", "cathedral", "chapel")
    if b in ("church", "cathedral", "chapel") or name in ("Hauptwache", "Katharinenkirche", "Paulskirche", "Kaiserdom St. Bartholomäus", "Alte Oper", "Römer"):
        return 3
    if b in ("garage", "garages", "roof", "parking", "shed", "kiosk", "service", "greenhouse", "carport"): return 4
    if mat in ("glass", "mirror") or (h >= 55 and b not in ("apartments", "residential")): return 0
    if b in ("apartments", "residential", "house", "terrace", "dormitory", "detached", "semidetached_house") or hist: return 2
    if h >= 45: return 0
    return 1

buildings = []
seen_names = set()
for rs, t, i, isp in cands:
    b = t.get("building") or ""
    if b in SKIP_B or t.get("location") == "underground": continue
    try:
        if int(t.get("layer", "0")) < 0: continue
    except ValueError: pass
    r = ring(rs[0])[:-1]
    if len(r) < 3 or (area(r) < 12 and (height(t) or 0) < 100): continue
    cx = sum(p[0] for p in r) / len(r); cy = sum(p[1] for p in r) / len(r)
    if i == "w%d" % OMNI or pip(cx, cy, omni_poly): continue          # our own tower: we are inside it
    if not visible(r): continue
    if not isp and has_parts(r): continue
    hh = height(t); mh = minh(t)
    name = t.get("name") if t.get("name") in INFO else None
    seed = h32(i)
    if hh is None:
        bt = b or "yes"
        hh = {"garage": 3, "garages": 3, "shed": 3, "kiosk": 3.5, "roof": 5, "carport": 3, "house": 10, "church": 22, "service": 4,
              "greenhouse": 4, "bridge": 8, "industrial": 10, "school": 14, "kindergarten": 8}.get(bt, 15.5 + seed * 6.5)
        if t.get("roof:shape") in ("gabled", "hipped", "mansard", "gambrel") and "roof:height" not in t: hh += 0
    if b == "roof" and mh == 0: mh = hh - 1.2
    if hh <= mh + 0.5: continue
    cls = style(t, hh, t.get("name"))
    col = colour(t)
    pitched = cls == 2 and hh < 40 and (t.get("roof:shape") in (None, "gabled", "hipped", "mansard", "gambrel", "side_hipped", "half-hipped", "pyramidal")) and t.get("roof:shape") != "flat"
    roofH = 0.0
    if pitched:
        roofH = num(t.get("roof:height", "")) or (3.2 + seed * 2.2)
        if t.get("roof:shape") is None and seed < 0.25: roofH = 0.0       # some Altbau have flat-topped Mansards seen from above
    trade = 1 if (t.get("name") in TRADING) else 0
    tol = 0.35 if math.hypot(*P(cx, cy)) < 700 else 1.2
    rr = simplify(r + [r[0]], tol)[:-1]
    if len(rr) < 3: rr = r
    out = {"p": flat(rr), "y0": round(mh, 1), "y1": round(hh - roofH, 1), "c": cls, "s": round(seed, 3)}
    if roofH: out["rh"] = round(roofH, 1)
    if col: out["col"] = col
    if trade: out["tr"] = 1
    if name:
        out["n"] = nid(name); seen_names.add(name)
    mat = (t.get("building:material") or "").lower()
    if mat in ("mirror",): out["m"] = 1
    buildings.append(out)

# parts that carry no name but belong to a named outline: give them the outline's name
named_outlines = []
for rs, t, i, isp in cands:
    if not isp and t.get("name") in INFO and t.get("name") in TRADING | set(INFO):
        named_outlines.append((ring(rs[0])[:-1], t.get("name")))
for bd in buildings:
    if "n" in bd: continue
    xs = bd["p"][0::2]; zs = bd["p"][1::2]
    cx = sum(xs) / len(xs) / 10; cz = sum(zs) / len(zs) / 10
    # back to E/N for the test
    for r, nm in named_outlines:
        rr = [P(e, n) for e, n in r]
        if pip(cx, cz, rr):
            bd["n"] = nid(nm)
            if nm in TRADING: bd["tr"] = 1
            break

# --- duplicates: OSM often maps one tower as two nearly identical parts. Their walls would sit in the same
# place and flicker against each other on screen, so keep one: stacked parts are trimmed, doubles dropped.
def _bb(b): xs = b["p"][0::2]; zs = b["p"][1::2]; return min(xs), min(zs), max(xs), max(zs)
_grid = collections.defaultdict(list)
for _i, _b in enumerate(buildings):
    _a = _bb(_b); _grid[(_a[0] // 500, _a[1] // 500)].append(_i)
_drop = set()
for _i, _b in enumerate(buildings):
    if _i in _drop: continue
    _a = _bb(_b)
    for _gx in (-1, 0, 1):
        for _gz in (-1, 0, 1):
            for _j in _grid[(_a[0] // 500 + _gx, _a[1] // 500 + _gz)]:
                if _j <= _i or _j in _drop or _i in _drop: continue
                _o = buildings[_j]; _c = _bb(_o)
                ix = max(0, min(_a[2], _c[2]) - max(_a[0], _c[0])) * max(0, min(_a[3], _c[3]) - max(_a[1], _c[1]))
                un = (_a[2] - _a[0]) * (_a[3] - _a[1]) + (_c[2] - _c[0]) * (_c[3] - _c[1]) - ix
                if not un or ix / un < 0.75: continue
                top_i, top_j = _b["y1"] + _b.get("rh", 0), _o["y1"] + _o.get("rh", 0)
                if min(top_i, top_j) <= max(_b["y0"], _o["y0"]): continue
                lo, hi = (_b, _o) if _b["y0"] < _o["y0"] else (_o, _b)
                if hi["y0"] > lo["y0"] + 2 and top_i != top_j and (hi["y1"] + hi.get("rh", 0)) > (lo["y1"] + lo.get("rh", 0)):
                    lo["y1"] = hi["y0"]; lo.pop("rh", None)          # stacked: the lower one stops where the upper begins
                else:
                    keep, gone = (_i, _j) if top_i >= top_j else (_j, _i)
                    k, g = buildings[keep], buildings[gone]
                    k["y0"] = min(k["y0"], g["y0"])
                    if "n" in g and "n" not in k: k["n"] = g["n"]
                    if g.get("tr"): k["tr"] = 1
                    _drop.add(gone)
print("duplicates merged", len(_drop))
buildings = [b for i, b in enumerate(buildings) if i not in _drop]

# --- roads and the drive graph ----------------------------------------------------------------
WIDTH = {"motorway": 20, "trunk": 16, "primary": 13, "secondary": 11, "tertiary": 9.5, "unclassified": 7, "residential": 7, "living_street": 6,
         "service": 4.5, "busway": 7, "primary_link": 7, "secondary_link": 7, "tertiary_link": 6, "trunk_link": 7, "pedestrian": 6,
         "footway": 2.4, "cycleway": 2, "path": 2.2, "steps": 2.5, "track": 3}
DRIVE = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "living_street", "primary_link", "secondary_link", "tertiary_link", "trunk_link"}
KIND = {k: i for i, k in enumerate(["primary", "secondary", "tertiary", "residential", "service", "pedestrian", "footway", "busway"])}
def kind(hw):
    if hw in ("motorway", "trunk", "primary", "primary_link", "trunk_link"): return 0
    if hw in ("secondary", "secondary_link"): return 1
    if hw in ("tertiary", "tertiary_link", "unclassified"): return 2
    if hw in ("residential", "living_street"): return 3
    if hw == "service": return 4
    if hw == "pedestrian": return 5
    if hw == "busway": return 7
    return 6
gidx, gpts = {}, []
signals = {i for i, (lo, la, t) in nodes.items() if t and t.get("highway") == "traffic_signals"}
def gnode(n):
    if n not in gidx:
        x, z = P(*L(*nodes[n][:2])); gidx[n] = len(gpts); gpts.append([q(x), q(z), 1 if n in signals else 0])
    return gidx[n]
roads = []
roadnames = []
rn_idx = {}
for wid, (nd, t) in ways.items():
    hw = t.get("highway")
    if hw not in WIDTH: continue
    if t.get("tunnel") in ("yes", "building_passage") or t.get("covered") == "yes": continue
    try:
        if int(t.get("layer", "0")) < 0: continue
    except ValueError: pass
    if t.get("area") == "yes": continue
    nn = [n for n in nd if n in nodes]
    if len(nn) < 2: continue
    r = [nodes[n][:2] for n in nn]
    if not visible([L(*p) for p in r], 60): continue
    if WIDTH[hw] < 3 and min(math.hypot(*P(*L(*p))) for p in r) > 700: continue   # footpaths only near enough to see
    if WIDTH[hw] < 3:   # thin paths: fewer points
        keep = [nn[0]] + [n for k_, n in enumerate(nn[1:-1]) if k_ % 2 == 1] + [nn[-1]]
        nn = keep
    if hw == "service" and t.get("service") in ("parking_aisle", "driveway"): w = 3.5
    else: w = WIDTH[hw]
    if "width" in t and num(t["width"]): w = min(max(num(t["width"]), 2), 26)
    elif "lanes" in t and num(t["lanes"]) and hw in DRIVE: w = max(w, num(t["lanes"]) * 3.25 + 0.8)
    lanes = int(num(t.get("lanes", "0")) or 0)
    ow = 1 if t.get("oneway") in ("yes", "1", "true") or t.get("junction") == "roundabout" else (-1 if t.get("oneway") == "-1" else 0)
    nm = t.get("name") or ""
    if nm and nm not in rn_idx: rn_idx[nm] = len(roadnames); roadnames.append(nm)
    roads.append({"k": kind(hw), "w": round(w, 1), "n": [gnode(n) for n in nn], "o": ow, "d": 1 if hw in DRIVE else 0,
                  "l": lanes, "nm": rn_idx.get(nm, -1), "sw": 1 if (hw in DRIVE and hw not in ("service",) and t.get("sidewalk") != "no") else 0})

# --- trams -----------------------------------------------------------------------------------
trams = []
for wid, (nd, t) in ways.items():
    if t.get("railway") == "tram" and t.get("tunnel") != "yes" and t.get("layer", "0") in ("0", "1"):
        nn = [n for n in nd if n in nodes]
        if len(nn) < 2 or not visible([L(*nodes[n][:2]) for n in nn], 60): continue
        trams.append([gnode(n) for n in nn])

# --- areas: squares, parks, water, parking ------------------------------------------------------
areas = []
def add_area(k, r):
    r = [L(*nodes[n][:2]) for n in r if n in nodes]
    if len(r) < 4 or not visible(r, 40) or area(r) < 20: return
    rr = simplify(r, 0.5)
    areas.append([k, flat(rr[:-1] if rr[0] == rr[-1] else rr)])
def akind(t):
    if t.get("highway") in ("pedestrian", "footway") and t.get("area") == "yes": return 0
    if t.get("place") == "square" or t.get("area:highway") in ("pedestrian", "footway"): return 0
    if t.get("leisure") in ("park", "garden", "playground") or t.get("landuse") in ("grass", "village_green", "flowerbed", "meadow", "recreation_ground") or t.get("natural") in ("scrub", "grassland", "wood", "shrubbery"): return 1
    if t.get("natural") == "water" or t.get("waterway") == "riverbank": return 2
    if t.get("amenity") == "parking" and t.get("parking", "surface") == "surface": return 3
    if t.get("area:highway") in ("primary", "secondary", "tertiary", "residential", "unclassified", "service", "traffic_island"): return 4 if t.get("area:highway") != "traffic_island" else 0
    return None
for wid, (nd, t) in ways.items():
    if nd[0] != nd[-1]: continue
    k = akind(t)
    if k is not None: add_area(k, nd)
for rid, (mem, t) in rels.items():
    if t.get("type") != "multipolygon": continue
    k = akind(t)
    if k is None: continue
    for rr in assemble(mem): add_area(k, rr)

# --- trees, lamps --------------------------------------------------------------------------------
trees, lamps = [], []
def push_pt(arr, e, n, *extra):
    x, z = P(e, n)
    if (z > 40 and x < -30) or math.hypot(x, z) > 2700: return
    arr += [q(x), q(z), *extra]
for i, (lo, la, t) in nodes.items():
    if not t: continue
    if t.get("natural") == "tree":
        e, n = L(lo, la); push_pt(trees, e, n, int(num(t.get("height", "")) or (9 + h32(i) * 8)))
    elif t.get("highway") == "street_lamp":
        e, n = L(lo, la); push_pt(lamps, e, n)
for wid, (nd, t) in ways.items():
    if t.get("natural") == "tree_row":
        r = ring(nd)
        for (x1, y1), (x2, y2) in zip(r, r[1:]):
            d = math.hypot(x2 - x1, y2 - y1); k = max(1, int(d / 9))
            for j in range(k): push_pt(trees, x1 + (x2 - x1) * j / k, y1 + (y2 - y1) * j / k, int(9 + h32((wid, j)) * 8))

lampgrid = collections.defaultdict(list)
for i in range(0, len(lamps), 2): lampgrid[(lamps[i] // 250, lamps[i + 1] // 250)].append((lamps[i] / 10, lamps[i + 1] / 10))
def near_lamp(x, z, d):
    gx, gz = int(x * 10 // 250), int(z * 10 // 250)
    return any(math.hypot(x - a, z - b) < d for ox_ in (-1, 0, 1) for oz_ in (-1, 0, 1) for a, b in lampgrid.get((gx + ox_, gz + oz_), []))
added = 0
for rd in roads:
    if not rd["d"] and rd["k"] != 5: continue
    pts_ = [(gpts[n][0] / 10, gpts[n][1] / 10) for n in rd["n"]]
    acc, side = 0.0, 1
    step_ = 26 if rd["k"] <= 2 else 32
    for (x1, z1), (x2, z2) in zip(pts_, pts_[1:]):
        d = math.hypot(x2 - x1, z2 - z1)
        if d < 1e-3: continue
        nx_, nz_ = -(z2 - z1) / d, (x2 - x1) / d
        while acc < d:
            x = x1 + (x2 - x1) * acc / d + nx_ * side * (rd["w"] / 2 + 1.2); z = z1 + (z2 - z1) * acc / d + nz_ * side * (rd["w"] / 2 + 1.2)
            if math.hypot(x, z) < 2700 and not near_lamp(x, z, 18):
                lamps += [q(x), q(z)]; lampgrid[(int(x * 10 // 250), int(z * 10 // 250))].append((x, z)); added += 1
            if rd["k"] <= 1: side = -side
            acc += step_
        acc -= d
print("lamps added", added)

# --- landmarks for the camera and the labels -------------------------------------------------------
def node_named(nm, **kw):
    for i, (lo, la, t) in nodes.items():
        if t and t.get("name") == nm and all(t.get(k) == v for k, v in kw.items()): return P(*L(lo, la))
marks = {"gutenberg": node_named("Gutenberg-Denkmal"), "hauptwache": node_named("Hauptwache", place="square")}
marks = {k: [round(v[0], 1), round(v[1], 1)] for k, v in marks.items() if v}

data = {"G": G, "bearing": round(bearing, 2), "names": names, "roadnames": roadnames, "b": buildings, "pts": [v for p in gpts for v in p], "roads": roads,
        "trams": trams, "areas": areas, "trees": trees, "lamps": lamps, "marks": marks,
        "src": "Map data © OpenStreetMap contributors, ODbL"}
json.dump(data, open(OUT, "w"), separators=(",", ":"), ensure_ascii=False)
print("bearing", round(bearing, 1), "buildings", len(buildings), "named", sorted(seen_names), "roads", len(roads), "pts", len(gpts), "trams", len(trams),
      "areas", len(areas), "trees", len(trees) // 3, "lamps", len(lamps) // 2, "marks", marks)
