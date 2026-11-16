# Set up with Claude

If you use [Claude](https://claude.ai) with scheduled tasks and the PubMed and bioRxiv connectors, Claude can run the digest for you, including AI summaries, and put it on a page you can open on your phone and computer. It uses your Claude plan's usage instead of a separate API key.

Copy the text below into a new Claude chat, fill in the parts in brackets, and send it.

```
Set up a weekly literature digest for me as a scheduled task.

Topics (search each separately, and also papers that combine them):
- [Topic 1]: [keyword, keyword, keyword]
- [Topic 2]: [keyword, keyword, keyword]

Researchers to follow (PubMed style "Lastname Initials", optional ORCID):
- [Lastname AB]

Sources: PubMed, bioRxiv [categories], medRxiv [categories].

Every [Monday] at [11:00] [time zone], search the past 7 days, write a five-point summary
(aim, methods, results, discussion, caveats) for each paper that matches, and update a page I
can open on my phone and computer. Notify me when it is ready.
Keep token use low, and tell me roughly what each weekly run costs before you set it up.
```

The same approach powers the digest this project grew out of. The free versions in this repository (Google Sheets, GitHub, your own computer) do the same searching without Claude; only the AI summaries need a key.
