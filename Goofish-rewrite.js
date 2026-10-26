// 闲鱼去广告：Loon [Rewrite] 响应规则的 Surge 脚本版
// 原插件：ccyykk666、ddgksf2013（Loon，2026-09-19）
// 来源：https://raw.githubusercontent.com/ccyykk666/Loon-Plugin/main/plugins/goofish/goofish_ad.lpx
// 说明：Loon 的 response.json.jq/replace/delete 在 Surge 模块里没有等价物（模块不能新增 Body Rewrite 段），
// 故把 18 条响应规则逐条翻成等价 JS。原规则全部要求 status 200，这里开头统一门禁。
// jq 翻译约定：`x |= map(select(p))` 译为数组则过滤、缺失/null 则置 []、其他形状不动；
// 简单赋值（`.data.x = v`）译为建路径赋值（与 jq 的 = 一致）；delete 为守卫删除。
// 失败模式安全：非 200、body 不是 JSON 或中途异常时原样放行。

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
// jq `parent.key |= map(select(pred))` 的近似
function __mapFilter(parent, key, pred) {
  if (!__isObj(parent)) return;
  if (Array.isArray(parent[key])) parent[key] = parent[key].filter(pred);
  else if (parent[key] == null) parent[key] = [];
}

// 首页圈子：def clean（见原插件 circle.list 那条 jq）
function __cleanCircle(o) {
  if (!__isObj(o)) return;
  if (Array.isArray(o.circleList)) {
    o.circleList = o.circleList.filter(function (it) {
      return !it || typeof it !== "object" || it.bizCode !== "saveMoney";
    });
  }
  if (Array.isArray(o.headList)) {
    o.headList.forEach(function (it) {
      if (!__isObj(it)) return;
      if (it.bizCode === "main" && String(it.circleId) === "100") delete it.headerGuideConfig;
      if (__isObj(it.showInfo) &&
        ((it.bizCode === "market" && String(it.circleId) === "202") ||
         (it.bizCode === "recycle" && String(it.circleId) === "203"))) {
        it.showInfo.rightTagImage = { lightUrl: "", selectUrl: "", url: "" };
      }
    });
  }
}

var url = $request.url;
var obj = null;
try { obj = JSON.parse($response.body); } catch (e) { obj = null; }

