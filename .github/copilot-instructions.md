# LeetCode Tracker Project

This project automatically fetches LeetCode statistics and updates a GitHub README daily.

## Project Structure
- `update_readme.py` - Main Python script that fetches LeetCode stats and updates README
- `.github/workflows/update-stats.yml` - GitHub Actions workflow for daily automation
- `README.md` - Auto-updated README with LeetCode statistics
- `requirements.txt` - Python dependencies

## Configuration
Set the following GitHub repository secret:
- `LEETCODE_USERNAME` - Your LeetCode username

## Local Development
1. Install dependencies: `pip install -r requirements.txt`
2. Set environment variable: `$env:LEETCODE_USERNAME = "your_username"`
3. Run: `python update_readme.py`
