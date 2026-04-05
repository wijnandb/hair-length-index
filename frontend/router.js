/**
 * Hash Router for Hair Length Index
 *
 * Routes:
 *   #/                      → Home (league grid)
 *   #/{league-slug}         → League page
 *   #/{league-slug}/{team}  → Team detail page
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

function parseHash() {
  const hash = location.hash.replace(/^#\/?/, '');
  if (!hash) return { view: 'home' };

  const parts = hash.split('/');
  const leagueSlug = parts[0];
  const leagueCode = LEAGUE_SLUGS[leagueSlug];

  if (!leagueCode) return { view: 'home' };

  if (parts.length >= 2 && parts[1]) {
    return { view: 'team', league: leagueCode, leagueSlug, teamSlug: parts[1] };
  }
  return { view: 'league', league: leagueCode, leagueSlug };
}

function navigateTo(hash) {
  location.hash = hash;
}

function leagueUrl(code) {
  return `#/${CODE_TO_SLUG[code] || code.toLowerCase()}`;
}

function teamUrl(leagueCode, teamSlug) {
  return `#/${CODE_TO_SLUG[leagueCode] || leagueCode.toLowerCase()}/${teamSlug}`;
}

function updateMeta(title, description) {
  document.title = title;
  const ogTitle = document.querySelector('meta[property="og:title"]');
  if (ogTitle) ogTitle.content = title;
  const ogDesc = document.querySelector('meta[property="og:description"]');
  if (ogDesc && description) ogDesc.content = description;
}

let onRouteChange = null;

function initRouter(callback) {
  onRouteChange = callback;
  window.addEventListener('hashchange', () => onRouteChange(parseHash()));
  // Initial route
  onRouteChange(parseHash());
}