if (Number($response.status) !== 200 || obj === null || typeof obj !== "object") {
  $done({});
} else {
  var matched = false;

  if (url.indexOf("mtop.taobao.idlecommerce.splash.async.ads") !== -1) {
    __set(obj, "data.adMap", {});
    matched = true;
  } else if (url.indexOf("mtop.idle.idleadv.scene.restore") !== -1) {
    __set(obj, "data.trackParams.stageMatch", "false");
    matched = true;
  } else if (url.indexOf("mtop.taobao.idle.user.strategy.list") !== -1) {
    __set(obj, "data.strategies", [{}]);
    matched = true;
  } else if (url.indexOf("mtop.taobao.idlehome.home.circle.list") !== -1) {
    // jq: .data |= clean | if (.data.next | type) == "object" then .data.next |= clean else . end
    __cleanCircle(obj.data);
    if (__isObj(obj.data) && __isObj(obj.data.next)) __cleanCircle(obj.data.next);
    matched = true;
  } else if (url.indexOf("mtop.taobao.idlehome.home.nextfresh") !== -1 ||
             url.indexOf("mtop.taobao.idlehome.widget.refresh.get") !== -1) {
    if (__isObj(obj.data)) {
      if (__isObj(obj.data.configInfo) && __isObj(obj.data.configInfo.experimentContext)) {
        obj.data.configInfo.experimentContext.widget_is_show = "false";
      }
      if (Array.isArray(obj.data.homeTopList)) obj.data.homeTopList = [];
      delete obj.data.bannerReturnDO;
      delete obj.data.widgetReturnDO;
      __mapFilter(obj.data, "sections", function (s) {
        return !!s && !!s.data && s.data.bizType === "item";
      });
    }
    matched = true;
  } else if (url.indexOf("mtop.taobao.idlemtopsearch.item.search.activate") !== -1) {
    __set(obj, "data.cardList", [{}]);
    matched = true;
  } else if (url.indexOf("mtop.taobao.idlemtopsearch.search.discover") !== -1) {
    __del(obj, "data.resultList");
    matched = true;
  } else if (url.indexOf("mtop.taobao.idle.item.buy.feeds") !== -1) {
    __del(obj, "data.sections");
    matched = true;
  } else if (url.indexOf("mtop.taobao.idle.local.home") !== -1) {
    __mapFilter(obj.data, "sections", function (s) {
      return !!s && !!s.data && s.data.bizType === "item";
    });
    matched = true;
  } else if (url.indexOf("mtop.taobao.idlemtopsearch.search.shade") !== -1) {
    __set(obj, "data.singleShadeWords", [{}]);
    matched = true;
  } else if (url.indexOf("mtop.taobao.idlemtopsearch.detailpage.search.shade") !== -1) {
    __set(obj, "data.idleShadeOutputDo.result", []);
    __set(obj, "data.idleShadeOutputDo.scroll", "false");
    matched = true;
  } else if (url.indexOf("mtop.taobao.idlemtopsearch.search.activate.tablist") !== -1) {
    __set(obj, "data.tabList", []);
    matched = true;
  } else if (url.indexOf("mtop.taobao.idlemtopsearch.search.activate.trendlist") !== -1) {
    __set(obj, "data.resultList", []);
    matched = true;
  } else if (url.indexOf("mtop.taobao.idle.user.page.my.adapter") !== -1) {
    __set(obj, "data.ability", []);
    __mapFilter(obj.data && obj.data.container, "sections", function (s) {
      return !!s && /head|user|trade/.test(String(s.sectionBizCode));
    });
    matched = true;
  } else if (url.indexOf("mtop.taobao.idle.trade.full.info") !== -1) {
    __mapFilter(obj.data, "components", function (c) {
      return !c || (c.render !== "recommendTabVO" && c.render !== "priceRateDetailVO" && c.render !== "bannerVO");
    });
    matched = true;
  } else if (url.indexOf("mtop.taobao.idle.awesome.detail.unit") !== -1) {
    if (obj.data && obj.data.flowData && __isObj(obj.data.flowData.body) &&
        Array.isArray(obj.data.flowData.body.sections)) {
      obj.data.flowData.body.sections.forEach(function (sec) {
        if (sec && Array.isArray(sec.components)) {
          sec.components = sec.components.filter(function (c) {
            return !c || c.key !== "Basic_Native_spn_marketing_module" ||
              !(c.data && c.data.template && c.data.template.name === "marketing_module_bargain_activity");
          });
        }
      });
    }
    matched = true;
  } else if (url.indexOf("mtop.taobao.idle.item.recommend") !== -1) {
    __mapFilter(obj.data, "cardList", function (c) {
      return !c || !c.cardData || c.cardData.bizType !== "mamaAD";
    });
    matched = true;
  } else if (url.indexOf("mtop.taobao.idlemtopsearch.search/") !== -1 ||
             url.indexOf("mtop.taobao.idlemtopsearch.search?") !== -1) {
    // jq: .data.resultList |= map(select(.data.item.main.clickParam.args.biz_type == "item"))
    __mapFilter(obj.data, "resultList", function (it) {
      return !!it && !!it.data && !!it.data.item && !!it.data.item.main &&
        !!it.data.item.main.clickParam && !!it.data.item.main.clickParam.args &&
        it.data.item.main.clickParam.args.biz_type === "item";
    });
    matched = true;
  }

  if (matched) {
    try { $done({ body: JSON.stringify(obj) }); } catch (e) { $done({}); }
  } else {
    $done({});
  }
}
