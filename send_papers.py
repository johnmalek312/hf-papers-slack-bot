import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.request import urlopen

import requests

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_USER_ID = os.environ["SLACK_USER_ID"]
RSS_FEED_URL = "https://papers.takara.ai/api/feed"
MAX_PAPERS = 3


def fetch_papers():
    """Fetch latest papers from HF Daily Papers RSS feed."""
    with urlopen(RSS_FEED_URL) as resp:
        xml_data = resp.read()

    root = ET.fromstring(xml_data)
    items = root.findall(".//item")

    if not items:
        print("No entries found in feed.")
        return []

    papers = []
    for item in items[:MAX_PAPERS]:
        title = item.findtext("title", "Untitled")
        link = item.findtext("link", "#")
        if len(title) > 120:
            title = title[:117] + "..."
        papers.append({"title": title, "link": link})

    return papers


def format_message(papers):
    """Format papers into a Slack message."""
    today = datetime.now(timezone.utc).strftime("%A, %B %d %Y")
    lines = [f"*📄 HF Daily Papers — {today}*\n"]

    for i, p in enumerate(papers, 1):
        lines.append(f"{i}. <{p['link']}|{p['title']}>")

    lines.append(f"\n_Source: <https://huggingface.co/papers|HF Daily Papers>_")
    return "\n".join(lines)


def send_slack_dm(text):
    """Send a DM to the configured Slack user."""
    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        json={
            "channel": SLACK_USER_ID,
            "text": text,
            "unfurl_links": False,
            "unfurl_media": False,
        },
    )

    data = resp.json()
    if not data.get("ok"):
        print(f"ERROR: Slack API error: {data.get('error')}")
        sys.exit(1)

    print(f"Message sent successfully to {SLACK_USER_ID}")


def main():
    print("Fetching papers...")
    papers = fetch_papers()

    if not papers:
        print("No papers today. Skipping.")
        return

    print(f"Found {len(papers)} papers. Sending to Slack...")
    msg = format_message(papers)
    send_slack_dm(msg)


if __name__ == "__main__":
    main()
