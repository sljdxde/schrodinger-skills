#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全国城市购房分析取数与学区工作流助手（house-buying skill）。

本脚本只做「编排与计划 + 取数适配」，不替用户下决策。真实数据来自三条通道：

1) 抓包 / 平台 API 模式（数据最稳）
   微信小程序（杭房数研 / 小鸡选房）是封闭生态，没有公开网页 API；贝壳、
   我爱我家等网站也有反爬策略。取数做法是：在手机上用 mitmproxy / Charles
   对微信抓包，或从站点公开接口拿到调用后端时的 HTTPS 接口（endpoint）和
   登录态（token / cookie），填进 `sources.json`，脚本即可脚本化拉取。
   抓包一次，长期复用。

2) 浏览器渲染模式（反爬兜底，可选）
   对 JS 渲染、UA/头校验等常见反爬，可给数据源配置 `browser: true` 与
   `cookie`、`headers`、`request_interval`，脚本会先用浏览器化请求直连；
   仍拿不到数据时尝试本机已安装的 Playwright 渲染页面再解析。只采集公开
   页面数据，不破解验证码、不做高频批量抓取。

3) 联网检索兜底模式（默认）
   没有配置 endpoint/token 时，脚本会生成「精确到数据源与城市」的检索式，
   由 AI 代理用 WebSearch / WebFetch 取数，再把结果回填。

所有数据源统一要求输出价格时间轴：同一小区用月度粒度记录挂牌价、成交价和
样本量，禁止只给一个「当前均价」就下趋势判断。

学区工作流（用户定义的流程）：
   选学区 -> 找到学区下所有小区（区分回迁房 / 商品房）-> 按小区平均挂牌价排序
   -> 用用户预算过滤 -> 去不同数据源拉取房源时间轴并分析
   若用户直接给小区（可多个）-> 跳过发现/排序，直接拉取分析
   最后 -> 给出学区 vs 周边非学区房价差异比较，并分析后续走势

依赖：仅标准库；Playwright 为可选增强。Python 3.9+。
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

SKILL_DIR = Path(__file__).resolve().parents[1]
SOURCES_CONFIG = SKILL_DIR / "scripts" / "sources.json"

DEFAULT_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 "
                   "Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/json;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def normalize_month(raw) -> str:
    """把 2026-07-01 / 2026年7月 / 2026/7 统一成 YYYY-MM。"""
    s = str(raw or "").strip()
    if not s:
        return ""
    m = re.search(r"(\d{4})[-/年.](\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    return s[:7]


# --------------------------------------------------------------------------- #
# 数据结构
# --------------------------------------------------------------------------- #
@dataclass
class Community:
    name: str
    city: str = ""
    district: str = ""
    school: str = ""
    # commodity=商品房, resettlement=回迁房, unknown=未区分
    housing_type: str = "unknown"
    avg_listing_price: Optional[float] = None  # 元/㎡
    listing_count: Optional[int] = None
    history: list = field(default_factory=list)  # PricePoint dicts，月度时间轴
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "city": self.city,
            "district": self.district,
            "school": self.school,
            "housing_type": self.housing_type,
            "avg_listing_price": self.avg_listing_price,
            "listing_count": self.listing_count,
            "history": self.history,
            "note": self.note,
        }


@dataclass
class PriceSample:
    community: str
    price_per_sqm: float
    city: str = ""
    total_price: Optional[float] = None
    area: Optional[float] = None
    deal_date: str = ""
    source: str = ""
    kind: str = "listing"  # listing=挂牌, transaction=成交

    def to_dict(self) -> dict:
        return {
            "community": self.community,
            "city": self.city,
            "price_per_sqm": self.price_per_sqm,
            "total_price": self.total_price,
            "area": self.area,
            "deal_date": self.deal_date,
            "source": self.source,
            "kind": self.kind,
        }


@dataclass
class PricePoint:
    """小区价格时间轴上的一个时间点，date 统一成 YYYY-MM。"""
    community: str
    city: str = ""
    date: str = ""
    price_per_sqm: Optional[float] = None
    total_price: Optional[float] = None
    area: Optional[float] = None
    source: str = ""
    kind: str = "listing"  # listing=挂牌, transaction=成交
    count: Optional[int] = None  # 该月份样本量
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "community": self.community,
            "city": self.city,
            "date": self.date,
            "price_per_sqm": self.price_per_sqm,
            "total_price": self.total_price,
            "area": self.area,
            "source": self.source,
            "kind": self.kind,
            "count": self.count,
            "note": self.note,
        }


@dataclass
class SourceFetchResult:
    source: str
    community: str
    city: str = ""
    listings: list = field(default_factory=list)
    transactions: list = field(default_factory=list)
    history: list = field(default_factory=list)
    queries: list = field(default_factory=list)
    raw_note: str = ""
    confidence: str = "low"
    mode: str = "websearch"  # api / websearch
    months: int = 36
    tier: str = "T3"  # 数据源分级 T0/T1/T1.5/T2/T3/T4

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "community": self.community,
            "city": self.city,
            "listings": [s.to_dict() for s in self.listings],
            "transactions": [s.to_dict() for s in self.transactions],
            "history": [p.to_dict() for p in self.history],
            "queries": self.queries,
            "raw_note": self.raw_note,
            "confidence": self.confidence,
            "mode": self.mode,
            "months": self.months,
            "tier": self.tier,
        }

# --------------------------------------------------------------------------- #
# 数据源适配器
# --------------------------------------------------------------------------- #
class BaseSource:
    name = "base"
    kind = "mini_program"  # mini_program / web
    # 该源主力提供什么口径
    provides = "listing"  # listing / transaction / both
    # 数据源分级（house-buying 五级体系，见 references/data-source-playbook.md）：
    # T0=核心平台(贝壳系/我爱我家) / T1=官方佐证(住建/网签/不动产登记) /
    # T1.5=城市本地高频源(接近网签，如杭房数研) / T2=政务App与本地小程序 /
    # T3=交叉验证(诸葛找房/安居客/房天下/58同城) / T4=舆情
    tier = "T3"

    def __init__(self, cfg: Optional[dict] = None, city: str = "杭州"):
        self.cfg = cfg or {}
        self.city = city

    def _cfg_for(self, city: Optional[str] = None) -> dict:
        """支持 sources.json 里按城市覆盖 endpoint/token/cookie/headers。"""
        city = city or self.city
        cities = self.cfg.get("cities")
        if isinstance(cities, dict):
            specific = cities.get(city)
            if isinstance(specific, dict):
                merged = {k: v for k, v in self.cfg.items() if k != "cities"}
                merged.update(specific)
                return merged
        return self.cfg

    def endpoint_for(self, city: Optional[str] = None) -> Optional[str]:
        return self._cfg_for(city).get("endpoint")

    def token_for(self, city: Optional[str] = None) -> Optional[str]:
        return self._cfg_for(city).get("token")

    def can_api(self, city: Optional[str] = None) -> bool:
        cfg = self._cfg_for(city)
        return bool(cfg.get("endpoint") and (cfg.get("token") or cfg.get("cookie")))

    def fetch(self, community: str, district: str = "",
              city: Optional[str] = None, months: int = 36) -> SourceFetchResult:
        city = city or self.city
        if self.can_api(city):
            try:
                res = self._fetch_api(community, district, city, months)
                res.tier = self.tier
                return res
            except Exception as exc:  # 兜底回检索
                res = self._fetch_websearch(community, district, city, months)
                res.tier = self.tier
                res.raw_note = f"API 拉取失败({exc})，已退回联网检索模式。{res.raw_note}"
                return res
        res = self._fetch_websearch(community, district, city, months)
        res.tier = self.tier
        return res

    # ---- API 模式：子类实现具体接口 ----
    def _fetch_api(self, community: str, district: str, city: str,
                   months: int = 36) -> SourceFetchResult:
        raise NotImplementedError

    # ---- 检索模式：默认生成精确检索式 ----
    def _fetch_websearch(self, community: str, district: str, city: str,
                         months: int = 36) -> SourceFetchResult:
        queries = self.search_queries(community, district, city, months)
        return SourceFetchResult(
            source=self.name,
            community=community,
            city=city,
            queries=queries,
            raw_note=("未配置接口，请按上述检索式联网取数后回填 "
                      "listings/transactions/history。"),
            confidence="low",
            mode="websearch",
            months=months,
        )

    def search_queries(self, community: str, district: str, city: str = "杭州",
                       months: int = 36) -> list:
        raise NotImplementedError

    # ---- 通用请求：浏览器化请求头、Cookie、限速、重试 ----
    def _request_text(self, url: str, city: Optional[str] = None,
                      headers: Optional[dict] = None) -> str:
        cfg = self._cfg_for(city or self.city)
        h = dict(DEFAULT_HEADERS)
        if headers:
            h.update(headers)
        h.update(cfg.get("headers") or {})
        cookie = cfg.get("cookie") or cfg.get("cookies")
        if cookie:
            h["Cookie"] = str(cookie)
        token = cfg.get("token")
        if token and "Authorization" not in h:
            h["Authorization"] = f"Bearer {token}"
        interval = float(cfg.get("request_interval") or 0)
        if interval > 0:
            time.sleep(interval)
        retries = max(1, int(cfg.get("retries") or 2) + 1)
        timeout = float(cfg.get("timeout") or 20)
        last_exc = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers=h)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read().decode("utf-8", "replace")
            except Exception as exc:
                last_exc = exc
                if attempt < retries - 1:
                    time.sleep(1.0 + attempt)
        if last_exc:
            raise last_exc
        return ""

    def _request_json(self, url: str, city: Optional[str] = None) -> dict:
        text = self._request_text(
            url, city=city,
            headers={"Accept": "application/json, text/plain, */*"},
        )
        return json.loads(text)

    @staticmethod
    def _url_with_params(endpoint: str, **params) -> str:
        sep = "&" if "?" in endpoint else "?"
        return endpoint + sep + urllib.parse.urlencode(params)

    @staticmethod
    def _extract_rows(obj) -> list:
        """从常见 JSON 形状里抽取记录数组。"""
        if isinstance(obj, list):
            return obj
        if isinstance(obj, dict):
            for key in ("data", "list", "items", "records", "communityList",
                        "result", "rows", "content", "priceHistory"):
                v = obj.get(key)
                if isinstance(v, list) and v:
                    return v
            if "data" in obj and isinstance(obj["data"], dict):
                for key in ("list", "items", "records", "communityList",
                            "rows", "priceHistory"):
                    v = obj["data"].get(key)
                    if isinstance(v, list) and v:
                        return v
        return []

    @staticmethod
    def _to_float(val) -> Optional[float]:
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        try:
            return float(str(val).replace(",", "").replace("万", "0000")
                         .replace("元", "").replace("㎡", "").strip())
        except ValueError:
            return None

    @staticmethod
    def _to_int(val) -> Optional[int]:
        if val is None:
            return None
        if isinstance(val, bool):
            return None
        try:
            return int(float(str(val).replace(",", "").strip()))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _history_point(row: dict, community: str, city: str, source: str,
                       kind: str = "listing") -> Optional[PricePoint]:
        price = BaseSource._to_float(
            row.get("price") or row.get("unitPrice") or row.get("avgPrice")
            or row.get("pricePerSqm")
        )
        if price is None:
            return None
        return PricePoint(
            community=community,
            city=city,
            date=normalize_month(row.get("date") or row.get("month")
                                 or row.get("dealDate") or row.get("time") or ""),
            price_per_sqm=price,
            total_price=BaseSource._to_float(row.get("totalPrice") or row.get("total")),
            area=BaseSource._to_float(row.get("area") or row.get("buildArea")),
            source=source,
            kind=kind,
            count=BaseSource._to_int(row.get("count") or row.get("num")
                                     or row.get("volume") or row.get("dealCount")),
        )

    def _build_result(self, rows: list, community: str, city: str, source: str,
                      default_kind: str = "listing") -> tuple:
        listings: list = []
        transactions: list = []
        history: list = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            price = self._to_float(r.get("price") or r.get("unitPrice")
                                   or r.get("avgPrice") or r.get("pricePerSqm")
                                   or r.get("listingPrice"))
            if price is None:
                continue
            total = self._to_float(r.get("totalPrice") or r.get("total"))
            area = self._to_float(r.get("area") or r.get("buildArea"))
            kind = str(r.get("kind") or r.get("type") or default_kind).lower()
            sample_kind = "transaction" if "trans" in kind else "listing"
            sample = PriceSample(
                community=community,
                city=city,
                price_per_sqm=price,
                total_price=total,
                area=area,
                deal_date=str(r.get("date") or r.get("dealDate") or ""),
                source=source,
                kind=sample_kind,
            )
            (transactions if sample_kind == "transaction" else listings).append(sample)
            hs = (r.get("history") or r.get("priceHistory") or r.get("monthly")
                  or r.get("trend") or r.get("points"))
            if isinstance(hs, list):
                for hp in hs:
                    if not isinstance(hp, dict):
                        continue
                    point = self._history_point(hp, community, city, source, sample_kind)
                    if point is not None and point.price_per_sqm is not None:
                        history.append(point)
        return listings, transactions, history


