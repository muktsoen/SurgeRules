#!/usr/bin/env python3
"""Merge three HTTPDNS blocker modules into BlockHTTPDNS.sgmodule.

Sources:
  beta     - QingRex LoonKissSurge Beta HTTPDNS拦截器
  official - VirgilClyne GetSomeFries 拦截HTTPDNS (Official)
  bm7      - blackmatrix7 BlockHTTPDNS

Merge rules (all behavior-preserving, every rule is REJECT):
  * Union across sources; dedupe by (type, value, action).
  * Params are unioned (blackmatrix7 omits extended-matching/pre-matching).
  * DOMAIN / DOMAIN-SUFFIX containing "httpdns"/"httpsdns" are dropped:
    the two DOMAIN-KEYWORD rules at the top already match them.
  * DOMAIN covered by an identical DOMAIN-SUFFIX, and DOMAIN-SUFFIX
    covered by a parent suffix, are dropped.
  * An IP range fully contained in a larger range is dropped
    (no aggregation: never widen a range, never merge /32s into /24s).
  * USER-AGENT case variants are kept as-is (Surge case-sensitivity
    of USER-AGENT matching is unconfirmed).
  * [URL Rewrite] lines are converted to Surge syntax (no dash, no
    quotes) and bracketed IPv6 literals "[...]" are unbracketed
    (blackmatrix7 writes them as regex character classes, which
    over-match; the correct unbracketed form exists in Official).
  * [Map Local], [MITM] hosts and force-http-engine-hosts are unioned.

Deterministic: same inputs -> byte-identical output.
Prints a summary; 'unchanged' if the module is already up to date,
else rewrites BlockHTTPDNS.sgmodule and prints 'changed'.
"""
import csv
import io
import ipaddress
import re
import sys
import urllib.request

SOURCES = {
    "beta": "https://raw.githubusercontent.com/QingRex/LoonKissSurge/refs/heads/main/Surge/Beta/HTTPDNS%E6%8B%A6%E6%88%AA%E5%99%A8.beta.sgmodule",
    "official": "https://raw.githubusercontent.com/QingRex/LoonKissSurge/refs/heads/main/Surge/Official/%E6%8B%A6%E6%88%AAHTTPDNS.official.sgmodule",
    "bm7": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rewrite/Surge/BlockHTTPDNS/BlockHTTPDNS.sgmodule",
}
MODULE_PATH = "BlockHTTPDNS.sgmodule"
ICON = "https://raw.githubusercontent.com/luestr/IconResource/main/Other_icon/120px/HTTPDNS.png"

TYPE_ORDER = ["DOMAIN-KEYWORD", "USER-AGENT", "URL-REGEX", "DOMAIN",
              "DOMAIN-SUFFIX", "IP-CIDR", "IP-CIDR6"]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "SurgeRules-sync"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8")


def section(text, name):
    m = re.search(r"\[" + re.escape(name) + r"\](.*?)(?=\n\[|\Z)", text, re.S)
    return m.group(1) if m else ""


def split_rule(line):
    try:
        parts = next(csv.reader(io.StringIO(line)))
    except Exception:
        parts = line.split(",")
    parts = [p.strip() for p in parts]
    if len(parts) < 3:
        return None
    return parts[0], parts[1], parts[2], tuple(parts[3:])


