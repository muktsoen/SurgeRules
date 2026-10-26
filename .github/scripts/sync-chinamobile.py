#!/usr/bin/env python3
"""中国移动去广告 Surge 模块自动同步转换器。

上游：ccyykk666 的 Loon 插件
  https://raw.githubusercontent.com/ccyykk666/Loon-Plugin/main/plugins/china-mobile/china_mobile_ad.plugin
  https://raw.githubusercontent.com/ccyykk666/Loon-Plugin/main/plugins/china-mobile/remove_ads.js

每次运行：
  1. 读上游插件，解析 [Argument] 开关、[Script] 脚本规则、[Rewrite] 改写规则、[MITM] 域名。
  2. 给上游 remove_ads.js 打移植补丁，生成 ChinaMobile.js：
     - 前置纯 JS AES 垫片（chinamobile-shim.js，模拟 Loon 的 $crypto.aes）；
     - $argument 由对象改为分号字符串解析；
     - ARGUMENT_DEFAULTS 按上游 [Argument] 重算；
     - 补 Loon Rewrite 两条（支付弹窗 data=null、广告接口 body=[]）。
  3. 生成 ChinaMobile.sgmodule：
     - [Script] 行由上游规则转换（正则里的 \\/ 还原为 /，去掉 /i 标记）；
     - [MITM] = 上游域名 + 旧模块里上游没有的域名（自定义域名不会被洗掉）；
     - 自定义保留区（标记行之间的内容）原样保留，见 MARK_START / MARK_END。
  4. 只有内容真正变化时才写文件并刷新更新时间，无变化则不写（避免空提交）。

用法：python3 sync-chinamobile.py <插件文件> <上游脚本文件> [旧模块] [输出JS] [输出模块]
"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

PLUGIN_URL = "https://raw.githubusercontent.com/ccyykk666/Loon-Plugin/main/plugins/china-mobile/china_mobile_ad.plugin"
SCRIPT_URL = "https://raw.githubusercontent.com/ccyykk666/Loon-Plugin/main/plugins/china-mobile/remove_ads.js"
JS_URL = "https://raw.githubusercontent.com/muktsoen/SurgeRules/main/ChinaMobile.js"
REQ_URL = "https://raw.githubusercontent.com/muktsoen/SurgeRules/main/ChinaMobile-request.js"

MARK_START = "# ===== 自定义规则（自动同步会保留此区域内容） ====="
MARK_END = "# ===== 自定义规则结束 ====="

HEADER = """// 中国移动去广告（Surge 移植版）
// 原作者：ccyykk666（Loon 插件，2026-10-24）
// 来源：https://raw.githubusercontent.com/ccyykk666/Loon-Plugin/main/plugins/china-mobile/remove_ads.js
// 移植改动：
//   1. 前置纯 JS AES-128-CBC 垫片，模拟 Loon 的 $crypto.aes（Surge 没有该 API）。
//   2. $argument 由对象改为分号分隔字符串解析，模块 #!arguments 保留 8 个开关。
//   3. 补 Loon Rewrite 两条：支付弹窗 data=null、广告过滤接口 body=[]。
// 其余逻辑与原脚本一致。
"""

OLD_ARGS = '  var ARGUMENTS =\n    typeof $argument === "object" && $argument !== null ? $argument : {};'
NEW_ARGS = "  var ARGUMENTS = __parseSurgeArgs();"

ENABLED_ANCHOR = """  function enabled(name) {
    var value = Object.prototype.hasOwnProperty.call(ARGUMENTS, name)
      ? ARGUMENTS[name]
      : ARGUMENT_DEFAULTS[name];
    return value === true || value === "true" || value === 1 || value === "1";
  }
"""

BRANCHES = """
  // Surge 移植补充：Loon Rewrite 两条（原 response.json 改写），在解密前处理。
  if (/\\/i\\/v1\\/pay\\/popWindowQry\\//.test(url)) {
    try {
      var __pop = JSON.parse(responseBody);
      if (__pop && typeof __pop === "object") __pop.data = null;
      $done({body: JSON.stringify(__pop)});
    } catch (e) { $done({}); }
    return;
  }
  if (/AdInfoFilter\\/getAdInfos(?:\\?|$)/.test(url) && enabled("MineClean")) {
    try {
      var __ad = JSON.parse(responseBody);
      if (__ad && typeof __ad === "object") __ad.body = [];
      $done({body: JSON.stringify(__ad)});
    } catch (e) { $done({}); }
    return;
  }
