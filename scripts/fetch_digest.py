import json
import os
import urllib.request
from datetime import datetime, timezone


def fetch_stories(query, n=6):
    encoded = urllib.parse.quote(query)
    # search_by_date + a created_at floor: /search ranks by relevance with no
    # date filter, so digests carried years-old stories. points>20 keeps the
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
        stories = []
        seen = set()
        for hit in data.get("hits", []):
            title = hit.get("title", "").strip()
            points = hit.get("points", 0) or 0
            story_url = hit.get("url") or (
                f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            )
            hn_url = f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            comments = hit.get("num_comments", 0) or 0
            if title and title not in seen:
                seen.add(title)
                stories.append({
                    "title": title,
                    "url": story_url,
                    "hn_url": hn_url,
                    "points": points,
                    "comments": comments,
                })
            if len(stories) >= n:
                break
        return stories
    except Exception as e:
        print(f"fetch failed for '{query}': {e}")
        return []


def fetch_arxiv(n=3):
    url = (
        "https://export.arxiv.org/api/query"
        "?search_query=cat:cs.AI+OR+cat:cs.LG&sortBy=submittedDate"
        "&sortOrder=descending&max_results=10"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            raw = r.read().decode("utf-8")
        papers = []
        entries = raw.split("<entry>")[1:]
        for entry in entries[:n]:
            title = entry.split("<title>")[1].split("</title>")[0].strip()
            link = ""
            for part in entry.split("<link "):
                if 'type="text/html"' in part or 'rel="alternate"' in part:
                    href = part.split('href="')[1].split('"')[0]
                    link = href
                    break
            if not link and "<id>" in entry:
                link = entry.split("<id>")[1].split("</id>")[0].strip()
            if title:
                papers.append({"title": title, "url": link})
        return papers
    except Exception as e:
        print(f"arxiv fetch failed: {e}")
        return []


def build_digest(date_str, hn_stories, arxiv_papers):
    lines = [
        f"# {date_str}",
        "",
        "> auto-generated daily digest of AI agent and LLM news",
        "",
    ]

    if hn_stories:
        lines += ["## hacker news", ""]
        for s in hn_stories:
            lines.append(
                f"- **[{s['title']}]({s['url']})** "
                f"&nbsp; [{s['points']} pts &middot; {s['comments']} comments]({s['hn_url']})"
            )
        lines.append("")

    if arxiv_papers:
        lines += ["## arxiv (cs.AI / cs.LG)", ""]
        for p in arxiv_papers:
            lines.append(f"- [{p['title']}]({p['url']})")
        lines.append("")

    if not hn_stories and not arxiv_papers:
        lines += ["*no stories fetched today*", ""]

    return "\n".join(lines)


def write_digest():
    import urllib.parse  # ensure available inside subprocess

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    display_date = now.strftime("%d %b %Y")
    year = now.strftime("%Y")
    month = now.strftime("%m")

    hn_stories = fetch_stories("ai agents llm")
    arxiv_papers = fetch_arxiv()

    content = build_digest(display_date, hn_stories, arxiv_papers)

    folder = os.path.join(year, month)
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, f"{date_str}.md")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"wrote {filepath}: {len(hn_stories)} hn stories, {len(arxiv_papers)} arxiv papers")

if __name__ == "__main__":
    import urllib.parse
    write_digest()
