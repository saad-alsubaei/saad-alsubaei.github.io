import json, urllib.request, sys, re
sys.path.insert(0, "tools"); import add_tweets as a
tid = json.load(open("tweets-queue.json"))[0]["url"].split("/")[-1]
out = {}
def tryget(name, url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"})
        with urllib.request.urlopen(req, timeout=30) as r: b = r.read().decode("utf-8", "replace"); out[name] = {"status": r.status, "body": b[:1500]}
    except Exception as e: out[name] = {"err": str(e)[:300]}
tryget("synd_tok", f"https://cdn.syndication.twimg.com/tweet-result?id={tid}&lang=ar&token={a._token(tid)}")
tryget("synd_a", f"https://cdn.syndication.twimg.com/tweet-result?id={tid}&lang=en&token=a")
tryget("fx", f"https://api.fxtwitter.com/alsubaeisaaad/status/{tid}")
tryget("vx", f"https://api.vxtwitter.com/alsubaeisaaad/status/{tid}")
tryget("oembed", f"https://publish.twitter.com/oembed?url=https://x.com/alsubaeisaaad/status/{tid}&omit_script=1")
json.dump(out, open("tweets-test.json", "w"), ensure_ascii=False, indent=1)
