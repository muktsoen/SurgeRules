#!/usr/bin/env python3
"""闲鱼合并模块（Xianyu）上游同步检查，每周跑一次。

为什么不是全自动重生成：合并版是手工合并的——重叠接口的清理交集、
同一字段的冲突裁决（以可莉新版为准）、搜索的 g-acs 限定等都是人工判断，
没有可靠的通用 jq→JS 重生成器；自动重生成一旦裁决错了会静默破坏去广告效果。
所以本脚本只做安全的事：
  - 取两边上游（ccyykk666 的 goofish_ad.lpx 走 GitHub raw，可靠；
    可莉现网版走 kelee.one 直取，runner 若被 Cloudflare 挡则跳过、不报错）；
  - 对比规则正文（忽略 #!date 等元数据行，只看规则本身）；
  - 无变化：静默退出；有变化：更新快照文件并输出 diff，供 workflow 提交快照 + 开 issue 提醒人工重合并；
  - 首次跑：只建快照基线，不开 issue。

输出（供 workflow 用）：
  - $GITHUB_OUTPUT：changed=true/false、snapshot_init=true/false
  - /tmp/xianyu-diff.md：有变化时写入的 issue 正文（含规则 diff，截断 200 行）
快照位置：.github/upstream/xianyu/{goofish_ad,FleaMarket_remove_ads}.lpx
"""

import difflib
import os
import subprocess
import sys

SNAP_DIR = ".github/upstream/xianyu"
DIFF_MD = "/tmp/xianyu-diff.md"

UPSTREAMS = [
    {
        "key": "goofish",
        "label": "ccyykk666 版 goofish_ad.lpx",
        "url": "https://raw.githubusercontent.com/ccyykk666/Loon-Plugin/main/plugins/goofish/goofish_ad.lpx",
        "snap": "goofish_ad.lpx",
        "required": True,
    },
    {
        "key": "fleamarket",
        "label": "可莉现网版 FleaMarket_remove_ads.lpx",
        # 优先走公网 scripthub（XIANYU_FM_URL，存在 GitHub secret 里，含随机路径保护）；
        # 未设则回落 kelee.one 直取（runner 常被其 Cloudflare 挡，挡了就跳过）。
        "url": os.environ.get("XIANYU_FM_URL") or "https://kelee.one/Tool/Loon/Lpx/FleaMarket_remove_ads.lpx",
        "snap": "FleaMarket_remove_ads.lpx",
        "required": False,
    },
]


def fetch(url, uas):
    for ua in uas:
        try:
            r = subprocess.run(
                ["curl", "-sL", "--max-time", "30", "-A", ua, url],
                capture_output=True, text=True, timeout=60,
            )
        except Exception as e:
            print(f"  fetch error ({ua[:20]}...): {e}")
            continue
        body = r.stdout or ""
        if r.returncode == 0 and body.startswith("#!name="):
            return body
        print(f"  fetch 未拿到插件文本（ua={ua[:20]}...，rc={r.returncode}，前 80 字节={body[:80]!r}）")
    return None


def body_of(text):
    """规则正文：去掉 #! 元数据行（日期等只改元数据不算规则变化），其余原样。"""
    lines = [ln for ln in text.splitlines() if not ln.startswith("#!")]
    return "\n".join(lines).strip() + "\n"


def set_output(name, value):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")
    print(f"output: {name}={value}")


def main():
    os.makedirs(SNAP_DIR, exist_ok=True)
    changed = []
    inited = []
    skipped = []
    diffs = []

    for up in UPSTREAMS:
        print(f"== {up['label']} ==")
        text = fetch(up["url"], [
            "Loon/3.5.1 (iPhone; iOS 26.1; Scale/3.00)",
            "curl/8.0",
        ])
        if text is None:
            if up["required"]:
                print("  上游必需但取不到，中止（不改任何文件）")
                return 1
            print("  取不到，跳过（不算变化、不报错）")
            skipped.append(up["label"])
            continue
        snap_path = os.path.join(SNAP_DIR, up["snap"])
        if not os.path.exists(snap_path):
            with open(snap_path, "w", encoding="utf-8") as f:
                f.write(text)
            print("  快照不存在，已建基线（不开 issue）")
            inited.append(up["label"])
            continue
        with open(snap_path, encoding="utf-8") as f:
            old = f.read()
        if body_of(old) == body_of(text):
            print("  规则正文无变化")
            continue
        with open(snap_path, "w", encoding="utf-8") as f:
            f.write(text)
        d = list(difflib.unified_diff(
            body_of(old).splitlines(), body_of(text).splitlines(),
            fromfile=f"旧版 {up['snap']}", tofile=f"新版 {up['snap']}", lineterm="",
        ))
        diffs.append((up["label"], d))
        print(f"  规则正文有变化（diff {len(d)} 行），已更新快照")
        changed.append(up["label"])

    if changed:
        with open(DIFF_MD, "w", encoding="utf-8") as f:
            f.write("闲鱼合并模块（Xianyu.sgmodule）上游有更新，需人工重合并。\n\n")
            f.write("原因：合并版是手工合并的（重叠接口取清理交集、冲突以可莉新版为准），\n")
            f.write("不能全自动重生成；请按上游新规则重新合并后推送，合并版测试通过后再关 issue。\n\n")
            for label, d in diffs:
                f.write(f"## {label}\n\n```diff\n")
                f.write("\n".join(d[:200]))
                if len(d) > 200:
                    f.write(f"\n...（diff 共 {len(d)} 行，仅展示前 200 行）")
                f.write("\n```\n\n")
            if skipped:
                f.write(f"（另：以下上游本次未取到，已跳过：{', '.join(skipped)}）\n")
        set_output("changed", "true")
    else:
        set_output("changed", "false")
    set_output("snapshot_init", "true" if inited else "false")
    print(f"changed={changed} inited={inited} skipped={skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
