import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone


MARKER_START = "<!-- FEED:START -->"
MARKER_END = "<!-- FEED:END -->"


def fetch_ai_stories(n=5):
    # search_by_date + a created_at floor: the plain /search endpoint ranks by
    # relevance with no date filter, so the feed showed years-old stories under
    # today's date. points>20 keeps the recency window from surfacing noise.
    week_ago = int(datetime.now(timezone.utc).timestamp()) - 7 * 86400
    filters = urllib.parse.quote(f"created_at_i>{week_ago},points>20")
    url = (
        "https://hn.algolia.com/api/v1/search_by_date"
        f"?query=ai+agents+llm&tags=story&hitsPerPage=30"
        f"&numericFilters={filters}"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
        stories = []
        seen = set()
        for hit in data.get("hits", []):
            title = hit.get("title", "").strip()
            story_url = hit.get("url") or (
                f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            )
            if title and title not in seen:
                seen.add(title)
                stories.append(f"- [{title}]({story_url})")
            if len(stories) >= n:
                break
        return stories
    except Exception as e:
        print(f"fetch failed: {e}")
        return []


def build_section(stories, date_str):
    if not stories:
        return f"{MARKER_START}\n<!-- refreshed {date_str}, no stories fetched -->\n{MARKER_END}"
    lines = "\n".join(stories)
    return (
        f"{MARKER_START}\n"
        f"### from the feed &nbsp;·&nbsp; {date_str}\n\n"
        f"{lines}\n"
        f"{MARKER_END}"
    )


def update_readme():
    with open("README.md", "r", encoding="utf-8") as f:
        content = f.read()

    date_str = datetime.now(timezone.utc).strftime("%d %b %Y")
    stories = fetch_ai_stories()
    section = build_section(stories, date_str)

    if MARKER_START in content and MARKER_END in content:
        start = content.index(MARKER_START)
        end = content.index(MARKER_END) + len(MARKER_END)
        new_content = content[:start] + section + content[end:]
    else:
        new_content = content.rstrip() + f"\n\n{section}\n"

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"readme updated: {date_str}, {len(stories)} stories")


if __name__ == "__main__":
    update_readme()
