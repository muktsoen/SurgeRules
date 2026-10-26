// 闲鱼去广告：kelee.one 现网版 Loon [Rewrite] 响应规则的 Surge 脚本版
// 原插件：可莉（Loon，2026-10-02，loon 3.5.1(998））
// 来源（经 VPS2 上自部署的 Script Hub 实例代取，因 kelee.one 站点对我侧网络 Cloudflare 拦截）：
//   https://kelee.one/Tool/Loon/Lpx/FleaMarket_remove_ads.lpx
// 说明：Loon 的 response.json.jq/delete 在 Surge 模块里没有等价物（模块不能新增 Body Rewrite 段），
// 故把 17 条响应规则逐条翻成等价 JS；7 条请求 reject_dict 规则在 FleaMarket-request.js 里。
// 注意：搜索的两条规则原插件只写了 g-acs 域名，模块里用单独一行 pattern 限定，脚本内不再重复判域名。
// jq 翻译约定：`x |= map(select(p))` 译为数组则过滤、缺失/null 则置 []、其他形状不动；
// 简单赋值译为建路径赋值；delete 为守卫删除。失败模式安全：body 不是 JSON 或中途异常时原样放行。

function __hasOwn(o, k) { return !!o && Object.prototype.hasOwnProperty.call(o, k); }
function __isObj(o) { return !!o && typeof o === "object" && !Array.isArray(o); }
function __set(o, path, v) {
  var keys = path.split(".");
  var cur = o;
  for (var i = 0; i < keys.length - 1; i++) {
    if (!cur[keys[i]] || typeof cur[keys[i]] !== "object") cur[keys[i]] = {};
    cur = cur[keys[i]];
  }
  cur[keys[keys.length - 1]] = v;
}
function __del(o, path) {
  var keys = path.split(".");
  var cur = o;
  for (var i = 0; i < keys.length - 1; i++) {
    if (!cur || typeof cur[keys[i]] !== "object") return;
    cur = cur[keys[i]];
  }
  if (cur && typeof cur === "object") delete cur[keys[keys.length - 1]];
}
// 沿路径走到父对象，对其 key 做 jq `|=` map 过滤；父对象不存在则不动
function __mapPath(o, path, key, pred) {
  var cur = o;
  for (var i = 0; i < path.length; i++) {
    if (!__isObj(cur)) return;
    cur = cur[path[i]];
  }
  if (!__isObj(cur)) return;
  if (Array.isArray(cur[key])) cur[key] = cur[key].filter(pred);
  else if (cur[key] == null) cur[key] = [];
}

var url = $request.url;
var obj = null;
try { obj = JSON.parse($response.body); } catch (e) { obj = null; }

