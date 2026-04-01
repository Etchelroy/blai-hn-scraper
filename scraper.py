import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime, timezone

DB_FILE = "hn_posts.db"
REPORT_FILE = "report.html"
HN_URL = "https://news.ycombinator.com/"

def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            score INTEGER NOT NULL,
            fetched_at TEXT NOT NULL,
            UNIQUE(title, url)
        )
    """)
    conn.commit()

def fetch_posts():
    try:
        resp = requests.get(HN_URL, timeout=10, headers={"User-Agent": "hn-scraper/1.0"})
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Network error: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    posts = []

    title_rows = soup.select("tr.athing")[:10]
    for row in title_rows:
        try:
            title_tag = row.select_one("span.titleline > a")
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            url = title_tag.get("href", "")
            if url.startswith("item?"):
                url = HN_URL + url

            subtext = row.find_next_sibling("tr")
            score = 0
            if subtext:
                score_tag = subtext.select_one("span.score")
                if score_tag:
                    score_text = score_tag.get_text(strip=True)
                    score = int(score_text.split()[0])

            posts.append({
                "title": title,
                "url": url,
                "score": score,
                "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            })
        except Exception as e:
            print(f"Error parsing post: {e}")
            continue

    return posts

def store_posts(conn, posts):
    inserted = 0
    for p in posts:
        try:
            conn.execute(
                """
                INSERT INTO posts (title, url, score, fetched_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(title, url) DO UPDATE SET
                    score = excluded.score,
                    fetched_at = excluded.fetched_at
                """,
                (p["title"], p["url"], p["score"], p["fetched_at"])
            )
            inserted += 1
        except sqlite3.Error as e:
            print(f"DB error for '{p['title']}': {e}")
    conn.commit()
    print(f"Stored/updated {inserted} posts.")

def load_all_posts(conn):
    cur = conn.execute("SELECT title, url, score, fetched_at FROM posts ORDER BY score DESC")
    return cur.fetchall()

def generate_report(posts):
    rows_html = ""
    for i, (title, url, score, fetched_at) in enumerate(posts, 1):
        rows_html += f"""
        <tr>
            <td class="rank">{i}</td>
            <td class="title"><a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a></td>
            <td class="score">{score}</td>
            <td class="timestamp">{fetched_at}</td>
        </tr>"""

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Hacker News Top Posts Report</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f6f6ef;
    color: #333;
    padding: 2rem;
  }}
  header {{
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }}
  header .logo {{
    background: #ff6600;
    color: white;
    font-weight: bold;
    font-size: 1.1rem;
    padding: 6px 10px;
    border-radius: 4px;
  }}
  header h1 {{
    font-size: 1.4rem;
    font-weight: 700;
    color: #1a1a1a;
  }}
  .meta {{
    font-size: 0.82rem;
    color: #888;
    margin-bottom: 1.5rem;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    background: white;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  }}
  thead {{
    background: #ff6600;
    color: white;
  }}
  thead th {{
    padding: 12px 16px;
    text-align: left;
    font-size: 0.85rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }}
  tbody tr {{
    border-bottom: 1px solid #f0f0f0;
    transition: background 0.15s;
  }}
  tbody tr:last-child {{ border-bottom: none; }}
  tbody tr:hover {{ background: #fff8f2; }}
  td {{
    padding: 12px 16px;
    font-size: 0.9rem;
    vertical-align: middle;
  }}
  td.rank {{
    color: #aaa;
    font-weight: 700;
    width: 40px;
    text-align: center;
  }}
  td.title a {{
    color: #333;
    text-decoration: none;
    font-weight: 500;
  }}
  td.title a:hover {{ color: #ff6600; text-decoration: underline; }}
  td.score {{
    color: #ff6600;
    font-weight: 700;
    width: 80px;
    text-align: right;
  }}
  td.timestamp {{
    color: #999;
    font-size: 0.78rem;
    width: 180px;
    white-space: nowrap;
  }}
  .empty {{
    text-align: center;
    padding: 2rem;
    color: #999;
  }}
</style>
</head>
<body>
<header>
  <span class="logo">HN</span>
  <h1>Hacker News &mdash; Top Posts Report</h1>
</header>
<p class="meta">Generated at {generated_at} &bull; {len(posts)} posts stored &bull; sorted by score descending</p>
<table>
  <thead>
    <tr>
      <th>#</th>
      <th>Title</th>
      <th style="text-align:right">Score</th>
      <th>Fetched At</th>
    </tr>
  </thead>
  <tbody>
    {"".join(rows_html) if posts else '<tr><td colspan="4" class="empty">No posts found.</td></tr>'}
  </tbody>
</table>
</body>
</html>"""

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Report written to {REPORT_FILE}")

def main():
    print("Fetching HN front page...")
    posts = fetch_posts()
    if not posts:
        print("No posts fetched. Aborting.")
        return

    print(f"Fetched {len(posts)} posts.")

    conn = sqlite3.connect(DB_FILE)
    try:
        init_db(conn)
        store_posts(conn, posts)
        all_posts = load_all_posts(conn)
    finally:
        conn.close()

    generate_report(all_posts)
    print("Done.")

if __name__ == "__main__":
    main()