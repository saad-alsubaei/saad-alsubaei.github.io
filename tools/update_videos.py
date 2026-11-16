"""مرئيات المكتبة من قناة يوتيوب تلقائياً ← videos.json (يُشغَّل من GitHub Actions كل ٣ ساعات).

التصنيفات = «قوائم التشغيل» (Playlists) في قناة صاحب المكتبة: كل قائمة تصير تصنيفاً في المكتبة،
فيكفي أن يضيف المقطع إلى قائمته في يوتيوب ليظهر في مكانه هنا. المقاطع التي ليست في أي قائمة تظهر في «متنوعة».

الإعدادات في books.json ← site:
  "social": {"youtube": "https://www.youtube.com/@handle"}   رابط القناة (مطلوب)
  "youtubeChannelId": "UC…"     اختياري (يُستخرج من الرابط تلقائياً)
  "videoLists": [{"id": "PL…", "title": "اسم يظهر في المكتبة"}]   اختياري: ترتيب التصنيفات وأسماؤها،
                 ويمكن إخفاء قائمة بـ "hide": true. بدونه تظهر كل قوائم القناة بترتيبها في يوتيوب.
مفتاح YouTube Data API (مجاني) في Secrets باسم YT_API_KEY: يجلب كل المقاطع والمدد.
بدون مفتاح: يقرأ آخر ١٥ مقطعاً من كل قائمة عبر RSS ويُبقي ما سبق حفظه (يتراكم مع الوقت).
"""
import json, os, re, sys, urllib.request, urllib.parse, xml.etree.ElementTree as ET, datetime, http.client

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "videos.json")
site = json.load(open(os.path.join(ROOT, "books.json"), encoding="utf-8")).get("site", {})
yt_url = ((site.get("social") or {}).get("youtube") or "").strip()
KEY = os.environ.get("YT_API_KEY", "").strip()
UA = {"User-Agent": "Mozilla/5.0 (library-bot)", "Accept-Language": "ar,en;q=0.8"}
if not yt_url:
    print("لا يوجد رابط قناة يوتيوب في site.social.youtube — تم التخطي"); sys.exit(0)

def fetch(url, data=None):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")

def api(path, **q):
    q["key"] = KEY
    return json.loads(fetch("https://www.googleapis.com/youtube/v3/" + path + "?" + urllib.parse.urlencode(q)))

# ---------- القناة ----------
cid = (site.get("youtubeChannelId") or "").strip()
if not cid:
    m = re.search(r"/channel/(UC[\w-]{22})", yt_url)
    if m: cid = m.group(1)
if not cid and KEY:
    h = re.search(r"@([\w.\-]+)", yt_url)
    if h:
        r = api("channels", part="id", forHandle="@" + h.group(1))
        if r.get("items"): cid = r["items"][0]["id"]
if not cid:
    html = fetch(yt_url)
    m = re.search(r'"(?:externalId|channelId)":"(UC[\w-]{22})"', html) or re.search(r"channel_id=(UC[\w-]{22})", html)
    if m: cid = m.group(1)
if not cid:
    print("تعذّر معرفة معرّف القناة — أضف site.youtubeChannelId"); sys.exit(1)
uploads = "UU" + cid[2:]
print("القناة:", cid)

old = {}
try: old = json.load(open(OUT, encoding="utf-8"))
except Exception: pass
oldv = {v["yt"]: v for v in old.get("videos", [])}

videos, lists = {}, []

def add(vid, title, date, lid=None, dur=None):
    v = videos.get(vid)
    if v is None:
        v = dict(oldv.get(vid, {}), yt=vid)
        if KEY: v["lists"] = []  # مع المفتاح نعرف عضوية القوائم كاملة، فنبدأ من جديد
    v["title"] = title or v.get("title", "")
    if date: v["date"] = date[:10]
    if dur is not None: v["dur"] = dur
    v.setdefault("lists", [])
    if lid and lid not in v["lists"]: v["lists"].append(lid)
    videos[vid] = v

def iso_dur(s):
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m: return None
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se

