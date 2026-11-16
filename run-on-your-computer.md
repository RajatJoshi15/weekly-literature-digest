# Run on your own computer

Everything stays on your machine. The digest only goes out when your computer is on at the scheduled time.

## 1. Get the files

You need **Python 3.11 or newer** (check with `python3 --version`). Nothing else to install.

Download this repository (**Code → Download ZIP**) and unzip it, or:

```
git clone https://github.com/RajatJoshi15/weekly-literature-digest.git
cd weekly-literature-digest
```

## 2. Edit your settings

Open `settings.toml` in any text editor. Set your topics, researchers, sources, and the switches:

- `[email] notifications = true` sends the digest by email at the `day`, `time` and `timezone` you set. `false` means you run it yourself.
- `[ai] summaries = true` adds a five-point summary per paper (needs an API key, see below).

## 3. Add your email details (only if notifications are on)

Create a file called `.env` next to `digest.py`:

```
EMAIL_ADDRESS=you@gmail.com
EMAIL_APP_PASSWORD=abcd efgh ijkl mnop
# EMAIL_TO=you@university.edu        optional; default is EMAIL_ADDRESS
# ANTHROPIC_API_KEY=sk-ant-...       optional; only for AI summaries
# BLUESKY_HANDLE=you.bsky.social     optional; only for Bluesky keyword search
# BLUESKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

For Gmail, `EMAIL_APP_PASSWORD` is an [app password](https://myaccount.google.com/apppasswords) (it needs 2-Step Verification on). It is not your normal password, and you can revoke it at any time. For other providers, also set `SMTP_HOST` and `SMTP_PORT`.

## 4. Try it

```
python3 digest.py --dry-run
```

This writes `preview.html` (open it in your browser) and sends nothing. Run `python3 digest.py` to get a real digest now.

## 5. Make it weekly

The script checks the day and time itself, so schedule it to run every hour with `--scheduled`; it only sends when the time has come.

**Mac or Linux**: run `crontab -e` and add (with your own path):

```
7 * * * * cd /path/to/weekly-literature-digest && /usr/bin/env python3 digest.py --scheduled >> digest.log 2>&1
```

**Windows**: open Task Scheduler → **Create Basic Task** → trigger **Daily**, then in the task's properties set it to repeat **every 1 hour**. Action: **Start a program** `python`, arguments `digest.py --scheduled`, start in the folder you unzipped.

If your computer is off at the scheduled time, the digest goes out at the next hourly check within 24 hours.
