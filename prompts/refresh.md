# Weekly refresh: scheduled task instructions

- **Name:** Weekly brain stimulation literature refresh
- **Schedule:** Mondays at 9:40 AM IST (`CRON_TZ=Asia/Calcutta 40 9 * * 1`)
- **Model:** Claude Sonnet 5.5
- **Notifications:** off (the 11 AM reminder notifies instead)
- **Runs:** in the cloud; no computer needed

The text below is the exact prompt each run receives.

---

Weekly refresh of the "Brain Stimulation Literature Digest" artifact (slug 9d8912ad-9d05-4adf-9523-f8688412fd6c). The page code (index.html) must never be changed or re-sent. You only add or replace JSON data files: data/manifest.json and data/week-<date>.json. Keep token use low: request only what the steps below need. If a tool is deferred, load it with ToolSearch first.

DATES. TODAY = today's date in Asia/Calcutta. YESTERDAY = the day before. All search windows end at YESTERDAY, so each day is checked exactly once.

1. READ STATE
- Call mcp__claude-artifacts__list_files on the slug. Keep `version` (base_version for publishing) and the list of week files.
- Read data/manifest.json with mcp__claude-artifacts__read_file. It has: updated, coverage {pubmed, biorxiv, medrxiv} (last date fully checked, YYYY-MM-DD), queries {stim, ef, bg} (PubMed queries), weeks (newest first), seen {lower-case DOI: week}.
- If data/week-TODAY.json already exists, read it too; you will add to it instead of replacing it.
- If the claude-artifacts tools are unavailable, stop and report that.

2. PUBMED (window: day after coverage.pubmed through YESTERDAY; skip if empty)
- For each of queries.stim, queries.ef and queries.bg: mcp__PubMed__search_articles with datetype "edat", date_from/date_to as YYYY/MM/DD, max_results 100, paging with retstart while has_more. Do not add terms; each query is near the connector's 20-operator limit. Record total_count per topic and collect all PMIDs.
- CORE = PMIDs in the stim set that are also in the ef set or the bg set.
- Fetch metadata (get_article_metadata, up to 20 PMIDs per call) for CORE PMIDs whose DOI is not in seen. If CORE has more than 40, take the 40 newest and say so in the report. Keep only papers that actually study a brain-stimulation method (TMS, TMS-EEG, TUS/transcranial or low-intensity focused ultrasound, DBS, tDCS, tACS) together with executive functions or the basal ganglia. Drop false hits, for example TMS or TUS used as an unrelated abbreviation.
- TOPIC PICKS: for each topic, run the same query again with sort "relevance" and max_results 15. Take PMIDs not in CORE and not already in seen, fetch metadata for the first 10, and keep the 6 most relevant to research on brain stimulation, executive functions and basal-ganglia circuits. Prefer human and translational original studies, trials and systematic reviews, and skip papers where the topic is only incidental.
- If PubMed fails after one retry, skip it and leave coverage.pubmed unchanged.

3. PREPRINTS (bioRxiv window: day after coverage.biorxiv through YESTERDAY; medRxiv window: day after coverage.medrxiv through YESTERDAY)
- bioRxiv: mcp__bioRxiv__search_preprints with server "biorxiv", category "neuroscience", date_from, date_to (YYYY-MM-DD), cursor 0. Each call returns about 30 results in date order. Call again with cursor advanced by the number returned until a call returns none. Cap: 30 calls.
- medRxiv: the same with server "medrxiv" and no category. Cap: 40 calls. Consider only results whose category is "neurology", "psychiatry and clinical psychology" or "rehabilitation medicine and physical therapy".
- Skip results with version above 1, and DOIs already in seen.
- From title and abstract preview, mark candidates: CORE if they mention a stimulation method AND executive functions (including cognitive control, cognitive flexibility, set shifting, task switching, inhibitory control, response inhibition, working memory) or the basal ganglia (including striatum, caudate, putamen, globus pallidus, subthalamic nucleus, substantia nigra, nucleus accumbens). TOPIC if they clearly centre on just one of the three topics.
- Read candidates with get_preprint before adding them. Add all CORE preprints, up to 10 per server, and at most 2 TOPIC preprints per topic per server.
- Coverage for each server: YESTERDAY if paging finished. If you hit the cap, use the day before the date of the last result you saw. If the server failed, leave its coverage unchanged.

4. WRITE ENTRIES. One JSON object per kept paper:
{"id": "<PMID, or the DOI for preprints>", "date": "<publication or posting date YYYY-MM-DD>", "source": "PubMed" | "bioRxiv" | "medRxiv", "journal": "<ISO abbreviation, or bioRxiv/medRxiv>", "title": "<title>", "doi": "<doi>", "tags": [...], "type": "<study design; for preprints end with (preprint, not peer reviewed)>", "points": [["Aim","..."],["Primary methods","..."],["Results","..."],["Discussion","..."],["Caveats","..."]]}
- Tags only from: "TMS" (rTMS, iTBS, TMS-EEG), "TUS" (transcranial or focused ultrasound stimulation), "DBS", "TDCS" (tDCS or tACS), "EF" (any executive-function construct above), "BG" (basal ganglia or its nuclei). The page treats a paper with a stimulation tag plus EF or BG as a core match, so tag accurately.
- Points: one or two plain sentences each, in your own words from the abstract. Never copy abstract sentences. Include sample size and design in Primary methods where given.

5. BUILD FILES in a fresh working folder (Write tool, then validate with python json.load):
- data/week-TODAY.json: {"added": "TODAY", "range": {"from": "<PubMed window start>", "to": "YESTERDAY"}, "counts": {"stim": n, "ef": n, "bg": n}, "items": [...]}. If the file already existed, keep its items, add the new ones, and keep its range/counts unless PubMed ran this time. Leave out "range" and "counts" if PubMed did not run and the file is new. Write this file every run, even when "items" is empty: a separate 11 AM reminder checks for it.
- data/manifest.json: the same object with updated = TODAY, coverage updated as above, TODAY at the front of weeks (no duplicates), weeks trimmed to the 12 newest, every new DOI (lower case) added to seen with TODAY, and seen entries removed for any week that was trimmed. Keep queries unchanged.
- Validate: both files parse; every item has all keys, 5 points and only allowed tags.

6. PUBLISH with mcp__claude-artifacts__publish_files: slug, base_version = version from step 1, mode "patch", files = [{"as": "data/manifest.json", "path": <absolute path>}, {"as": "data/week-TODAY.json", "path": <absolute path>}], remove = ["data/week-<date>.json" for each trimmed week]. Never include index.html. On a conflict, call list_files again and retry once with the new version.

7. REPORT in 6 lines or fewer: new core matches and topic picks per source, notable titles (up to 5), any source that failed or hit its cap, and the new coverage dates. Credit PubMed for article data.
