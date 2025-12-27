#!/usr/bin/env python3
"""
Reddit Post Monitor and Email Notifier Workflow

This script fetches new posts from specified Reddit subreddits using direct GET requests to Reddit's
unofficial .json endpoints (no API key required). It filters posts based on configurable conditions,
then sends the title and link of matching new posts via email. It tracks sent posts in a local file
to avoid duplicates on subsequent runs.

Designed to be run periodically (e.g., via cron or task scheduler) as a workflow.

Python version: Tested on Python 3.14 (compatible with 3.8+).

Dependencies: requests (pip install requests)
"""
import json
import os
import pprint
import smtplib
from datetime import datetime
from email.message import EmailMessage
from typing import Dict, List

import pystache
import requests
from dotenv import load_dotenv

load_dotenv()

# ----------------------------- Configuration -----------------------------

# Email configuration
SMTP_SERVER = "smtp.gmail.com"          # e.g., "smtp.gmail.com" for Gmail
SMTP_PORT = 587
EMAIL_FROM = "fstemarie+gd@gmail.com"
# Use app password for Gmail
EMAIL_PASSWORD = os.getenv("GAMEDEALS_EMAIL_PASSWORD")
EMAIL_RECIPIENTS = os.getenv("GAMEDEALS_EMAIL_RECIPIENTS") or "fstemarie@gmail.com"

# Storage for tracking sent posts
# Local file to store sent post IDs
SENT_FILE = os.getenv("GAMEDEALS_SENT_FILE") or "sent_posts.json"

# User-Agent (required by Reddit; customize to identify your script)
HEADERS = {
    "User-Agent": "py_GameDeals/1.0"
}


SUBREDDIT = "GameDeals"  # List of subreddits to monitor (without r/)
SORT_BY = "new"                         # Options: "hot", "new", "top", "rising"
# Max posts to fetch per subreddit (Reddit usually caps at ~100)
LIMIT = 50

TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #2E2E2E;
            background-image: url('https://img.freepik.com/premium-vector/carbon-fiber-background_79145-383.jpg'); /* Adding the new carbon fiber background */
            background-size: cover;
            background-attachment: fixed;
            margin: 0;
            padding: 20px;
        }
        .card-container {
            display: flex;
            flex-direction: column;
            align-items: flex-start; /* Align cards to the left */
            gap: 20px;
        }
        .card {
            background-color: #f8f8f8; /* Adjusted to a less white color */
            border: 1px solid #ccc;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 20px;
            width: 100%;
            max-width: 500px;
            box-sizing: border-box; /* Ensure padding is included in the width calculation */
        }
        .card-title {
            font-size: 20px;
            margin-bottom: 10px;
        }
        .card-links {
            display: flex;
            gap: 10px;
        }
        .card-link {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 20px;
            background-color: #2E2E2E; /* Same color as the background */
            color: #ffffff;
            text-decoration: none;
            font-size: 14px;
        }
    </style>
    <title>Game List</title>
</head>
<body>
    <div class="card-container" id="card-container">
        {{#posts}}
        <div class="card">
            <div class="card-title">{{title}}</div>
            <div class="card-links">
                <a href="http://www.reddit.com{{permalink}}" class="card-link">Reddit link</a>
                <a href="{{url}}" class="card-link">Direct link</a>
            </div>
        </div>
        {{/posts}}
    </div>

    <script>
        // JavaScript to make all cards the same width
        window.onload = function() {
            var cards = document.querySelectorAll('.card');
            var maxWidth = 0;

            // Find the widest card
            cards.forEach(function(card) {
                maxWidth = Math.max(maxWidth, card.offsetWidth);
            });

            // Set all cards to the width of the widest card
            cards.forEach(function(card) {
                card.style.width = maxWidth + 'px';
            });
        }
    </script>
</body>
</html>
"""

# Filtering conditions (to be defined/customized later)


def filter_post(post: Dict) -> bool:
    """
    Return True if the post should be included.
    Example placeholders:
    - if post['score'] >= 10:
    - if "question" in post['title'].lower():
    """
    # Get rid of self posts
    if post["domain"].lower() == "self.gamedeals":
        return False
    title = post["title"].lower()
    subs = ["steam", "gog", "epic"]
    if not any(sub in title for sub in subs):
        return False
    subs = ["limited time", "free weekend", "free to play", "trial", "buy"]
    if any(sub in title for sub in subs):
        return False
    subs = ["free", "100"]
    if not any(sub in title for sub in subs):
        return False
    return True


# -----------------------------------------------------------------------

def render_posts_html(template: str, posts: List[Dict]) -> str:
    """Render HTML content for email using a simple template."""
    html = pystache.render(template, {"posts": posts})
    return html


def load_sent_posts() -> set:
    """Load set of previously sent post IDs from file."""
    if os.path.exists(SENT_FILE):
        with open(SENT_FILE, "r") as f:
            data = json.load(f)
            return set(data.get("sent_ids", []))
    return set()


def save_sent_posts(sent_ids: set):
    """Save the updated set of sent post IDs to file."""
    with open(SENT_FILE, "w") as f:
        json.dump({"sent_ids": list(sent_ids)}, f)


def fetch_posts(subreddit: str) -> List[Dict]:
    """Fetch posts from a subreddit as JSON."""
    url = f"https://www.reddit.com/r/{subreddit}/{SORT_BY}.json?limit={LIMIT}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    data = response.json()
    posts = []
    for child in data["data"]["children"]:
        p = child["data"]
        posts.append({
            "id": p["id"],
            "title": p["title"],
            "url": p['url'],
            "domain": p["domain"],
            "permalink": f"https://www.reddit.com{p['permalink']}",
        })
    return posts


def send_email(html: str):
    """Send an email with the list of new matching posts."""
    msg = EmailMessage()
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_RECIPIENTS
    msg["Subject"] = f"/r/Gamedeals (python)"
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.send_message(msg)


def main():
    sent_ids = load_sent_posts()
    new_matching_posts = []

    try:
        posts = fetch_posts(SUBREDDIT)
        for post in posts:
            if post["id"] not in sent_ids and filter_post(post):
                new_matching_posts.append(post)
                sent_ids.add(post["id"])
    except Exception as e:
        print(f"Error fetching {SUBREDDIT}: {e}")

    if new_matching_posts:
        html = render_posts_html(TEMPLATE, new_matching_posts)
        send_email(html)
        save_sent_posts(sent_ids)
        print(f"Sent email with {len(new_matching_posts)} new posts.")
    else:
        print("No new matching posts.")


if __name__ == "__main__":
    main()