class WebSource(BaseSource):
    """网页源：浏览器化直连 + 可选 Playwright 渲染兜底。"""
    kind = "web"

    def _fetch_html(self, url: str, city: Optional[str] = None) -> str:
        city = city or self.city
        cfg = self._cfg_for(city)
        html = ""
        try:
            html = self._request_text(url, city=city)
        except Exception:
            html = ""
        if cfg.get("browser"):
            rendered = self._playwright_html(url, city)
            if rendered:
                html = rendered
        return html

    def _playwright_html(self, url: str, city: str) -> str:
        cfg = self._cfg_for(city)
        if not cfg.get("browser"):
            return ""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return ""
        try:
            with sync_playwright() as p:
                browser_type_name = cfg.get("browser_type") or "chromium"
                browser_type = getattr(p, browser_type_name, p.chromium)
                browser = browser_type.launch(
                    headless=bool(cfg.get("headless", True)),
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context = browser.new_context(
                    user_agent=cfg.get("user_agent") or DEFAULT_HEADERS["User-Agent"],
                    locale="zh-CN",
                    viewport={"width": 1280, "height": 900},
                )
                cookie = cfg.get("cookie") or cfg.get("cookies")
                if cookie:
                    cookies = []
                    domain = urllib.parse.urlparse(url).hostname or ""
                    for item in str(cookie).split(";"):
                        if "=" in item:
                            name, value = item.strip().split("=", 1)
                            cookies.append({
                                "name": name,
                                "value": value,
                                "domain": domain,
                                "path": "/",
                            })
                    if cookies:
                        context.add_cookies(cookies)
                headers = cfg.get("headers") or {}
                if headers and not cookie:
                    context.set_extra_http_headers(headers)
                page = context.new_page()
                timeout_ms = float(cfg.get("timeout_ms") or 30000)
                page.goto(
                    url,
                    wait_until=cfg.get("wait_until") or "domcontentloaded",
                    timeout=timeout_ms,
                )
                if cfg.get("wait_selector"):
                    page.wait_for_selector(
                        cfg["wait_selector"],
                        timeout=float(cfg.get("timeout_ms") or 15000),
                    )
                html = page.content()
                browser.close()
                return html
        except Exception:
            return ""

    def _embedded_json_rows(self, html: str) -> list:
        patterns = [
            r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            r'<script[^>]+id="__NUXT_DATA__"[^>]*>(.*?)</script>',
            r'<script[^>]+type="application/json"[^>]*>(.*?)</script>',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.S)
            if m:
                try:
                    obj = json.loads(html_lib.unescape(m.group(1)))
                    rows = self._extract_rows(obj)
                    if rows:
                        return rows
                except Exception:
                    continue
        for marker in ("__INITIAL_STATE__", "__APP_DATA__", "__NUXT__"):
            idx = html.find(marker)
            if idx < 0:
                continue
            start = html.find("{", idx)
            if start < 0:
                continue
            try:
                obj, _ = json.JSONDecoder().raw_decode(html[start:])
                rows = self._extract_rows(obj)
                if rows:
                    return rows
            except Exception:
                continue
        return []

    def _rows_from_html(self, html: str) -> list:
        rows = self._embedded_json_rows(html)
        if rows:
            return rows
        # 兜底：从页面内嵌 JSON 字段里抓 price，只能当线索，不可当精确证据。
        seen = set()
        out = []
        for raw in re.findall(r'"(?:unitPrice|avgPrice|price)"\s*:\s*(\d+(?:\.\d+)?)', html):
            value = float(raw)
            if value not in seen:
                seen.add(value)
                out.append({"price": value})
        return out


class HangfangSource(BaseSource):
    """杭房数研（微信小程序）：城市日度/月度网签与小区量价走势。"""
    name = "杭房数研"
    kind = "mini_program"
    provides = "both"
    tier = "T1.5"  # 城市本地高频源，接近网签口径

    def search_queries(self, community: str, district: str, city: str = "杭州",
                       months: int = 36) -> list:
        c = f"{district} " if district else ""
        return [
            f"杭房数研 {city} {c}{community} 成交价",
            f"杭房数研 {city} {c}{community} 挂牌价 均价",
            f"杭房数研 {city} {c}{community} 近{months}个月 量价走势 月度",
            f"{community} 杭房数研 网签 套数 每月",
        ]

    def _fetch_api(self, community: str, district: str, city: str,
                   months: int = 36) -> SourceFetchResult:
        url = self._url_with_params(
            self.endpoint_for(city),
            community=community, district=district, city=city, months=months,
        )
        obj = self._request_json(url, city=city)
        rows = self._extract_rows(obj)
        listings, transactions, history = self._build_result(
            rows, community, city, self.name,
        )
        return SourceFetchResult(
            source=self.name, community=community, city=city,
            listings=listings, transactions=transactions, history=history,
            raw_note=(f"API 拉取成功：挂牌 {len(listings)} 条，成交 "
                      f"{len(transactions)} 条，历史点 {len(history)} 个。"),
            confidence="high", mode="api", months=months,
        )


class XiaojiSource(BaseSource):
    """小鸡选房（微信小程序）：挂盘价主力源，覆盖板块/小区维度。"""
    name = "小鸡选房"
    kind = "mini_program"
    provides = "listing"
    tier = "T2"  # 城市本地小程序（挂盘口径）

    def search_queries(self, community: str, district: str, city: str = "杭州",
                       months: int = 36) -> list:
        c = f"{district} " if district else ""
        return [
            f"小鸡选房 {city} {c}{community} 挂牌价",
            f"{community} 小鸡选房 {city} 成交价 近期",
            f"小鸡选房 {city} {c}{community} 挂牌量 均价",
            f"{community} 小鸡选房 小区画像 带看",
        ]

    def _fetch_api(self, community: str, district: str, city: str,
                   months: int = 36) -> SourceFetchResult:
        url = self._url_with_params(
            self.endpoint_for(city),
            kw=community, district=district, city=city, months=months,
        )
        obj = self._request_json(url, city=city)
        rows = self._extract_rows(obj)
        listings, transactions, history = self._build_result(
            rows, community, city, self.name,
        )
        return SourceFetchResult(
            source=self.name, community=community, city=city,
            listings=listings, transactions=transactions, history=history,
            raw_note=(f"API 拉取成功：挂牌 {len(listings)} 条，成交 "
                      f"{len(transactions)} 条，历史点 {len(history)} 个。"),
            confidence="medium", mode="api", months=months,
        )


class BeikeSource(WebSource):
    """贝壳/链家（网页）：全国城市成交+挂牌，T0 核心数据源。"""
    name = "贝壳"
    kind = "web"
    provides = "both"
    tier = "T0"

    def search_queries(self, community: str, district: str, city: str = "杭州",
                       months: int = 36) -> list:
        c = f"{district} " if district else ""
        return [
            f"{city} {c}{community} 贝壳 成交",
            f"{city} {c}{community} 挂牌价 成交价",
            f"{city} {community} 近{months}个月 房价 走势图 贝壳",
        ]

    def _fetch_api(self, community: str, district: str, city: str,
                   months: int = 36) -> SourceFetchResult:
        cfg = self._cfg_for(city)
        endpoint = self.endpoint_for(city)
        if not endpoint:
            return self._fetch_websearch(community, district, city, months)
        if cfg.get("html") or cfg.get("render"):
            html = self._fetch_html(endpoint, city)
            rows = self._rows_from_html(html)
            mode_note = "HTML/浏览器渲染模式"
        else:
            obj = self._request_json(endpoint, city=city)
            rows = self._extract_rows(obj)
            mode_note = "JSON API 模式"
        listings, transactions, history = self._build_result(
            rows, community, city, self.name,
        )
        raw_note = (f"{mode_note}：挂牌 {len(listings)} 条，成交 "
                    f"{len(transactions)} 条，历史点 {len(history)} 个。")
        if not rows:
            raw_note += " 未解析到结构化记录，请核对 endpoint/selectors 或改用检索模式。"
        return SourceFetchResult(
            source=self.name, community=community, city=city,
            listings=listings, transactions=transactions, history=history,
            raw_note=raw_note,
            confidence="high" if rows else "low",
            mode="api", months=months,
        )


class WoaiwojiaSource(WebSource):
    """我爱我家（网页）：全国城市挂牌+成交，T0 核心数据源。"""
    name = "我爱我家"
    kind = "web"
    provides = "both"
    tier = "T0"

    def search_queries(self, community: str, district: str, city: str = "杭州",
                       months: int = 36) -> list:
        c = f"{district} " if district else ""
        return [
            f"{city} {c}{community} 我爱我家 挂牌价",
            f"{city} {c}{community} 我爱我家 成交价 近期",
            f"{city} {community} 近{months}个月 我爱我家 房价走势",
        ]

    def _fetch_api(self, community: str, district: str, city: str,
                   months: int = 36) -> SourceFetchResult:
        cfg = self._cfg_for(city)
        endpoint = self.endpoint_for(city)
        if not endpoint:
            return self._fetch_websearch(community, district, city, months)
        if cfg.get("html") or cfg.get("render"):
            html = self._fetch_html(endpoint, city)
            rows = self._rows_from_html(html)
            mode_note = "HTML/浏览器渲染模式"
        else:
            obj = self._request_json(endpoint, city=city)
            rows = self._extract_rows(obj)
            mode_note = "JSON API 模式"
        listings, transactions, history = self._build_result(
            rows, community, city, self.name,
        )
        raw_note = (f"{mode_note}：挂牌 {len(listings)} 条，成交 "
                    f"{len(transactions)} 条，历史点 {len(history)} 个。")
        if not rows:
            raw_note += " 未解析到结构化记录，请核对 endpoint/selectors 或改用检索模式。"
        return SourceFetchResult(
            source=self.name, community=community, city=city,
            listings=listings, transactions=transactions, history=history,
            raw_note=raw_note,
            confidence="high" if rows else "low",
            mode="api", months=months,
        )


# --------------------------------------------------------------------------- #
# T3 交叉验证源（诸葛找房 / 安居客 / 房天下 / 58同城）
# --------------------------------------------------------------------------- #
# 用途：同一指标的多源交叉比对，标注一致性程度。只做交叉验证，不单独支撑结论；
# 未配置 API 时一律退回联网检索模式（生成精确检索式，由代理取数回填）。
class ZhugeSource(WebSource):
    """诸葛找房（网页）：多平台聚合挂牌+成交，全国，T3 交叉验证源。"""
    name = "诸葛找房"
    kind = "web"
    provides = "both"
    tier = "T3"

    def search_queries(self, community: str, district: str, city: str = "杭州",
                       months: int = 36) -> list:
        c = f"{district} " if district else ""
        return [
            f"{city} {c}{community} 诸葛找房 挂牌价 成交价",
            f"{city} {c}{community} 诸葛找房 小区 均价 走势",
            f"{community} 诸葛找房 近{months}个月 房价 走势",
        ]


class AnjukeSource(WebSource):
    """安居客（网页）：挂牌口径为主，全国，T3 交叉验证源。"""
    name = "安居客"
    kind = "web"
    provides = "listing"
    tier = "T3"

    def search_queries(self, community: str, district: str, city: str = "杭州",
                       months: int = 36) -> list:
        c = f"{district} " if district else ""
        return [
            f"{city} {c}{community} 安居客 挂牌价 均价",
            f"{city} {c}{community} 安居客 小区 二手房 房价",
            f"{community} 安居客 近{months}个月 房价走势 月度",
        ]


class FangSource(WebSource):
    """房天下（网页）：挂牌口径为主，全国，T3 交叉验证源。"""
    name = "房天下"
    kind = "web"
    provides = "listing"
    tier = "T3"

    def search_queries(self, community: str, district: str, city: str = "杭州",
                       months: int = 36) -> list:
        c = f"{district} " if district else ""
        return [
            f"{city} {c}{community} 房天下 挂牌价 均价",
            f"{city} {c}{community} 房天下 二手房 房价 走势",
            f"{community} 房天下 近{months}个月 小区房价 月度",
        ]


class WubaSource(WebSource):
    """58同城房产（网页）：挂牌为主，中介重复房源多，T3 低置信交叉源。"""
    name = "58同城"
    kind = "web"
    provides = "listing"
    tier = "T3"

    def search_queries(self, community: str, district: str, city: str = "杭州",
                       months: int = 36) -> list:
        c = f"{district} " if district else ""
        return [
            f"{city} {c}{community} 58同城 二手房 挂牌价",
            f"{city} {c}{community} 58同城 小区 均价",
        ]


def load_sources(city: str = "杭州") -> list:
    """加载配置好的数据源（endpoint/token/cookie/headers 在 sources.json）。"""
    sources = [
        # T0 核心双源
        BeikeSource(city=city),
        WoaiwojiaSource(city=city),
        # T1.5 / T2 城市本地高频源与小程序（杭州）
        XiaojiSource(city=city),
        HangfangSource(city=city),
        # T3 交叉验证源
        ZhugeSource(city=city),
        AnjukeSource(city=city),
        FangSource(city=city),
        WubaSource(city=city),
    ]
    if SOURCES_CONFIG.is_file():
        try:
            cfg_all = json.loads(SOURCES_CONFIG.read_text(encoding="utf-8"))
        except Exception:
            cfg_all = {}
        for s in sources:
            if s.name in cfg_all:
                s.cfg = cfg_all[s.name] or {}
            s.city = city
    return sources


# --------------------------------------------------------------------------- #
# 学区工作流编排
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# 全国城市源注册表（预置内置，避免运行时检索）
# --------------------------------------------------------------------------- #
CITY_REGISTRY_PATH = SKILL_DIR / "scripts" / "city_sources.json"


def load_city_registry() -> dict:
    if CITY_REGISTRY_PATH.is_file():
        try:
            return json.loads(CITY_REGISTRY_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def city_source_queries(city: str) -> dict:
    """按声明城市从注册表生成精确取数检索式与源指引。

    全国网页源（贝壳/我爱我家）始终可用；政府公开源、政务 APP、本地小程序
    按注册表给出，避免运行时再检索。未内置城市则退回全国源 + 联网检索。
    """
    reg = load_city_registry()
    entry = reg.get(city, {})
    queries: list = []
    sources: list = []
    for ns in entry.get("national", ["贝壳", "我爱我家"]):
        sources.append(ns)
        queries.append(f"{city} {ns} 二手房 挂牌价 成交价 近36个月 走势")
    for g in entry.get("gov", []):
        sources.append(g.get("name", "政府源"))
        q = f"{city} {g.get('name', '')} 二手房 网签 成交公示 月度"
        if g.get("url"):
            q += f" ({g['url']})"
        queries.append(q)
    for app in entry.get("gov_app", []):
        sources.append(app.get("name", "政务APP"))
        queries.append(f"{app.get('name', '')} {city} 不动产 住房 查询 二手房")
    for mp in entry.get("mini_program", []):
        name = mp.get("name", "")
        if name and name != "无":
            sources.append(name)
            queries.append(f"{name} {city} 二手房 成交价 小区 走势")
    if not entry:
        queries.append(
            f"{city} 二手房 成交价 挂牌价 近36个月 走势"
            f"（未内置源，建议贝壳/我爱我家 + 联网检索兜底）")
    return {
        "city": city,
        "registered": bool(entry),
        "recommended_sources": sources,
        "queries": queries,
        "note": entry.get("note", ""),
        "public_access_summary": [
            f"{g.get('name')}: {g.get('public_access')}"
            for g in entry.get("gov", [])
        ],
    }


# --------------------------------------------------------------------------- #
# 维度网络（单一维度展开策略，见 references/dimension-network.md）
# --------------------------------------------------------------------------- #
# 先做透第一维度「房价」（mandatory），再按用户诉求逐层展开其余维度；
# 每个维度列出：数据字段、推荐来源层级（T0-T4）、展开条件、报告输出位置。
DIMENSION_FRAMEWORK = {
    "price": {
        "name": "房价",
        "mandatory": True,
        "fields": [
            "挂牌价（月度时间轴）", "成交价（月度时间轴）", "环比MoM", "同比YoY",
            "3/6/12/24/36个月涨跌幅", "带看量", "在售房源量", "议价空间", "成交周期",
        ],
        "sources": ["T0 贝壳系(贝壳/链家)+我爱我家", "T1 官方网签/住建公示",
                    "T1.5 城市本地高频源(杭房数研类)", "T3 诸葛找房/安居客/房天下/58同城交叉验证"],
        "expand_when": "每次分析必做",
        "output": "报告「交易与价格」章节：走势图 + 时间轴表格 + 峰/谷/当前值 + 动量指标",
    },
    "volume": {
        "name": "成交量",
        "mandatory": False,
        "fields": [
            "月度成交套数（新房/二手分开）", "月度挂牌量", "成交周期（天）",
            "带看量/带看转化", "近3/6/12个月成交量变化",
        ],
        "sources": ["T1 住建局/网签平台月度成交公示", "T1.5 城市高频源", "T0 平台成交记录",
                    "T3 诸葛找房/中指研究院"],
        "expand_when": "用户关心市场热度、判断趋势拐点、砍价时机",
        "output": "报告「市场供需与热度」章节：成交量柱状图（render_bar_chart）",
    },
    "supply_demand": {
        "name": "供需比",
        "mandatory": False,
        "fields": [
            "在售挂牌量", "近12个月成交量", "去化周期（挂牌量/月均成交量）",
            "新增挂牌 vs 成交比", "库存消化速度",
        ],
        "sources": ["T0 平台挂牌量", "T1 网签平台库存/可售公示", "T1.5 城市高频源"],
        "expand_when": "判断议价空间与买方/卖方市场强弱",
        "output": "报告「市场供需与热度」章节：去化周期与挂牌/成交比",
    },
    "land": {
        "name": "土地出让",
        "mandatory": False,
        "fields": [
            "近12个月涉宅用地出让宗数/面积/楼面价", "溢价率/流拍率",
            "板块内新增供应对存量竞争", "土地成交价对房价预期的传导",
        ],
        "sources": ["T1 自然资源局/规划资源局土地出让公告与成交公示",
                    "T1 市公共资源交易中心"],
        "expand_when": "判断片区未来供应量与价格预期（新房扎堆风险）",
        "output": "报告「土地与供应」章节（若有数据）",
    },
    "school_policy": {
        "name": "学区/政策",
        "mandatory": False,
        "fields": [
            "对口小学/初中（当年招生公告口径）", "落户/房户一致/学位占用规则",
            "学区预警/多校划片/教师轮岗", "限购/限售/限贷/公积金政策",
            "二手房参考价机制",
        ],
        "sources": ["T1 教育局招生公告", "T1 住建/房管政策文件", "T2 政务App政策板块"],
        "expand_when": "涉及学区、政策敏感期、用户有入学诉求（必做）",
        "output": "报告「学区」系列章节 + 政策风险清单",
    },
    "population": {
        "name": "人口流动",
        "mandatory": False,
        "fields": [
            "常住人口/净流入（统计公报）", "出生人口与学龄人口趋势",
            "就业/产业人口结构", "租售比与空置 proxy",
        ],
        "sources": ["T1 统计局统计公报", "T1 政府工作报告", "T4 主流媒体（低置信）"],
        "expand_when": "判断中长期需求底座（少子化/人口流出风险）",
        "output": "报告「长期人口与供需」评分维度 + 情景分析依据",
    },
    "credit": {
        "name": "信贷环境",
        "mandatory": False,
        "fields": [
            "首套/二套房贷利率", "首付比例政策", "公积金贷款额度/利率",
            "LPR走势与放款周期", "经营贷/消费贷监管口径",
        ],
        "sources": ["T1 央行/金融监管总局公告", "T1 住建/公积金中心政策",
                    "T2 政务App公积金板块"],
        "expand_when": "测算月供、评估购买力与政策宽松/收紧方向",
        "output": "报告「家庭现金流与贷款」章节",
    },
}


def cmd_dimensions(args) -> int:
    """输出维度网络框架：7 维度（房价为第一维度）的字段/来源/展开条件/输出位置。"""
    name = getattr(args, "dimension", "") or ""
    if name:
        dim = DIMENSION_FRAMEWORK.get(name)
        if not dim:
            print(f"未知维度：{name}（可选：{', '.join(DIMENSION_FRAMEWORK)}）",
                  file=sys.stderr)
            return 2
        print(json.dumps({name: dim}, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(DIMENSION_FRAMEWORK, ensure_ascii=False, indent=2))
    return 0


# --------------------------------------------------------------------------- #
# 价格时间轴走势图（自包含 SVG，无外部依赖）
# --------------------------------------------------------------------------- #
def render_timeline_chart(history: list, title: str = "", width: int = 720,
                          height: int = 300) -> str:
    """根据月度 history 生成双序列（挂牌/成交）SVG 折线图。

    history: list[dict]，元素含 date/price_per_sqm/kind/count(可选)。
    返回 SVG 字符串（中文标签、元/㎡ 纵轴、YYYY-MM 横轴），可嵌入 HTML 报告；
    转 docx 时由 html-to-docx 转图。零依赖，不引入 matplotlib/plotly。
    配色避坑：挂牌=蓝、成交=橙，不套用股市红涨绿跌语义。
    样本量 count<5 的月份用空心点，不实线连接（调用方保证）。
    """
    pts = [p for p in (history or []) if isinstance(p, dict) and p.get("price_per_sqm")]
    if not pts:
        return "<!-- 无时间轴数据，无法生成走势图 -->"
    months = sorted({str(p.get("date", "")) for p in pts if p.get("date")})
    if len(months) < 2:
        return "<!-- 时间轴不足 2 个月，无法生成走势图 -->"
    series: dict = {"listing": {}, "transaction": {}}
    for p in pts:
        d = str(p.get("date", ""))
        k = "transaction" if "trans" in str(p.get("kind", "listing")).lower() else "listing"
        try:
            series[k][d] = (float(p["price_per_sqm"]), int(p.get("count") or 0))
        except (TypeError, ValueError):
            continue
    all_vals = [v for s in series.values() for v, _ in s.values()]
    if not all_vals:
        return "<!-- 价格数据无法解析，无法生成走势图 -->"
    lo, hi = min(all_vals), max(all_vals)
    pad = (hi - lo) * 0.12 or max(hi * 0.05, 1)
    ymin, ymax = lo - pad, hi + pad
    L, R, T, B = 56, 16, 30, 40
    plot_w, plot_h = width - L - R, height - T - B
    n = len(months)

    def x(i: int) -> float:
        return L + (plot_w * i / (n - 1)) if n > 1 else L + plot_w / 2

    def y(v: float) -> float:
        return T + plot_h * (1 - (v - ymin) / (ymax - ymin or 1))

    colors = {"listing": "#2f6fed", "transaction": "#f5933b"}
    labels = {"listing": "挂牌均价", "transaction": "成交均价"}
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
           f'font-family="-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">',
           f'<rect width="{width}" height="{height}" fill="#ffffff"/>']
    if title:
        svg.append(f'<text x="{L}" y="18" font-size="13" fill="#1f2937" '
                   f'font-weight="600">{title}</text>')
    for gi in range(5):
        gv = ymin + (ymax - ymin) * gi / 4
        gy = y(gv)
        svg.append(f'<line x1="{L}" y1="{gy:.1f}" x2="{width - R}" y2="{gy:.1f}" '
                   f'stroke="#eceef1" stroke-width="1"/>')
        svg.append(f'<text x="{L - 6}" y="{gy + 4:.1f}" font-size="10" fill="#6b7280" '
                   f'text-anchor="end">{gv / 10000:.2f}万</text>')
    xticks = [0, n // 2, n - 1] if n > 2 else list(range(n))
    for i in xticks:
        svg.append(f'<text x="{x(i):.1f}" y="{height - B + 16}" font-size="10" '
                   f'fill="#6b7280" text-anchor="middle">{months[i]}</text>')
    flat = []
    for key in ("listing", "transaction"):
        dmap = series[key]
        if not dmap:
            continue
        coords = [(x(months.index(m)), y(v)) for m, (v, _) in dmap.items()]
        poly = " ".join(f"{cx:.1f},{cy:.1f}" for cx, cy in coords)
        svg.append(f'<polyline points="{poly}" fill="none" stroke="{colors[key]}" '
                   f'stroke-width="2"/>')
        for m, (v, c) in dmap.items():
            cx, cy = x(months.index(m)), y(v)
            if c and c < 5:
                svg.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="2.8" fill="#fff" '
                           f'stroke="{colors[key]}" stroke-width="1.4"/>')
            else:
                svg.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="2.8" '
                           f'fill="{colors[key]}"/>')
        flat.extend((m, v, key) for m, (v, _) in dmap.items())
    if flat:
        hi_pt = max(flat, key=lambda t: t[1])
        lo_pt = min(flat, key=lambda t: t[1])
        hx, hy = x(months.index(hi_pt[0])), y(hi_pt[1])
        lx2, ly2 = x(months.index(lo_pt[0])), y(lo_pt[1])
        svg.append(f'<text x="{hx:.1f}" y="{hy - 8:.1f}" font-size="9" '
                   f'fill="{colors[hi_pt[2]]}" text-anchor="middle">'
                   f'峰 {hi_pt[1] / 10000:.2f}万</text>')
        svg.append(f'<text x="{lx2:.1f}" y="{ly2 + 14:.1f}" font-size="9" '
                   f'fill="{colors[lo_pt[2]]}" text-anchor="middle">'
                   f'谷 {lo_pt[1] / 10000:.2f}万</text>')
    lx = L
    for key in ("listing", "transaction"):
        if series[key]:
            svg.append(f'<rect x="{lx}" y="{height - 12}" width="10" height="10" '
                       f'fill="{colors[key]}"/>')
            svg.append(f'<text x="{lx + 14}" y="{height - 3}" font-size="10" '
                       f'fill="#374151">{labels[key]}</text>')
            lx += 92
    svg.append("</svg>")
    return "\n".join(svg)


# --------------------------------------------------------------------------- #
# 环比 / 同比 / N 月涨跌幅（数据链路第一维度「房价」的强制输出）
# --------------------------------------------------------------------------- #
def _kind_group(history: list) -> dict:
    """把月度时间轴按口径分组：listing / transaction，键为 YYYY-MM -> (price, count)。"""
    grouped: dict = {"listing": {}, "transaction": {}}
    for p in (history or []):
        if not isinstance(p, dict):
            continue
        d = str(p.get("date", "")).strip()
        v = p.get("price_per_sqm")
        if not d or v is None:
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        k = "transaction" if "trans" in str(p.get("kind", "listing")).lower() else "listing"
        cnt = p.get("count")
        try:
            cnt = int(cnt or 0)
        except (TypeError, ValueError):
            cnt = 0
        grouped[k][d] = (v, cnt)
    return grouped


def _shift_month(d: str, n: int) -> str:
    """YYYY-MM 向前/后推 n 个月（n 可为负）。"""
    y, m = d.split("-")
    total = int(y) * 12 + int(m) - 1 + n
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def compute_mom_yoy(history: list, months: int = 36) -> dict:
    """从月度时间轴计算房价动量指标（口径分挂牌/成交）。

    输出字段：
      mom:           月度环比（本月 / 上月 - 1），{date: pct}；仅当相邻月份存在时计算，
                     缺月不编造（2025-03 之后直接到 2026-01 不产生环比）
      yoy:           月度同比（本月 / 去年同月 - 1），{date: pct}
      change_nm:     N 个月涨跌幅 {3: pct, 6: pct, 12: pct, 24: pct, 36: pct}
                     （当前月 vs 恰好 N 个月前的月份，按日历月差；该月缺失则跳过）
      peak/valley:   区间内峰值 / 谷值 {date, price}
      current:       最新月份 {date, price, count}
      months_covered: 覆盖的月份数
    无数据或样本不足时不编造：单个时点无法算环比/同比时返回 None。
    """
    grouped = _kind_group(history)
    out: dict = {}
    for kind in ("listing", "transaction"):
        dmap = grouped[kind]
        if not dmap:
            continue
        dates = sorted(dmap)
        mom: dict = {}
        yoy: dict = {}
        for i, d in enumerate(dates):
            if i > 0:
                prev_date, prev = dates[i - 1], dmap[dates[i - 1]][0]
                if prev and _shift_month(prev_date, 1) == d:
                    mom[d] = (dmap[d][0] - prev) / prev
            # 同比：去年同月（YYYY-MM 减一年）
            y, m = d.split("-") if "-" in d else (d, "")
            if m:
                ly = f"{int(y) - 1:04d}-{m}"
                if ly in dmap:
                    base = dmap[ly][0]
                    if base:
                        yoy[d] = (dmap[d][0] - base) / base
        change_nm: dict = {}
        cur = dmap[dates[-1]][0]
        for n in (3, 6, 12, 24, 36):
            target = _shift_month(dates[-1], -n)
            if target in dmap and dmap[target][0]:
                change_nm[n] = (cur - dmap[target][0]) / dmap[target][0]
        vals = [(d, v[0]) for d, v in dmap.items()]
        peak = {"date": max(vals, key=lambda t: t[1])[0],
                "price": max(v for _, v in vals)}
        valley = {"date": min(vals, key=lambda t: t[1])[0],
                  "price": min(v for _, v in vals)}
        last_date, (last_price, last_count) = dates[-1], dmap[dates[-1]]
        out[kind] = {
            "mom": mom,
            "yoy": yoy,
            "change_nm": change_nm,
            "peak": peak,
            "valley": valley,
            "current": {"date": last_date, "price": last_price, "count": last_count},
            "months_covered": len(dates),
        }
    return out


class SchoolDistrictWorkflow:
    def __init__(self, sources: Optional[list] = None, city: str = "杭州"):
        self.city = city
        self.sources = sources or load_sources(city)
        for src in self.sources:
            src.city = city

    # 1) 发现学区下所有小区：生成检索式（真实小区名单由代理联网补全）
    def discover_queries(self, school: str) -> list:
        return [
            f"{self.city} {school} 学区 对口 小区 名单",
            f"{school} 学区划分 对口小区",
            f"{self.city} {school} 学区房 小区 回迁房 商品房",
            f"{school} 学区 小区 均价 挂牌",
        ]

    # 2) 按平均挂牌价排序
    def rank_by_listing_price(self, communities: list,
                              reverse: bool = True) -> list:
        known = [c for c in communities if c.avg_listing_price is not None]
        unknown = [c for c in communities if c.avg_listing_price is None]
        known.sort(key=lambda c: c.avg_listing_price, reverse=reverse)
        return known + unknown

    # 3) 按预算过滤：est_area 为用户预估面积段（㎡）
    def filter_by_budget(self, communities: list, budget_wan: float,
                         est_area: float, upper_factor: float = 1.15) -> list:
        out = []
        for c in communities:
            if c.avg_listing_price is None:
                out.append(c)
                continue
            est_total_wan = c.avg_listing_price * est_area / 10000.0
            if est_total_wan <= budget_wan * upper_factor:
                out.append(c)
        return out

    # 4) 多源拉取房源信息（含月度时间轴）
    def collect(self, communities: list, months: int = 36) -> dict:
        result = {}
        for c in communities:
            per_community = {}
            community_city = c.city or self.city
            for src in self.sources:
                res = src.fetch(c.name, c.district, community_city, months)
                per_community[src.name] = res.to_dict()
            result[c.name] = per_community
        return result

    # 5) 学区 vs 周边非学区差异比较 + 走势分析
    def compare_school_vs_nonschool(self, school_comm: list,
                                    nonschool_comm: list) -> dict:
        def avg_price(comms, htype=None):
            sel = [c for c in comms if c.avg_listing_price is not None]
            if htype:
                sel = [c for c in sel if c.housing_type == htype]
            if not sel:
                return None
            return sum(c.avg_listing_price for c in sel) / len(sel)

        # 学区侧：优先用商品房口径（回迁房会拉低均价，单独标注）
        sc_comm = avg_price(school_comm, "commodity")
        sc_all = avg_price(school_comm)
        ns = avg_price(nonschool_comm)
        premium = None
        if sc_comm is not None and ns not in (None, 0):
            premium = (sc_comm - ns) / ns

        return {
            "school_avg_listing_commodity": sc_comm,
            "school_avg_listing_all": sc_all,
            "nonschool_avg_listing": ns,
            "school_premium_rate": premium,
            "school_community_count": len(school_comm),
            "nonschool_community_count": len(nonschool_comm),
            "resettlement_note": (
                "学区侧含回迁房时已用商品房口径算溢价；回迁房通常挂牌价更低、"
                "居住品质/流动性较弱，比较时单独列出，不混入溢价计算。"
                if any(c.housing_type == "resettlement" for c in school_comm) else ""
            ),
            "trend_analysis_prompts": [
                "用 forecasting-framework.md 输出基准/乐观/悲观三情景，"
                "重点量化少子化对目标入学年份的学位需求影响。",
                "对比学区与周边非学区近 12-36 个月成交/挂牌月度时间轴，"
                "判断溢价收敛还是扩张，不能用单一当前均价代替趋势。",
                "检查目标学校招生政策（多校划片、教师轮岗、学位预警）对确定性的冲击方向。",
                "给出学区房相对非学区的「后续走势」结论：溢价可持续/收窄/反转，及触发信号。",
            ],
        }

# --------------------------------------------------------------------------- #
# 输出：把社区名单 / 分析结果落盘成 plan.json
# --------------------------------------------------------------------------- #
def _read_communities_from_args(args) -> tuple:
    data: dict = {}
    if args.input:
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    else:
        comms = []
        for name in [x.strip() for x in (args.communities or "").split(",") if x.strip()]:
            comms.append(Community(name=name))
        data["communities"] = [c.to_dict() for c in comms]
    school = data.get("school", getattr(args, "school", "") or "")
    city = data.get("city") or getattr(args, "city", "杭州") or "杭州"
    budget = float(data.get("budget", args.budget if args.budget is not None else 0) or 0)
    area = float(data.get("area", args.area if args.area is not None else 90) or 90)

    def with_city(raw_list: list) -> list:
        out = []
        for c in raw_list:
            c = dict(c)
            c.setdefault("city", city)
            out.append(Community(**c))
        return out

    communities = with_city(data.get("communities", []))
    non_school = with_city(data.get("non_school_communities", []))
    return school, city, budget, area, communities, non_school


def cmd_school(args) -> int:
    school, city, budget, area, communities, non_school = _read_communities_from_args(args)
    wf = SchoolDistrictWorkflow(city=city)
    months = int(getattr(args, "months", 36) or 36)
    if not communities:
        # 还没有小区名单：先输出发现检索式，让代理补全
        plan = {
            "mode": "school-discover",
            "school": school,
            "city": city,
            "discover_queries": wf.discover_queries(school),
            "next_step": "用上述检索式找到学区下所有小区，区分回迁房/商品房，"
                         "填入各小区平均挂牌价后重新运行本命令。",
        }
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    ranked = wf.rank_by_listing_price(communities)
    filtered = wf.filter_by_budget(ranked, budget, area) if budget else ranked
    fetch_plan = wf.collect(filtered, months)
    comparison = None
    if non_school:
        # 溢价比较用「完整学区小区集」(ranked)，而非预算过滤后的子集，
        # 否则高价学区房被滤掉会把溢价算小，结论失真。
        comparison = wf.compare_school_vs_nonschool(ranked, non_school)

    plan = {
        "mode": "school",
        "school": school,
        "city": city,
        "budget_wan": budget,
        "est_area_sqm": area,
        "months": months,
        "ranked_all": [c.to_dict() for c in ranked],
        "budget_filtered": [c.to_dict() for c in filtered],
        "per_source_fetch_plan": fetch_plan,
        "school_vs_nonschool": comparison,
    }
    _dump_plan(plan, args.output)
    return 0


def cmd_communities(args) -> int:
    _, city, budget, area, communities, _ = _read_communities_from_args(args)
    wf = SchoolDistrictWorkflow(city=city)
    months = int(getattr(args, "months", 36) or 36)
    if not communities:
        print("请提供 --communities '小区A,小区B' 或 --input plan.json", file=sys.stderr)
        return 2
    ranked = wf.rank_by_listing_price(communities)
    filtered = wf.filter_by_budget(ranked, budget, area) if budget else ranked
    fetch_plan = wf.collect(filtered, months)
    plan = {
        "mode": "communities",
        "city": city,
        "budget_wan": budget,
        "est_area_sqm": area,
        "months": months,
        "ranked_all": [c.to_dict() for c in ranked],
        "budget_filtered": [c.to_dict() for c in filtered],
        "per_source_fetch_plan": fetch_plan,
    }
    _dump_plan(plan, args.output)
    return 0


def cmd_fetch(args) -> int:
    city = args.city or "杭州"
    sources = load_sources(city)
    src = next((s for s in sources if s.name == args.source), None)
    if src is None:
        print(f"未知数据源：{args.source}（可选："
              f"{', '.join(s.name for s in sources)}）", file=sys.stderr)
        return 2
    res = src.fetch(args.community, args.district or "", city,
                    int(getattr(args, "months", 36) or 36))
    print(json.dumps(res.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_timeline(args) -> int:
    city = args.city or "杭州"
    sources = load_sources(city)
    selected = [s for s in sources if not args.source or s.name == args.source]
    if not selected:
        print(f"未知数据源：{args.source}（可选："
              f"{', '.join(s.name for s in sources)}）", file=sys.stderr)
        return 2
    result = {
        "mode": "timeline",
        "city": city,
        "community": args.community,
        "district": args.district or "",
        "months": int(getattr(args, "months", 36) or 36),
        "sources": [],
    }
    for src in selected:
        res = src.fetch(args.community, args.district or "", city,
                        int(getattr(args, "months", 36) or 36))
        data = res.to_dict()
        data["history"] = sorted(data["history"], key=lambda p: p.get("date", ""))
        result["sources"].append(data)
    # 合并所有源时间轴，生成自包含 SVG 走势图，随结果一并返回
    merged = []
    for s in result["sources"]:
        merged.extend(s.get("history", []))
    result["svg_chart"] = render_timeline_chart(
        merged, title=f"{args.community}（{city}）价格走势")
    _dump_plan(result, args.output)
    return 0


def cmd_sources(args) -> int:
    info = city_source_queries(args.city)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def _dump_plan(plan: dict, output: Optional[str]) -> None:
    text = json.dumps(plan, ensure_ascii=False, indent=2)
    if output:
        Path(output).write_text(text, encoding="utf-8")
        print(f"已写出分析计划：{output}")
    else:
        print(text)

# --------------------------------------------------------------------------- #
# 报告辅助：橄榄手记主题 / 可点击引用 / 学区梯队
# --------------------------------------------------------------------------- #
OLIVE_CSS = """/* 橄榄手记风格（house-buying 报告，单文件自包含） */
:root{
  --paper:#f6f3ec; --card:#fffdf8; --ink:#2f2a24; --sub:#8a8272;
  --olive:#5c6b3c; --olive-soft:#e8ecd9; --accent:#b45309;
  --line:#e4ddcd; --warn:#f6e9e3; --warn-ink:#9a3412;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  line-height:1.75;font-size:15px}
.wrap{max-width:860px;margin:0 auto;padding:32px 20px 80px}
h1{font-family:Georgia,"Songti SC","SimSun",serif;color:var(--olive);
  font-size:26px;margin:0 0 6px}
h2{font-family:Georgia,"Songti SC","SimSun",serif;color:var(--olive);
  font-size:20px;margin:40px 0 12px;padding-bottom:8px;border-bottom:2px solid var(--line)}
h3{font-size:16px;margin:22px 0 8px;color:var(--ink)}
p{margin:8px 0}
.meta{color:var(--sub);font-size:13px;margin-bottom:22px}
.verdict{background:var(--olive-soft);border:1px solid var(--olive);
  border-radius:14px;padding:20px 22px;margin:18px 0}
.verdict .big{font-size:21px;font-weight:700;color:var(--olive);margin-bottom:8px}
.kv{display:grid;grid-template-columns:110px 1fr;row-gap:4px;font-size:14px}
.kv b{color:var(--sub);font-weight:600}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;
  padding:18px 22px;box-shadow:0 1px 4px rgba(92,107,60,.08);margin:14px 0}
table{width:100%;border-collapse:collapse;margin:14px 0;font-size:13.5px;
  background:var(--card);border-radius:12px;overflow:hidden}
th{background:var(--olive-soft);font-weight:600;text-align:left}
th,td{border:1px solid var(--line);padding:7px 10px;vertical-align:top}
.num{text-align:right;font-variant-numeric:tabular-nums}
.chartbox{background:var(--card);border:1px solid var(--line);border-radius:14px;
  padding:14px;margin:16px 0}
.chartbox svg{width:100%;height:auto;display:block}
.caption{color:var(--sub);font-size:12.5px;margin-top:8px}
.cite-ref{color:var(--olive);text-decoration:none;font-size:.85em;vertical-align:super;font-weight:600}
.cite-ref:hover{text-decoration:underline}
.cite-meta{color:var(--sub);font-size:12px;margin-left:6px;font-weight:400}
.cites a{color:var(--olive);text-decoration:underline;text-underline-offset:3px}
.cites li{margin:4px 0;font-size:13.5px}
.warn{background:var(--warn);border:1px solid #e5b8a4;color:var(--warn-ink);
  border-radius:10px;padding:12px 16px;font-size:14px;margin:14px 0}
.tag{display:inline-block;background:var(--olive-soft);color:var(--olive);
  border-radius:6px;padding:1px 8px;font-size:12px;margin-right:6px}
.foot{margin-top:48px;padding-top:16px;border-top:1px solid var(--line);
  color:var(--sub);font-size:12.5px}
"""


def olive_theme_css() -> str:
    """返回「橄榄手记」风格完整 CSS（浅色、高对比、清晰优先），粘入 <style> 即可。"""
    return OLIVE_CSS


def render_citations(cites: list) -> str:
    """生成可点击参考资料列表 HTML（<ol class="cites">）。

    每条 <li> 带 id="cite-N"，正文可用 <a href="#cite-N" class="cite-ref">[N]</a>
    点击跳转到对应引用。url 缺失显示“未提供链接”，不编造。空列表返回空串。

    引用防伪元数据（可选字段，见 data-source-playbook.md「引用格式规范」）：
      label        来源名称 + 标题（必填）
      url          真实链接（必填；缺失显示“未提供链接”）
      date         发布时间或访问时间，如 "2026-07" / "2026-07-15 访问"
      caliber      数据口径，如 "成交" / "挂牌" / "网签" / "参考均价"
      consistency  多源一致性程度，如 "双源一致" / "单源" / "来源冲突（见正文）"
    输出形如：
      <li id="cite-1"><a href="..." target="_blank">label</a>
        <span class="cite-meta">[2026-07发布；口径:成交；一致性:双源一致]</span></li>
    """
    if not cites:
        return ""
    items = []
    for i, c in enumerate(cites, 1):
        label = str(c.get("label") or f"来源 {i}")
        url = str(c.get("url") or "").strip()
        meta_parts = []
        date = str(c.get("date") or "").strip()
        if date:
            meta_parts.append(f"{date}发布" if "访问" not in date else date)
        caliber = str(c.get("caliber") or "").strip()
        if caliber:
            meta_parts.append(f"口径:{caliber}")
        consistency = str(c.get("consistency") or "").strip()
        if consistency:
            meta_parts.append(f"一致性:{consistency}")
        meta = f' <span class="cite-meta">[{"; ".join(meta_parts)}]</span>' if meta_parts else ""
        if url:
            items.append(
                f'<li id="cite-{i}"><a href="{url}" target="_blank" rel="noopener">'
                f"{label}</a>{meta}</li>")
        else:
            items.append(f'<li id="cite-{i}">{label}（未提供链接）{meta}</li>')
    return '<ol class="cites">\n' + "\n".join(items) + "\n</ol>"


def school_tier_rank(school: str, city: str = "") -> dict:
    """内置少量已知学校的梯队（第一/二/三/四），未收录返回“未评级”。

    内置表仅覆盖示例城市（南京/杭州）；其余按 references/school-tier-reference.md
    联网评估。梯队是公开口碑/官方信息整理的参考，报告必须另附评级依据与来源。
    """
    _KNOWN = {
        ("南京", "拉萨路小学"): ("第一梯队", "公认头部名校，学位预警常见"),
        ("南京", "力学小学"): ("第一梯队", "传统名校，集团化办学"),
        ("南京", "琅琊路小学"): ("第一梯队", "传统名校"),
        ("南京", "北京东路小学"): ("第一梯队", "传统名校，集团化"),
        ("南京", "银城小学"): ("第二梯队", "优质集团校，口碑好"),
        ("南京", "晓庄小学"): ("第二梯队", "区级优质集团校，2018 复校，三年级学业检测全区名列前茅"),
        ("南京", "伯乐中学"): ("第二梯队", "省示范初中，校方称连续 40 余年中考居全区第一方阵"),
        ("杭州", "学军小学"): ("第一梯队", "公认头部"),
        ("杭州", "文三街小学"): ("第一梯队", "传统名校"),
        ("杭州", "保俶塔实验学校"): ("第一梯队", "九年一贯头部"),
        ("杭州", "采荷一小"): ("第二梯队", "优质区属"),
    }
    hit = _KNOWN.get((city, school))
    if hit:
        tier, basis = hit
        return {"school": school, "city": city, "tier": tier,
                "basis": basis, "known": True}
    return {"school": school, "city": city,
            "tier": "未评级（证据不足）",
            "basis": "内置表未收录，按 references/school-tier-reference.md 联网评估并附来源",
            "known": False}


# --------------------------------------------------------------------------- #
# 报告辅助：更多零依赖 SVG 图表（横向比较 / 三情景 / 学区梯队）
# --------------------------------------------------------------------------- #
def _svg_boilerplate(width: int, height: int, title: str = "") -> list:
    """SVG 公共头。"""
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
           f'font-family="-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">',
           f'<rect width="{width}" height="{height}" fill="#fffdf8"/>']
    if title:
        svg.append(f'<text x="16" y="20" font-size="13" fill="#2f2a24" '
                   f'font-weight="600">{title}</text>')
    return svg


def render_bar_chart(data: list, title: str = "", width: int = 720,
                     height: int = 340, value_fmt: str = "{:.0f}") -> str:
    """生成零依赖 SVG 柱状图。

    data: list[dict] = [{"label": "华荟花园", "value": 28038}, ...]
    value_fmt: 柱顶数值格式化字符串，默认整数。
    配色：橄榄绿系，标题位于左上角。
    """
    if not data:
        return "<!-- 无柱状图数据 -->"
    try:
        vals = [float(d["value"]) for d in data]
    except (KeyError, TypeError, ValueError):
        return "<!-- 柱状图数据格式错误 -->"
    labels = [str(d.get("label", "")) for d in data]
    n = len(data)
    top = 36 if title else 18
    bottom = 72
    left = 56
    right = 24
    plot_h = height - top - bottom
    plot_w = width - left - right
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.12 or max(hi * 0.05, 1)
    ymin, ymax = max(0, lo - pad), hi + pad

    svg = _svg_boilerplate(width, height, title)
    # grid lines (5)
    for gi in range(5):
        gv = ymin + (ymax - ymin) * gi / 4
        gy = top + plot_h * (1 - (gv - ymin) / (ymax - ymin or 1))
        svg.append(f'<line x1="{left}" y1="{gy:.1f}" x2="{width - right}" y2="{gy:.1f}" '
                   f'stroke="#e4ddcd" stroke-width="1"/>')
        svg.append(f'<text x="{left - 8}" y="{gy + 4:.1f}" font-size="10" fill="#8a8272" '
                   f'text-anchor="end">{gv / 10000:.2f}万</text>')

    bar_w = plot_w / n * 0.55
    gap = plot_w / n
    colors = ["#5c6b3c", "#6b7c4a", "#8a9a6a", "#a8b38a", "#c6cfaa"]
    for i, (lab, v) in enumerate(zip(labels, vals)):
        x = left + gap * i + (gap - bar_w) / 2
        bh = plot_h * (v - ymin) / (ymax - ymin or 1)
        y = top + plot_h - bh
        color = colors[i % len(colors)]
        svg.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
                   f'rx="4" fill="{color}"/>')
        svg.append(f'<text x="{x + bar_w / 2:.1f}" y="{y - 6:.1f}" font-size="10" '
                   f'fill="#2f2a24" text-anchor="middle">{value_fmt.format(v)}</text>')
        # x label: wrap by char, max 2 lines
        cx = x + bar_w / 2
        if len(lab) <= 5:
            svg.append(f'<text x="{cx:.1f}" y="{height - bottom + 18}" font-size="10" '
                       f'fill="#6b7280" text-anchor="middle">{lab}</text>')
        else:
            mid = len(lab) // 2
            svg.append(f'<text x="{cx:.1f}" y="{height - bottom + 14}" font-size="9" '
                       f'fill="#6b7280" text-anchor="middle">{lab[:mid]}</text>')
            svg.append(f'<text x="{cx:.1f}" y="{height - bottom + 28}" font-size="9" '
                       f'fill="#6b7280" text-anchor="middle">{lab[mid:]}</text>')
    svg.append("</svg>")
    return "\n".join(svg)


def render_range_chart(data: list, title: str = "", width: int = 720,
                       height: int = 320) -> str:
    """生成零依赖 SVG 区间/三情景图。

    data: list[dict] = [
        {"label": "基准", "low": -8, "mid": -2, "high": 3},
        {"label": "乐观", "low": 0, "mid": 3, "high": 8},
        {"label": "悲观", "low": -15, "mid": -10, "high": -3},
    ]
    每个条表示一个情景在多个时间维度（6-12月/1-3年/3-10年）的 low~high 区间，
    中点 mid 用圆点标注。单位：%。
    """
    if not data:
        return "<!-- 无区间图数据 -->"
    try:
        lows = [float(d["low"]) for d in data]
        highs = [float(d["high"]) for d in data]
        mids = [float(d["mid"]) for d in data]
        labels = [str(d.get("label", "")) for d in data]
    except (KeyError, TypeError, ValueError):
        return "<!-- 区间图数据格式错误 -->"
    lo, hi = min(lows), max(highs)
    pad = (hi - lo) * 0.15 or max(abs(hi) * 0.1, 1)
    xmin, xmax = lo - pad, hi + pad
    top = 38 if title else 20
    bottom = 50
    left = 72
    right = 32
    plot_w = width - left - right
    plot_h = height - top - bottom
    n = len(data)
    row_h = plot_h / n

    def x(v: float) -> float:
        return left + plot_w * (v - xmin) / (xmax - xmin or 1)

    svg = _svg_boilerplate(width, height, title)
    # 0 基准线
    zx = x(0)
    svg.append(f'<line x1="{zx:.1f}" y1="{top}" x2="{zx:.1f}" y2="{height - bottom}" '
               f'stroke="#9a3412" stroke-width="1" stroke-dasharray="3,3"/>')
    # grid lines
    for gi in range(5):
        gv = xmin + (xmax - xmin) * gi / 4
        gx = x(gv)
        svg.append(f'<line x1="{gx:.1f}" y1="{top}" x2="{gx:.1f}" y2="{height - bottom}" '
                   f'stroke="#e4ddcd" stroke-width="1"/>')
        svg.append(f'<text x="{gx:.1f}" y="{height - bottom + 14}" font-size="10" '
                   f'fill="#8a8272" text-anchor="middle">{gv:.0f}%</text>')

    colors = {"乐观": "#5c6b3c", "基准": "#8a9a6a", "悲观": "#b45309"}
    for i, (lab, low, mid_v, high) in enumerate(zip(labels, lows, mids, highs)):
        y = top + row_h * i + row_h / 2
        x1, x2 = x(low), x(high)
        color = colors.get(lab, "#6b7c4a")
        # 区间条
        svg.append(f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" '
                   f'stroke="{color}" stroke-width="6" stroke-linecap="round"/>')
        # 端点
        svg.append(f'<circle cx="{x1:.1f}" cy="{y:.1f}" r="3" fill="{color}"/>')
        svg.append(f'<circle cx="{x2:.1f}" cy="{y:.1f}" r="3" fill="{color}"/>')
        # 中点
        xm = x(mid_v)
        svg.append(f'<circle cx="{xm:.1f}" cy="{y:.1f}" r="4" fill="#fff" '
                   f'stroke="{color}" stroke-width="2"/>')
        svg.append(f'<text x="{xm:.1f}" y="{y - 10:.1f}" font-size="9" '
                   f'fill="{color}" text-anchor="middle">{mid_v:.0f}%</text>')
        # label
        svg.append(f'<text x="{left - 8}" y="{y + 4:.1f}" font-size="11" '
                   f'fill="#2f2a24" text-anchor="end" font-weight="600">{lab}</text>')

    svg.append("</svg>")
    return "\n".join(svg)


# 兼容别名：学区梯队对比本质是柱状图
def render_tier_chart(data: list, title: str = "", width: int = 720,
                      height: int = 300) -> str:
    """生成学区梯队指数对比柱状图（10=第一梯队，7=第二梯队，5=第三梯队，3=第四梯队）。"""
    return render_bar_chart(data, title=title, width=width, height=height,
                            value_fmt="{:.0f}")

# --------------------------------------------------------------------------- #
# 自检
# --------------------------------------------------------------------------- #
def _mock_server(port: int, payload: dict) -> None:
    class H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):  # noqa: N802
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    # 给服务器一点启动时间
    import time
    time.sleep(0.4)
    _mock_server.srv = srv


