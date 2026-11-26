// 星驿付、星驿秘书去广告
// Loon 规则转制：命中以下广告接口时返回 404，其余请求放行。
//  - 星驿付 开屏广告：POST gtqt.postar.cn/gtqt-mht-api/appAdvertApi/openAppAdvert
//  - 星驿付 首页横幅/弹窗/悬浮/我的页面推广：POST gtqt.postar.cn/gtqt-mht-api/appAdvertApi/homePageAdvert
//  - 星驿付 原生广告服务：POST ac1.dcloud.net.cn/app/acs（仅 UA 以 XYFPostar 开头；Loon 原规则为 /^XYFPostar//，按此外理）
//  - 星驿秘书 开屏广告：POST gtqt.postar.cn/gtqt-mms-service/appAdvertApi/openAppAdvert
//  - 星驿秘书 系统公告及弹窗：POST gtqt.postar.cn|gtqtpostar.gtxygroup.com/gtqt-mms-service/popover/unifyPopup

const RULES = [
  { method: "POST", pattern: /^https:\/\/gtqt\.postar\.cn\/gtqt-mht-api\/appAdvertApi\/openAppAdvert(?:\?.*)?/ },
  { method: "POST", pattern: /^https:\/\/gtqt\.postar\.cn\/gtqt-mht-api\/appAdvertApi\/homePageAdvert(?:\?.*)?/ },
  { method: "POST", pattern: /^https:\/\/ac1\.dcloud\.net\.cn\/app\/acs(?:\?.*)?/, ua: /^XYFPostar/ },
  { method: "POST", pattern: /^https:\/\/gtqt\.postar\.cn\/gtqt-mms-service\/appAdvertApi\/openAppAdvert(?:\?|)/ },
  { method: "POST", pattern: /^https:\/\/(?:gtqt\.postar\.cn|gtqtpostar\.gtxygroup\.com)\/gtqt-mms-service\/popover\/unifyPopup(?:\?|)/ },
];

function getHeader(headers, name) {
  if (!headers) return "";
  const lower = name.toLowerCase();
  for (const k of Object.keys(headers)) {
    if (k.toLowerCase() === lower) return headers[k] || "";
  }
  return "";
}

(function main() {
  try {
    const url = $request.url || "";
    const method = ($request.method || "").toUpperCase();
    const ua = getHeader($request.headers, "User-Agent");
    for (const rule of RULES) {
      if (rule.method && method !== rule.method) continue;
      if (!rule.pattern.test(url)) continue;
      if (rule.ua && !rule.ua.test(ua)) continue;
      $done({ response: { status: 404, headers: {}, body: "" } });
      return;
    }
    $done({});
  } catch (e) {
    $done({});
  }
})();