"""

URL_RE = re.compile(r"\$\{url\}\s*~=\s*/((?:\\.|[^/])*)/[a-z]*")


def surge_pattern(loon_pattern):
    """Loon 正则转 Surge：反斜杠转义的斜杠还原为 /，去掉 /i 标记（字面量均为小写）。"""
    return loon_pattern.replace("\\/", "/")


def script_name(pattern):
    if "bottomNavigationService" in pattern:
        return "CM-bottomnav"
    if "getNavigation" in pattern:
        return "CM-navigation"
    if "getMyPageNew" in pattern:
        return "CM-mypage"
    if "getTopAreaList" in pattern:
        return "CM-homepage"
    if "message_query" in pattern or "myCardVoucher" in pattern or "commonBoard" in pattern:
        return "CM-h5"
    if "/cust/" in pattern:
        return "CM-recharge"
    return None


def parse_plugin(text):
    section = None
    args = []          # [(name, default_bool)]，保持上游顺序
    script_rules = []  # [pattern]
    rewrite_rules = [] # [(pattern, action)]
    hostnames = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#!"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if section == "Argument":
            m = re.match(r"^(\w+)\s*=\s*switch\s*,\s*(true|false)", line)
            if m:
                args.append((m.group(1), m.group(2) == "true"))
        elif section == "Script":
            m = URL_RE.search(line)
            if m:
                script_rules.append(surge_pattern(m.group(1)))
            else:
                print(f"WARNING: 无法解析 Script 行：{line}")
        elif section == "Rewrite":
            m = URL_RE.search(line)
            if m:
                action = line.split(" then ", 1)[1].strip() if " then " in line else ""
                rewrite_rules.append((surge_pattern(m.group(1)), action))
            else:
                print(f"WARNING: 无法解析 Rewrite 行：{line}")
        elif section == "MITM":
            if line.lower().startswith("hostname"):
                hostnames.extend(
                    h.strip() for h in line.split("=", 1)[1].split(",") if h.strip()
                )
    return args, script_rules, rewrite_rules, hostnames


def parse_old_module(text):
    """返回 (自定义区行列表, MITM 域名列表, 旧更新时间字符串)。"""
    custom = []
    in_zone = False
    seen_zone = False
    hostnames = []
    old_ts = ""
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if line.strip() == MARK_START:
            in_zone = True
            seen_zone = True
            continue
        if line.strip() == MARK_END:
            in_zone = False
            continue
        if in_zone:
            custom.append(line)
            continue
        if line.startswith("# 更新时间："):
            old_ts = line.split("：", 1)[1].strip()
        if line.lower().startswith("hostname"):
            rhs = line.split("=", 1)[1]
            rhs = rhs.replace("%APPEND%", "").replace("%INSERT%", "")
            hostnames.extend(h.strip() for h in rhs.split(",") if h.strip())
    if not seen_zone:
        print("WARNING: 旧模块中没有自定义保留区标记，自定义规则将为空")
    return custom, hostnames, old_ts


def build_js(upstream_js, shim, args):
    patched = upstream_js
    if patched.count(OLD_ARGS) != 1:
        raise SystemExit("补丁失败：ARGUMENTS 初始化行未找到或不唯一")
    patched = patched.replace(OLD_ARGS, NEW_ARGS)
    defaults = "  var ARGUMENT_DEFAULTS = {\n" + ",\n".join(
        f"    {name}: {'true' if default else 'false'}" for name, default in args
    ) + "\n  };"
    patched, n = re.subn(r"  var ARGUMENT_DEFAULTS = \{[^}]*\};", defaults, patched)
    if n != 1:
        raise SystemExit("补丁失败：ARGUMENT_DEFAULTS 块未找到或不唯一")
    if patched.count(ENABLED_ANCHOR) != 1:
        raise SystemExit("补丁失败：enabled() 锚点未找到或不唯一")
    patched = patched.replace(ENABLED_ANCHOR, ENABLED_ANCHOR + BRANCHES)
    return HEADER + shim + "\n" + patched


def build_module(args, script_rules, rewrite_rules, upstream_hosts, custom, extra_hosts, ts):
    argstr = ";".join(name + ":{{{" + name + "}}}" for name, _ in args)
    argdecl = ",".join(f"{name}:{'true' if d else 'false'}" for name, d in args)
    lines = []
    lines.append("#!name=中国移动去广告")
    lines.append(
        "#!desc=由 ccyykk666 的 Loon 插件移植而来，Surge 可用。含 AES 垫片（模拟 Loon 的 $crypto.aes）与 8 个开关。"
    )
    lines.append("#!author=ccyykk666")
    lines.append(f"#!arguments={argdecl}")
    lines.append("")
    lines.append(f"# 来源：{PLUGIN_URL}")
    lines.append(f"# 脚本：{JS_URL}")
    lines.append(f"# 更新时间：{ts}")
    lines.append("")
    lines.append("[Script]")
    extra_n = 0
    for pattern in script_rules:
        name = script_name(pattern)
        if name is None:
            extra_n += 1
            name = f"CM-extra-{extra_n}"
            print(f"WARNING: 未识别的 Script 规则，暂用 {name}：{pattern}")
        lines.append(
            f"{name} = type=http-response,pattern={pattern},requires-body=true,"
            f"script-path={JS_URL},argument={argstr}"
        )
    popwindow = adfilter = reject = None
    for pattern, action in rewrite_rules:
        if "reject_dict" in action:
            reject = pattern
        elif 'replace("data", null)' in action:
            popwindow = pattern
        elif 'jq(".body=[]")' in action:
            adfilter = pattern
        else:
            print(f"WARNING: 未识别的 Rewrite 规则，已跳过：{pattern} -> {action}")
    if popwindow is None or adfilter is None or reject is None:
        print("WARNING: 上游 Rewrite 规则不完整（缺 reject/popWindow/getAdInfos 其中之一）")
    if popwindow and "popWindowQry" not in popwindow:
        print("WARNING: 上游 popWindow 规则地址变了，fork 内分支可能失效，需人工检查")
    if adfilter and "AdInfoFilter/getAdInfos" not in adfilter:
        print("WARNING: 上游 getAdInfos 规则地址变了，fork 内分支可能失效，需人工检查")
    if popwindow:
        lines.append(
            f"CM-popwindow = type=http-response,pattern={popwindow},requires-body=true,"
            f"script-path={JS_URL},argument={argstr}"
        )
    if adfilter:
        lines.append(
            f"CM-adfilter = type=http-response,pattern={adfilter},requires-body=true,"
            f"script-path={JS_URL},argument={argstr}"
        )
    if reject:
        lines.append(
            f"CM-reject = type=http-request,pattern={reject},script-path={REQ_URL}"
        )
    lines.append(MARK_START)
    lines.extend(custom)
    lines.append(MARK_END)
    lines.append("")
    lines.append("[MITM]")
    seen = set()
    hosts = []
    for h in upstream_hosts + extra_hosts:
        if h not in seen:
            seen.add(h)
            hosts.append(h)
    lines.append("hostname = %APPEND% " + ", ".join(hosts))
    return "\n".join(lines) + "\n"


def main():
    plugin_path, script_path = sys.argv[1], sys.argv[2]
    old_module_path = sys.argv[3] if len(sys.argv) > 3 else "ChinaMobile.sgmodule"
    out_js_path = sys.argv[4] if len(sys.argv) > 4 else "ChinaMobile.js"
    out_module_path = sys.argv[5] if len(sys.argv) > 5 else "ChinaMobile.sgmodule"
    shim_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "chinamobile-shim.js"
    )

    with open(plugin_path, encoding="utf-8") as f:
        plugin_text = f.read()
    with open(script_path, encoding="utf-8") as f:
        upstream_js = f.read()
    with open(shim_path, encoding="utf-8") as f:
        shim = f.read()
    old_module = ""
    if os.path.exists(old_module_path):
        with open(old_module_path, encoding="utf-8") as f:
            old_module = f.read()
    custom, old_hosts, old_ts = parse_old_module(old_module)

    args, script_rules, rewrite_rules, upstream_hosts = parse_plugin(plugin_text)
    if not args or not script_rules:
        raise SystemExit("上游插件解析失败：开关或脚本规则为空")

    new_js = build_js(upstream_js, shim, args)
    extra_hosts = [h for h in old_hosts if h not in upstream_hosts]

    # 先用旧时间戳比对：内容无变化则不写文件，避免空提交
    new_module_old_ts = build_module(
        args, script_rules, rewrite_rules, upstream_hosts, custom, extra_hosts, old_ts
    )
    js_changed = True
    if os.path.exists(out_js_path):
        with open(out_js_path, encoding="utf-8") as f:
            js_changed = f.read() != new_js
    module_changed = new_module_old_ts != old_module
    if not js_changed and not module_changed:
        print("no change")
        return

    bj = timezone(timedelta(hours=8))
    fresh_ts = datetime.now(bj).strftime("%Y-%m-%d %H:%M:%S") + "（北京时间）"
    new_module = build_module(
        args, script_rules, rewrite_rules, upstream_hosts, custom, extra_hosts, fresh_ts
    )
    if js_changed:
        with open(out_js_path, "w", encoding="utf-8") as f:
            f.write(new_js)
        print(f"ChinaMobile.js updated ({len(new_js.encode())} bytes)")
    if module_changed:
        with open(out_module_path, "w", encoding="utf-8") as f:
            f.write(new_module)
        print("ChinaMobile.sgmodule updated")
    print(
        f"args={len(args)} scripts={len(script_rules)} rewrites={len(rewrite_rules)} "
        f"hosts={len(upstream_hosts)}+{len(extra_hosts)} custom_lines={len(custom)}"
    )


if __name__ == "__main__":
    main()
