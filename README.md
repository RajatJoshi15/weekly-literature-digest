# Weekly Literature Digest

**A free weekly email of new research papers from PubMed, bioRxiv and medRxiv, for your keywords and the researchers you follow.** Set it up once; every week it searches for you and sends you what's new. Optional AI summaries.

Website: https://rajatjoshi15.github.io/weekly-literature-digest/

- **Your topics, your way:** list keywords per topic; get each topic separately, plus papers that combine topics.
- **Follow researchers:** add names (or ORCIDs) and see their new papers and preprints first.
- **Preprints included:** bioRxiv and medRxiv, filtered by your keywords and categories.
- **Bluesky:** new posts from researchers you follow, and optionally posts linking to papers on your topics.
- **On your schedule:** pick the day, time and time zone, or turn email off and refresh when you like.
- **Free:** no AI and no cost unless you switch on AI summaries with your own key.

## Choose your setup

| Option | In one line | Guide |
| --- | --- | --- |
| **Google Sheet** | Easiest: no coding or passwords; runs on Google and emails you from your own Gmail. | [Set up →](google-sheets/SETUP.md) |
| **GitHub** | Free and fully automatic; good if you're comfortable with GitHub, and keeps an archive of every digest. | [Set up ↓](#set-up-on-github) |
| **Your own computer** | Everything stays on your machine; sends only while your computer is on. | [Set up →](run-on-your-computer.md) |
| **Claude** | Claude searches, summarises and builds a page for you; needs a Claude plan with scheduled tasks. | [Set up →](claude/SETUP.md) |

All options search the same sources and use the same switches.

## The switches

| Setting | ON | OFF |
| --- | --- | --- |
| **Email notifications** | You get the digest by email every week at your day, time and time zone. | Nothing is sent; refresh whenever you want new papers. |
| **AI summaries** | Each paper gets a five-point summary: aim, methods, results, discussion, caveats. Needs your own [Anthropic API key](https://console.anthropic.com/); you pay for what you use, capped per digest. | You get everything below, free. |
| **Bluesky keyword search** | Posts on your topics that link to papers. Free, but needs a Bluesky app password. | Only posts by researchers you follow (no login needed). |

**Always included, free:** title, authors, journal, publication date, study type (for example randomised controlled trial, review), which of your keywords matched, DOI link, PubMed link, free full-text link when one exists, an excerpt of the abstract (the results and conclusions when the abstract is structured), and a link to the full weekly list on PubMed.

## What a digest looks like

> **Brain stimulation x Executive functions**
> 12 new on PubMed · see the full list
>
> **Theta-burst stimulation improves inhibitory control in Parkinson's disease**
> Smith A, Jones B, Lee C et al. · Brain Stimul · 10 Nov 2026 · Randomized Controlled Trial
> Matched: theta burst, inhibitory control
> **Results:** Response inhibition improved after active but not sham stimulation …
> DOI · PubMed · Free full text

(Example entry for illustration.)

## Set up on GitHub

1. Click **Use this template → Create a new repository** at the top of this page. A private repository is fine.
2. In your new repository, open [`settings.toml`](settings.toml), click the pencil icon, and edit:
   - your **topics** and keywords, any **combinations**, and **researchers** to follow;
   - `[email]`: `notifications`, `day`, `time` and `timezone`;
   - `[ai] summaries` and the sources you want.
   Then click **Commit changes**.
3. Add your email details as secrets: **Settings → Secrets and variables → Actions → New repository secret**:
   - `EMAIL_ADDRESS`: the Gmail address that sends the digest.
   - `EMAIL_APP_PASSWORD`: a Gmail [app password](https://myaccount.google.com/apppasswords) (needs 2-Step Verification). Not your normal password, and you can revoke it at any time.
   - Optional: `EMAIL_TO` (send somewhere else), `ANTHROPIC_API_KEY` (AI summaries), `BLUESKY_HANDLE` and `BLUESKY_APP_PASSWORD` (Bluesky keyword search), `NCBI_API_KEY` (faster PubMed), and `SMTP_HOST`/`SMTP_PORT` for non-Gmail accounts.

   Secrets are encrypted: nobody can read them, even in a public repository.
4. Open the **Actions** tab, enable workflows if GitHub asks, choose **Weekly literature digest → Run workflow**, and tick **Preview only** for a first test. The digest appears on the run's summary page.

That's it. The workflow checks once an hour and sends the digest at your chosen time (GitHub can run it a few minutes late). With email notifications off, use **Run workflow** whenever you want a digest; each one is saved in the `digests` folder.

**Cost:** free. The hourly check takes a few seconds and fits within GitHub's free Actions allowance, including for private repositories.

## FAQ

**How do I get weekly PubMed alerts by email?**
Pick a setup above, list your keywords, and turn **Email notifications** on. You get one email a week with the new PubMed papers for each topic, plus bioRxiv and medRxiv preprints.

**Can I follow specific researchers or authors?**
Yes. Add them as "Lastname Initials" (for example `Smith JA`). Adding an ORCID is the most reliable way to avoid people with the same name; an affiliation also helps.

**Does it include preprints?**
Yes: bioRxiv and medRxiv, matched against your keywords in titles and abstracts. You can limit each server to the categories you care about. Preprints are not peer reviewed, and are labelled as such.

**How are papers chosen?**
For each topic, the most relevant new PubMed papers of the week (PubMed's own relevance ranking), up to the number you set, plus matching preprints. Combinations and researchers come first. A paper appears only once, and never again in later weeks.

**Can I add papers to Zotero?**
Copy a paper's DOI from the digest, then in Zotero use **Add Item by Identifier** (the magic-wand button) and paste. Zotero fills in the full record. You can paste several DOIs at once.

**Why not Google Scholar or X (Twitter)?**
Google Scholar has no API that tools like this can use. X now charges for every post read through its API, so it can't be part of a free tool. Bluesky's API is open and free, so it is included.

**What do AI summaries cost?**
Only what your API provider charges for the summaries you generate. A weekly digest is a few dozen short abstracts, and `max_papers` caps how many are summarised.

**Is my data private?**
Your settings live in your own copy (sheet, repository or computer). Email passwords and API keys are stored as secrets, never in files. Abstracts appear only in your private email; the archive saved in a repository has titles, links and summaries only.

## Data sources

Paper data comes from [PubMed](https://pubmed.ncbi.nlm.nih.gov/) via the NCBI E-utilities, and from the [bioRxiv and medRxiv API](https://api.biorxiv.org/). Posts come from the public [Bluesky API](https://docs.bsky.app/). Please follow their terms of use; each digest links to every original record.

## Feedback

Ideas, bugs and questions are welcome in [Issues](https://github.com/RajatJoshi15/weekly-literature-digest/issues). If the digest is useful to you, a star helps other researchers find it.
