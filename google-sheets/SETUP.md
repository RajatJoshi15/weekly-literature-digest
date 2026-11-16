# Set up with Google Sheets (easiest)

No coding and no passwords. It runs on Google's servers and emails you from your own Gmail. Takes about 5 minutes.

## 1. Create the sheet

1. Open [sheets.new](https://sheets.new) to create a blank Google Sheet. Give it a name, for example "Weekly literature digest".
2. In the menu, choose **Extensions → Apps Script**.
3. Delete everything in the editor, then paste the whole of [`Code.gs`](Code.gs) (open it, click **Copy raw file**, then paste).
4. Click **Save** (the disk icon), then close the Apps Script tab.
5. Reload the Google Sheet. A new menu called **Weekly digest** appears after a few seconds.

## 2. Set it up

1. Choose **Weekly digest → Set up this sheet**.
2. Google asks you to authorise the script the first time. Choose your account, then **Advanced → Go to (your project) → Allow**. Google shows this warning for every personal script; the script only uses your sheet, sends email to you, and reads public research databases.
3. The sheet gets five tabs:
   - **Settings**: the on/off switches, day and time, sources.
   - **Topics**: one row per topic, with keywords separated by commas. Example topics are filled in; replace them with yours.
   - **Combinations**: papers that must match several topics at once (optional).
   - **Researchers**: people to follow, as "Lastname Initials" (for example `Smith JA`), with optional ORCID, affiliation and Bluesky handle.
   - **Digest**: where new papers appear, newest at the top.

## 3. Choose how you get updates

In the **Settings** tab:

- **Email notifications = ON**: you get the digest by email every week on the day and hour you set. After changing the day, hour or this switch, choose **Weekly digest → Apply settings**.
- **Email notifications = OFF**: nothing is sent. Choose **Weekly digest → Refresh now** whenever you want new papers in the Digest tab.

The time zone is the spreadsheet's own (**File → Settings → Time zone**).

## 4. Optional extras

- **AI summaries**: choose **Weekly digest → Add AI key**, paste an [Anthropic API key](https://console.anthropic.com/), then set **AI summaries = ON**. Each paper then gets a five-point summary (aim, methods, results, discussion, caveats). You pay Anthropic for what you use; **Max AI summaries** caps it.
- **Bluesky keyword search**: create an app password in Bluesky (**Settings → Privacy and security → App passwords**), add it with **Weekly digest → Add Bluesky login**, then set **Bluesky keyword search = ON**. Following researchers' Bluesky accounts needs no login.

Keys and passwords are stored privately in your Google account, not in the sheet, so sharing the sheet does not share them.

## Limits

- Google stops a script after 6 minutes. If a run reports that it stopped early, add **bioRxiv categories** or **medRxiv categories** in Settings to narrow the preprint search.
- Free Gmail accounts can send 100 emails a day from scripts, which is far more than this needs.
