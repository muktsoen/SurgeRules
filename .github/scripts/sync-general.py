#!/usr/bin/env python3
"""Merge SukkaW Always Real IP Plus + VirgilClyne General Enhanced
into General.sgmodule.

Sources:
  sukka  - https://ruleset.skk.moe/Modules/sukka_common_always_realip.sgmodule
  virgil - VirgilClyne GetSomeFries sgmodule/General.sgmodule

Merge rules:
  * always-real-ip: union; drop an exact entry when a wildcard in the
    union already covers it (Surge '*' matches a single label, so only
    single-label coverage is treated as redundant -- conservative).
  * skip-proxy: union; drop an IP range fully contained in a larger
    range (192.168.122.1/32 inside 192.168.0.0/16).
  * MITM hostname exclusions and hostname-disabled: union, kept as-is.
  * Directives are normalized to %APPEND% (VirgilClyne used %INSERT%;
    for these unordered sets the effect is identical).
  * Output lists are sorted alphabetically for deterministic diffs.

Deterministic: same inputs -> byte-identical output.
Prints a summary; 'unchanged' if the module is already up to date,
else rewrites General.sgmodule and prints 'changed'.
"""
import ipaddress
import re
import urllib.request

SOURCES = {
    "sukka": "https://ruleset.skk.moe/Modules/sukka_common_always_realip.sgmodule",
    "virgil": "https://github.com/VirgilClyne/GetSomeFries/raw/main/sgmodule/General.sgmodule",
}
MODULE_PATH = "General.sgmodule"
ICON = "https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Bypass.png"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "SurgeRules-sync"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8")


def general_list(text, key):
    m = re.search(rf"^{key}\s*=\s*%?(?:APPEND|INSERT)?%?\s*(.+)$", text, re.M)
    if not m:
        return []
    return [x.strip() for x in m.group(1).split(",") if x.strip()]


def mitm_list(text, key):
    m = re.search(r"\[MITM\](.*?)(?=\n\[|\Z)", text, re.S)
    if not m:
        return []
    mm = re.search(rf"^{key}\s*=\s*%?(?:APPEND|INSERT)?%?\s*(.+)$", m.group(1), re.M)
    if not mm:
        return []
    return [x.strip() for x in mm.group(1).split(",") if x.strip()]


def wildcard_covers(wildcard, entry):
    """Single-label '*' semantics: '*' matches exactly one dot-separated label."""
    if "*" not in wildcard or "*" in entry:
        return False
    pat = re.escape(wildcard).replace(r"\*", r"[^.]+")
    return re.fullmatch(pat, entry) is not None


def main():
    texts = {src: fetch(url) for src, url in SOURCES.items()}

    sukka_realip = general_list(texts["sukka"], "always-real-ip")
    virgil_skip = general_list(texts["virgil"], "skip-proxy")
    virgil_realip = general_list(texts["virgil"], "always-real-ip")
    virgil_mitm = mitm_list(texts["virgil"], "hostname")
    virgil_disabled = mitm_list(texts["virgil"], "hostname-disabled")

    # ---- always-real-ip: union, drop exact entries covered by a wildcard ----
    realip = sorted(set(sukka_realip) | set(virgil_realip), key=str.lower)
    wildcards = [x for x in realip if "*" in x]
    removed_covered = []
    kept_realip = []
    for e in realip:
        if "*" in e:
            kept_realip.append(e)
            continue
        cover = next((w for w in wildcards if wildcard_covers(w, e)), None)
        if cover:
            removed_covered.append((e, cover))
        else:
            kept_realip.append(e)
    kept_realip = sorted(kept_realip, key=str.lower)

    # ---- skip-proxy: union, drop IP ranges contained in a larger range ----
    skip = sorted(set(virgil_skip), key=str.lower)
    removed_contained = []
    kept_skip = list(skip)
    nets = {}
    for e in skip:
        try:
            nets[e] = ipaddress.ip_network(e, strict=False)
        except ValueError:
            pass
    for e1, n1 in nets.items():
        for e2, n2 in nets.items():
            if e1 != e2 and n1.version == n2.version and n1.subnet_of(n2) and n1 != n2:
                removed_contained.append((e1, e2))
                kept_skip.remove(e1)
                break
    kept_skip = sorted(kept_skip, key=str.lower)

    mitm = sorted(set(virgil_mitm), key=str.lower)
    disabled = sorted(set(virgil_disabled), key=str.lower)

    out = []
    out.append("#!name=General")
    out.append("#!desc=通用增强：返回真实 IP、跳过代理、MITM 排除。合并自 SukkaW Always Real IP Plus + VirgilClyne General Enhanced，去重后每周一自动更新。")
    out.append("#!author=SukkaW, VirgilClyne")
    out.append(f"#!icon={ICON}")
    out.append("")
    out.append("[General]")
    out.append(f"skip-proxy = %APPEND% {', '.join(kept_skip)}")
    out.append(f"always-real-ip = %APPEND% {', '.join(kept_realip)}")
    out.append("")
    out.append("[MITM]")
    out.append(f"hostname = %APPEND% {', '.join(mitm)}")
    out.append(f"hostname-disabled = %APPEND% {', '.join(disabled)}")
    new_content = "\n".join(out).strip() + "\n"

    print(f"always-real-ip: sukka={len(sukka_realip)} virgil={len(virgil_realip)} union={len(set(sukka_realip) | set(virgil_realip))} removed covered={len(removed_covered)} merged={len(kept_realip)}")
    for e, w in removed_covered:
        print(f"  covered: {e} by {w}")
    print(f"skip-proxy: virgil={len(virgil_skip)} removed contained={len(removed_contained)} merged={len(kept_skip)}")
    for e1, e2 in removed_contained:
        print(f"  contained: {e1} in {e2}")
    print(f"mitm hostname: {len(mitm)}; hostname-disabled: {len(disabled)}")
    try:
        old = open(MODULE_PATH, encoding="utf-8").read()
    except FileNotFoundError:
        old = ""
    if old == new_content:
        print("unchanged")
    else:
        open(MODULE_PATH, "w", encoding="utf-8").write(new_content)
        print("changed")


if __name__ == "__main__":
    main()