def self_test() -> int:
    ok = True

    # 1) 排序 + 预算过滤逻辑
    comms = [
        Community(name="A", city="杭州", housing_type="commodity", avg_listing_price=60000),
        Community(name="B", city="杭州", housing_type="resettlement", avg_listing_price=30000),
        Community(name="C", city="杭州", housing_type="commodity", avg_listing_price=80000),
        Community(name="D", city="杭州", housing_type="commodity", avg_listing_price=None),
    ]
    wf = SchoolDistrictWorkflow()
    ranked = wf.rank_by_listing_price(comms)
    assert [c.name for c in ranked[:3]] == ["C", "A", "B"], "排序错误"
    filtered = wf.filter_by_budget(ranked, budget_wan=500, est_area=90)
    # C: 80000*90/10000=720万 > 500*1.15 -> 过滤掉；A: 540万 -> 留；B: 270万 -> 留；D: 未知 -> 留
    assert [c.name for c in filtered] == ["A", "B", "D"], f"预算过滤错误: {[c.name for c in filtered]}"
    print("✓ 排序与预算过滤逻辑正确")

    # 2) 学区 vs 非学区溢价计算
    school_comm = [
        Community(name="学1", housing_type="commodity", avg_listing_price=70000),
        Community(name="学2", housing_type="commodity", avg_listing_price=60000),
        Community(name="学回", housing_type="resettlement", avg_listing_price=30000),
    ]
    nonschool = [Community(name="非1", housing_type="commodity", avg_listing_price=50000)]
    cmp = wf.compare_school_vs_nonschool(school_comm, nonschool)
    # 商品房口径均值 (70000+60000)/2=65000；溢价 (65000-50000)/50000=0.30
    assert abs(cmp["school_avg_listing_commodity"] - 65000) < 1e-6, "学区均价错误"
    assert abs(cmp["school_premium_rate"] - 0.30) < 1e-6, f"溢价率错误: {cmp['school_premium_rate']}"
    assert cmp["resettlement_note"], "回迁房提示缺失"
    print("✓ 学区溢价与回迁房区分正确（溢价率 30%）")

    # 3) 数据源检索式生成：城市必须可声明，不再写死杭州
    h = HangfangSource()
    q = h.search_queries("文鼎苑", "西湖", "杭州", 36)
    assert any("杭房数研" in x and "文鼎苑" in x for x in q), "杭房检索式缺失"
    x = XiaojiSource()
    qx = x.search_queries("文鼎苑", "西湖", "杭州", 36)
    assert any("小鸡选房" in x and "文鼎苑" in x for x in qx), "小鸡检索式缺失"
    b = BeikeSource()
    qb = b.search_queries("文鼎苑", "浦东", "上海", 24)
    assert any("上海" in x and "贝壳" in x for x in qb), "贝壳检索式未带城市"
    assert not any("杭州" in x for x in qb), "贝壳检索式残留杭州"
    w = WoaiwojiaSource()
    qw = w.search_queries("文鼎苑", "浦东", "上海", 24)
    assert any("我爱我家" in x and "上海" in x for x in qw), "我爱我家检索式缺失"
    print("✓ 城市化检索式与新增我爱我家源正确")

    # 4) API 模式 + 时间轴（mock 服务器验证历史点解析）
    _mock_server(8791, {
        "data": {"list": [
            {"price": 62000, "totalPrice": 558, "area": 90, "date": "2026-07",
             "type": "listing", "history": [
                 {"month": "2026-06", "price": 61000, "count": 3},
                 {"month": "2026-05", "price": 59500, "count": 2},
             ]},
            {"price": 60000, "totalPrice": 540, "area": 90, "date": "2026-06",
             "type": "transaction", "history": [
                 {"month": "2026-06", "price": 59000, "count": 1},
             ]},
        ]}
    })
    h_api = HangfangSource(cfg={"endpoint": "http://127.0.0.1:8791/data",
                                "token": "test-token"})
    res = h_api.fetch("文鼎苑", "西湖", "上海", 24)
    assert res.mode == "api", "未走 API 模式"
    assert res.city == "上海", "城市未透传"
    assert len(res.listings) == 1 and len(res.transactions) == 1, "API 解析错误"
    assert len(res.history) >= 3, f"时间轴解析错误: {len(res.history)}"
    assert all(p.date.startswith("2026-") for p in res.history), "时间轴日期未归一化"
    assert res.confidence == "high", "API 置信度错误"
    print("✓ 杭房数研 API 模式（mock）解析正确：挂牌1/成交1/时间轴3点")

    # 5) 城市级配置覆盖
    b_cfg = BeikeSource(cfg={"cities": {
        "上海": {"endpoint": "http://127.0.0.1:8791/data", "token": "t"},
    }})
    assert b_cfg.can_api("上海"), "城市级 API 配置未生效"
    assert not b_cfg.can_api("北京"), "未配置城市不应误判可 API"
    srcs = load_sources("上海")
    assert any(s.name == "我爱我家" for s in srcs), "我爱我家未纳入数据源"
    print("✓ 城市级配置与我爱我家数据源注册正确")
    _mock_server.srv.shutdown()

    # 6) 无配置时退回检索模式
    h_ws = HangfangSource()
    res2 = h_ws.fetch("文鼎苑", "西湖", "上海", 12)
    assert res2.mode == "websearch", "未退回检索模式"
    assert any("上海" in x for x in res2.queries), "检索式未带城市"
    print("✓ 未配置接口时正确退回联网检索模式")

    # 7) 报告辅助：橄榄手记 CSS / 可点击引用（含锚点）/ 学区梯队 / 图表
    css = olive_theme_css()
    assert "--olive:#5c6b3c" in css, "橄榄手记 CSS 缺失主色"
    assert ".cite-ref" in css, "引用锚点样式缺失"
    cites = render_citations(
        [{"label": "栖霞区教育局2025年招生办法", "url": "https://edu.example.gov/a"}])
    assert 'href="https://edu.example.gov/a"' in cites, "引用链接未生成"
    assert 'target="_blank"' in cites, "引用未新开窗口"
    assert 'id="cite-1"' in cites, "引用未生成 cite-N 锚点"
    assert render_citations([]) == "", "空引用应返回空串"

    bar = render_bar_chart([{"label": "A", "value": 100}, {"label": "B", "value": 200}])
    assert "<svg" in bar and "A" in bar and "B" in bar, "柱状图生成失败"
    rng = render_range_chart([
        {"label": "乐观", "low": 0, "mid": 3, "high": 8},
        {"label": "基准", "low": -8, "mid": -2, "high": 3},
        {"label": "悲观", "low": -15, "mid": -10, "high": -3},
    ])
    assert "<svg" in rng and "乐观" in rng, "区间图生成失败"
    tier = render_tier_chart([
        {"label": "拉力琅", "value": 10},
        {"label": "晓庄小学", "value": 7},
    ])
    assert "<svg" in tier and "晓庄小学" in tier, "梯队图生成失败"

    t = school_tier_rank("晓庄小学", "南京")
    assert t["known"] and t["tier"] == "第二梯队", f"学区梯队查表错误: {t}"
    t2 = school_tier_rank("未知学校甲", "南京")
    assert not t2["known"] and "未评级" in t2["tier"], "未知学校应返回未评级"
    print("✓ 橄榄手记CSS / 可点击引用锚点 / 学区梯队 / SVG 图表辅助正确")

    # 8) T3 交叉验证源注册 + 数据源分级标注
    srcs = load_sources("上海")
    names = {s.name for s in srcs}
    for n in ("贝壳", "我爱我家", "诸葛找房", "安居客", "房天下", "58同城"):
        assert n in names, f"数据源未注册: {n}"
    tier_map = {s.name: s.tier for s in srcs}
    assert tier_map["贝壳"] == "T0" and tier_map["我爱我家"] == "T0", "T0 核心源分级错误"
    assert tier_map["诸葛找房"] == "T3" and tier_map["58同城"] == "T3", "T3 交叉源分级错误"
    assert tier_map["杭房数研"] == "T1.5", "杭房数研应标注 T1.5 城市高频源"
    z = ZhugeSource()
    assert any("诸葛找房" in x and "上海" in x for x in z.search_queries("文鼎苑", "浦东", "上海", 24)), "诸葛检索式缺失"
    w = WubaSource()
    assert any("58同城" in x and "上海" in x for x in w.search_queries("文鼎苑", "浦东", "上海", 24)), "58同城检索式缺失"
    # fetch 结果带 tier
    res = ZhugeSource().fetch("文鼎苑", "浦东", "上海", 12)
    assert res.tier == "T3" and res.mode == "websearch", "T3 源 fetch 分级/模式错误"
    print("✓ T3 交叉验证源注册与五级分级标注正确")

    # 9) 环比/同比/N月涨跌幅
    momyoy = compute_mom_yoy([
        {"date": "2026-01", "price_per_sqm": 10000, "kind": "listing", "count": 10},
        {"date": "2026-02", "price_per_sqm": 11000, "kind": "listing", "count": 8},
        {"date": "2026-03", "price_per_sqm": 9900, "kind": "listing", "count": 6},
        {"date": "2025-03", "price_per_sqm": 9000, "kind": "listing", "count": 5},
    ])
    assert "listing" in momyoy, "环比/同比缺少挂牌口径"
    L = momyoy["listing"]
    # 2026-02 vs 2026-01: (11000-10000)/10000 = +10%；2026-03 vs 2026-02 = -10%
    assert abs(L["mom"]["2026-02"] - 0.10) < 1e-9, f"环比计算错误: {L['mom']}"
    assert abs(L["mom"]["2026-03"] + 0.10) < 1e-9, f"环比计算错误: {L['mom']}"
    # 2025-03 与 2026-01 不连续，缺月不编造环比
    assert "2026-01" not in L["mom"], "缺月不应编造环比"
    # 同比：2026-03 vs 2025-03 = +10%
    assert abs(L["yoy"]["2026-03"] - 0.10) < 1e-9, f"同比计算错误: {L['yoy']}"
    # 12个月涨跌幅：2026-03 vs 2025-03 = +10%；3/6 个月前月份缺失 → 不输出
    assert abs(L["change_nm"][12] - 0.10) < 1e-9, f"12月涨跌幅错误: {L['change_nm']}"
    assert 3 not in L["change_nm"], "缺月不应编造3月涨跌幅"
    assert L["peak"]["price"] == 11000 and L["valley"]["date"] == "2025-03", "峰谷错误"
    assert L["current"]["price"] == 9900 and L["months_covered"] == 4, "当前值错误"
    # 单点时点不编造环比
    single = compute_mom_yoy([{"date": "2026-07", "price_per_sqm": 50000, "kind": "listing"}])
    assert single["listing"]["mom"] == {}, "单月不应产生环比"
    print("✓ 环比/同比/12月涨跌幅/峰谷/当前值计算正确（含缺月不编造）")

    # 10) 引用防伪元数据（发布时间/口径/一致性）+ 维度框架
    cites = render_citations([
        {"label": "贝壳某小区页", "url": "https://hz.ke.com/xiaoqu/a",
         "date": "2026-07-15 访问", "caliber": "挂牌", "consistency": "双源一致"},
        {"label": "教育局招生公告", "url": "https://edu.example.gov/b",
         "date": "2026-06", "caliber": "官方文件"},
    ])
    assert 'class="cite-meta"' in cites and "口径:挂牌" in cites, "引用元数据未生成"
    assert "一致性:双源一致" in cites and "2026-07-15 访问" in cites, "引用元数据内容错误"
    assert 'href="https://hz.ke.com/xiaoqu/a"' in cites, "引用链接丢失"
    dims = DIMENSION_FRAMEWORK
    assert set(dims) == {"price", "volume", "supply_demand", "land",
                         "school_policy", "population", "credit"}, "维度框架缺失"
    assert dims["price"]["mandatory"] is True and dims["volume"]["mandatory"] is False, "第一维度标记错误"
    print("✓ 引用防伪元数据与7维度网络框架正确")

    print("\nself-test passed" if ok else "self-test failed")
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> int:
    p = argparse.ArgumentParser(description="全国城市购房取数与学区工作流助手")
    sub = p.add_subparsers(dest="cmd")

    ps = sub.add_parser("school", help="学区流程：发现小区→排序→预算过滤→多源拉取→差异比较")
    ps.add_argument("--school", default="")
    ps.add_argument("--city", default="杭州", help="目标城市，例如 上海 / 北京 / 杭州")
    ps.add_argument("--budget", type=float, default=None, help="总预算（万元）")
    ps.add_argument("--area", type=float, default=None, help="预估面积（㎡）")
    ps.add_argument("--months", type=int, default=36, help="时间轴长度（月）")
    ps.add_argument("--communities", default="")
    ps.add_argument("--input", default="")
    ps.add_argument("--output", default="")
    ps.set_defaults(func=cmd_school)

    pc = sub.add_parser("communities", help="直接给小区（多个）流程：排序→预算过滤→多源拉取")
    pc.add_argument("--communities", default="")
    pc.add_argument("--school", default="")
    pc.add_argument("--city", default="杭州", help="目标城市，例如 上海 / 北京 / 杭州")
    pc.add_argument("--budget", type=float, default=None)
    pc.add_argument("--area", type=float, default=None)
    pc.add_argument("--months", type=int, default=36)
    pc.add_argument("--input", default="")
    pc.add_argument("--output", default="")
    pc.set_defaults(func=cmd_communities)

    pf = sub.add_parser("fetch", help="单源拉取某个小区的挂盘/成交/时间轴数据")
    pf.add_argument("--source", required=True,
                    help="贝壳 / 我爱我家 / 杭房数研 / 小鸡选房 / 诸葛找房 / 安居客 / 房天下 / 58同城")
    pf.add_argument("--community", required=True)
    pf.add_argument("--district", default="")
    pf.add_argument("--city", default="杭州", help="目标城市，例如 上海 / 北京 / 杭州")
    pf.add_argument("--months", type=int, default=36)
    pf.set_defaults(func=cmd_fetch)

    pt = sub.add_parser("timeline", help="拉取某小区近 N 个月价格时间轴（支持单源或全源）")
    pt.add_argument("--community", required=True)
    pt.add_argument("--district", default="")
    pt.add_argument("--city", default="杭州", help="目标城市，例如 上海 / 北京 / 杭州")
    pt.add_argument("--months", type=int, default=36)
    pt.add_argument("--source", default="", help="留空表示所有数据源")
    pt.add_argument("--output", default="")
    pt.set_defaults(func=cmd_timeline)

    psrc = sub.add_parser("sources", help="按声明城市列出预置信息源与精确取数检索式")
    psrc.add_argument("--city", required=True, help="目标城市，例如 上海 / 北京 / 杭州")
    psrc.set_defaults(func=cmd_sources)

    pdim = sub.add_parser(
        "dimensions", help="输出维度网络框架（房价为第一维度，其余按诉求逐层展开）")
    pdim.add_argument("--dimension", default="", help="单维查询：price/volume/supply_demand/"
                      "land/school_policy/population/credit")
    pdim.set_defaults(func=cmd_dimensions)

    p.add_argument("--self-test", action="store_true", help="运行自检")
    args = p.parse_args()
    if args.self_test:
        return self_test()
    if not getattr(args, "cmd", None):
        p.print_help()
        return 1
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
