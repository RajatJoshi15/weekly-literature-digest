/**
 * Weekly literature digest for Google Sheets.
 * https://github.com/RajatJoshi15/weekly-literature-digest
 *
 * New PubMed, bioRxiv and medRxiv papers for your keywords and the researchers you
 * follow, plus Bluesky posts, written into this sheet and (optionally) emailed to you
 * every week from your own Gmail. No passwords needed.
 *
 * Setup: Extensions > Apps Script, paste this file, save, reload the sheet, then use
 * the "Weekly digest" menu > "Set up this sheet".
 */

const EUTILS = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils';
const PREPRINT_API = 'https://api.biorxiv.org/details';
const BSKY_PUBLIC = 'https://public.api.bsky.app/xrpc';
const BSKY_AUTH = 'https://bsky.social/xrpc';
const ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages';
const DAYS = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY'];
const GENERIC_TYPES = ['journal article', "research support, non-u.s. gov't", 'research support, n.i.h., extramural',
  "research support, u.s. gov't, non-p.h.s.", 'research support, n.i.h., intramural',
  "research support, u.s. gov't, p.h.s.", 'english abstract', 'comment', 'news'];
const SUMMARY_LABELS = ['Aim', 'Methods', 'Results', 'Discussion', 'Caveats'];
const TIME_BUDGET_MS = 5 * 60 * 1000; // Apps Script stops runs at 6 minutes
const PAPER_LINK = /doi\.org|biorxiv\.org|medrxiv\.org|pubmed|ncbi\.nlm\.nih\.gov|arxiv\.org|nature\.com|science\.org|cell\.com|sciencedirect|springer|wiley|plos|frontiersin|elifesciences|jneurosci|oup\.com|tandfonline|sagepub|mdpi/i;

const SETTINGS_ROWS = [
  ['Email notifications', 'ON', 'ON: emailed every week at the day and hour below. OFF: use Weekly digest > Refresh now.'],
  ['Day', 'Monday', 'Day of the week for the email.'],
  ['Hour (0-23)', 11, 'Hour of the day, in this spreadsheet\'s time zone (File > Settings).'],
  ['Send to', '', 'Leave empty to send to your own Gmail. Separate several addresses with commas.'],
  ['Lookback days', 7, 'How many days back each digest looks.'],
  ['Max papers per topic', 10, 'Most relevant PubMed papers listed per topic.'],
  ['Max papers per combination', 25, ''],
  ['Max papers per researcher', 10, ''],
  ['Include abstracts', 'ON', 'Free. Shows the results and conclusions of each abstract.'],
  ['AI summaries', 'OFF', 'ON: five-point summary per paper. Needs an API key (Weekly digest > Add AI key). You pay for use.'],
  ['AI model', 'claude-haiku-5-5', ''],
  ['Max AI summaries', 40, 'Cap per digest, to cap cost.'],
  ['PubMed', 'ON', ''],
  ['bioRxiv', 'ON', ''],
  ['medRxiv', 'ON', ''],
  ['Bluesky', 'ON', 'Free: posts by researchers who have a Bluesky handle in the Researchers tab.'],
  ['bioRxiv categories', 'neuroscience', 'Comma-separated. Empty means all.'],
  ['medRxiv categories', 'neurology, psychiatry and clinical psychology, rehabilitation medicine and physical therapy', 'Comma-separated. Empty means all.'],
  ['Bluesky keyword search', 'OFF', 'Free, but needs a Bluesky app password (Weekly digest > Add Bluesky login).'],
  ['Bluesky posts per topic', 5, ''],
];

const EXAMPLE_TOPICS = [
  ['Brain stimulation', 'transcranial magnetic stimulation, TMS, rTMS, theta burst, TMS-EEG, transcranial ultrasound, transcranial focused ultrasound, low-intensity focused ultrasound, ultrasound neuromodulation, TUS, deep brain stimulation, transcranial direct current stimulation, tDCS, transcranial alternating current stimulation, tACS', ''],
  ['Executive functions', 'executive function, executive functions, executive functioning, executive control, executive dysfunction, cognitive control, cognitive flexibility, set shifting, task switching, inhibitory control, response inhibition, cognitive inhibition, working memory', ''],
  ['Basal ganglia', 'basal ganglia, striatum, striatal, caudate, putamen, globus pallidus, subthalamic nucleus, substantia nigra, nucleus accumbens', ''],
];
const EXAMPLE_COMBINATIONS = [
  ['Brain stimulation x Executive functions', 'Brain stimulation, Executive functions'],
  ['Brain stimulation x Basal ganglia', 'Brain stimulation, Basal ganglia'],
];
const DIGEST_HEADER = ['Added', 'Section', 'Title', 'Authors', 'Journal', 'Published', 'Type', 'Matched',
  'Summary or abstract excerpt', 'Link', 'PubMed', 'Free full text'];

// ------------------------------------------------------------------ menu and setup

function onOpen() {
  SpreadsheetApp.getUi().createMenu('Weekly digest')
    .addItem('Set up this sheet', 'setupSheet')
    .addItem('Refresh now', 'refreshNow')
    .addItem('Send the email now', 'sendNow')
    .addSeparator()
    .addItem('Apply settings (turn weekly email on or off)', 'applySchedule')
    .addItem('Add AI key (optional)', 'addAiKey')
    .addItem('Add Bluesky login (optional)', 'addBlueskyLogin')
    .addToUi();
}

