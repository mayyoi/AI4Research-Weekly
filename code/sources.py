# -*- coding: utf-8 -*-
"""
抓取层：把各信息源的内容统一成同一种格式。

设计要点：
1. 只用 Python 自带库，不需要安装任何依赖（少一个安装步骤，就少一处可能失败的地方）。
2. 每个源都包在 try/except 里：某个源挂了只会少几条内容，绝不会让整封周报失败。
"""

from __future__ import annotations

import gzip
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from datetime import date, datetime, timedelta, timezone

USER_AGENT = (
    "Mozilla/5.0 (compatible; AI4Research-Weekly/1.0; "
    "+https://github.com/mayyoi/AI4Research-Weekly)"
)

# 如果环境里提供了 GITHUB_TOKEN（GitHub Actions 会自动提供），
# 就用它来提升 GitHub 接口的调用次数上限。没有也能跑，只是额度低一些。
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()

# 每条抓取结果的统一格式
EMPTY_ITEM = {
    "title": "",
    "url": "",
    "summary": "",
    "source": "",
    "published": "",
    "extra": "",
    "pool": "",
}


def http_get(url: str, timeout: int = 30, accept_json: bool = False) -> str:
    """发 GET 请求并返回文本，自动处理 gzip/deflate 压缩。"""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/json" if accept_json else "*/*",
    }
    if GITHUB_TOKEN and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        encoding = (response.headers.get("Content-Encoding") or "").lower()
    if encoding == "gzip":
        raw = gzip.decompress(raw)
    elif encoding == "deflate":
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
    return raw.decode("utf-8", errors="replace")


def http_get_json(url: str, timeout: int = 30):
    return json.loads(http_get(url, timeout=timeout, accept_json=True))


def _clean(text) -> str:
    """去掉 HTML 标签、转义字符和多余空白，得到干净的纯文本。"""
    if text is None:
        return ""
    text = str(text)
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _truncate(text: str, limit: int = 700) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + " …"


def _iso_date(value: str) -> str:
    """尽量把各种日期写法统一成 YYYY-MM-DD。"""
    if not value:
        return ""
    value = str(value).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value
    for pattern in (r"(\d{4})-(\d{2})-(\d{2})", r"(\d{4})/(\d{2})/(\d{2})", r"(\d{4})(\d{2})(\d{2})"):
        match = re.search(pattern, value)
        if match:
            return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    try:
        parsed = datetime.strptime(value[:16].strip(), "%a, %d %b %Y")
        return parsed.date().isoformat()
    except ValueError:
        return ""


def _is_within_days(published: str, days: int) -> bool:
    iso = _iso_date(published)
    if not iso:
        return True
    try:
        return date.fromisoformat(iso) >= date.today() - timedelta(days=days)
    except ValueError:
        return True


def fetch_arxiv(source: dict, days: int) -> list[dict]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    window = f"[{start.strftime('%Y%m%d%H%M')} TO {end.strftime('%Y%m%d%H%M')}]"
    params = {
        "search_query": f"({source['query']}) AND submittedDate:{window}",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": str(source.get("limit", 30)),
    }
    xml_text = http_get("https://export.arxiv.org/api/query?" + urllib.parse.urlencode(params), timeout=45)
    root = ET.fromstring(xml_text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = []
    for entry in root.findall("atom:entry", ns):
        title = _clean(entry.findtext("atom:title", default="", namespaces=ns))
        if not title:
            continue
        authors = [_clean(a.findtext("atom:name", default="", namespaces=ns)) for a in entry.findall("atom:author", ns)]
        categories = [c.attrib.get("term", "") for c in entry.findall("atom:category", ns)]
        items.append({
            **EMPTY_ITEM,
            "title": title,
            "url": entry.findtext("atom:id", default="", namespaces=ns).strip(),
            "summary": _truncate(_clean(entry.findtext("atom:summary", default="", namespaces=ns))),
            "source": source["name"],
            "published": _iso_date(entry.findtext("atom:published", default="", namespaces=ns)),
            "extra": ("作者：" + "、".join(authors[:3]) + "　" if authors else "") + "领域：" + ", ".join(categories[:3]),
            "pool": source.get("pool", ""),
        })
    return items


def _local_name(tag) -> str:
    """取标签的本地名（去掉命名空间），例如 {http://...}item -> item。"""
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1].lower()


def _iter_feed_entries(root):
    """
    按标签名（忽略命名空间）找出所有条目。
    这样才能同时吃下三种订阅格式：
      RSS 2.0  <item>
      RSS 1.0 / RDF  <item>（带命名空间，Nature 系列就是这种）
      Atom     <entry>
    """
    for element in root.iter():
        if _local_name(element.tag) in ("item", "entry"):
            yield element


def _child_value(node, names: tuple[str, ...], prefer_attr: str = "") -> str:
    """在直接子节点里按标签名取值；prefer_attr 非空时优先读该属性（Atom 的 link）。"""
    fallback = ""
    for child in node:
        if _local_name(child.tag) not in names:
            continue
        if prefer_attr:
            href = child.attrib.get(prefer_attr)
            if href:
                return href
        value = "".join(child.itertext()).strip()
        if value and not fallback:
            fallback = value
        if value:
            return value
    return fallback


def _parse_feed(xml_text: str, source: dict) -> list[dict]:
    """兼容 RSS 2.0 / RSS 1.0(RDF) / Atom 三种订阅格式。"""
    root = ET.fromstring(xml_text)
    items = []
    for node in _iter_feed_entries(root):
        title = _clean(_child_value(node, ("title",)))
        link = _clean(_child_value(node, ("link",), prefer_attr="href"))
        summary = _clean(_child_value(node, ("description", "encoded", "summary", "content")))
        published = _child_value(node, ("pubdate", "date", "updated", "published", "issued"))
        if not title or not link:
            continue
        items.append({
            **EMPTY_ITEM,
            "title": title,
            "url": link.strip(),
            "summary": _truncate(summary, 500),
            "source": source["name"],
            "published": _iso_date(published),
            "pool": source.get("pool", ""),
        })
    return items


def fetch_rss(source: dict, days: int) -> list[dict]:
    return _parse_feed(http_get(source["url"], timeout=30), source)


def fetch_github(source: dict, days: int) -> list[dict]:
    since = (date.today() - timedelta(days=days)).isoformat()
    params = {
        "q": source["query"].replace("{since}", since),
        "sort": "stars",
        "order": "desc",
        "per_page": str(source.get("limit", 20)),
    }
    url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(params)
    payload = http_get_json(url, timeout=30)
    # GitHub 对未登录的搜索接口限制很严，偶尔会"假装成功但返回 0 条"。
    # 所以如果第一次是空的，等一会儿再试一次。
    if not payload.get("items"):
        print(f"      （{source['name']} 第一次返回空，15 秒后重试一次）")
        time.sleep(15)
        payload = http_get_json(url, timeout=30)
    items = []
    for repo in payload.get("items", []):
        description = _clean(repo.get("description") or "")
        topics = ", ".join(repo.get("topics") or [])
        items.append({
            **EMPTY_ITEM,
            "title": repo.get("full_name", ""),
            "url": repo.get("html_url", ""),
            "summary": _truncate(f"{description}　标签：{topics}" if topics else description, 400),
            "source": source["name"],
            "published": _iso_date(repo.get("created_at", "")),
            "extra": f"⭐ {repo.get('stargazers_count', 0)}　语言：{repo.get('language') or '未标注'}",
            "pool": source.get("pool", ""),
        })
    return items


def fetch_biorxiv(source: dict, days: int) -> list[dict]:
    end = date.today()
    start = end - timedelta(days=min(days, 30))
    url = f"https://api.{source['server']}.org/details/{source['server']}/{start.isoformat()}/{end.isoformat()}/0"
    payload = http_get_json(url, timeout=45)
    items = []
    for record in payload.get("collection", []):
        title = _clean(record.get("title"))
        if not title:
            continue
        items.append({
            **EMPTY_ITEM,
            "title": title,
            "url": f"https://doi.org/{record.get('doi')}",
            "summary": _truncate(_clean(record.get("abstract")), 500),
            "source": source["name"],
            "published": _iso_date(record.get("date", "")),
            "extra": _clean(record.get("category", "")),
            "pool": source.get("pool", ""),
        })
    return items


def fetch_pubmed(source: dict, days: int) -> list[dict]:
    # 注意：PubMed 的 "(last N days[dp])" 写法现在无论怎么拼都返回 0 条，
    # 但 datetype=pdat + reldate=N 参数写法是可靠的（实测 21 天能返回数千条）。
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode({
        "db": "pubmed",
        "term": source["query"],
        "retmode": "json",
        "retmax": str(source.get("limit", 30)),
        "sort": "pub date",
        "datetype": "pdat",
        "reldate": str(days),
    })
    ids = http_get_json(search_url, timeout=30).get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode({
        "db": "pubmed",
        "id": ",".join(ids),
        "retmode": "xml",
    })
    root = ET.fromstring(http_get(fetch_url, timeout=60))
    items = []
    for article in root.findall(".//PubmedArticle"):
        pmid = _clean(article.findtext(".//PMID"))
        title_node = article.find(".//ArticleTitle")
        title = _clean("".join(title_node.itertext())) if title_node is not None else ""
        if not title:
            continue
        parts = []
        for node in article.findall(".//Abstract/AbstractText"):
            label = node.attrib.get("Label", "")
            body = _clean("".join(node.itertext()))
            parts.append(f"{label}: {body}" if label else body)
        year = _clean(article.findtext(".//PubDate/Year"))
        month = _clean(article.findtext(".//PubDate/Month"))
        items.append({
            **EMPTY_ITEM,
            "title": title,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "summary": _truncate(" ".join(parts), 600),
            "source": source["name"],
            "published": _iso_date(f"{year}-{month}-01") if year else "",
            "extra": _clean(article.findtext(".//Journal/Title")),
            "pool": source.get("pool", ""),
        })
    return items


def fetch_hf(source: dict, days: int) -> list[dict]:
    payload = http_get_json(f"https://huggingface.co/api/daily_papers?limit={source.get('limit', 40)}", timeout=40)
    items = []
    for entry in payload if isinstance(payload, list) else []:
        paper = entry.get("paper") or {}
        title = _clean(paper.get("title"))
        if not title:
            continue
        items.append({
            **EMPTY_ITEM,
            "title": title,
            "url": f"https://huggingface.co/papers/{paper.get('id')}",
            "summary": _truncate(_clean(paper.get("summary")), 600),
            "source": source["name"],
            "published": _iso_date(entry.get("publishedAt") or paper.get("publishedAt", "")),
            "extra": "Hugging Face 每日精选",
            "pool": source.get("pool", ""),
        })
    return items


def fetch_hn(source: dict, days: int) -> list[dict]:
    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    params = {
        "query": source["query"],
        "tags": "story",
        "numericFilters": f"created_at_i>{since},points>{source.get('min_points', 30)}",
        "hitsPerPage": str(source.get("limit", 40)),
    }
    payload = http_get_json("https://hn.algolia.com/api/v1/search_by_date?" + urllib.parse.urlencode(params), timeout=30)
    items = []
    for hit in payload.get("hits", []):
        title = _clean(hit.get("title"))
        if not title:
            continue
        items.append({
            **EMPTY_ITEM,
            "title": title,
            "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
            "summary": _truncate(_clean(hit.get("story_text") or ""), 300),
            "source": source["name"],
            "published": _iso_date((hit.get("created_at") or "")[:10]),
            "extra": f"Hacker News {hit.get('points', 0)} 赞　{hit.get('num_comments', 0)} 评论",
            "pool": source.get("pool", ""),
        })
    return items


FETCHERS = {
    "arxiv": fetch_arxiv,
    "rss": fetch_rss,
    "github": fetch_github,
    "biorxiv": fetch_biorxiv,
    "pubmed": fetch_pubmed,
    "hf": fetch_hf,
    "hn": fetch_hn,
}


def fetch_all(sources: list[dict], days: int, verbose: bool = True) -> tuple[list[dict], list[str]]:
    """抓取全部信息源。返回 (统一格式的条目列表, 失败的源说明)。"""
    items: list[dict] = []
    failures: list[str] = []
    for source in sources:
        fetcher = FETCHERS.get(source["kind"])
        if fetcher is None:
            failures.append(f"{source['name']}：未知 kind={source['kind']}")
            continue
        got, error = [], None
        for attempt in (1, 2):
            try:
                got = fetcher(source, days)
                error = None
                break
            except Exception as exc:  # noqa: BLE001
                error = exc
                if attempt == 1:
                    if verbose:
                        print(f"  [源] {source['name']:<26s} 第 1 次失败，5 秒后重试")
                    time.sleep(5)
        if error is not None:
            if isinstance(error, urllib.error.HTTPError):
                failures.append(f"{source['name']}：HTTP {error.code}")
                label = f"失败 HTTP {error.code}"
            else:
                failures.append(f"{source['name']}：{type(error).__name__}")
                label = f"失败 {type(error).__name__}"
            if verbose:
                print(f"  [源] {source['name']:<26s} {label}")
        else:
            got = [g for g in got if _is_within_days(g.get("published", ""), days)]
            items.extend(got)
            if verbose:
                print(f"  [源] {source['name']:<26s} 抓到 {len(got):>3d} 条")
        # GitHub 的接口限制比较严，间隔给长一点
        time.sleep(3.0 if source["kind"] == "github" else 0.4)
    return items, failures