def main():
    texts = {src: fetch(url) for src, url in SOURCES.items()}

    # ---- [Rule]: union + param union ----
    keys = {}  # (type, value, action) -> set(params)
    raw_counts = {}
    for src, text in texts.items():
        n = 0
        for line in section(text, "Rule").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            r = split_rule(line)
            if not r:
                print(f"WARN unparsed rule {src}: {line}", file=sys.stderr)
                continue
            typ, value, action, params = r
            keys.setdefault((typ, value, action), set()).update(params)
            n += 1
        raw_counts[src] = n
    beta_keys = set()
    for line in section(texts["beta"], "Rule").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        r = split_rule(line)
        if r:
            beta_keys.add(r[:3])

    # semantic dedupe
    removed_shadowed = []
    removed_contained = []
    merged = dict(keys)
    for k in list(merged):
        typ, value, action = k
        if typ in ("DOMAIN", "DOMAIN-SUFFIX") and ("httpdns" in value.lower() or "httpsdns" in value.lower()):
            removed_shadowed.append(k)
            del merged[k]
    for k in list(merged):
        typ, value, action = k
        if typ == "DOMAIN" and (typ.replace("DOMAIN", "DOMAIN-SUFFIX"), value, action) in merged:
            removed_shadowed.append(k)
            del merged[k]
    suffixes = {k[1] for k in merged if k[0] == "DOMAIN-SUFFIX"}
    for k in list(merged):
        if k[0] == "DOMAIN-SUFFIX" and any(k[1] != p and k[1].endswith("." + p) for p in suffixes):
            removed_shadowed.append(k)
            del merged[k]
    ip_keys = [k for k in merged if k[0] in ("IP-CIDR", "IP-CIDR6")]
    nets = {}
    for k in ip_keys:
        try:
            nets[k] = ipaddress.ip_network(k[1], strict=False)
        except ValueError:
            pass
    for k1, n1 in nets.items():
        for k2, n2 in nets.items():
            if k1 != k2 and k1[0] == k2[0] and k1[2] == k2[2] \
                    and n1.version == n2.version and n1.subnet_of(n2) and n1 != n2:
                removed_contained.append((k1, k2))
                merged.pop(k1, None)
                break

    def param_str(params):
        order = ["extended-matching", "no-resolve", "pre-matching"]
        ps = sorted(params, key=lambda p: order.index(p) if p in order else 99)
        return "," + ",".join(ps) if ps else ""

    def quote_value(typ, value):
        return f'"{value}"' if typ in ("USER-AGENT", "URL-REGEX") else value

    def sort_key(item):
        typ, value, action = item[0]
        if typ in ("IP-CIDR", "IP-CIDR6"):
            try:
                return (TYPE_ORDER.index(typ), int(ipaddress.ip_network(value, strict=False).network_address))
            except ValueError:
                pass
        return (TYPE_ORDER.index(typ), value.lower())

    rule_lines = []
    for (typ, value, action), params in sorted(merged.items(), key=sort_key):
        rule_lines.append(f"{typ},{quote_value(typ, value)},{action}{param_str(params)}")

    # ---- [URL Rewrite]: normalize to Surge syntax, dedupe ----
    rewrites = set()
    for src, text in texts.items():
        for line in section(text, "URL Rewrite").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if " - " in line:
                pat, act = line.rsplit(" - ", 1)
            else:
                pat, act = line.rsplit(" ", 1)
            pat = pat.strip()
            if len(pat) >= 2 and pat.startswith('"') and pat.endswith('"'):
                pat = pat[1:-1]
            # unbracket IPv6 literals mistakenly written as char classes
            pat = re.sub(r"\[([0-9a-fA-F:]+)\]",
                         lambda m: m.group(1) if m.group(1).count(":") >= 2 else m.group(0), pat)
            rewrites.add((pat, act.strip()))
    rewrite_lines = [f"{p} {a}" for p, a in sorted(rewrites)]

    # ---- [Map Local] ----
    maplocal = set()
    for src, text in texts.items():
        for line in section(text, "Map Local").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                maplocal.add(line)
    maplocal_lines = sorted(maplocal)

    # ---- [MITM] hosts ----
    hosts = set()
    for src, text in texts.items():
        for line in section(text, "MITM").splitlines():
            line = line.strip()
            if line.startswith("hostname"):
                hosts.update(h.strip() for h in line.split("=", 1)[1].replace("%APPEND%", "").split(",") if h.strip())
    mitm_hosts = sorted(hosts)

    # ---- [General] force-http-engine-hosts (first-seen order) ----
    engine_hosts = []
    for src in ("official", "bm7", "beta"):
        for line in section(texts[src], "General").splitlines():
            line = line.strip()
            if line.startswith("force-http-engine-hosts"):
                for h in line.split("=", 1)[1].replace("%APPEND%", "").split(","):
                    h = h.strip()
                    if h and h not in engine_hosts:
                        engine_hosts.append(h)

    # ---- assemble ----
    out = []
    out.append("#!name=BlockHTTPDNS")
    out.append("#!desc=拦截常见 HTTPDNS 服务。合并自 QingRex Beta、VirgilClyne Official、blackmatrix7 三份，去重后每周一自动更新。")
    out.append("#!author=QingRex, VirgilClyne, blackmatrix7")
    out.append(f"#!icon={ICON}")
    out.append("")
    out.append("[General]")
    out.append(f"force-http-engine-hosts = %APPEND% {', '.join(engine_hosts)}")
    out.append("")
    out.append("[Rule]")
    out.extend(rule_lines)
    out.append("")
    out.append("[URL Rewrite]")
    out.extend(rewrite_lines)
    out.append("")
    if maplocal_lines:
        out.append("[Map Local]")
        out.extend(maplocal_lines)
        out.append("")
    out.append("[MITM]")
    out.append(f"hostname = %APPEND% {', '.join(mitm_hosts)}")
    new_content = "\n".join(out).strip() + "\n"

    # ---- summary ----
    beta_nonshadowed = {k for k in beta_keys
                        if not (k[0] in ("DOMAIN", "DOMAIN-SUFFIX")
                                and ("httpdns" in k[1].lower() or "httpsdns" in k[1].lower()))}
    new_vs_beta = len(set(merged) - beta_nonshadowed)
    print(f"raw rules: beta={raw_counts['beta']} official={raw_counts['official']} bm7={raw_counts['bm7']} (total {sum(raw_counts.values())})")
    print(f"union keys: {len(keys)}; removed shadowed: {len(removed_shadowed)}; removed IP-contained: {len(removed_contained)}")
    print(f"merged rules: {len(rule_lines)} (new vs beta non-shadowed: {new_vs_beta})")
    print(f"rewrites: {len(rewrite_lines)}; map-local: {len(maplocal_lines)}; mitm hosts: {len(mitm_hosts)}; engine hosts: {len(engine_hosts)}")
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
