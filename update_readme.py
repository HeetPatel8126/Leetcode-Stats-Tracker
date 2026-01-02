"""
LeetCode Stats Tracker
Fetches LeetCode statistics and updates GitHub README automatically.
"""

import os
import requests
from datetime import datetime


def fetch_leetcode_stats(username: str) -> dict:
    """Fetch LeetCode statistics using the public GraphQL API."""
    url = "https://leetcode.com/graphql"
    
    query = """
    query getUserProfile($username: String!) {
        matchedUser(username: $username) {
            username
            submitStats: submitStatsGlobal {
                acSubmissionNum {
                    difficulty
                    count
                    submissions
                }
            }
            profile {
                ranking
                reputation
                starRating
            }
        }
        userContestRanking(username: $username) {
            attendedContestsCount
            rating
            globalRanking
            topPercentage
        }
    }
    """
    
    headers = {
        "Content-Type": "application/json",
        "Referer": f"https://leetcode.com/{username}/",
    }
    
    response = requests.post(
        url,
        json={"query": query, "variables": {"username": username}},
        headers=headers,
        timeout=10
    )
    
    if response.status_code != 200:
        raise Exception(f"Failed to fetch data: {response.status_code}")
    
    data = response.json()
    
    if "errors" in data:
        raise Exception(f"GraphQL Error: {data['errors']}")
    
    return data["data"]


def parse_stats(data: dict) -> dict:
    """Parse the raw API response into a clean stats dictionary."""
    user = data.get("matchedUser", {})
    contest = data.get("userContestRanking", {})
    
    submit_stats = user.get("submitStats", {}).get("acSubmissionNum", [])
    
    stats = {
        "username": user.get("username", "N/A"),
        "ranking": user.get("profile", {}).get("ranking", "N/A"),
        "total_solved": 0,
        "easy_solved": 0,
        "medium_solved": 0,
        "hard_solved": 0,
        "contest_rating": "N/A",
        "contests_attended": "N/A",
        "top_percentage": "N/A",
    }
    
    for item in submit_stats:
        difficulty = item.get("difficulty", "")
        count = item.get("count", 0)
        
        if difficulty == "All":
            stats["total_solved"] = count
        elif difficulty == "Easy":
            stats["easy_solved"] = count
        elif difficulty == "Medium":
            stats["medium_solved"] = count
        elif difficulty == "Hard":
            stats["hard_solved"] = count
    
    if contest:
        stats["contest_rating"] = round(contest.get("rating", 0), 2)
        stats["contests_attended"] = contest.get("attendedContestsCount", 0)
        top_pct = contest.get("topPercentage")
        stats["top_percentage"] = f"{round(top_pct, 2)}%" if top_pct else "N/A"
    
    return stats


def generate_readme_content(stats: dict) -> str:
    """Generate the README content with LeetCode statistics."""
    now = datetime.now(tz=__import__('datetime').timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    # Calculate progress bars
    easy_bar = create_progress_bar(stats["easy_solved"], 830)  # Approx total easy
    medium_bar = create_progress_bar(stats["medium_solved"], 1750)  # Approx total medium
    hard_bar = create_progress_bar(stats["hard_solved"], 750)  # Approx total hard
    
    content = f"""# 📊 LeetCode Stats Tracker

![LeetCode Stats](https://img.shields.io/badge/LeetCode-{stats['username']}-orange?style=for-the-badge&logo=leetcode)

## 🏆 Profile Statistics

| Metric | Value |
|--------|-------|
| 👤 **Username** | [{stats['username']}](https://leetcode.com/{stats['username']}/) |
| 🏅 **Ranking** | #{stats['ranking']:,} |
| ✅ **Total Solved** | **{stats['total_solved']}** |

## 📈 Problem Solving Progress

| Difficulty | Solved | Progress |
|------------|--------|----------|
| 🟢 Easy | {stats['easy_solved']} | {easy_bar} |
| 🟡 Medium | {stats['medium_solved']} | {medium_bar} |
| 🔴 Hard | {stats['hard_solved']} | {hard_bar} |

## 🎯 Contest Statistics

| Metric | Value |
|--------|-------|
| 📊 **Contest Rating** | {stats['contest_rating']} |
| 🎪 **Contests Attended** | {stats['contests_attended']} |
| 📍 **Top Percentage** | {stats['top_percentage']} |

---

<p align="center">
  <i>🤖 This README is automatically updated daily via GitHub Actions</i><br>
  <sub>Last updated: {now}</sub>
</p>

<!-- LEETCODE_STATS_START -->
<!-- Auto-generated content - Do not edit manually -->
<!-- LEETCODE_STATS_END -->
"""
    return content


def create_progress_bar(solved: int, total: int, length: int = 20) -> str:
    """Create a text-based progress bar."""
    percentage = min(solved / total, 1.0) if total > 0 else 0
    filled = int(length * percentage)
    empty = length - filled
    bar = "█" * filled + "░" * empty
    pct_text = f"{percentage * 100:.1f}%"
    return f"`{bar}` {pct_text}"


def update_readme(content: str, filepath: str = "README.md"):
    """Write the updated content to README.md file."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ README.md updated successfully!")


def main():
    """Main entry point for the LeetCode stats tracker."""
    # Get username from environment variable
    username = os.environ.get("LEETCODE_USERNAME")
    
    if not username:
        print("❌ Error: LEETCODE_USERNAME environment variable not set!")
        print("Please set it using:")
        print('  Windows: $env:LEETCODE_USERNAME = "your_username"')
        print('  Linux/Mac: export LEETCODE_USERNAME="your_username"')
        return 1
    
    print(f"📊 Fetching LeetCode stats for: {username}")
    
    try:
        # Fetch and parse stats
        raw_data = fetch_leetcode_stats(username)
        stats = parse_stats(raw_data)
        
        print(f"✅ Successfully fetched stats!")
        print(f"   Total Solved: {stats['total_solved']}")
        print(f"   Easy: {stats['easy_solved']} | Medium: {stats['medium_solved']} | Hard: {stats['hard_solved']}")
        
        # Generate and update README
        readme_content = generate_readme_content(stats)
        update_readme(readme_content)
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
