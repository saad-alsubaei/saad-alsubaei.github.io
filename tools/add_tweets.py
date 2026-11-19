#!/usr/bin/env python3
"""إضافة تغريدات جديدة لقسم «من تغريدات الدكتور» من قائمة الانتظار tweets-queue.json.

لوحة الإدارة (admin.html) تكتب في tweets-queue.json، وهذا السكربت (يشغّله tweets.yml تلقائياً) :
  {"url": "https://x.com/.../status/123", "cat": ""}   ← يجلب النص والصور من رابط التغريدة
  {"id": "123", "text": "...", "imgs": ["tw/in/a.jpg"], "cat": "", "date": "2026-11-19"}  ← إضافة يدوية
  {"del": "123"}                                        ← حذف تغريدة من القسم
المجاني فقط: يستخدم صفحة التضمين العامة للتغريدات (بلا مفتاح ولا اشتراك).
"""
import json, os, re, sys, html, io, datetime, urllib.request, urllib.parse
from PIL import Image

Q, DB = "tweets-queue.json", "tweets.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; library-bot/1.0)"}

CAT = [('الأذكار والأدعية', r'دعاء|الدعاء|يدعو|تسبيح|التسبيح|استغفار|اللهم|أذكار|الذكر|يارب|سبحان', 1.3),
 ('الحديث ورجاله', r'حديث|الحديث|المحدث|الحافظ|رواه|روى|إسناد|سنده|بسند|ضعيف|البخاري|مسلم|الترمذي|أبوداود|أبي داود|النسائي|ابن ماجه|مسند|سنن|الدارقطني|ابن معين|الرواة|راوي|العلل|الجرح|الضعفاء', 1.2),
 ('الفقه والأحكام', r'حكم|يجوز|لا يجوز|الصلاة|صلاة|الجمعة|الأضحية|الحج|الصيام|صوم|رمضان|زكاة|الزكاة|فتوى|أفتى|الإجماع|الفقه|فقهاء|المذهب|الطهارة|الوضوء|الجنائز|المساجد|المسجد|بدعة|البدع|سنة', 1.1),
 ('السيرة والصحابة', r'النبي ﷺ|رسول الله|ﷺ|الصحابي|الصحابة|أبو بكر|أبي بكر|عمر بن الخطاب|عثمان|علي بن أبي طالب|أم المؤمنين|حجة الوداع|غزوة|السيرة', 1.1),
 ('المرأة والأسرة', r'المرأة|امرأة|الزوج|الزوجة|زوجته|النساء|الأبناء|الأولاد|البنات|الأسرة', 1.0),
 ('اللغة والأدب', r'شعر|الشاعر|أبيات|بيت|قصيدة|النحو|النحوي|اللغة|العربية|الأدب|المتنبي|البلاغة|فصاحة', 1.0),
 ('التاريخ والكتب', r'كتاب|كتب|الكتاب|مخطوط|طبعة|تحقيق|حقق|الأندلس|تاريخ|التاريخ|رحلة|غرناطة|قرطبة|إشبيلية|دمشق|بغداد|الدولة|خليفة|مؤلف|مصنف|المكتبة', 0.9),
 ('أخلاق وسير السلف', r'السلف|الزهد|الورع|الأخلاق|العقلاء|ترجمة|رحمه الله|العلماء|قال الإمام', 0.9)]

def categorize(t, cats):
    sc = {c: len(re.findall(p, t)) * w for c, p, w in CAT}
    best = max(sc, key=sc.get)
    c = best if sc[best] > 0 else 'خواطر وطرائف'
    return c if c in cats else cats[-1]

def clean(t):
    t = html.unescape(t or "")
    t = re.sub(r'https://t\.co/\S+', '', t)
    return re.sub(r'\n{3,}', '\n\n', t).strip()

norm = lambda x: re.sub(r'[\W_\d]+', '', x)[:70]

def get(url, raw=False):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
        b = r.read()
    return b if raw else json.loads(b.decode("utf-8"))

def tweet_id(s):
    m = re.search(r'status(?:es)?/(\d{6,25})', s or "") or re.fullmatch(r'\s*(\d{6,25})\s*', s or "")
    return m.group(1) if m else None

def fetch(tid):
    """يجلب نص التغريدة وصورها مجاناً بلا مفتاح.
    ١) خدمة FxTwitter العامة المجانية (تعمل مع حساب الدكتور).  ٢) صفحة التضمين الرسمية احتياطاً."""
    err = None
    try:
        d = get(f"https://api.fxtwitter.com/i/status/{tid}")
        t = d.get("tweet") or {}
        if t.get("id"):
            photos = [m["url"] for m in ((t.get("media") or {}).get("photos") or []) if m.get("url")]
            ts = t.get("created_timestamp")
            date = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d") if ts else datetime.date.today().isoformat()
            return clean(t.get("text") or ""), photos, date
        err = d.get("message")
    except Exception as ex: err = str(ex)
    d = get(f"https://cdn.syndication.twimg.com/tweet-result?id={tid}&lang=ar&token={_token(tid)}")
    if not d or d.get("__typename") == "TweetTombstone":
        raise RuntimeError("تعذّر جلب التغريدة تلقائياً (قد تكون محذوفة) — استخدم «الإضافة اليدوية»")
    text = d.get("text") or ""
    nt = (d.get("note_tweet") or {}).get("note_tweet_results", {}).get("result", {}).get("text")
    if nt: text = nt
    photos = [m["media_url_https"] for m in d.get("mediaDetails") or [] if m.get("type") == "photo"]
    date = (d.get("created_at") or "")[:10] or datetime.date.today().isoformat()
    return clean(text), photos, date