function setupSheet() {
  const ss = SpreadsheetApp.getActive();
  const make = (name, header, rows) => {
    let sh = ss.getSheetByName(name);
    if (!sh) {
      sh = ss.insertSheet(name);
      sh.getRange(1, 1, 1, header.length).setValues([header]).setFontWeight('bold');
      if (rows && rows.length) sh.getRange(2, 1, rows.length, rows[0].length).setValues(rows);
      sh.setFrozenRows(1);
    }
    return sh;
  };
  const settings = make('Settings', ['Setting', 'Value', 'Notes'], SETTINGS_ROWS);
  settings.setColumnWidth(1, 220).setColumnWidth(2, 260).setColumnWidth(3, 520);
  const onOff = SpreadsheetApp.newDataValidation().requireValueInList(['ON', 'OFF'], true).build();
  const days = SpreadsheetApp.newDataValidation().requireValueInList(
    ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'], true).build();
  SETTINGS_ROWS.forEach((row, i) => {
    if (row[1] === 'ON' || row[1] === 'OFF') settings.getRange(i + 2, 2).setDataValidation(onOff);
    if (row[0] === 'Day') settings.getRange(i + 2, 2).setDataValidation(days);
  });
  make('Topics', ['Topic', 'Keywords (comma-separated)', 'Exclude (optional)'], EXAMPLE_TOPICS).setColumnWidth(2, 700);
  make('Combinations', ['Name', 'Topics that must all match (comma-separated)'], EXAMPLE_COMBINATIONS).setColumnWidth(1, 300).setColumnWidth(2, 400);
  make('Researchers', ['Name (Lastname Initials)', 'ORCID (optional)', 'Affiliation (optional)', 'Bluesky handle (optional)'], [])
    .setColumnWidths(1, 4, 220);
  const digest = make('Digest', DIGEST_HEADER, []);
  digest.setColumnWidth(3, 420).setColumnWidth(9, 520);
  const sent = make('_sent', ['Key', 'Date'], []);
  sent.hideSheet();
  const first = ss.getSheetByName('Sheet1');
  if (first && first.getLastRow() === 0 && ss.getSheets().length > 1) ss.deleteSheet(first);
  ss.setActiveSheet(settings);
  applySchedule(true);
  SpreadsheetApp.getUi().alert('Set up done.\n\n1. Edit your keywords in the Topics tab (and people in Researchers).\n' +
    '2. Check the Settings tab.\n3. Use Weekly digest > Refresh now to see your first digest.\n\n' +
    'If Email notifications is ON, you will also get it by email every week.');
}

function applySchedule(silent) {
  const s = readSettings();
  ScriptApp.getProjectTriggers().filter(t => t.getHandlerFunction() === 'scheduledRun')
    .forEach(t => ScriptApp.deleteTrigger(t));
  let msg;
  if (s.emailOn) {
    const day = String(s.day || 'Monday').toUpperCase();
    if (DAYS.indexOf(day) < 0) throw new Error('Day must be a day of the week, like Monday.');
    const hour = Math.max(0, Math.min(23, parseInt(s.hour, 10) || 9));
    ScriptApp.newTrigger('scheduledRun').timeBased().onWeekDay(ScriptApp.WeekDay[day]).atHour(hour)
      .everyWeeks(1).inTimezone(SpreadsheetApp.getActive().getSpreadsheetTimeZone()).create();
    msg = 'Weekly email is ON: every ' + s.day + ' between ' + hour + ':00 and ' + (hour + 1) + ':00 (' +
      SpreadsheetApp.getActive().getSpreadsheetTimeZone() + ').';
  } else {
    msg = 'Weekly email is OFF. Use Weekly digest > Refresh now whenever you want new papers.';
  }
  if (silent !== true) SpreadsheetApp.getUi().alert(msg);
  return msg;
}

function addAiKey() {
  const ui = SpreadsheetApp.getUi();
  const r = ui.prompt('AI summaries (optional)', 'Paste your Anthropic API key. It is stored privately in your ' +
    'account, not in the sheet. Leave empty and press OK to remove it.', ui.ButtonSet.OK_CANCEL);
  if (r.getSelectedButton() !== ui.Button.OK) return;
  const props = PropertiesService.getUserProperties();
  if (r.getResponseText().trim()) props.setProperty('ANTHROPIC_API_KEY', r.getResponseText().trim());
  else props.deleteProperty('ANTHROPIC_API_KEY');
  ui.alert('Saved. Set "AI summaries" to ON in the Settings tab to use it.');
}

function addBlueskyLogin() {
  const ui = SpreadsheetApp.getUi();
  const h = ui.prompt('Bluesky keyword search (optional)', 'Your Bluesky handle, e.g. name.bsky.social', ui.ButtonSet.OK_CANCEL);
  if (h.getSelectedButton() !== ui.Button.OK) return;
  const p = ui.prompt('Bluesky app password', 'Create one in Bluesky: Settings > Privacy and security > App passwords. ' +
    'Do not use your main password.', ui.ButtonSet.OK_CANCEL);
  if (p.getSelectedButton() !== ui.Button.OK) return;
  const props = PropertiesService.getUserProperties();
  props.setProperty('BLUESKY_HANDLE', h.getResponseText().trim());
  props.setProperty('BLUESKY_APP_PASSWORD', p.getResponseText().trim());
  ui.alert('Saved. Set "Bluesky keyword search" to ON in the Settings tab to use it.');
}

function refreshNow() { runDigest({ email: false, interactive: true }); }
function sendNow() { runDigest({ email: true, interactive: true }); }
function scheduledRun() { runDigest({ email: true, interactive: false }); }

// ------------------------------------------------------------------ settings

function readSettings() {
  const ss = SpreadsheetApp.getActive();
  const sh = ss.getSheetByName('Settings');
  if (!sh) throw new Error('Run Weekly digest > Set up this sheet first.');
  const map = {};
  sh.getRange(2, 1, Math.max(1, sh.getLastRow() - 1), 2).getValues().forEach(r => { map[String(r[0]).trim()] = r[1]; });
  const on = k => String(map[k] || '').trim().toUpperCase() === 'ON';
  const num = (k, d) => { const n = parseInt(map[k], 10); return isNaN(n) ? d : n; };
  const list = k => String(map[k] || '').split(',').map(x => x.trim()).filter(Boolean);
  const topics = rowsOf('Topics').filter(r => r[0] && r[1]).map(r => ({
    name: String(r[0]).trim(), keywords: splitList(r[1]), exclude: splitList(r[2]) }));
  const combinations = rowsOf('Combinations').filter(r => r[0] && r[1]).map(r => ({
    name: String(r[0]).trim(), topics: splitList(r[1]) }));
  const researchers = rowsOf('Researchers').filter(r => r[0] || r[1]).map(r => ({
    name: String(r[0] || '').trim(), orcid: String(r[1] || '').trim(), affiliation: String(r[2] || '').trim(),
    bluesky: String(r[3] || '').trim().replace(/^@/, '') }));
  return {
    emailOn: on('Email notifications'), day: String(map['Day'] || 'Monday').trim(), hour: map['Hour (0-23)'],
    sendTo: String(map['Send to'] || '').trim(), lookback: num('Lookback days', 7),
    maxTopic: num('Max papers per topic', 10), maxCombo: num('Max papers per combination', 25),
    maxResearcher: num('Max papers per researcher', 10), abstracts: on('Include abstracts'),
    ai: on('AI summaries'), aiModel: String(map['AI model'] || 'claude-haiku-5-5').trim(), aiMax: num('Max AI summaries', 40),
    pubmed: on('PubMed'), biorxiv: on('bioRxiv'), medrxiv: on('medRxiv'), bluesky: on('Bluesky'),
    biorxivCats: list('bioRxiv categories'), medrxivCats: list('medRxiv categories'),
    bskySearch: on('Bluesky keyword search'), bskyPerTopic: num('Bluesky posts per topic', 5),
    topics, combinations, researchers };
}

function rowsOf(name) {
  const sh = SpreadsheetApp.getActive().getSheetByName(name);
  if (!sh || sh.getLastRow() < 2) return [];
  return sh.getRange(2, 1, sh.getLastRow() - 1, sh.getLastColumn()).getValues();
}

function splitList(value) {
  return String(value || '').split(/[,\n]/).map(x => x.trim()).filter(Boolean);
}

// ------------------------------------------------------------------ matching

function stripAccents(s) { return String(s).normalize('NFKD').replace(/[̀-ͯ]/g, ''); }

function keywordPlain(kw) {
  if (/\b(AND|NOT)\b/.test(kw)) return [];
  return kw.split(/\s+OR\s+/).map(p => p.replace(/\[[^\]]*\]/g, '').replace(/["()]/g, '').trim()).filter(Boolean);
}

function keywordRegex(phrase) {
  // spaces and hyphens are interchangeable: "set shifting" also matches "set-shifting"
  const body = phrase.trim().split(/[\s\-]+/).filter(Boolean)
    .map(part => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('[\\s\\-]*');
  const acronym = phrase === phrase.toUpperCase() && /[A-Z]/.test(phrase) && phrase.length <= 8;
  return new RegExp('(^|[^A-Za-z0-9])' + body + '(?![A-Za-z0-9])', acronym ? '' : 'i');
}

function makeMatcher(topic) {
  const rules = [];
  topic.keywords.forEach(kw => keywordPlain(kw).forEach(p => rules.push([p, keywordRegex(p)])));
  const exclude = [];
  (topic.exclude || []).forEach(kw => keywordPlain(kw).forEach(p => exclude.push(keywordRegex(p))));
  return text => {
    if (exclude.some(rx => rx.test(text))) return [];
    const seen = {}, out = [];
    rules.forEach(([p, rx]) => { if (rx.test(text) && !seen[p.toLowerCase()]) { seen[p.toLowerCase()] = 1; out.push(p); } });
    return out;
  };
}

function nameKey(name) {
  name = stripAccents(name).trim();
  let last, first;
  if (name.indexOf(',') >= 0) { [last, first] = [name.split(',')[0], name.split(',').slice(1).join(',')]; }
  else { const bits = name.split(/\s+/); last = bits.length > 1 ? bits.slice(0, -1).join(' ') : name; first = bits.length > 1 ? bits[bits.length - 1] : ''; }
  return [last.trim().toLowerCase(), first.replace(/[^A-Za-z]/g, '').slice(0, 1).toLowerCase()];
}

function personInAuthors(person, authors) {
  if (!person.name) return false;
  const [wl, wi] = nameKey(person.name);
  return authors.some(a => { const [l, i] = nameKey(a); return l === wl && (!wi || !i || i === wi); });
}

// ------------------------------------------------------------------ HTTP

function getJson(url, options) {
  options = Object.assign({ muteHttpExceptions: true, headers: {} }, options || {});
  for (let attempt = 0; attempt < 3; attempt++) {
    const resp = UrlFetchApp.fetch(url, options);
    const code = resp.getResponseCode();
    if (code >= 200 && code < 300) return resp.getContentText();
    if ([429, 500, 502, 503, 504].indexOf(code) >= 0 && attempt < 2) { Utilities.sleep(3000 * (attempt + 1)); continue; }
    throw new Error('HTTP ' + code + ' from ' + url.split('?')[0]);
  }
}

// ------------------------------------------------------------------ PubMed

function pubmedTerm(kw) {
  kw = kw.trim();
  if (kw.indexOf('[') >= 0 || /\b(AND|OR|NOT)\b/.test(kw)) return '(' + kw + ')';
  return '"' + kw + '"[tiab]';
}

function topicQuery(t) {
  let q = '(' + t.keywords.map(pubmedTerm).join(' OR ') + ')';
  if (t.exclude && t.exclude.length) q += ' NOT (' + t.exclude.map(pubmedTerm).join(' OR ') + ')';
  return q;
}

function researcherQuery(p) {
  const parts = [];
  if (p.orcid) parts.push('"' + p.orcid + '"[auid]');
  if (p.name) {
    let q = '"' + p.name + '"[au]';
    if (p.affiliation) q = '(' + q + ' AND "' + p.affiliation + '"[ad])';
    parts.push(q);
  }
  return parts.length ? '(' + parts.join(' OR ') + ')' : null;
}

function dateFilter(start, end, tz) {
  return '("' + Utilities.formatDate(start, tz, 'yyyy/MM/dd') + '"[edat] : "' + Utilities.formatDate(end, tz, 'yyyy/MM/dd') + '"[edat])';
}

function esearch(query, start, end, tz, retmax) {
  const payload = { db: 'pubmed', term: query + ' AND ' + dateFilter(start, end, tz), retmode: 'json',
    retmax: String(retmax || 9999), sort: 'relevance', tool: 'weekly-literature-digest' };
  const r = JSON.parse(getJson(EUTILS + '/esearch.fcgi', { method: 'post', payload: payload }));
  Utilities.sleep(400);
  const res = r.esearchresult || {};
  if (res.ERROR) throw new Error('PubMed rejected the query: ' + res.ERROR);
  return { count: parseInt(res.count || '0', 10), ids: res.idlist || [] };
}

function childText(el, path) {
  let cur = el;
  for (const part of path.split('/')) { if (!cur) return ''; cur = cur.getChild(part); }
  return cur ? cur.getValue().replace(/\s+/g, ' ').trim() : '';
}

function efetch(pmids) {
  const out = {};
  for (let i = 0; i < pmids.length; i += 150) {
    const batch = pmids.slice(i, i + 150);
    let xml = getJson(EUTILS + '/efetch.fcgi', { method: 'post', payload: { db: 'pubmed', id: batch.join(','), retmode: 'xml', tool: 'weekly-literature-digest' } });
    Utilities.sleep(400);
    xml = xml.replace(/<!DOCTYPE[^>]*>/i, '');
    const root = XmlService.parse(xml).getRootElement();
    root.getChildren('PubmedArticle').forEach(art => {
      const p = parsePubmed(art);
      out[p.pmid] = p;
    });
  }
  return out;
}

function parsePubmed(art) {
  const cit = art.getChild('MedlineCitation');
  const a = cit.getChild('Article');
  const pmid = childText(cit, 'PMID');
  const authors = [];
  const al = a.getChild('AuthorList');
  if (al) al.getChildren('Author').forEach(au => {
    if (au.getChild('CollectiveName')) authors.push(childText(au, 'CollectiveName'));
    else if (au.getChild('LastName')) authors.push((childText(au, 'LastName') + ' ' + childText(au, 'Initials')).trim());
  });
  const abstract = [];
  const ab = a.getChild('Abstract');
  if (ab) ab.getChildren('AbstractText').forEach(t => {
    const label = t.getAttribute('Label') ? t.getAttribute('Label').getValue() : '';
    abstract.push([label ? label.charAt(0) + label.slice(1).toLowerCase() : '', t.getValue().replace(/\s+/g, ' ').trim()]);
  });
  const types = [];
  const ptl = a.getChild('PublicationTypeList');
  if (ptl) ptl.getChildren('PublicationType').forEach(t => types.push(t.getValue().trim()));
  const informative = types.filter(t => GENERIC_TYPES.indexOf(t.toLowerCase()) < 0);
  let doi = '', pmc = '';
  const pd = art.getChild('PubmedData');
  const idl = pd ? pd.getChild('ArticleIdList') : null;
  if (idl) idl.getChildren('ArticleId').forEach(id => {
    const type = id.getAttribute('IdType') ? id.getAttribute('IdType').getValue() : '';
    if (type === 'doi' && !doi) doi = id.getValue().trim();
    if (type === 'pmc') pmc = id.getValue().trim();
  });
  if (!doi) a.getChildren('ELocationID').forEach(e => {
    if (e.getAttribute('EIdType') && e.getAttribute('EIdType').getValue() === 'doi' && !doi) doi = e.getValue().trim();
  });
  return {
    key: 'pmid:' + pmid, source: 'PubMed', pmid: pmid, doi: doi, pmc: pmc,
    title: childText(a, 'ArticleTitle'), authors: authors,
    journal: childText(a, 'Journal/ISOAbbreviation') || childText(a, 'Journal/Title'),
    date: pubDate(a), type: informative.length ? informative.join(', ') : (types.length ? 'Journal Article' : ''),
    abstract: abstract, matched: [], summary: null,
    url: doi ? 'https://doi.org/' + doi : 'https://pubmed.ncbi.nlm.nih.gov/' + pmid + '/',
  };
}

function pubDate(a) {
  const ad = a.getChild('ArticleDate');
  const pad = n => ('0' + n).slice(-2);
  if (ad && childText(ad, 'Year')) return childText(ad, 'Year') + '-' + pad(childText(ad, 'Month') || 1) + '-' + pad(childText(ad, 'Day') || 1);
  const j = a.getChild('Journal');
  const pd = j && j.getChild('JournalIssue') ? j.getChild('JournalIssue').getChild('PubDate') : null;
  if (!pd) return '';
  return [childText(pd, 'Year') || childText(pd, 'MedlineDate').slice(0, 4), childText(pd, 'Month'), childText(pd, 'Day')].filter(Boolean).join(' ');
}

// ------------------------------------------------------------------ bioRxiv / medRxiv

function preprints(server, start, end, tz, categories, deadline) {
  const papers = [];
  let complete = true;
  const cats = categories.length ? categories.map(c => c.toLowerCase()) : [null];
  const from = Utilities.formatDate(start, tz, 'yyyy-MM-dd'), to = Utilities.formatDate(end, tz, 'yyyy-MM-dd');
  cats.forEach(cat => {
    let cursor = 0;
    while (true) {
      if (Date.now() > deadline) { complete = false; break; }
      let url = PREPRINT_API + '/' + server + '/' + from + '/' + to + '/' + cursor + '/json';
      if (cat) url += '?category=' + encodeURIComponent(cat.replace(/ /g, '_'));
      const data = JSON.parse(getJson(url));
      const batch = data.collection || [];
      const msg = (data.messages || [{}])[0];
      batch.forEach(p => {
        if (String(p.version || '1') !== '1') return;
        if (cat && String(p.category || '').trim().toLowerCase() !== cat) return;
        papers.push(p);
      });
      const count = parseInt(msg.count || batch.length || 0, 10);
      cursor += count;
      if (!batch.length || !count || cursor >= parseInt(msg.total || 0, 10)) break;
    }
  });
  return { papers: papers, complete: complete };
}

function preprintToPaper(p, label) {
  const doi = p.doi || '';
  return {
    key: 'doi:' + doi.toLowerCase(), source: label, pmid: '', doi: doi, pmc: '',
    title: String(p.title || '').replace(/\s+/g, ' ').trim(),
    authors: String(p.authors || '').split(';').map(x => x.trim()).filter(Boolean),
    journal: label, date: p.date || '', type: 'Preprint (' + String(p.category || '').trim() + '), not peer reviewed',
    abstract: p.abstract ? [['', String(p.abstract).trim()]] : [], matched: [], summary: null,
    url: doi ? 'https://doi.org/' + doi : '',
  };
}

// ------------------------------------------------------------------ Bluesky

function bskySimplify(post) {
  const record = post.record || {};
  const links = [];
  const ext = post.embed && post.embed.external && post.embed.external.uri;
  if (ext) links.push(ext);
  (record.facets || []).forEach(f => (f.features || []).forEach(x => { if (x.uri) links.push(x.uri); }));
  const author = post.author || {};
  const rkey = String(post.uri || '').split('/').pop();
  return { key: 'bsky:' + post.uri, author: author.displayName || author.handle || '', handle: author.handle || '',
    text: record.text || '', date: String(record.createdAt || '').slice(0, 10), likes: post.likeCount || 0,
    reposts: post.repostCount || 0, url: 'https://bsky.app/profile/' + author.handle + '/post/' + rkey, links: links };
}

function bskyAuthorPosts(handle, sinceIso) {
  const url = BSKY_PUBLIC + '/app.bsky.feed.getAuthorFeed?actor=' + encodeURIComponent(handle) + '&limit=50&filter=posts_no_replies';
  const feed = JSON.parse(getJson(url)).feed || [];
  return feed.filter(i => !i.reason && i.post && i.post.record && String(i.post.record.createdAt || '') >= sinceIso)
    .map(i => bskySimplify(i.post));
}

function bskyToken() {
  const props = PropertiesService.getUserProperties();
  const handle = props.getProperty('BLUESKY_HANDLE'), password = props.getProperty('BLUESKY_APP_PASSWORD');
  if (!handle || !password) return null;
  const r = JSON.parse(getJson(BSKY_AUTH + '/com.atproto.server.createSession', {
    method: 'post', contentType: 'application/json', payload: JSON.stringify({ identifier: handle, password: password }) }));
  return r.accessJwt;
}

function bskySearch(token, query, sinceIso) {
  const url = BSKY_AUTH + '/app.bsky.feed.searchPosts?q=' + encodeURIComponent(query) + '&since=' + encodeURIComponent(sinceIso) + '&sort=top&limit=25';
  return (JSON.parse(getJson(url, { headers: { Authorization: 'Bearer ' + token } })).posts || []).map(bskySimplify);
}

// ------------------------------------------------------------------ AI summaries (optional)

function aiSummary(paper, model, key) {
  const abstract = paper.abstract.map(x => (x[0] ? x[0] + ': ' : '') + x[1]).join(' ');
  if (!abstract) return null;
  const prompt = 'Summarise this research paper for a researcher\'s weekly literature digest. Write exactly five fields, ' +
    'one plain sentence each, in your own words (do not copy sentences from the abstract): Aim, Methods (include design ' +
    'and sample size if given), Results, Discussion, Caveats. If the abstract does not say, write "Not stated". Reply with ' +
    'JSON only, for example {"Aim": "...", "Methods": "...", "Results": "...", "Discussion": "...", "Caveats": "..."}\n\n' +
    'Title: ' + paper.title + '\nAbstract: ' + abstract.slice(0, 6000);
  const r = JSON.parse(getJson(ANTHROPIC_URL, { method: 'post', contentType: 'application/json',
    headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01' },
    payload: JSON.stringify({ model: model, max_tokens: 500, messages: [{ role: 'user', content: prompt }] }) }));
  const text = (r.content || []).filter(b => b.type === 'text').map(b => b.text).join('');
  const m = text.match(/\{[\s\S]*\}/);
  if (!m) return null;
  try {
    const parsed = JSON.parse(m[0]);
    const out = {};
    SUMMARY_LABELS.forEach(l => { if (parsed[l]) out[l] = String(parsed[l]).trim(); });
    return out;
  } catch (e) { return null; }
}

// ------------------------------------------------------------------ the digest

function runDigest(opts) {
  const started = Date.now();
  const deadline = started + TIME_BUDGET_MS - 60 * 1000;
  const ss = SpreadsheetApp.getActive();
  const tz = ss.getSpreadsheetTimeZone();
  const s = readSettings();
  if (!s.topics.length && !s.researchers.length) throw new Error('Add at least one topic or researcher first.');
  const sentSheet = ss.getSheetByName('_sent');
  const sent = {};
  if (sentSheet.getLastRow() > 1) sentSheet.getRange(2, 1, sentSheet.getLastRow() - 1, 1).getValues().forEach(r => { sent[r[0]] = 1; });
  const shown = {};
  const fresh = k => !sent[k] && !shown[k];
  const end = new Date();
  const start = new Date(end.getTime() - s.lookback * 86400000);
  const sinceIso = start.toISOString();
  const problems = [];
  const matchers = {};
  s.topics.forEach(t => { matchers[t.name] = makeMatcher(t); });
  const topicIds = {}, topicCounts = {}, researcherIds = {};

  if (s.pubmed) {
    try {
      s.topics.forEach(t => { const r = esearch(topicQuery(t), start, end, tz); topicIds[t.name] = r.ids; topicCounts[t.name] = r.count; });
      s.researchers.forEach(p => { const q = researcherQuery(p); if (q) researcherIds[p.name || p.orcid] = esearch(q, start, end, tz, 200).ids; });
    } catch (e) { problems.push('PubMed: ' + e.message); }
  }

  let pool = [];
  [['biorxiv', 'bioRxiv', s.biorxiv, s.biorxivCats], ['medrxiv', 'medRxiv', s.medrxiv, s.medrxivCats]].forEach(x => {
    if (!x[2]) return;
    try {
      const r = preprints(x[0], start, end, tz, x[3], deadline);
      pool = pool.concat(r.papers.map(p => preprintToPaper(p, x[1])));
      if (!r.complete) problems.push(x[1] + ': stopped early to stay within the time limit; add categories in Settings to narrow it');
    } catch (e) { problems.push(x[1] + ': ' + e.message); }
  });
  const tag = p => { const text = p.title + ' ' + p.abstract.map(a => a[1]).join(' '); p._topics = {}; s.topics.forEach(t => { p._topics[t.name] = matchers[t.name](text); }); };
  pool.forEach(tag);

  let wanted = [];
  Object.keys(researcherIds).forEach(k => { wanted = wanted.concat(researcherIds[k].slice(0, s.maxResearcher * 2)); });
  const comboIds = {};
  s.combinations.forEach(c => {
    const first = topicIds[c.topics[0]] || [];
    const sets = c.topics.map(t => (topicIds[t] || []).reduce((m, id) => { m[id] = 1; return m; }, {}));
    comboIds[c.name] = first.filter(id => sets.every(set => set[id]));
    wanted = wanted.concat(comboIds[c.name].slice(0, s.maxCombo * 2));
  });
  s.topics.forEach(t => { wanted = wanted.concat((topicIds[t.name] || []).slice(0, s.maxTopic * 3)); });
  wanted = wanted.filter((id, i) => wanted.indexOf(id) === i && !sent['pmid:' + id]);
  let records = {};
  if (wanted.length) { try { records = efetch(wanted); } catch (e) { problems.push('PubMed details: ' + e.message); } }
  Object.keys(records).forEach(k => tag(records[k]));

  const take = (p, matched) => {
    shown[p.key] = 1;
    p.matched = matched || [].concat.apply([], Object.keys(p._topics || {}).map(k => p._topics[k])).filter((v, i, a) => a.indexOf(v) === i);
    return p;
  };
  const sections = [];

  s.researchers.forEach(person => {
    const label = person.name || person.orcid;
    let items = [];
    (researcherIds[label] || []).forEach(id => { const r = records[id]; if (r && fresh(r.key)) items.push(take(r, [label])); });
    pool.forEach(p => { if (fresh(p.key) && personInAuthors(person, p.authors)) items.push(take(p, [label])); });
    items = items.slice(0, s.maxResearcher);
    let posts = [];
    if (s.bluesky && person.bluesky) { try { posts = bskyAuthorPosts(person.bluesky, sinceIso).filter(x => !sent[x.key]); } catch (e) { problems.push('Bluesky (' + person.bluesky + '): ' + e.message); } }
    if (items.length || posts.length) sections.push({ name: 'New from ' + label, items: items, posts: posts });
  });

  s.combinations.forEach(c => {
    let items = [];
    (comboIds[c.name] || []).forEach(id => { const r = records[id]; if (r && fresh(r.key)) items.push(take(r)); });
    pool.forEach(p => { if (fresh(p.key) && c.topics.every(t => p._topics[t] && p._topics[t].length)) items.push(take(p)); });
    sections.push({ name: c.name, items: items.slice(0, s.maxCombo), posts: [], total: (comboIds[c.name] || []).length });
  });

  let token = null;
  if (s.bluesky && s.bskySearch) { try { token = bskyToken(); if (!token) problems.push('Bluesky keyword search is ON, but no Bluesky login was added'); } catch (e) { problems.push('Bluesky sign-in: ' + e.message); } }
  s.topics.forEach(t => {
    const items = [];
    (topicIds[t.name] || []).forEach(id => { const r = records[id]; if (r && fresh(r.key) && items.length < s.maxTopic) items.push(take(r)); });
    const pre = pool.filter(p => fresh(p.key) && p._topics[t.name] && p._topics[t.name].length)
      .sort((a, b) => (b._topics[t.name].length - a._topics[t.name].length) || String(b.date).localeCompare(String(a.date)));
    pre.slice(0, Math.max(3, Math.floor(s.maxTopic / 2))).forEach(p => items.push(take(p)));
    let posts = [];
    if (token && Date.now() < deadline) {
      const found = {};
      const phrases = [].concat.apply([], t.keywords.map(keywordPlain)).slice(0, 5);
      for (const phrase of phrases) {
        try {
          bskySearch(token, phrase.indexOf(' ') >= 0 ? '"' + phrase + '"' : phrase, sinceIso).forEach(post => {
            if (post.links.some(u => PAPER_LINK.test(u)) && !found[post.key] && !sent[post.key]) found[post.key] = post;
          });
        } catch (e) { problems.push('Bluesky search: ' + e.message); break; }
      }
      posts = Object.keys(found).map(k => found[k]).sort((a, b) => (b.likes + 2 * b.reposts) - (a.likes + 2 * a.reposts)).slice(0, s.bskyPerTopic);
    }
    sections.push({ name: t.name, items: items, posts: posts, total: topicCounts[t.name] || 0 });
  });

  if (s.ai) {
    const key = PropertiesService.getUserProperties().getProperty('ANTHROPIC_API_KEY');
    if (!key) problems.push('AI summaries are ON, but no AI key was added');
    else {
      let budget = s.aiMax;
      outer: for (const sec of sections) for (const p of sec.items) {
        if (budget <= 0 || Date.now() > deadline) break outer;
        try { p.summary = aiSummary(p, s.aiModel, key); budget--; } catch (e) { problems.push('AI summary failed: ' + e.message); break outer; }
      }
    }
  }

  writeToSheet(sections, s, tz);
  const now = Utilities.formatDate(new Date(), tz, 'yyyy-MM-dd');
  const newRows = [];
  sections.forEach(sec => { sec.items.forEach(p => newRows.push([p.key, now])); sec.posts.forEach(p => newRows.push([p.key, now])); });
  if (newRows.length) sentSheet.getRange(sentSheet.getLastRow() + 1, 1, newRows.length, 2).setValues(newRows);

  const count = sections.reduce((n, sec) => n + sec.items.length, 0);
  if (opts.email && s.emailOn || opts.email && opts.interactive) {
    const to = s.sendTo || Session.getEffectiveUser().getEmail();
    MailApp.sendEmail({ to: to, subject: 'Weekly literature digest: ' + count + ' new papers (' + now + ')',
      htmlBody: renderHtml(sections, s, start, end, tz, problems), body: renderText(sections) });
  }
  if (opts.interactive) {
    SpreadsheetApp.getActive().toast(count + ' new papers' + (problems.length ? '. Notes: ' + problems.join('; ') : '.'), 'Weekly digest', 10);
    ss.setActiveSheet(ss.getSheetByName('Digest'));
  }
}

function abstractExcerpt(abstract, maxWords) {
  maxWords = maxWords || 90;
  const keep = abstract.filter(x => /^(result|finding|conclusion|interpretation)/i.test(x[0]));
  const chosen = keep.length ? keep : abstract;
  const out = [];
  let used = 0;
  for (const [label, text] of chosen) {
    const words = text.split(/\s+/);
    if (used + words.length > maxWords) { const w = words.slice(0, Math.max(0, maxWords - used)); if (w.length) out.push([label, w.join(' ') + ' …']); break; }
    out.push([label, text]); used += words.length;
  }
  return out;
}

function shortAuthors(a) { return a.length <= 3 ? a.join(', ') : a.slice(0, 3).join(', ') + ' et al.'; }

function writeToSheet(sections, s, tz) {
  const sh = SpreadsheetApp.getActive().getSheetByName('Digest');
  const today = Utilities.formatDate(new Date(), tz, 'yyyy-MM-dd');
  const rows = [];
  sections.forEach(sec => {
    sec.items.forEach(p => {
      const detail = p.summary ? SUMMARY_LABELS.filter(l => p.summary[l]).map(l => l + ': ' + p.summary[l]).join('\n')
        : (s.abstracts ? abstractExcerpt(p.abstract).map(x => (x[0] ? x[0] + ': ' : '') + x[1]).join('\n') : '');
      rows.push([today, sec.name, p.title, shortAuthors(p.authors), p.journal, p.date, p.type, (p.matched || []).join(', '),
        detail, p.url, p.pmid ? 'https://pubmed.ncbi.nlm.nih.gov/' + p.pmid + '/' : '',
        p.pmc ? 'https://pmc.ncbi.nlm.nih.gov/articles/' + p.pmc + '/' : '']);
    });
    sec.posts.forEach(post => rows.push([today, sec.name + ' (Bluesky)', post.text.slice(0, 300), '@' + post.handle, 'Bluesky', post.date, 'Post', '', '', post.url, '', '']));
  });
  if (!rows.length) rows.push([today, '', 'No new papers matched this time.', '', '', '', '', '', '', '', '', '']);
  sh.insertRowsAfter(1, rows.length);
  sh.getRange(2, 1, rows.length, DIGEST_HEADER.length).setValues(rows).setWrap(true).setVerticalAlignment('top');
}

function esc(s) { return String(s || '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

function renderHtml(sections, s, start, end, tz, problems) {
  const f = d => Utilities.formatDate(d, tz, 'd MMM yyyy');
  const out = ['<div style="font-family:Arial,sans-serif;max-width:720px;color:#1d1d1b;">',
    '<h1 style="font-size:22px;margin:0 0 4px;">Weekly literature digest</h1>',
    '<p style="color:#6b6a64;margin:0 0 18px;">New papers added ' + f(start) + ' to ' + f(end) + '</p>'];
  sections.forEach(sec => {
    if (!sec.items.length && !sec.posts.length) return;
    out.push('<h2 style="font-size:18px;border-bottom:1px solid #e5e2da;padding-bottom:4px;margin:26px 0 8px;">' + esc(sec.name) + '</h2>');
    sec.items.forEach(p => {
      const links = ['<a href="' + esc(p.url) + '">' + (p.doi ? 'DOI' : 'Link') + '</a>'];
      if (p.pmid) links.push('<a href="https://pubmed.ncbi.nlm.nih.gov/' + esc(p.pmid) + '/">PubMed</a>');
      if (p.pmc) links.push('<a href="https://pmc.ncbi.nlm.nih.gov/articles/' + esc(p.pmc) + '/">Free full text</a>');
      out.push('<div style="margin:0 0 16px;"><div style="font-weight:600;"><a style="color:#1d1d1b;text-decoration:none;" href="' + esc(p.url) + '">' + esc(p.title) + '</a></div>');
      out.push('<div style="color:#6b6a64;font-size:13px;">' + [shortAuthors(p.authors), p.journal, p.date, p.type].filter(Boolean).map(esc).join(' &middot; ') + '</div>');
      if (p.matched && p.matched.length) out.push('<div style="font-size:12px;color:#2f5d50;">Matched: ' + esc(p.matched.join(', ')) + '</div>');
      if (p.summary) out.push('<ul style="margin:6px 0;padding-left:18px;font-size:14px;">' + SUMMARY_LABELS.filter(l => p.summary[l]).map(l => '<li><b>' + l + ':</b> ' + esc(p.summary[l]) + '</li>').join('') + '</ul>');
      else if (s.abstracts && p.abstract.length) out.push('<div style="font-size:13px;margin:4px 0;color:#3f3e3a;">' + abstractExcerpt(p.abstract).map(x => (x[0] ? '<b>' + esc(x[0]) + ':</b> ' : '') + esc(x[1])).join('<br>') + '</div>');
      out.push('<div style="font-size:13px;">' + links.join(' &middot; ') + '</div></div>');
    });
    if (sec.posts.length) {
      out.push('<p style="font-weight:600;margin:12px 0 6px;">On Bluesky</p>');
      sec.posts.forEach(post => out.push('<div style="margin:0 0 10px;font-size:14px;"><b>' + esc(post.author) + '</b> <span style="color:#6b6a64;">@' + esc(post.handle) + ' &middot; ' + esc(post.date) + '</span><div>' + esc(post.text) + '</div><a href="' + esc(post.url) + '">Open post</a></div>'));
    }
  });
  if (problems.length) out.push('<p style="color:#9a3412;font-size:13px;margin-top:24px;">Notes: ' + esc(problems.join('; ')) + '</p>');
  out.push('<p style="color:#6b6a64;font-size:12px;margin-top:24px;">Data from PubMed (NCBI), bioRxiv, medRxiv and Bluesky. Preprints are not peer reviewed. ' +
    'Made with <a href="https://github.com/RajatJoshi15/weekly-literature-digest">weekly-literature-digest</a>.</p></div>');
  return out.join('\n');
}

function renderText(sections) {
  const lines = ['Weekly literature digest', ''];
  sections.forEach(sec => {
    if (!sec.items.length && !sec.posts.length) return;
    lines.push(sec.name.toUpperCase(), '');
    sec.items.forEach(p => lines.push('- ' + p.title, '  ' + [shortAuthors(p.authors), p.journal, p.date].join(' | '), '  ' + p.url));
    sec.posts.forEach(post => lines.push('- Bluesky @' + post.handle + ': ' + post.text.slice(0, 200) + ' ' + post.url));
    lines.push('');
  });
  return lines.join('\n');
}