if (obj === null || typeof obj !== "object") {
  $done({});
} else {
  var matched = false;

  if (url.indexOf("mtop.taobao.idlehome.home.nextfresh") !== -1) {
    // jq: homeTopList filter kingkongDo；sections 先按 cardType 再按模板名两次过滤（即同时满足）
    __mapPath(obj, ["data"], "homeTopList", function (s) {
      return !!s && s.sectionType === "kingkongDo";
    });
    __mapPath(obj, ["data"], "sections", function (s) {
      var ct = s && s.data && s.data.clickParam && s.data.clickParam.args && s.data.clickParam.args.cardType;
      if (ct === "homeMultiBanner" || ct === "mamaAD") return false;
      var tn = s && s.template && s.template.name;
      return typeof tn === "string" && (tn === "idlefish_home_new_commodity_card" || tn.indexOf("fish_home_tags_item_card") !== -1);
    });
    matched = true;
  } else if (url.indexOf("mtop.taobao.idlehome.widget.refresh.get") !== -1) {
    __mapPath(obj, ["data"], "homeTopList", function (s) {
      return !!s && s.sectionType === "kingkongDo";
    });
    matched = true;
  } else if (url.indexOf("mtop.taobao.idle.home.whale.modulet") !== -1) {
    __mapPath(obj, ["data", "container"], "sections", function (s) {
      return !!s && !!s.template && s.template.name === "fish_home_miniapp";
    });
    matched = true;
  } else if (url.indexOf("mtop.taobao.idle.fun.follow.feed.list") !== -1) {
    __mapPath(obj, ["data"], "sections", function (s) {
      return !!s && s.cardType === 2001;
    });
    matched = true;
  } else if (url.indexOf("mtop.taobao.idlehome.home.community") !== -1) {
    __mapPath(obj, ["data"], "feedsList", function (f) {
      return !!f && !!f.template && (f.template.name === "idlefish_home_new_commodity_card" || f.template.name === "idlefish_home_new_content_card");
    });
    matched = true;
  } else if (url.indexOf("mtop.taobao.idlehome.home.newitem.page") !== -1) {
    __mapPath(obj, ["data"], "sections", function (s) {
      var ct = s && s.data && s.data.clickParam && s.data.clickParam.args && s.data.clickParam.args.cardType;
      return ct !== "banner" && ct !== "mamaAD";
    });
    matched = true;
  } else if (url.indexOf("mtop.taobao.idle.local.flow.plat.section") !== -1) {
    __mapPath(obj, ["data", "data"], "components", function (c) {
      return !!c && __isObj(c.data) && __isObj(c.data.template) &&
        typeof c.data.template.name === "string" && c.data.template.name.indexOf("fish_city_kingkong") !== -1;
    });
    matched = true;
  } else if (url.indexOf("mtop.taobao.idle.local.home.top") !== -1) {
    __mapPath(obj, ["data", "data"], "components", function (c) {
      return !!c && c.key === "fish_home_second_stage_top_cardV3";
    });
    matched = true;
  } else if (url.indexOf("mtop.taobao.idle.local.home") !== -1) {
    __mapPath(obj, ["data"], "sections", function (s) {
      return !!s && (!s.template || s.template.cardEnum !== "ads") && s.cardType === "common";
    });
    matched = true;
  } else if (url.indexOf("mtop.idle.user.page.my.adapter") !== -1) {
    // jq: sections 只留 my_fy<数字>_(header|user_info|trade|appraise|tools)；
    // 有 tips 的 level 删掉；entry2025 的工具箱按指定顺序重排并每 5 个一组；删 data.ability
    __mapPath(obj, ["data", "container"], "sections", function (s) {
      var tn = (s && s.template && s.template.name) || "";
      return /^my_fy[0-9]+_(header|user_info|trade|appraise|tools)$/.test(tn);
    });
    if (obj.data && obj.data.container && Array.isArray(obj.data.container.sections)) {
      obj.data.container.sections.forEach(function (s) {
        if (!__isObj(s) || !__isObj(s.item)) return;
        if (__isObj(s.item.level) && __isObj(s.item.level.exContent) && __hasOwn(s.item.level.exContent, "tips")) {
          delete s.item.level;
        }
        if (s.sectionBizCode === "entry2025" && __isObj(s.item.tool) && __isObj(s.item.tool.exContent) && Array.isArray(s.item.tool.exContent.tools)) {
          var ORDER = [5, 39, 6, 30, 29, 2, 32, 3, 1];
          var flat = [];
          s.item.tool.exContent.tools.forEach(function (row) {
            (Array.isArray(row) ? row : [row]).forEach(function (t) {
              if (t && t.exContent && ORDER.indexOf(t.exContent.id) !== -1) flat.push(t);
            });
          });
          flat.sort(function (a, b) { return ORDER.indexOf(a.exContent.id) - ORDER.indexOf(b.exContent.id); });
          var chunked = [];
          for (var i = 0; i < flat.length; i += 5) chunked.push(flat.slice(i, i + 5));
          s.item.tool.exContent.tools = chunked;
        }
      });
    }
    __del(obj, "data.ability");
    matched = true;
  } else if (url.indexOf("mtop.taobao.idlehome.home.circle.list") !== -1) {
    // jq: circleList 各项 showInfo 删 titleImage 与 atmosphereImageUrl；
    // next.headList 只留 main/market/IDLE_CIRCLE，并删其 showInfo.rightTagImage
    if (__isObj(obj.data) && Array.isArray(obj.data.circleList)) {
      obj.data.circleList.forEach(function (it) {
        if (__isObj(it) && __isObj(it.showInfo)) {
          delete it.showInfo.titleImage;
          delete it.showInfo.atmosphereImageUrl;
        }
      });
    }
    if (__isObj(obj.data) && __isObj(obj.data.next)) {
      __mapPath(obj, ["data", "next"], "headList", function (h) {
        return !!h && (h.bizCode === "main" || h.bizCode === "market" || h.bizCode === "IDLE_CIRCLE");
      });
      if (Array.isArray(obj.data.next.headList)) {
        obj.data.next.headList.forEach(function (h) {
          if (__isObj(h) && __isObj(h.showInfo)) delete h.showInfo.rightTagImage;
        });
      }
    }
    matched = true;
  } else if (url.indexOf("mtop.taobao.idlehome.magic.home.page.list") !== -1) {
    __del(obj, "data.topList");
    matched = true;
  } else if (url.indexOf("mtop.taobao.idlemtopsearch.search/") !== -1) {
    // g-acs 搜索两条规则（模块 pattern 已限定 g-acs 域名）：bizType 为 ad 的结果删掉，同时删 resultPrefixBar
    __mapPath(obj, ["data"], "resultList", function (it) {
      var bt = it && it.data && it.data.item && it.data.item.main && it.data.item.main.exContent &&
        it.data.item.main.exContent.dislikeFeedback && it.data.item.main.exContent.dislikeFeedback.clickParam &&
        it.data.item.main.exContent.dislikeFeedback.clickParam.args && it.data.item.main.exContent.dislikeFeedback.clickParam.args.bizType;
      return bt !== "ad";
    });
    __del(obj, "data.resultPrefixBar");
    matched = true;
  } else if (url.indexOf("mtop.taobao.idlemtopsearch.search.discover") !== -1) {
    __mapPath(obj, ["data"], "resultList", function (it) {
      return !it || it.type !== "MarketHotSpot";
    });
    matched = true;
  } else if (url.indexOf("mtop.taobao.idlemtopsearch.item.search.activate") !== -1) {
    if (__isObj(obj.data) && Array.isArray(obj.data.cardList)) {
      obj.data.cardList.forEach(function (it) {
        if (__isObj(it) && __hasOwn(it, "cardData") && __isObj(it.cardData) && __hasOwn(it.cardData, "hotwords")) {
          delete it.cardData.hotwords;
        }
      });
    }
    matched = true;
  } else if (url.indexOf("mtop.taobao.idle.trade.full.info") !== -1) {
    // jq 白名单：只留 orderStatusVO / addressInfoVO / orderInfoVO
    __mapPath(obj, ["data"], "components", function (c) {
      return !!c && (c.render === "orderStatusVO" || c.render === "addressInfoVO" || c.render === "orderInfoVO");
    });
    matched = true;
  }

  if (matched) {
    try { $done({ body: JSON.stringify(obj) }); } catch (e) { $done({}); }
  } else {
    $done({});
  }
}
