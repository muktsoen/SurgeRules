#!/usr/bin/env python3
"""Sync Umetrip.sgmodule from the upstream Loon plugin (xingjiu29/Umetrip).

Deterministic conversion: Loon [Rule]/[Script]/[Rewrite]/[MitM] -> Surge .sgmodule.
Prints 'unchanged' if the module is already up to date, else rewrites
Umetrip.sgmodule in place and prints 'changed'.
"""
import re
import sys
import urllib.request

PLUGIN_URL = "https://raw.githubusercontent.com/xingjiu29/Umetrip/refs/heads/main/umetrip.plugin"
MODULE_PATH = "Umetrip.sgmodule"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "SurgeRules-sync"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8")


def section(text, name):
    m = re.search(r"\[" + re.escape(name) + r"\](.*?)(?=\n\[|\Z)", text, re.S)
    return m.group(1).strip() if m else ""


def main():
    plugin = fetch(PLUGIN_URL)

    def meta(key):
        m = re.search(r"^#!" + re.escape(key) + r"\s*=\s*(.+)$", plugin, re.M)
        return m.group(1).strip() if m else ""

    name = meta("name") or "航旅纵横去广告"
    desc = meta("desc") or ""
    author = meta("author") or ""
    icon = meta("icon") or ""
    header = [f"#!name={name}"]
    if desc:
        if author:
            header.append(f"#!desc={desc}。由 Loon 插件转换，原作者：{author}，源仓库 xingjiu29/Umetrip")
        else:
            header.append(f"#!desc={desc}")
    if author:
        header.append(f"#!author={author}")
    if icon:
        header.append(f"#!icon={icon}")
    out = ["\n".join(header), ""]

    rules = [l.strip() for l in section(plugin, "Rule").splitlines()
             if l.strip() and not l.strip().startswith("#")]
    out.append("[Rule]")
    out.extend(rules)
    out.append("")

    script_lines = [l.strip() for l in section(plugin, "Script").splitlines()
                    if l.strip() and not l.strip().startswith("#")]
    out.append("[Script]")
    for line in script_lines:
        m = re.search(r"~=\s*/(.+?)/i\s+then\s+script\(\"([^\"]+)\"\)\s+with\s+(.*)$", line)
        if not m:
            print(f"WARN: unparsed script line: {line}", file=sys.stderr)
            continue
        regex_body, script_url, opts = m.group(1), m.group(2), m.group(3)
        timeout = "30"
        tm = re.search(r"timeout=(\d+)", opts)
        if tm:
            timeout = tm.group(1)
        req_body = "1" if "requires_body=true" in opts else "0"
        bin_mode = "1" if "binary_body_mode=true" in opts else "0"
        out.append(f"Umetrip = type=http-response, pattern=(?i){regex_body}, "
                   f"requires-body={req_body}, binary-body-mode={bin_mode}, "
                   f"timeout={timeout}, engine=jsc, script-path={script_url}")
    out.append("")

    rewrites = [l.strip() for l in section(plugin, "Rewrite").splitlines()
                if l.strip() and not l.strip().startswith("#")]
    out.append("[URL Rewrite]")
    for line in rewrites:
        if " - " in line:
            pat, act = line.rsplit(" - ", 1)
            out.append(f"{pat.strip()} {act.strip()}")
        else:
            out.append(line)
    out.append("")

    hostnames = ""
    for line in section(plugin, "MitM").splitlines():
        line = line.strip()
        if line.startswith("hostname"):
            hostnames = line.split("=", 1)[1].strip()
    out.append("[MITM]")
    out.append(f"hostname = {hostnames}")

    new_content = "\n".join(out).strip() + "\n"
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