def _token(tid):
    # نفس معادلة التضمين الرسمية: ((id/1e15)*π).toString(36) — نحسبها بـ node إن وُجد لمطابقة دقّة جافاسكربت
    import math, subprocess
    try:
        out = subprocess.run(["node", "-e", f"process.stdout.write(((Number('{tid}')/1e15)*Math.PI).toString(36).replace(/(0+|\\.)/g,''))"], capture_output=True, text=True, timeout=10).stdout.strip()
        if out: return out
    except Exception: pass
    return re.sub(r'(0+|\.)', '', _b36((int(tid) / 1e15) * math.pi))[:11]

def _b36(x):
    # مثل Number.prototype.toString(36) في جافاسكربت للأعداد الكسرية
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    ip, fp = int(x), x - int(x); s = ""
    while True:
        s = digits[ip % 36] + s; ip //= 36
        if not ip: break
    if fp:
        s += "."
        for _ in range(12):
            fp *= 36; d = int(fp); s += digits[d]; fp -= d
            if not fp: break
    return s

def save_img(src_bytes, name):
    im = Image.open(io.BytesIO(src_bytes)).convert("RGB")
    m = im.copy(); m.thumbnail((900, 900), Image.LANCZOS); m.save("tw/m/" + name, quality=76, optimize=True, progressive=True)
    t = im.copy(); t.thumbnail((420, 560), Image.LANCZOS); t.save("tw/t/" + name, quality=72, optimize=True, progressive=True)
    return {"t": "tw/t/" + name, "m": "tw/m/" + name, "w": m.size[0], "h": m.size[1]}

def main():
    if not os.path.exists(Q): return
    queue = json.load(open(Q, encoding="utf-8"))
    if not queue: return
    db = json.load(open(DB, encoding="utf-8"))
    cats = db.get("cats") or []
    items = db["items"]; ids = {x["id"] for x in items}; texts = {norm(x["text"]): x["id"] for x in items}
    os.makedirs("tw/t", exist_ok=True); os.makedirs("tw/m", exist_ok=True)
    left, log = [], []
    for e in queue:
        try:
            if e.get("del"):
                tid = tweet_id(e["del"]) or str(e["del"])
                x = next((x for x in items if x["id"] == tid), None)
                if x:
                    for im in x.get("imgs", []):
                        for p in (im["t"], im["m"]):
                            if os.path.exists(p): os.remove(p)
                    items.remove(x); ids.discard(tid); texts.pop(norm(x["text"]), None)
                log.append(f"حذف {tid}"); continue
            tid = tweet_id(e.get("url") or "") or (str(e["id"]) if e.get("id") else None)
            if e.get("text") is not None and not tid: tid = "m" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S") + str(queue.index(e))
            if not tid: raise RuntimeError("الرابط غير صحيح — انسخ رابط التغريدة من زر المشاركة")
            if e.get("test"):   # فحص الجلب فقط بدون إضافة (للتأكد أن الخدمة تعمل)
                text, photos, date = fetch(tid)
                json.dump({"id": tid, "date": date, "photos": photos, "text": text[:300]}, open("tweets-test.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                log.append(f"فحص ناجح {tid}"); continue
            if tid in ids: log.append(f"موجودة مسبقاً {tid}"); continue
            if e.get("text") is not None:   # إضافة يدوية
                text, date = clean(e["text"]), e.get("date") or datetime.date.today().isoformat()
                blobs = []
                for p in e.get("imgs") or []:
                    blobs.append(open(p, "rb").read()); os.remove(p)
            else:
                text, photos, date = fetch(tid)
                blobs = [get(u if "fxtwitter" in u or "name=" in u else u + ("&" if "?" in u else "?") + "name=large", raw=True) for u in photos[:4]]
            if not text: raise RuntimeError("لا يوجد نص في التغريدة")
            k = norm(text)
            if k in texts: log.append(f"مكررة (نفس نص {texts[k]})"); continue
            imgs = [save_img(b, f"{tid}-{j}.jpg") for j, b in enumerate(blobs)]
            title = text.split("\n")[0].strip()
            cat = e.get("cat") if e.get("cat") in cats else categorize(text, cats)
            items.append({"id": tid, "date": date, "title": title if len(title) <= 90 else title[:88] + "…", "text": text, "cat": cat, "imgs": imgs, "added": datetime.date.today().isoformat()})
            ids.add(tid); texts[k] = tid; log.append(f"أضيفت {tid} ← {cat}")
        except Exception as ex:
            # تبقى في القائمة مع سبب الفشل لتظهر في لوحة الإدارة (يمكن حذفها أو إضافتها يدوياً من هناك)
            e["error"] = str(ex)[:200]; left.append(e)
            log.append(f"فشل: {e.get('url') or e.get('id')} — {e['error']}")
    items.sort(key=lambda x: (x.get("date") or "", x["id"]), reverse=True)
    json.dump(db, open(DB, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(left, open(Q, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n".join(log))

if __name__ == "__main__":
    main()
