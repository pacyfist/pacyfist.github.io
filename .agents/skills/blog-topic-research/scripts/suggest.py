#!/usr/bin/env python3
"""Pull real autocomplete suggestions from Google and Bing for candidate topics.

Autocomplete is the closest thing to free search-volume data: engines only
suggest completions they actually see typed. A seed with a full ten-suggestion
tree on both engines has real, sustained demand. A seed that returns nothing but
its own echo has none, however exciting the technology is.

Usage:
    python3 suggest.py "seed term" ["another seed" ...]
    python3 suggest.py --deep "seed term"      # expand with a-z and question words

No dependencies, no API keys. Stdlib only.
"""

import json
import sys
import time
import urllib.parse
import urllib.request

# Pin the locale. Without hl/gl the endpoint infers a region from the caller,
# which for a Polish-based author leaks Polish-language completions ("... co to")
# into results meant to measure global English demand.
GOOGLE = "https://suggestqueries.google.com/complete/search?client=firefox&hl=en&gl=us&q="
BING = "https://api.bing.com/osjson.aspx?market=en-US&query="
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

QUESTION_WORDS = ["how to", "what is", "why", "when", "does", "can i", "vs", "error"]


def fetch(base, term):
    """Return the suggestion list for one term from one engine, or [] on failure."""
    url = base + urllib.parse.quote(term)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        # Both engines use the OpenSearch shape: [query, [suggestions], ...]
        return [s for s in data[1] if s.lower() != term.lower()]
    except Exception as e:
        print(f"  ! {base.split('/')[2]} failed for {term!r}: {e}", file=sys.stderr)
        return []


def probe(term):
    """Query both engines for one term. Returns (google, bing, both)."""
    g = fetch(GOOGLE, term)
    time.sleep(0.3)
    b = fetch(BING, term)
    time.sleep(0.3)
    both = sorted(set(x.lower() for x in g) & set(x.lower() for x in b))
    return g, b, both


def report(term, deep=False):
    g, b, both = probe(term)
    print(f"\n{'=' * 68}\nSEED: {term}\n{'=' * 68}")
    print(f"\nGoogle ({len(g)}):")
    for s in g:
        print(f"  - {s}")
    print(f"\nBing ({len(b)}):")
    for s in b:
        print(f"  - {s}")
    if both:
        print(f"\nOn BOTH engines ({len(both)}) <- strongest demand signal:")
        for s in both:
            print(f"  * {s}")
    else:
        print("\nNo overlap between engines.")

    if not g and not b:
        print("\n>> DEAD SEED. Nobody is typing this. If the topic still looks")
        print(">> good, the phrasing is wrong -- find the head term people do type.")

    if deep:
        print(f"\n--- deep expansion for {term!r} ---")
        suffixes = [chr(c) for c in range(ord("a"), ord("z") + 1)]
        found = {}
        for suf in suffixes:
            for s in fetch(GOOGLE, f"{term} {suf}"):
                found.setdefault(s.lower(), set()).add("g")
            time.sleep(0.15)
        for q in QUESTION_WORDS:
            for s in fetch(GOOGLE, f"{q} {term}"):
                found.setdefault(s.lower(), set()).add("q")
            time.sleep(0.15)
        print(f"\n{len(found)} expanded queries:")
        for s in sorted(found):
            print(f"  - {s}")


def main():
    args = [a for a in sys.argv[1:] if a != "--deep"]
    deep = "--deep" in sys.argv
    if not args:
        print(__doc__)
        sys.exit(1)
    for term in args:
        report(term, deep=deep)
    print("\nReading the results:")
    print("  Full tree on both engines  -> real, sustained demand.")
    print("  Rich tree on Google only   -> demand, but weaker Bing upside.")
    print("  Only 'release date'/'when' -> anticipation traffic; converts poorly.")
    print("  Nothing                    -> no demand at this phrasing.")


if __name__ == "__main__":
    main()
