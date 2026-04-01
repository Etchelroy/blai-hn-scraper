import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime, timezone
import sys

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
            UNIQUE(url)
        )
    """)
    conn.commit()

def fetch_hn_posts():
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(HN_URL, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching Hacker News: {e}")
        return []
    
    try:
        soup = BeautifulSoup(response.content, 'html.parser')
    except Exception as e:
        print(f"Error parsing HTML: {e}")
        return []
    
    posts = []
    rows = soup.select('tr.athing')
    
    for i, row in enumerate(rows[:10]):
        try:
            title_elem = row.select_one('span.titleline > a')
            if not title_elem:
                continue
            
            title = title_elem.get_text(strip=True)
            url = title_elem.get('href', '')
            
            if not url.startswith('http'):
                url = 'https://news.ycombinator.com/' + url
            
            score_row = row.find_next('tr')
            score = 0
            if score_row:
                score_elem = score_row.select_one('span.score')
                if score_elem:
                    score_text = score_elem.get_text(strip=True)
                    score = int(score_text.split()[0])
            
            if title and url:
                posts.append({
                    'title': title,
                    'url': url,
                    'score': score
                })
        except (AttributeError, ValueError, IndexError) as e:
            continue
    
    return posts

def store_posts(posts):
    try:
        conn = sqlite3.connect(DB_FILE)
        init_db(conn)
        
        timestamp = datetime.now(timezone.utc).isoformat()
        
        for post in posts:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO posts (title, url, score, fetched_at)
                    VALUES (?, ?, ?, ?)
                """, (post['title'], post['url'], post['score'], timestamp))
            except sqlite3.Error as e:
                print(f"Error inserting post '{post['title']}': {e}")
        
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def generate_report():
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT title, url, score, fetched_at FROM posts ORDER BY score DESC")
        rows = cursor.fetchall()
        conn.close()
    except sqlite3.Error as e:
        print(f"Error reading database: {e}")
        rows = []
    
    html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hacker News Top Posts Report</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f6f6f0;
        }
        h1 {
            color: #ff6600;
            text-align: center;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            background-color: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        th {
            background-color: #ff6600;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: bold;
        }
        td {
            padding: 12px;
            border-bottom: 1px solid #e0e0e0;
        }
        tr:hover {
            background-color: #f9f9f9;
        }
        a {
            color: #0066cc;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        .score {
            font-weight: bold;
            color: #333;
            text-align: center;
            width: 80px;
        }
        .timestamp {
            color: #666;
            font-size: 0.9em;
            width: 180px;
        }
        .empty {
            text-align: center;
            padding: 20px;
            color: #999;
        }
    </style>
</head>
<body>
    <h1>Hacker News Top Posts</h1>
"""
    
    if rows:
        html_content += """    <table>
        <thead>
            <tr>
                <th>Title</th>
                <th class="score">Score</th>
                <th class="timestamp">Fetched At</th>
            </tr>
        </thead>
        <tbody>
"""
        for row in rows:
            title = row['title'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
            url = row['url'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
            score = row['score']
            timestamp = row['fetched_at']
            html_content += f"""            <tr>
                <td><a href="{url}" target="_blank">{title}</a></td>
                <td class="score">{score}</td>
                <td class="timestamp">{timestamp}</td>
            </tr>
"""
        html_content += """        </tbody>
    </table>
"""
    else:
        html_content += """    <div class="empty">
        <p>No posts found. Run the scraper to fetch posts.</p>
    </div>
"""
    
    html_content += """</body>
</html>
"""
    
    try:
        with open(REPORT_FILE, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"Report generated: {REPORT_FILE}")
    except IOError as e:
        print(f"Error writing report: {e}")

def main():
    print("Fetching top 10 posts from Hacker News...")
    posts = fetch_hn_posts()
    
    if posts:
        print(f"Found {len(posts)} posts. Storing to database...")
        store_posts(posts)
        print("Posts stored successfully.")
    else:
        print("No posts were fetched.")
    
    print("Generating HTML report...")
    generate_report()
    print("Done!")

if __name__ == "__main__":
    main()