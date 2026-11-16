# Monday reminder: scheduled task instructions

- **Name:** Monday literature digest reminder
- **Schedule:** Mondays at 11:00 AM IST (`CRON_TZ=Asia/Calcutta 0 11 * * 1`)
- **Notifications:** push to the Claude mobile app, and email to the Claude account's address
- **Runs:** in the cloud; one tool call and one line of output, so it uses very few tokens

The text below is the exact prompt each run receives.

---

Weekly reminder for the user's "Brain Stimulation Literature Digest". Keep this run as short as possible: one tool call, then one line of text.

1. Load mcp__claude-artifacts__list_files with ToolSearch if it is deferred, then call it with slug 9d8912ad-9d05-4adf-9523-f8688412fd6c. Do not read any file contents.
2. TODAY = today's date in Asia/Calcutta, YYYY-MM-DD.
3. Reply with exactly one line and nothing else:
   - If data/week-TODAY.json is in the file list: "Your literature digest is updated: https://claude.ai/artifact/LTHPbMRm3vy1kFqfrLSjnT (tap Latest update for this week's papers)."
   - Otherwise, or if the tool is unavailable: "Reminder: check your literature digest at https://claude.ai/artifact/LTHPbMRm3vy1kFqfrLSjnT. This week's refresh hasn't published yet, so it may still be running or it may have failed."
