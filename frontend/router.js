/**
 * Hash Router for Hair Length Index
 *
 * Routes:
 *   #/                              → Home
 *   #/{league-slug}                 → League page (auto-language)
 *   #/{league-slug}/{team}          → Team detail (auto-language)
 *   #/{lang}/{league-slug}          → League page (explicit language)
 *   #/{lang}/{league-slug}/{team}   → Team detail (explicit language)
 */

const LEAGUE_SLUGS = {
  'eredivisie': 'DED',
  'eerste-divisie': 'JE',
  'premier-league': 'PL',
  'bundesliga': 'BL',
  'la-liga': 'LL',
  'serie-a': 'SA',
  'ligue-1': 'L1',
};

const CODE_TO_SLUG = Object.fromEntries(
  Object.entries(LEAGUE_SLUGS).map(([slug, code]) => [code, slug])
);

const VALID_LANGS = new Set(['nl', 'en', 'de', 'es', 'it', 'fr']);

function parseHash() {
  const hash = location.hash.replace(/^#\/?/, '');
  if (!hash) return { view: 'home' };

  const parts = hash.split('/');
  let lang = null;
  let offset = 0;

  // Check if first segment is a language code
  if (VALID_LANGS.has(parts[0]) && !LEAGUE_SLUGS[parts[0]]) {
    lang = parts[0];
    offset = 1;
  }

  const leagueSlug = parts[offset];
  if (!leagueSlug) return { view: 'home', lang };

  const leagueCode = LEAGUE_SLUGS[leagueSlug];
  if (!leagueCode) return { view: 'home', lang };

  const teamSlug = parts[offset + 1];
  if (teamSlug) {
    return { view: 'team', league: leagueCode, leagueSlug, teamSlug, lang };
  }
  return { view: 'league', league: leagueCode, leagueSlug, lang };
}

function navigateTo(hash) {
  location.hash = hash;
}

// Current explicit language from URL (null = auto-detect from league)
let _urlLang = null;

function leagueUrl(code) {
  const slug = CODE_TO_SLUG[code] || code.toLowerCase();
  return _urlLang ? `#/${_urlLang}/${slug}` : `#/${slug}`;
}

function teamUrl(leagueCode, teamSlug) {
  const slug = CODE_TO_SLUG[leagueCode] || leagueCode.toLowerCase();
  return _urlLang ? `#/${_urlLang}/${slug}/${teamSlug}` : `#/${slug}/${teamSlug}`;
}

function updateMeta(title, description) {
  document.title = title;
  const ogTitle = document.querySelector('meta[property="og:title"]');
  if (ogTitle) ogTitle.content = title;
  const ogDesc = document.querySelector('meta[property="og:description"]');
  if (ogDesc && description) ogDesc.content = description;
}

let onRouteChange = null;

function _handleRoute() {
  const route = parseHash();
  _urlLang = route.lang || null;
  onRouteChange(route);
}

function initRouter(callback) {
  onRouteChange = callback;
  window.addEventListener('hashchange', _handleRoute);
  _handleRoute();
}
