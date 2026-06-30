"""
LeetCode Stats Tracker
Fetches LeetCode statistics and updates GitHub README automatically.
"""

import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2          # seconds — doubles each retry
RECENT_AC_LIMIT = 5
DEFAULT_USERNAME = "HeetPatel8126"

LANG_DISPLAY: dict[str, str] = {
    "python3": "Python",
    "python": "Python",
    "java": "Java",
    "cpp": "C++",
    "c": "C",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "golang": "Go",
    "rust": "Rust",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "csharp": "C#",
    "ruby": "Ruby",
    "scala": "Scala",
    "php": "PHP",
    "dart": "Dart",
    "mysql": "MySQL",
    "postgresql": "PostgreSQL",
}

GRAPHQL_QUERY = """
query getUserProfile($username: String!) {
    matchedUser(username: $username) {
        username
        submitStats: submitStatsGlobal {
            acSubmissionNum {
                difficulty
                count
                submissions
            }
            totalSubmissionNum {
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
        userCalendar {
            streak
            totalActiveDays
        }
        badges {
            displayName
            icon
            creationDate
        }
    }
    recentAcSubmissionList(username: $username, limit: 5) {
        title
        titleSlug
        timestamp
        statusDisplay
        lang
    }
    userContestRanking(username: $username) {
        attendedContestsCount
        rating
        globalRanking
        topPercentage
    }
    allQuestionsCount {
        difficulty
        count
    }
}
"""


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------
def fetch_leetcode_stats(username: str) -> dict[str, Any]:
    """Fetch LeetCode statistics with retry and exponential back-off."""
    headers = {
        "Content-Type": "application/json",
        "Referer": f"https://leetcode.com/{username}/",
    }
    payload = {
        "query": GRAPHQL_QUERY,
        "variables": {"username": username},
    }

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info(
                "Attempt %d/%d — fetching stats for %s",
                attempt, MAX_RETRIES, username,
            )
            resp = requests.post(
                LEETCODE_GRAPHQL_URL,
                json=payload,
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            if "errors" in data:
                raise ValueError(f"GraphQL errors: {data['errors']}")

            if not data.get("data", {}).get("matchedUser"):
                raise ValueError(f"User '{username}' not found")

            log.info("Data fetched successfully")
            return data["data"]

        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF_BASE ** attempt
                log.warning(
                    "Attempt %d failed: %s — retrying in %ds",
                    attempt, exc, wait,
                )
                time.sleep(wait)
            else:
                log.error("All %d attempts failed", MAX_RETRIES)

    raise RuntimeError(
        f"Failed after {MAX_RETRIES} retries"
    ) from last_error


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
def parse_stats(data: dict[str, Any]) -> dict[str, Any]:
    """Parse raw API response into a clean stats dictionary."""
    user = data.get("matchedUser") or {}
    contest = data.get("userContestRanking") or {}
    all_questions = data.get("allQuestionsCount") or []

    submit_stats = (user.get("submitStats") or {}).get("acSubmissionNum") or []
    total_submit = (user.get("submitStats") or {}).get("totalSubmissionNum") or []
    calendar = user.get("userCalendar") or {}
    recent = data.get("recentAcSubmissionList") or []

    # Dynamic question totals from the API
    question_totals: dict[str, int] = {}
    for q in all_questions:
        question_totals[q["difficulty"]] = q["count"]

    stats: dict[str, Any] = {
        "username": user.get("username", DEFAULT_USERNAME),
        "ranking": (user.get("profile") or {}).get("ranking", 0),
        "total_solved": 0,
        "easy_solved": 0,
        "medium_solved": 0,
        "hard_solved": 0,
        "total_easy": question_totals.get("Easy", 830),
        "total_medium": question_totals.get("Medium", 1750),
        "total_hard": question_totals.get("Hard", 750),
        "total_questions": question_totals.get("All", 3330),
        "acceptance_rate": 0.0,
        "streak": calendar.get("streak", 0),
        "total_active_days": calendar.get("totalActiveDays", 0),
        "contest_rating": "N/A",
        "contests_attended": "N/A",
        "top_percentage": "N/A",
        "recent_submissions": [],
        "badges": [],
    }

    # Solved counts per difficulty
    for item in submit_stats:
        diff = item.get("difficulty", "")
        count = item.get("count", 0)
        if diff == "All":
            stats["total_solved"] = count
        elif diff == "Easy":
            stats["easy_solved"] = count
        elif diff == "Medium":
            stats["medium_solved"] = count
        elif diff == "Hard":
            stats["hard_solved"] = count

    # Acceptance rate
    ac_subs = next(
        (s["submissions"] for s in submit_stats if s["difficulty"] == "All"), 0
    )
    total_subs = next(
        (s["submissions"] for s in total_submit if s["difficulty"] == "All"), 0
    )
    if total_subs > 0:
        stats["acceptance_rate"] = round(ac_subs / total_subs * 100, 1)

    # Contest stats
    if contest:
        rating = contest.get("rating")
        stats["contest_rating"] = round(rating, 2) if rating else "N/A"
        stats["contests_attended"] = contest.get("attendedContestsCount", "N/A")
        top_pct = contest.get("topPercentage")
        stats["top_percentage"] = f"{round(top_pct, 2)}%" if top_pct else "N/A"

    # Recent accepted submissions
    # Badges
    for badge in (user.get("badges") or []):
        icon = badge.get("icon", "")
        if icon and not icon.startswith("http"):
            icon = f"https://leetcode.com{icon}"
        stats["badges"].append({
            "name": badge.get("displayName", "Badge"),
            "icon": icon,
            "date": badge.get("creationDate", ""),
        })

    for sub in recent[:RECENT_AC_LIMIT]:
        stats["recent_submissions"].append({
            "title": sub.get("title", "Unknown"),
            "slug": sub.get("titleSlug", ""),
            "lang": LANG_DISPLAY.get(
                sub.get("lang", ""), sub.get("lang", "N/A")
            ),
            "timestamp": sub.get("timestamp", "0"),
        })

    return stats


# ---------------------------------------------------------------------------
# README generation
# ---------------------------------------------------------------------------
def create_progress_bar(solved: int, total: int, length: int = 20) -> str:
    """Create a Unicode progress bar with counts."""
    pct = min(solved / total, 1.0) if total > 0 else 0
    filled = int(length * pct)
    bar = "█" * filled + "░" * (length - filled)
    return f"`{bar}` {solved:,}/{total:,} ({pct * 100:.1f}%)"


def _format_timestamp(ts: str) -> str:
    """Convert a Unix timestamp string to a human-readable date."""
    try:
        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        return dt.strftime("%b %d, %Y")
    except (ValueError, OSError):
        return "—"


def generate_readme_content(stats: dict[str, Any]) -> str:
    """Generate a polished README with LeetCode statistics."""
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    username = stats["username"]

    # Progress bars
    easy_bar = create_progress_bar(stats["easy_solved"], stats["total_easy"])
    medium_bar = create_progress_bar(stats["medium_solved"], stats["total_medium"])
    hard_bar = create_progress_bar(stats["hard_solved"], stats["total_hard"])

    # Badges
    acceptance_encoded = f'{stats["acceptance_rate"]}%25'
    badges = (
        f'  <a href="https://leetcode.com/{username}/">\n'
        f'    <img src="https://img.shields.io/badge/LeetCode-{username}-FFA116'
        f'?style=for-the-badge&logo=leetcode&logoColor=white" '
        f'alt="LeetCode Profile"/>\n'
        f"  </a>\n"
        f'  <img src="https://img.shields.io/badge/Solved-'
        f'{stats["total_solved"]}_Problems-00b8a3'
        f'?style=for-the-badge" alt="Problems Solved"/>\n'
        f'  <img src="https://img.shields.io/badge/Acceptance-'
        f"{acceptance_encoded}-2d9bf0"
        f'?style=for-the-badge" alt="Acceptance Rate"/>'
    )

    # Recent AC table rows
    recent_rows = ""
    for i, sub in enumerate(stats["recent_submissions"], 1):
        link = f'[{sub["title"]}](https://leetcode.com/problems/{sub["slug"]}/)'
        date = _format_timestamp(sub["timestamp"])
        recent_rows += f"| {i} | {link} | {sub['lang']} | {date} |\n"

    recent_section = ""
    if recent_rows:
        recent_section = (
            "## Recent Accepted Submissions\n\n"
            "| # | Problem | Language | Date |\n"
            "|---|---------|----------|------|\n"
            f"{recent_rows}\n"
        )

    # Streak section
    streak_section = (
        "## Activity & Streaks\n\n"
        "| Metric | Value |\n"
        "|--------|-------|\n"
        f'| **Current Streak** | **{stats["streak"]}** days |\n'
        f'| **Total Active Days** | **{stats["total_active_days"]}** |\n\n'
    )

    # Contest section
    contest_section = (
        "## Contest Statistics\n\n"
        "| Metric | Value |\n"
        "|--------|-------|\n"
        f'| **Contest Rating** | {stats["contest_rating"]} |\n'
        f'| **Contests Attended** | {stats["contests_attended"]} |\n'
        f'| **Top Percentage** | {stats["top_percentage"]} |\n\n'
    )

    # Badges section
    badges_section = ""
    if stats["badges"]:
        badge_images = ""
        for b in stats["badges"]:
            badge_images += (
                f'  <img src="{b["icon"]}" '
                f'alt="{b["name"]}" width="80" '
                f'title="{b["name"]} ({b["date"]})"/>\n'
            )
        badges_section = (
            "## Badges\n\n"
            "<p align=\"center\">\n"
            f"{badge_images}"
            "</p>\n\n"
        )

    # LeetCard badge
    leetcard = (
        f'<p align="center">\n'
        f"  <img "
        f'src="https://leetcard.jacoblin.cool/{username}'
        f'?theme=dark&font=Baloo%202&ext=contest" '
        f'alt="LeetCode Card"/>\n'
        f"</p>\n"
    )

    content = (
        "![header](https://capsule-render.vercel.app/api"
        "?type=waving&color=gradient&customColorList=6,11,20"
        "&height=180&section=header"
        "&text=LeetCode%20Stats"
        "&fontSize=42&fontColor=fff"
        "&animation=twinkling&fontAlignY=32)\n"
        "\n"
        "<p align=\"center\">\n"
        f"{badges}\n"
        "</p>\n"
        "\n"
        "---\n"
        "\n"
        "## Profile Statistics\n"
        "\n"
        "| Metric | Value |\n"
        "|--------|-------|\n"
        f"| **Username** | [{username}](https://leetcode.com/{username}/) |\n"
        f"| **Ranking** | #{stats['ranking']:,} |\n"
        f"| **Total Solved** | **{stats['total_solved']}** / {stats['total_questions']:,} |\n"
        f"| **Acceptance Rate** | **{stats['acceptance_rate']}%** |\n"
        "\n"
        "## Problem Solving Progress\n"
        "\n"
        "| Difficulty | Solved | Progress |\n"
        "|------------|--------|----------|\n"
        f"| 🟢 Easy | {stats['easy_solved']} | {easy_bar} |\n"
        f"| 🟡 Medium | {stats['medium_solved']} | {medium_bar} |\n"
        f"| 🔴 Hard | {stats['hard_solved']} | {hard_bar} |\n"
        "\n"
        f"{streak_section}"
        f"{contest_section}"
        f"{recent_section}"
        f"{badges_section}"
        "---\n"
        "\n"
        f"{leetcard}"
        "\n"
        "<p align=\"center\">\n"
        "  <i>Auto-updated daily via GitHub Actions</i><br>\n"
        f"  <sub>Last updated: {now}</sub>\n"
        "</p>\n"
        "\n"
        "![footer](https://capsule-render.vercel.app/api"
        "?type=waving&color=gradient&customColorList=6,11,20"
        "&height=100&section=footer)\n"
        "\n"
        "<!-- LEETCODE_STATS_START -->\n"
        "<!-- Auto-generated content - Do not edit manually -->\n"
        "<!-- LEETCODE_STATS_END -->\n"
    )
    return content


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------
def update_readme(content: str, filepath: str = "README.md") -> None:
    """Write updated content to README.md, guarding against empty data."""
    if not content.strip():
        log.error("Refusing to write empty content to %s", filepath)
        return

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    log.info("%s updated successfully!", filepath)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> int:
    """Main entry point for the LeetCode stats tracker."""
    username = os.environ.get("LEETCODE_USERNAME") or DEFAULT_USERNAME

    log.info("Fetching LeetCode stats for: %s", username)

    try:
        raw_data = fetch_leetcode_stats(username)
        stats = parse_stats(raw_data)

        log.info("   Total Solved: %d", stats["total_solved"])
        log.info(
            "   Easy: %d | Medium: %d | Hard: %d",
            stats["easy_solved"],
            stats["medium_solved"],
            stats["hard_solved"],
        )
        log.info("   Acceptance Rate: %.1f%%", stats["acceptance_rate"])
        log.info("   Current Streak: %d days", stats["streak"])

        readme_content = generate_readme_content(stats)
        update_readme(readme_content)
        return 0

    except Exception:
        log.exception("Fatal error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