if KEY:
    # كل القوائم وكل مقاطعها
    tok = ""
    while True:
        r = api("playlists", part="snippet,contentDetails", channelId=cid, maxResults=50, pageToken=tok)
        for it in r.get("items", []):
            lists.append({"id": it["id"], "title": it["snippet"]["title"].strip(), "count": it["contentDetails"].get("itemCount", 0)})
        tok = r.get("nextPageToken") or ""
        if not tok: break
    def items(pid, lid):
        tok = ""
        while True:
            r = api("playlistItems", part="snippet,contentDetails", playlistId=pid, maxResults=50, pageToken=tok)
            for it in r.get("items", []):
                sn = it["snippet"]; vid = it["contentDetails"].get("videoId")
                if not vid or sn.get("title") in ("Private video", "Deleted video"): continue
                add(vid, sn.get("title", "").strip(), it["contentDetails"].get("videoPublishedAt") or sn.get("publishedAt", ""), lid)
            tok = r.get("nextPageToken") or ""
            if not tok: break
    items(uploads, None)
    for l in lists: items(l["id"], l["id"])
    ids = list(videos)
    for i in range(0, len(ids), 50):
        r = api("videos", part="contentDetails,status", id=",".join(ids[i:i + 50]))
        for it in r.get("items", []):
            v = videos.get(it["id"])
            if v is not None: v["dur"] = iso_dur(it["contentDetails"].get("duration"))
else:
    # بدون مفتاح: RSS (آخر ١٥ مقطعاً لكل قائمة) + أسماء القوائم من صفحة القناة
    NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015", "m": "http://search.yahoo.com/mrss/"}
    def rss(q, lid):
        root = ET.fromstring(fetch("https://www.youtube.com/feeds/videos.xml?" + q))
        for e in root.findall("a:entry", NS):
            add(e.findtext("yt:videoId", "", NS), (e.findtext("a:title", "", NS) or "").strip(), e.findtext("a:published", "", NS), lid)
        return (root.findtext("a:title", "", NS) or "").strip()
    rss("channel_id=" + cid, None)
    seen = []  # بترتيب ظهورها في القناة
    try:
        page = fetch(yt_url.rstrip("/") + "/playlists")
        for m in re.finditer(r'"playlistId":"((?:PL|OL)[\w-]+)"', page):
            pid = m.group(1)
            if pid not in seen: seen.append(pid)
    except Exception as e:
        print("صفحة القوائم:", e)
    for l in site.get("videoLists") or []:
        if l.get("id") and l["id"] not in seen: seen.append(l["id"])
    for pid in seen:
        try:
            t = rss("playlist_id=" + pid, pid)
            lists.append({"id": pid, "title": t})
        except Exception as e:
            print("قائمة", pid, e)
    # المقاطع القديمة المحفوظة تبقى (RSS لا يعرض إلا الأحدث)
    for vid, v in oldv.items():
        if vid not in videos: videos[vid] = v

# ---------- المقاطع القصيرة: /shorts/ID يرد 200 للقصير ويحوّل للعادي ----------
def is_short(vid):
    try:
        c = http.client.HTTPSConnection("www.youtube.com", timeout=20)
        c.request("HEAD", "/shorts/" + vid, headers=UA); r = c.getresponse(); c.close()
        return r.status == 200
    except Exception:
        return None
for vid, v in videos.items():
    if "short" not in v or v.get("short") is None:
        s = is_short(vid)
        if s is not None: v["short"] = s
    elif v.get("dur") and v["dur"] > 180: v["short"] = False

# ---------- ترتيب وأسماء التصنيفات من books.json إن وُجدت ----------
conf = site.get("videoLists") or []
if conf:
    byid = {l["id"]: l for l in lists}
    ordered = []
    for c in conf:
        l = byid.pop(c.get("id"), None)
        if l is None or c.get("hide"): continue
        if c.get("title"): l["title"] = c["title"]
        ordered.append(l)
    lists = ordered + list(byid.values())
hidden = {c["id"] for c in conf if c.get("hide")}
lists = [l for l in lists if l["id"] not in hidden and any(l["id"] in v.get("lists", []) for v in videos.values())]
for v in videos.values():
    v["lists"] = [x for x in v.get("lists", []) if any(x == l["id"] for l in lists)]
for l in lists:
    l["count"] = sum(1 for v in videos.values() if l["id"] in v["lists"])

vs = sorted(videos.values(), key=lambda v: v.get("date", ""), reverse=True)
data = {"channel": cid, "lists": lists, "videos": [{k: v[k] for k in ("yt", "title", "date", "dur", "short", "lists") if k in v and v[k] not in (None, "")} for v in vs]}
if {k: data[k] for k in ("lists", "videos")} == {k: old.get(k) for k in ("lists", "videos")}:
    print("لا تغيير"); sys.exit(0)
data["updated"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"✓ videos.json: {len(vs)} مقطعاً، {len(lists)} تصنيفاً")
