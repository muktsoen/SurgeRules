// 闲鱼去广告：kelee.one 现网版 Loon [Rewrite] 请求规则的 Surge 脚本版
// 原插件：可莉（Loon，2026-10-02）
// 7 条请求规则全是 reject_dict(200)，即回 200 空字典（与中国移动的 ChinaMobile-request.js 同一写法）。
var url = $request.url;
if (url.indexOf("mtop.taobao.idlecommerce.splash.ads/") !== -1 ||
    url.indexOf("mtop.taobao.idle.user.strategy.list/") !== -1 ||
    url.indexOf("mtop.taobao.idle.item.recommend.list/") !== -1 ||
    url.indexOf("mtop.taobao.idle.local.near.by.corner.info/") !== -1 ||
    url.indexOf("mtop.taobao.idle.item.buy.feeds/") !== -1 ||
    url.indexOf("mtop.taobao.idlemtopsearch.search.shade/") !== -1 ||
    url.indexOf("mtop.taobao.idle.playboy.recommend/") !== -1) {
  $done({ status: 200, headers: { "Content-Type": "application/json" }, body: "{}" });
} else {
  $done({});
}
