import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta


GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = os.environ.get("REPO", "adamentwistle/awesome-ai-agents-production")

CATEGORY_QUERIES = {
    "frameworks and orchestration": [
        "ai agent framework",
        "llm orchestration",
        "agentic workflow",
    ],
    "tool use and integrations": [
        "mcp server tools",
        "ai agent tools integrations",
        "function calling llm",
    ],
    "memory and state": [
        "agent memory llm",
        "long term memory ai agent",
    ],
    "sandboxed execution": [
        "ai code execution sandbox",
        "agent code interpreter",
    ],
    "deployment and infrastructure": [
        "llm deployment production",
        "ai agent infrastructure",
    ],
    "observability and monitoring": [
        "llm observability tracing",
        "ai agent monitoring",
    ],
    "evals and testing": [
        "llm eval framework",
        "ai agent testing benchmark",
    ],
    "on-chain and autonomous payments": [
        "ai agent blockchain onchain",
        "x402 crypto payment ai",
        "autonomous agent wallet web3",
    ],
}

MIN_STARS = 100
MAX_RESULTS_PER_QUERY = 3
DAYS_SINCE_UPDATE = 90


def github_headers():
    h = {"Accept": "application/vnd.github+json", "User-Agent": "awesome-curation-bot"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def get_existing_urls():
    urls = set()
    try:
        with open("README.md", "r", encoding="utf-8") as f:
            content = f.read()
        for match in re.finditer(r'\(https?://[^\)]+\)', content):
            url = match.group(0)[1:-1].rstrip("/").lower()
            urls.add(url)
    except FileNotFoundError:
        pass
    return urls


def search_github(query, existing_urls):
    since = (datetime.now(timezone.utc) - timedelta(days=DAYS_SINCE_UPDATE)).strftime("%Y-%m-%d")
    encoded = urllib.parse.quote(f"{query} pushed:>{since}")
    url = (
        f"https://api.github.com/search/repositories"
        f"?q={encoded}&sort=stars&order=desc&per_page=10"
    )
    try:
        req = urllib.request.Request(url, headers=github_headers())
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        results = []
        for item in data.get("items", []):
            stars = item.get("stargazers_count", 0)
            if stars < MIN_STARS:
                continue
            repo_url = item.get("html_url", "").rstrip("/").lower()
            if repo_url in existing_urls:
                continue
            results.append({
                "name": item.get("full_name", ""),
                "url": item.get("html_url", ""),
                "description": (item.get("description") or "").strip(),
                "stars": stars,
                "language": item.get("language") or "",
                "updated": item.get("pushed_at", "")[:10],
            })
            if len(results) >= MAX_RESULTS_PER_QUERY:
                break
        return results
    except Exception as e:
        print(f"github search failed for '{query}': {e}")
        return []


def search_hn(query, existing_urls, n=4):
    encoded = urllib.parse.quote(query)
    # search_by_date + a created_at floor: /search ranks by relevance with no
    # date filter, so candidates could be years old. points>20 keeps the
    # recency window from surfacing noise.
    week_ago = int(datetime.now(timezone.utc).timestamp()) - 7 * 86400
    filters = urllib.parse.quote(f"created_at_i>{week_ago},points>20")
    url = (
        f"https://hn.algolia.com/api/v1/search_by_date"
        f"?query={encoded}&tags=story&hitsPerPage=50"
        f"&numericFilters={filters}"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
        results = []
        seen_titles = set()
        for hit in data.get("hits", []):
            title = hit.get("title", "").strip()
            story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            norm_url = story_url.rstrip("/").lower()
            if norm_url in existing_urls or title in seen_titles:
                continue
            if not any(kw in title.lower() for kw in ["agent", "llm", "ai", "gpt", "claude", "production"]):
                continue
            seen_titles.add(title)
            results.append({
                "title": title,
                "url": story_url,
                "points": hit.get("points", 0) or 0,
            })
            if len(results) >= n:
                break
        return results
    except Exception as e:
        print(f"hn search failed: {e}")
        return []


def build_issue_body(candidates_by_category, hn_stories):
    now = datetime.now(timezone.utc).strftime("%d %b %Y")
    lines = [
        f"## weekly curation candidates — {now}",
        "",
        "auto-generated candidates for review. tick what's worth adding, write a one-liner, close the issue.",
        "",
        "> **the bar**: would this survive a production incident? actively maintained, real usage, clearly better than alternatives for at least one use case.",
        "",
    ]

    has_gh = any(candidates_by_category.values())
    if has_gh:
        lines.append("---")
        lines.append("")
        lines.append("### github candidates by section")
        lines.append("")
        for category, items in candidates_by_category.items():
            if not items:
                continue
            lines.append(f"#### {category}")
            lines.append("")
            for item in items:
                lang = f" · {item['language']}" if item['language'] else ""
                lines.append(f"- [ ] **[{item['name']}]({item['url']})** ⭐ {item['stars']:,}{lang}")
                if item['description']:
                    lines.append(f"  > {item['description']}")
                lines.append(f"  > last updated: {item['updated']}")
                lines.append("")

    if hn_stories:
        lines.append("---")
        lines.append("")
        lines.append("### hacker news — notable discussions")
        lines.append("")
        lines.append("_these are discussions and articles, not direct list entries — but may point to tools worth adding_")
        lines.append("")
        for story in hn_stories:
            lines.append(f"- [ ] [{story['title']}]({story['url']}) ({story['points']} pts)")
        lines.append("")

    if not has_gh and not hn_stories:
        lines.append("_no new candidates found this week above the quality threshold_")
        lines.append("")

    lines += [
        "---",
        "",
        "_opened automatically by the [curation pipeline](../../actions/workflows/curation-pipeline.yml)_",
    ]
    return "\n".join(lines)


def open_github_issue(title, body):
    url = f"https://api.github.com/repos/{REPO}/issues"
    payload = json.dumps({"title": title, "body": body, "labels": ["curation"]}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={**github_headers(), "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        print(f"issue opened: {data.get('html_url')}")
    except Exception as e:
        print(f"failed to open issue: {e}")


def run():
    existing_urls = get_existing_urls()
    print(f"found {len(existing_urls)} existing urls in readme")

    candidates_by_category = {}
    seen_urls = set(existing_urls)

    for category, queries in CATEGORY_QUERIES.items():
        items = []
        for query in queries:
            results = search_github(query, seen_urls)
            for r in results:
                norm = r["url"].rstrip("/").lower()
                if norm not in seen_urls:
                    seen_urls.add(norm)
                    items.append(r)
        candidates_by_category[category] = items
        print(f"  {category}: {len(items)} candidates")

    hn_stories = search_hn("ai agents production deployment llm", seen_urls)
    print(f"hn stories: {len(hn_stories)}")

    total = sum(len(v) for v in candidates_by_category.values()) + len(hn_stories)
    if total == 0:
        print("no candidates found, skipping issue creation")
        return

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    title = f"curation candidates — {now}"
    body = build_issue_body(candidates_by_category, hn_stories)
    open_github_issue(title, body)


if __name__ == "__main__":
    run()
