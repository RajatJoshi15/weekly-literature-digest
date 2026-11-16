# Brain Stimulation Literature Digest

A weekly literature digest on three research topics, searched separately and in combination:

- **Brain stimulation:** TMS, rTMS/iTBS, TMS-EEG, transcranial ultrasound stimulation (TUS), deep brain stimulation (DBS), tDCS and tACS
- **Executive functions:** including cognitive control, cognitive flexibility, set shifting, task switching, inhibitory control, response inhibition and working memory
- **Basal ganglia:** including striatum, caudate, putamen, globus pallidus, subthalamic nucleus, substantia nigra and nucleus accumbens

Papers that combine brain stimulation with executive functions or the basal ganglia are **core matches**, and every one is summarised. For each topic on its own, the six most relevant papers of the week are summarised, and the page links to the full weekly list on PubMed. Each summary has five points: aim, primary methods, results, discussion and caveats.

**Read it here:** https://rajatjoshi15.github.io/brain-stim-lit-digest/ (public copy, served by GitHub Pages from `docs/`).

The digest is built and run with Claude: two scheduled tasks and a page hosted on claude.ai. The weekly refresh updates the claude.ai page and then pushes the same data files to `docs/data/` in this repo, so the public copy stays current. The scheduled tasks run from a Claude account, so editing files here does not change them.

## How it works

| When (IST) | What | Where it runs |
| --- | --- | --- |
| Mondays 9:40 AM | **Refresh**: searches PubMed, bioRxiv (neuroscience) and medRxiv (neurology, psychiatry, rehabilitation) for the days since the last check, writes summaries, publishes a new weekly data file to the claude.ai page, and pushes it to this repo | Claude scheduled task, in the cloud ([prompts/refresh.md](prompts/refresh.md)) |
| Mondays 11:00 AM | **Reminder**: checks that this week's update was published and sends a push notification and an email with the page link | Claude scheduled task, in the cloud ([prompts/reminder.md](prompts/reminder.md)) |
| Any time | **Page**: filter by topic, technique, latest update, unread or preprints; mark papers as read; copy DOIs for Zotero | claude.ai page (private; read marks sync across devices) and the GitHub Pages copy (public; read marks saved per browser) |

The refresh only adds or replaces the JSON files in `docs/data/`. It never touches `index.html`, so the page's features survive every update. Weekly files older than 12 weeks are removed.

## Repository layout

```
docs/
  index.html                 The digest page: layout, filters, Zotero button, synced read marks
  data/manifest.json         Search queries, last-checked date per source, list of weeks, DOIs already added
  data/week-YYYY-MM-DD.json  One file per weekly update: date range, PubMed counts per topic, articles with summaries
prompts/
  refresh.md                 Exact instructions of the weekly refresh task
  reminder.md                Exact instructions of the Monday reminder task
exports/
  BSLD_articles_*.csv        Spreadsheet export of the articles (opens in Excel or Google Sheets)
```

### Week file format

```json
{
  "added": "2026-11-16",
  "range": { "from": "2026-11-09", "to": "2026-11-15" },
  "counts": { "stim": 98, "ef": 152, "bg": 149 },
  "items": [
    {
      "id": "PMID, or the DOI for preprints",
      "date": "YYYY-MM-DD",
      "source": "PubMed | bioRxiv | medRxiv",
      "journal": "ISO abbreviation",
      "title": "...",
      "doi": "...",
      "tags": ["TMS", "TUS", "DBS", "TDCS", "EF", "BG"],
      "type": "Study design",
      "points": [["Aim", "..."], ["Primary methods", "..."], ["Results", "..."], ["Discussion", "..."], ["Caveats", "..."]]
    }
  ]
}
```

A paper with a stimulation tag (`TMS`, `TUS`, `DBS`, `TDCS`) plus `EF` or `BG` is shown as a core match.

## Viewing the page locally

`index.html` loads its data with relative `fetch` calls, so serve the `docs` folder rather than opening the file directly:

```
cd docs
python3 -m http.server 8000
```

Then open http://localhost:8000. Read and Zotero marks are saved in your browser when the page runs outside Claude.

## Adding papers to Zotero

Each article has an **Add to Zotero** button that copies its DOI. In Zotero, use **Add Item by Identifier** (the magic-wand button) and paste. Several DOIs can be pasted at once.

## Notes

- The PubMed connector accepts at most 20 boolean operators per query, so the three topics are searched separately and core matches are found by intersecting the results.
- bioRxiv and medRxiv have no keyword search through the connector, so the refresh pages through every preprint posted in the window and filters by title and abstract.
- Google Scholar is not included.
- The first weekly file (2026-11-16) was picked by publication date from 16 Oct to 16 Nov 2026, before the topic split.

## Attribution

Article metadata comes from [PubMed](https://pubmed.ncbi.nlm.nih.gov/) (NCBI), [bioRxiv](https://www.biorxiv.org/) and [medRxiv](https://www.medrxiv.org/). Every entry links to its DOI. Summaries are written by Claude from each abstract, in its own words. Check the original paper before citing.
