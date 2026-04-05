/**
 * Hair Length Index — Frontend
 *
 * Loads hair-index.json and renders the ranking table.
 * Clicking a team loads per-team match data and shows the "hair growth strip."
 */

function daysToHuman(days) {
  if (!days || days <= 365) return '';
  const years = Math.floor(days / 365);
  const months = Math.floor((days % 365) / 30);
  if (years >= 1 && months > 0) {
    return `${years} ${t(years === 1 ? 'year' : 'years')} ${t('and')} ${months} ${t(months === 1 ? 'month' : 'months')}`;
  }
  if (years >= 1) return `${years} ${t(years === 1 ? 'year' : 'years')}`;
  return `${months} ${t(months === 1 ? 'month' : 'months')}`;
}

function slugify(name) {
  return name.normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

const LEAGUES = {
  ALL: { name: "All Leagues", file: "data/hair-index-global.json" },
  DED: { name: "Eredivisie", file: "data/hair-index.json" },
  JE: { name: "Eerste Divisie", file: "data/hair-index-je.json" },
  PL: { name: "Premier League", file: "data/hair-index-pl.json" },
  BL: { name: "Bundesliga", file: "data/hair-index-bl.json" },
  LL: { name: "La Liga", file: "data/hair-index-ll.json" },
  SA: { name: "Serie A", file: "data/hair-index-sa.json" },
  L1: { name: "Ligue 1", file: "data/hair-index-l1.json" },
};
let ITEMS_PER_PAGE = 25;
let currentPage = 1;
let allTeamsData = null;
let currentLeague = "DED";
const TEAMS_DIR = "data/teams";
let fixturesData = null;
let standingsData = {};  // keyed by internal league code
let fanData = null;      // lazy-loaded from data/fan-data.json

// Map internal league codes to standings file names
// JE is not on football-data.org — no standings available
const STANDINGS_FILES = {
  DED: "data/standings-DED.json",
  PL:  "data/standings-PL.json",
  BL:  "data/standings-BL.json",
  SA:  "data/standings-SA.json",
  LL:  "data/standings-LL.json",
  L1:  "data/standings-L1.json",
};

// Zone thresholds per league: [position] → zone class
// green = CL, blue = EL/ECL, orange = relegation playoff, red = direct relegation
const ZONE_CONFIG = {
  DED: { cl: [1], el: [2, 3], relPlayoff: [15, 16], rel: [17, 18] },
  PL:  { cl: [1, 2, 3, 4], el: [5], relPlayoff: [], rel: [18, 19, 20] },
  BL:  { cl: [1, 2, 3, 4], el: [5, 6], relPlayoff: [16], rel: [17, 18] },
  SA:  { cl: [1, 2, 3, 4], el: [5, 6], relPlayoff: [], rel: [18, 19, 20] },
  LL:  { cl: [1, 2, 3, 4], el: [5, 6], relPlayoff: [], rel: [18, 19, 20] },
  L1:  { cl: [1, 2, 3], el: [4], relPlayoff: [16], rel: [17, 18] },
};

function getPositionZone(league, position) {
  const config = ZONE_CONFIG[league];
  if (!config || !position) return "";
  if (config.cl.includes(position)) return "zone-cl";
  if (config.el.includes(position)) return "zone-el";
  if (config.relPlayoff.includes(position)) return "zone-rel-playoff";
  if (config.rel.includes(position)) return "zone-rel";
  return "";
}

function renderStandingsTable(league, highlightTeam) {
  const standings = standingsData[league];
  if (!standings || !standings.table || standings.table.length === 0) return "";

  const rows = standings.table.map(row => {
    const zone = getPositionZone(row.position, league);
    const isHighlight = highlightTeam && row.team.toLowerCase() === highlightTeam.toLowerCase();
    const classes = [zone, isHighlight ? 'highlight-row' : ''].filter(Boolean).join(' ');
    const classAttr = classes ? ` class="${classes}"` : "";
    return `
      <tr${classAttr}>
        <td>${row.position}</td>
        <td>${escapeHtml(row.team)}</td>
        <td>${row.played}</td>
        <td>${row.won}</td>
        <td>${row.drawn}</td>
        <td>${row.lost}</td>
        <td>${row.goals_for}:${row.goals_against}</td>
        <td>${row.goal_difference > 0 ? '+' : ''}${row.goal_difference}</td>
        <td><strong>${row.points}</strong></td>
      </tr>`;
  }).join("");

  const matchday = standings.matchday ? ` (${t('matchday')} ${standings.matchday})` : "";

  if (highlightTeam) {
    // On team page: open by default, no <details> wrapper
    return `
      <div class="standings-full">
        <h3>&#x1F4CA; ${t('standings')}${matchday}</h3>
        <table class="standings-table">
          <thead>
            <tr><th>#</th><th>${t('team')}</th><th>${t('played')}</th><th>${t('won_short')}</th><th>${t('drawn_short')}</th><th>${t('lost_short')}</th><th>${t('goals')}</th><th>+/-</th><th>${t('points')}</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  }

  return `
    <details class="standings-toggle">
      <summary>${t('standings')}${matchday}</summary>
      <table class="standings-table">
        <thead>
          <tr><th>#</th><th>${t('team')}</th><th>${t('played')}</th><th>${t('won_short')}</th><th>${t('drawn_short')}</th><th>${t('lost_short')}</th><th>${t('goals')}</th><th>+/-</th><th>${t('points')}</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </details>`;
}

function getStandingsPosition(team, league) {
  const standings = standingsData[league];
  if (!standings || !standings.table) return null;
  // Match by football_data_id first, then by team name
  if (team.football_data_id) {
    const row = standings.table.find(r => r.team_id === team.football_data_id);
    if (row) return row.position;
  }
  // Fallback: name match (loose)
  const teamLower = team.team.toLowerCase();
  const row = standings.table.find(r => r.team.toLowerCase() === teamLower);
  return row ? row.position : null;
}

const TIER_EMOJI = {
  "Fresh cut": "\u{1F487}",
  "Growing back": "\u2702\uFE0F",
  "Getting shaggy": "\u{1F488}",
  "Long & wild": "\u{1F981}",
  "Caveman": "\u{1F9D4}",
  "Bigfoot": "\u{1F9CC}",
  "Lost in time": "\u2753",
};

const TIER_AVATAR = {
  "Fresh cut":      { top: "shortFlat",           facialHair: "",              mouth: "smile",      eyes: "happy" },
  "Growing back":   { top: "shortCurly",          facialHair: "beardLight",    mouth: "default",    eyes: "default" },
  "Getting shaggy": { top: "shaggyMullet",        facialHair: "beardMedium",   mouth: "serious",    eyes: "squint" },
  "Long & wild":    { top: "longButNotTooLong",   facialHair: "beardMajestic", mouth: "serious",    eyes: "side" },
  "Caveman":        { top: "bigHair",             facialHair: "beardMajestic", mouth: "grimace",    eyes: "xDizzy" },
  "Bigfoot":      { top: "dreads",              facialHair: "beardMajestic", mouth: "screamOpen", eyes: "surprised", accessories: "prescription02" },
  "Lost in time":   { top: "hat",                  facialHair: "",              mouth: "concerned",  eyes: "closed" },
};

function avatarUrl(tier, seed) {
  const config = TIER_AVATAR[tier] || TIER_AVATAR["Lost in time"];
  const params = new URLSearchParams({
    seed: seed || "default",
    backgroundColor: "transparent",
    clotheColor: "262e33",
    skinColor: "d08b5b",
  });
  if (config.top) params.set("top", config.top);
  if (config.facialHair) params.set("facialHair", config.facialHair);
  if (config.mouth) params.set("mouth", config.mouth);
  if (config.eyes) params.set("eyes", config.eyes);
  if (config.accessories) params.set("accessories", config.accessories);
  return `https://api.dicebear.com/9.x/avataaars/svg?${params.toString()}`;
}

const TIER_CLASS = {
  "Fresh cut": "fresh",
  "Growing back": "growing",
  "Getting shaggy": "shaggy",
  "Long & wild": "wild",
  "Caveman": "caveman",
  "Bigfoot": "bigfoot",
  "Lost in time": "lost",
};

function tierClass(tier) {
  return TIER_CLASS[tier] || "lost";
}

const TIER_I18N_KEY = {
  "Fresh cut": "tier_fresh_cut",
  "Growing back": "tier_growing_back",
  "Getting shaggy": "tier_getting_shaggy",
  "Long & wild": "tier_long_wild",
  "Caveman": "tier_caveman",
  "Bigfoot": "tier_bigfoot",
  "Lost in time": "tier_lost_in_time",
};

function translateTier(tier) {
  const key = TIER_I18N_KEY[tier];
  return key ? t(key) : tier;
}

// Helper: get t() safely — falls back to key if i18n not loaded
function t(key, vars) {
  return typeof I18N !== 'undefined' ? I18N.t(key, vars) : key;
}
function currentLocale() {
  return typeof I18N !== 'undefined' ? I18N.getLocale() : 'nl-NL';
}

function formatDate(dateStr) {
  if (!dateStr) return t('not_found');
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString(currentLocale(), {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function formatDateShort(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString(currentLocale(), { day: "numeric", month: "short", year: "2-digit" });
}

function formatDays(days) {
  if (days === null || days === undefined) return "???";
  return days.toLocaleString(currentLocale());
}

function renderFormDots(form) {
  if (!form || form.length === 0) return "";
  return form
    .slice(0, 5)
    .map((r) => `<span class="form-dot ${r}" title="${r}">${r}</span>`)
    .join("");
}

function renderCompetitions(comps) {
  if (!comps || comps.length === 0) return "";
  return comps
    .map((c) => `<span class="comp-tag">${escapeHtml(c)}</span>`)
    .join("");
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// Team logo lookup — loaded from logo-map.json
let LOGO_MAP = {};
fetch("logo-map.json").then(r => r.ok ? r.json() : {}).then(m => { LOGO_MAP = m; }).catch(() => {});
function getLogoUrl(teamName) {
  return LOGO_MAP[teamName] || null;
}

let JERSEY_MAP = {};
fetch("jersey-map.json").then(r => r.ok ? r.json() : {}).then(m => { JERSEY_MAP = m; }).catch(() => {});
function getJerseyUrl(teamName) {
  return JERSEY_MAP[teamName] || null;
}

// === Hair Growth Strip ===

function renderGrowthStrip(teamData) {
  const matches = teamData.matches;
  const streak = teamData.streak;
  if (!matches || matches.length === 0) {
    return `<p class="no-matches">${t('no_match_data')}</p>`;
  }

  const startIdx = streak.found ? streak.start_index : -1;
  const endIdx = streak.found ? streak.end_index : -1;

  // Matches are most-recent-first; render left-to-right = newest on left
  const blocks = matches.map((m, i) => {
    const r = m.result || "?";
    const isStreak = streak.found && i >= startIdx && i <= endIdx;
    const extra = m.decided_in === "PENALTIES" ? ` (${t('penalties_short')})` :
                  m.decided_in === "EXTRA_TIME" ? ` (${t('extra_time_short')})` : "";
    const streakClass = isStreak ? " streak-highlight" : "";
    const markerAttr = isStreak && i === startIdx ? ' data-streak-start="true"' : "";
    return `<div class="strip-block ${r}${streakClass}"${markerAttr} data-opponent="${escapeHtml(m.opponent)}" data-score="${escapeHtml(m.score)}${escapeHtml(extra)}" data-date="${escapeHtml(m.date)}" data-competition="${escapeHtml(m.competition)}" data-home-away="${m.home_away || ''}">${r}</div>`;
  }).join("");

  // Legend
  const total = matches.length;
  const wins = matches.filter(m => m.result === "W").length;
  const draws = matches.filter(m => m.result === "D").length;
  const losses = matches.filter(m => m.result === "L").length;
  const oldest = matches[matches.length - 1]?.date || "";
  const streakLabel = streak.found
    ? t('streak_of_x_marked', { n: streak.length })
    : t('no_streak_found');

  return `
    <div class="strip-legend">
      <span>${total} ${t('matches_since')} ${formatDateShort(oldest)}</span>
      <span class="strip-stats">
        <span class="form-dot W">W</span>${wins}
        <span class="form-dot D">D</span>${draws}
        <span class="form-dot L">L</span>${losses}
      </span>
      <span class="strip-streak-label">${streakLabel}</span>
    </div>
    <div class="strip-hint">${t('newest_left_oldest_right')}</div>
    <div class="growth-strip">${blocks}</div>
  `;
}

// === Strip Tooltip ===

function ensureStripTooltip() {
  if (!document.getElementById('strip-tooltip')) {
    const tip = document.createElement('div');
    tip.id = 'strip-tooltip';
    tip.className = 'strip-tooltip';
    tip.style.display = 'none';
    document.body.appendChild(tip);
  }
  return document.getElementById('strip-tooltip');
}

function initStripTooltips(container) {
  const tooltip = ensureStripTooltip();
  const blocks = container.querySelectorAll('.strip-block');

  function showTooltip(block, e) {
    const opponent = block.dataset.opponent || '';
    const score = block.dataset.score || '';
    const date = block.dataset.date || '';
    const comp = block.dataset.competition || '';
    const ha = block.dataset.homeAway === 'H' ? t('home') : t('away');
    const oppLogo = getLogoUrl(opponent);

    tooltip.innerHTML = `
      <div class="strip-tooltip-row">
        ${oppLogo ? `<img src="${oppLogo}" class="strip-tooltip-logo" alt="" onerror="this.style.display='none'">` : ''}
        <strong>${opponent}</strong>
      </div>
      <div class="strip-tooltip-score">${score} (${ha})</div>
      <div class="strip-tooltip-meta">${formatDateShort(date)}</div>
      <div class="strip-tooltip-meta">${comp}</div>
    `;
    tooltip.style.display = 'block';

    const blockRect = block.getBoundingClientRect();
    const tipRect = tooltip.getBoundingClientRect();
    let left = blockRect.left + blockRect.width / 2 - tipRect.width / 2;
    let top = blockRect.top - tipRect.height - 8 + window.scrollY;

    // Keep within viewport horizontally
    if (left < 4) left = 4;
    if (left + tipRect.width > window.innerWidth - 4) left = window.innerWidth - tipRect.width - 4;
    // If above viewport, show below
    if (top < window.scrollY) top = blockRect.bottom + 8 + window.scrollY;

    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
  }

  function hideTooltip() {
    tooltip.style.display = 'none';
  }

  blocks.forEach(block => {
    block.addEventListener('mouseenter', (e) => showTooltip(block, e));
    block.addEventListener('mouseleave', hideTooltip);
    block.addEventListener('touchstart', (e) => {
      e.preventDefault();
      showTooltip(block, e);
    }, { passive: false });
  });

  document.addEventListener('touchstart', (e) => {
    if (!e.target.closest('.strip-block')) {
      hideTooltip();
    }
  });
}

// === Season Stats ===

function renderSeasonStats(teamData) {
  const matches = teamData.matches;
  if (!matches || matches.length === 0) return "";

  // Filter current season (2025-26): matches from July 2025 onward
  const seasonMatches = matches.filter(m => {
    if (!m.date) return false;
    const d = new Date(m.date + "T00:00:00");
    return (d.getFullYear() === 2025 && d.getMonth() >= 6) || d.getFullYear() === 2026;
  });

  if (seasonMatches.length === 0) return "";

  const total = seasonMatches.length;
  const wins = seasonMatches.filter(m => m.result === "W").length;
  const draws = seasonMatches.filter(m => m.result === "D").length;
  const losses = seasonMatches.filter(m => m.result === "L").length;

  // Goals: parse "2-1" format from score
  let goalsFor = 0, goalsAgainst = 0;
  seasonMatches.forEach(m => {
    if (!m.score) return;
    const parts = m.score.replace(/[^0-9-]/g, '').split('-');
    if (parts.length === 2) {
      const a = parseInt(parts[0], 10);
      const b = parseInt(parts[1], 10);
      if (!isNaN(a) && !isNaN(b)) {
        if (m.home_away === "H") {
          goalsFor += a;
          goalsAgainst += b;
        } else {
          goalsFor += b;
          goalsAgainst += a;
        }
      }
    }
  });

  // Home/away records
  const homeMatches = seasonMatches.filter(m => m.home_away === "H");
  const awayMatches = seasonMatches.filter(m => m.home_away === "A");
  const homeW = homeMatches.filter(m => m.result === "W").length;
  const homeD = homeMatches.filter(m => m.result === "D").length;
  const homeL = homeMatches.filter(m => m.result === "L").length;
  const awayW = awayMatches.filter(m => m.result === "W").length;
  const awayD = awayMatches.filter(m => m.result === "D").length;
  const awayL = awayMatches.filter(m => m.result === "L").length;

  return `
    <div class="season-stats">
      <h3>${t('season_stats')} 2025-26</h3>
      <div class="season-stats-grid">
        <div class="stat-item">
          <div class="stat-item-value">${total}</div>
          <div class="stat-item-label">${t('played_full')}</div>
        </div>
        <div class="stat-item">
          <div class="stat-item-value">${wins}W ${draws}D ${losses}L</div>
          <div class="stat-item-label">${t('won_short')}/${t('drawn_short')}/${t('lost_short')}</div>
        </div>
        <div class="stat-item">
          <div class="stat-item-value">${goalsFor}:${goalsAgainst}</div>
          <div class="stat-item-label">${t('goals_for_against')}</div>
        </div>
        <div class="stat-item">
          <div class="stat-item-value">${homeW}W ${homeD}D ${homeL}L</div>
          <div class="stat-item-label">${t('home_record')}</div>
        </div>
        <div class="stat-item">
          <div class="stat-item-value">${awayW}W ${awayD}D ${awayL}L</div>
          <div class="stat-item-label">${t('away_record')}</div>
        </div>
      </div>
    </div>`;
}

function renderStreakDetail(teamData) {
  const matches = teamData.matches;
  const streak = teamData.streak;
  const teamName = teamData.team;
  if (!streak || !streak.found || !matches) return "";

  const startIdx = streak.start_index;
  const endIdx = streak.end_index;
  const streakMatches = matches.slice(startIdx, endIdx + 1);

  // Streak matches are newest-first in the array, reverse for chronological display
  const chronological = [...streakMatches].reverse();

  const rows = chronological.map((m, i) => {
    const oppLogo = getLogoUrl(m.opponent);
    const ha = m.home_away === "H" ? "🏠" : "✈️";
    const extra = m.decided_in === "PENALTIES" ? ` (${t('penalties_short')})` :
                  m.decided_in === "EXTRA_TIME" ? ` (${t('extra_time_short')})` : "";
    const ytUrl = youtubeSearchUrl(teamName, m.opponent, m.home_away, m.date);
    return `
      <div class="streak-match">
        <span class="streak-match-num">${i + 1}</span>
        <span class="streak-match-date">${formatDateShort(m.date)}</span>
        <span class="streak-match-ha">${ha}</span>
        ${oppLogo ? `<img src="${oppLogo}" class="streak-match-logo" alt="" onerror="this.style.display='none'">` : '<span class="streak-match-logo-placeholder"></span>'}
        <span class="streak-match-opp">${escapeHtml(m.opponent)}</span>
        <span class="streak-match-score">${m.score}${extra}</span>
        <span class="streak-match-comp">${escapeHtml(m.competition)}</span>
        <a href="${ytUrl}" target="_blank" rel="noopener" class="streak-match-yt" title="${t('search_highlights')}">🎬</a>
      </div>`;
  }).join("");

  // Calculate date of first and last match in streak
  const firstDate = chronological[0]?.date;
  const lastDate = chronological[chronological.length - 1]?.date;

  return `
    <div class="streak-detail">
      <div class="streak-detail-header">
        <span class="streak-detail-title">✂️ ${t('the_streak', { n: streak.length })}</span>
        <span class="streak-detail-dates">${formatDateShort(firstDate)} — ${formatDateShort(lastDate)}</span>
      </div>
      <div class="streak-matches">${rows}</div>
    </div>`;
}

function youtubeSearchUrl(teamName, opponent, homeAway, date) {
  const home = homeAway === "H" ? teamName : opponent;
  const away = homeAway === "H" ? opponent : teamName;
  const query = `${home} ${away} ${t('highlights')} ${date}`;
  return `https://www.youtube.com/results?search_query=${encodeURIComponent(query)}`;
}

function renderMatchTable(teamData) {
  const matches = teamData.matches;
  const teamName = teamData.team;
  if (!matches || matches.length === 0) return "";
  const streak = teamData.streak;
  const startIdx = streak.found ? streak.start_index : -1;
  const endIdx = streak.found ? streak.end_index : -1;

  const rows = matches.map((m, i) => {
    const r = m.result || "";
    const ha = m.home_away === "H" ? t('home') : t('away');
    const extra = m.decided_in === "PENALTIES" ? ` (${t('penalties_short')})` :
                  m.decided_in === "EXTRA_TIME" ? ` (${t('extra_time_short')})` : "";
    const isStreak = streak.found && i >= startIdx && i <= endIdx;
    const rowClass = isStreak ? "streak-row" : "";
    const ytUrl = youtubeSearchUrl(teamName, m.opponent, m.home_away, m.date);
    const oppLogo = getLogoUrl(m.opponent);
    const logoImg = oppLogo ? `<img src="${oppLogo}" class="match-opp-logo" alt="" onerror="this.style.display='none'">` : "";
    return `
      <tr class="match-row ${r} ${rowClass}">
        <td class="match-date">${m.date}</td>
        <td class="match-result-dot"><span class="form-dot ${r}">${r}</span></td>
        <td class="match-opponent">${logoImg}${escapeHtml(m.opponent)} <span class="match-ha">(${ha})</span></td>
        <td class="match-score">${m.score}${extra}</td>
        <td class="match-comp">${escapeHtml(m.competition)}</td>
        <td class="match-yt"><a href="${ytUrl}" target="_blank" rel="noopener" class="yt-link" title="${t('search_highlights')}">&#x1F3AC;</a></td>
        <td class="match-source">${escapeHtml(m.source)}</td>
      </tr>`;
  }).join("");

  return `
    <details class="match-table-toggle">
      <summary>${t('all_matches_table')}</summary>
      <table class="match-table">
        <thead>
          <tr><th>${t('date_header')}</th><th></th><th>${t('opponent_header')}</th><th>${t('score_header')}</th><th>${t('competition_header')}</th><th></th><th>${t('source_header')}</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </details>`;
}

// === Team Cards ===

function renderTeamCard(team, rank) {
  const tc = tierClass(team.hair_tier);
  const emoji = TIER_EMOJI[team.hair_tier] || "";
  const daysStr = formatDays(team.days_since);
  const avatar = avatarUrl(team.hair_tier, team.short_name || team.team);

  // League position badge
  const position = getStandingsPosition(team, currentLeague);
  const zoneClass = position ? getPositionZone(currentLeague, position) : "";
  const positionBadge = position
    ? `<span class="position-badge ${zoneClass}" title="Competitiepositie">#${position}</span>`
    : "";

  let streakDetail = "";
  if (team.streak_found) {
    const endDate = formatDate(team.streak_end_date);
    streakDetail = `<strong>${team.streak_length}x</strong> ${t('wins_in_a_row')} \u2014 ${t('last_on')} ${endDate}`;
  } else {
    const depth = team.search_depth
      ? `${t('searched_until')} ${formatDate(team.search_depth)}`
      : t('no_data');
    streakDetail = `${t('no_streak_found')}. ${depth}`;
  }

  let notes = [];
  if (team.includes_aet_pens) {
    notes.push(`<span class="note">${t('incl_aet_pens')}</span>`);
  }
  if (!team.data_complete) {
    notes.push(`<span class="data-warning">${t('cup_data_missing')}</span>`);
  }

  return `
    <div class="team-card-wrapper" data-team-id="${team.team_id}">
      <div class="team-card" onclick="toggleDetail(this)">
        <div class="rank">${rank}${positionBadge}</div>

        <div class="avatar">
          <img src="${getLogoUrl(team.team) || avatar}" alt="${escapeHtml(team.team)}" class="avatar-img" loading="lazy"
               onerror="this.src='${avatar}'">
        </div>

        <div class="team-info">
          <a class="team-name" href="${teamUrl(currentLeague, team.slug || slugify(team.team))}" onclick="event.stopPropagation()">${escapeHtml(team.team)}</a>
          ${team.league_flag ? `<span class="league-flag" title="${escapeHtml(team.league_name || '')}">${team.league_flag}</span>` : ""}
          <span class="tier-badge tier-${tc}">${emoji} ${escapeHtml(translateTier(team.hair_tier))}</span>
        </div>

        <div class="hair-metric">
          <div class="days-number days-${tc}">${daysStr}</div>
          <div class="days-label">${t('days')}</div>
          ${team.days_since > 365 ? `<div class="days-human">${daysToHuman(team.days_since)}</div>` : ''}
        </div>

        <div class="team-details">
          <span class="streak-info">${streakDetail}</span>
          <div class="form">${renderFormDots(team.current_form)}</div>
          <div class="competitions">${renderCompetitions(team.competitions_in_streak)}</div>
          ${notes.join(" ")}
        </div>

        <div class="matches-since">
          ${team.matches_since > 0 ? team.matches_since + " " + t('matches') : t('active_streak')}
        </div>

        <button class="share-btn" onclick="shareTeam(event, '${escapeHtml(team.team)}', ${team.days_since}, '${emoji}', '${team.slug || slugify(team.team)}')" title="${t('share')}">&#8599;</button>
      </div>
      <div class="match-detail" style="display:none">
        <div class="detail-loading">${t('loading')}</div>
      </div>
    </div>
  `;
}

// === Index Rendering ===

function renderIndex(data) {
  const container = document.getElementById("index-table");
  const teams = data.teams;
  allTeamsData = teams;
  currentPage = 1;

  if (!teams || teams.length === 0) {
    container.innerHTML = `<div class="error">${t('no_data_available')}</div>`;
    return;
  }

  // For large lists (global view), paginate
  const pageSize = teams.length > 30 ? ITEMS_PER_PAGE : teams.length;
  const visible = teams.slice(0, pageSize);

  container.innerHTML = visible
    .map((team, i) => renderTeamCard(team, i + 1))
    .join("");

  // Add "load more" button for global view
  if (teams.length > pageSize) {
    container.innerHTML += `
      <div class="load-more" id="load-more">
        <button onclick="loadMoreTeams()" class="load-more-btn">
          ${t('load_more_teams')} (${teams.length - pageSize} ${t('remaining')})
        </button>
      </div>`;
  }

  const genDate = data.generated_at
    ? new Date(data.generated_at).toLocaleDateString(currentLocale(), {
        day: "numeric",
        month: "long",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : t('unknown');

  document.getElementById("updated").textContent = `${t('updated')} ${genDate}`;

  // Update footer with translated text
  const footerInspiration = document.getElementById("footer-inspiration");
  if (footerInspiration) footerInspiration.textContent = t('footer_inspiration');
  const footerNotes = document.getElementById("footer-notes");
  if (footerNotes) footerNotes.innerHTML = `${t('footer_note')}<br>${t('data_source_updated')} ${genDate}.`;

  // Add standings table after team cards
  const standingsHtml = renderStandingsTable(currentLeague);
  if (standingsHtml) {
    container.innerHTML += standingsHtml;
  }

  renderWatchCards(teams);
}

// === Data Loading ===

async function loadData(league) {
  if (league) currentLeague = league;
  const config = LEAGUES[currentLeague];
  try {
    const resp = await fetch(config.file);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    // Load fixtures (once)
    if (!fixturesData) {
      try {
        const fResp = await fetch("data/fixtures.json");
        if (fResp.ok) fixturesData = await fResp.json();
      } catch (e) { /* fixtures optional */ }
    }
    // Load standings for current league
    const standingsFile = STANDINGS_FILES[currentLeague];
    if (standingsFile && !standingsData[currentLeague]) {
      try {
        const sResp = await fetch(standingsFile);
        if (sResp.ok) standingsData[currentLeague] = await sResp.json();
      } catch (e) { /* standings optional */ }
    }
    renderIndex(data);
    // Update league selector active state
    document.querySelectorAll(".league-tab").forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.league === currentLeague);
    });
    // Update badge
    const badge = document.getElementById("league-badge");
    if (badge) badge.textContent = `${config.name} 2025-26`;
  } catch (err) {
    console.error("Failed to load data:", err);
    document.getElementById("index-table").innerHTML = `
      <div class="error">
        ${t('could_not_load')}. ${t('ensure_file_exists')} <code>${config.file}</code> ${t('exists')}<br>
        <small>${escapeHtml(err.message)}</small>
      </div>
    `;
  }
}

const teamDataCache = {};

async function loadTeamDetail(teamId) {
  if (teamDataCache[teamId]) return teamDataCache[teamId];
  const resp = await fetch(`${TEAMS_DIR}/${teamId}.json`);
  if (!resp.ok) return null;
  const data = await resp.json();
  teamDataCache[teamId] = data;
  return data;
}

async function toggleDetail(cardEl) {
  const wrapper = cardEl.closest(".team-card-wrapper");
  const detail = wrapper.querySelector(".match-detail");
  const teamId = wrapper.dataset.teamId;
  if (!detail) return;

  const isOpen = detail.style.display !== "none";

  // Close all others
  document.querySelectorAll(".match-detail").forEach((d) => {
    d.style.display = "none";
    d.closest(".team-card-wrapper")?.querySelector(".team-card")?.classList.remove("expanded");
  });

  if (!isOpen) {
    detail.style.display = "block";
    cardEl.classList.add("expanded");

    // Load team data on demand
    if (detail.querySelector(".detail-loading")) {
      const teamData = await loadTeamDetail(teamId);
      if (teamData) {
        detail.innerHTML = renderGrowthStrip(teamData) + renderStreakDetail(teamData) + renderMatchTable(teamData);
        // Init strip tooltips
        initStripTooltips(detail);
        // Auto-scroll to streak
        const streakEl = detail.querySelector('[data-streak-start="true"]');
        if (streakEl) {
          const strip = detail.querySelector(".growth-strip");
          if (strip) {
            strip.scrollLeft = streakEl.offsetLeft - strip.offsetWidth / 2;
          }
        }
      } else {
        detail.innerHTML = `<p class="no-matches">${t('could_not_load_team')}</p>`;
      }
    }
  }
}

// === Load More (pagination) ===

function loadMoreTeams() {
  if (!allTeamsData) return;
  currentPage++;
  const start = (currentPage - 1) * ITEMS_PER_PAGE;
  const end = start + ITEMS_PER_PAGE;
  const nextBatch = allTeamsData.slice(start, end);

  const container = document.getElementById("index-table");
  const loadMore = document.getElementById("load-more");
  if (loadMore) loadMore.remove();

  container.innerHTML += nextBatch
    .map((team, i) => renderTeamCard(team, start + i + 1))
    .join("");

  const remaining = allTeamsData.length - end;
  if (remaining > 0) {
    container.innerHTML += `
      <div class="load-more" id="load-more">
        <button onclick="loadMoreTeams()" class="load-more-btn">
          ${t('load_more_teams')} (${remaining} ${t('remaining')})
        </button>
      </div>`;
  }
}

// === Teams to Watch ===

function getConsecutiveWins(form) {
  let count = 0;
  for (const r of form) {
    if (r === "W") count++;
    else break;
  }
  return count;
}

function renderWatchCards(teams) {
  const section = document.getElementById("watch-section");
  const container = document.getElementById("watch-cards");
  if (!section || !container) return;

  const watchTeams = teams.filter((tm) => {
    if (!tm.current_form || tm.current_form.length === 0) return false;
    if (tm.days_since === null || tm.days_since === undefined) return false;
    if (tm.days_since <= 60) return false;
    return getConsecutiveWins(tm.current_form) >= 3;
  });

  if (watchTeams.length === 0) {
    section.style.display = "none";
    return;
  }

  section.style.display = "block";
  container.innerHTML = watchTeams
    .map((tm) => {
      const streak = getConsecutiveWins(tm.current_form);
      const toGo = 5 - streak;
      const logo = getLogoUrl(tm.team);
      const leagueFlag = tm.league_flag || "";
      const daysStr = tm.days_since ? tm.days_since.toLocaleString(currentLocale()) : "???";
      const label = toGo > 0
        ? t('x_more_to_go', { n: `<strong>${toGo}</strong>` })
        : `<strong>${t('ready_for_scissors')}</strong>`;
      return `
        <div class="watch-card" onclick="toggleWatchDetail(this, ${tm.team_id})">
          <div class="watch-header">
            ${logo ? `<img src="${logo}" class="watch-logo" alt="" onerror="this.style.display='none'">` : ""}
            <div>
              <div class="watch-team-name">${leagueFlag} ${escapeHtml(tm.team)}</div>
              <div class="watch-days">${daysStr} ${t('days')}</div>
            </div>
          </div>
          <div class="watch-streak-badge">${streak}x <span class="watch-streak-label">${t('in_a_row')}</span></div>
          <div class="watch-remaining">${label}</div>
          <div class="watch-detail" style="display:none">
            <div class="watch-loading">${t('loading')}</div>
          </div>
        </div>`;
    }).join("");
}

async function toggleWatchDetail(cardEl, teamId) {
  const detail = cardEl.querySelector(".watch-detail");
  if (!detail) return;
  const isOpen = detail.style.display !== "none";

  // Close all others
  document.querySelectorAll(".watch-detail").forEach(d => { d.style.display = "none"; });
  document.querySelectorAll(".watch-card").forEach(c => c.classList.remove("watch-expanded"));

  if (!isOpen) {
    detail.style.display = "block";
    cardEl.classList.add("watch-expanded");

    // Load streak matches from per-team file
    if (detail.querySelector(".watch-loading")) {
      const teamData = await loadTeamDetail(teamId);
      if (teamData && teamData.matches) {
        // Get the current consecutive wins
        let wins = [];
        for (const m of teamData.matches) {
          if (m.result === "W") wins.push(m);
          else break;
        }

        const matchRows = wins.map(m => {
          const oppLogo = getLogoUrl(m.opponent);
          const ha = m.home_away === "H" ? "🏠" : "✈️";
          return `<div class="watch-match">
            <span class="watch-match-date">${m.date}</span>
            ${oppLogo ? `<img src="${oppLogo}" class="watch-match-logo" alt="" onerror="this.style.display='none'">` : ""}
            <span class="watch-match-opp">${ha} ${escapeHtml(m.opponent)}</span>
            <span class="watch-match-score">${m.score}</span>
            <span class="form-dot W">W</span>
          </div>`;
        }).join("");

        // Find fixture for this team
        let nextMatchHtml = `<span class="watch-next-label">${t('next_match')}</span>`;
        if (fixturesData && teamData.team) {
          const fix = fixturesData[teamData.team];
          if (fix) {
            const fixLogo = getLogoUrl(fix.opponent);
            const ha = fix.home_away === "H" ? "🏠" : "✈️";
            const fixDate = formatDateShort(fix.date);
            nextMatchHtml = `
              <span class="watch-next-label">${t('next_match_label')}</span>
              <div class="watch-match watch-next-match">
                <span class="watch-match-date">${fixDate}</span>
                ${fixLogo ? `<img src="${fixLogo}" class="watch-match-logo" alt="" onerror="this.style.display='none'">` : ""}
                <span class="watch-match-opp">${ha} ${escapeHtml(fix.opponent)}</span>
              </div>`;
          }
        }

        detail.innerHTML = `
          <div class="watch-matches-title">${t('the_streak_label')}</div>
          ${matchRows}
          <div class="watch-next">
            ${nextMatchHtml}
          </div>
        `;
      } else {
        detail.innerHTML = `<div class="watch-no-data">${t('no_details')}</div>`;
      }
    }
  }
}

// === Social Sharing ===

async function shareTeam(event, teamName, days, emoji, teamSlug) {
  event.stopPropagation();
  const daysStr = days !== null && days !== undefined ? days.toLocaleString(currentLocale()) : "???";
  const leagueSlug = CODE_TO_SLUG[currentLeague] || 'eredivisie';
  const leagueName = LEAGUES[currentLeague]?.name || 'Eredivisie';
  const text = `${emoji} ${t('share_text', { team: teamName, days: daysStr })} #HairLengthIndex #${leagueName.replace(/\s+/g, '')}`;
  const url = `https://wijnandb.github.io/hair-length-index/#/${leagueSlug}/${teamSlug || ''}`;

  // Try native share first, then WhatsApp, then clipboard
  if (navigator.share) {
    try { await navigator.share({ title: "Hair Length Index", text, url }); return; }
    catch (e) { /* user cancelled — fall through to WhatsApp */ }
  }
  // WhatsApp deep link as primary fallback
  const waUrl = `https://wa.me/?text=${encodeURIComponent(text + "\n" + url)}`;
  if (/Android|iPhone|iPad/i.test(navigator.userAgent)) {
    window.open(waUrl, "_blank");
    return;
  }
  // Desktop: clipboard fallback
  {
    try {
      await navigator.clipboard.writeText(`${text}\n${url}`);
      const btn = event.currentTarget;
      btn.classList.add("share-copied");
      btn.textContent = "\u2713";
      setTimeout(() => { btn.classList.remove("share-copied"); btn.innerHTML = "&#8599;"; }, 1500);
    } catch (e) { /* clipboard not available */ }
  }
}

// === Fan Data (lazy-loaded) ===

async function loadFanData() {
  if (fanData) return fanData;
  try {
    const resp = await fetch("data/fan-data.json");
    if (resp.ok) {
      fanData = await resp.json();
    }
  } catch (e) { /* fan data optional */ }
  return fanData;
}

// === Standings Snippet (team context: 2 above + 2 below) ===

function renderStandingsSnippet(teamName, league) {
  const standings = standingsData[league];
  if (!standings || !standings.table || standings.table.length === 0) return "";

  const table = standings.table;
  const teamIdx = table.findIndex(r => r.team.toLowerCase() === teamName.toLowerCase());
  if (teamIdx === -1) return "";

  const startIdx = Math.max(0, teamIdx - 2);
  const endIdx = Math.min(table.length - 1, teamIdx + 2);
  const slice = table.slice(startIdx, endIdx + 1);

  const rows = slice.map(row => {
    const zone = getPositionZone(league, row.position);
    const zoneClass = zone ? ` ${zone}` : "";
    const isHighlight = row.team.toLowerCase() === teamName.toLowerCase();
    const highlightClass = isHighlight ? " highlight-row" : "";
    return `
      <tr class="${zoneClass}${highlightClass}">
        <td>${row.position}</td>
        <td>${escapeHtml(row.team)}</td>
        <td>${row.played}</td>
        <td>${row.won}</td>
        <td>${row.drawn}</td>
        <td>${row.lost}</td>
        <td>${row.goals_for}:${row.goals_against}</td>
        <td>${row.goal_difference > 0 ? '+' : ''}${row.goal_difference}</td>
        <td><strong>${row.points}</strong></td>
      </tr>`;
  }).join("");

  const matchday = standings.matchday ? ` (${t('matchday')} ${standings.matchday})` : "";

  return `
    <div class="standings-snippet">
      <h3>&#x1F4CA; ${t('standings')}${matchday}</h3>
      <table class="standings-table">
        <thead>
          <tr><th>#</th><th>${t('team')}</th><th>${t('played')}</th><th>${t('won_short')}</th><th>${t('drawn_short')}</th><th>${t('lost_short')}</th><th>${t('goals')}</th><th>+/-</th><th>${t('points')}</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

// === Team Page (full page for #/{league}/{team}) ===

async function renderTeamPage(leagueCode, teamSlug) {
  const config = LEAGUES[leagueCode];
  if (!config) return;
  currentLeague = leagueCode;
  const container = document.getElementById("index-table");

  try {
    // Load league data, standings, fan data in parallel
    const [leagueResp] = await Promise.all([
      fetch(config.file),
      (async () => {
        const standingsFile = STANDINGS_FILES[leagueCode];
        if (standingsFile && !standingsData[leagueCode]) {
          try {
            const sResp = await fetch(standingsFile);
            if (sResp.ok) standingsData[leagueCode] = await sResp.json();
          } catch (e) { /* optional */ }
        }
      })(),
      loadFanData(),
    ]);

    if (!leagueResp.ok) throw new Error(`HTTP ${leagueResp.status}`);
    const data = await leagueResp.json();

    const team = data.teams.find(t => (t.slug || slugify(t.team)) === teamSlug);
    if (!team) {
      container.innerHTML = `<div class="error">${t('team_not_found')}</div>`;
      return;
    }

    // Update meta
    updateMeta(
      `${team.team} — Hair Length Index`,
      `${team.team}: ${team.days_since ?? '???'} ${t('days_since_no_5_wins')}`
    );

    // Update tabs
    document.querySelectorAll(".league-tab").forEach(tab =>
      tab.classList.toggle("active", tab.dataset.league === leagueCode)
    );
    const badge = document.getElementById("league-badge");
    if (badge) badge.innerHTML = `<a href="${leagueUrl(leagueCode)}" style="color:inherit;text-decoration:none">&larr; ${config.name}</a>`;

    // Hide watch section
    const watchSection = document.getElementById("watch-section");
    if (watchSection) watchSection.style.display = "none";

    // Load team detail data
    const teamData = await loadTeamDetail(team.team_id);

    // --- Build team profile page ---
    const tc = tierClass(team.hair_tier);
    const emoji = TIER_EMOJI[team.hair_tier] || "";
    const logoUrl = getLogoUrl(team.team);
    const avatar = avatarUrl(team.hair_tier, team.short_name || team.team);
    const teamSlugForUrl = team.slug || slugify(team.team);

    // Fan data lookups (safe if fanData is null)
    const teamRivalries = fanData?.rivalries?.[team.team] || [];
    const teamHashtags = fanData?.hashtags?.[team.team] || [];
    const teamBirthday = fanData?.birthdays?.[team.team] || null;
    const teamFounded = teamBirthday?.year || null;

    // League flag + name
    const leagueFlag = team.league_flag || "";
    const leagueName = team.league_name || config.name;

    // --- 1. Hero header ---
    const jerseyUrl = getJerseyUrl(team.team);
    let heroHtml = `
      <a class="team-back-link" href="${leagueUrl(leagueCode)}">&larr; ${escapeHtml(config.name)}</a>
      <div class="team-hero">
        <img src="${logoUrl || avatar}" alt="${escapeHtml(team.team)}" class="team-hero-logo"
             onerror="this.src='${avatar}'">
        <div class="team-hero-info">
          <h1>${escapeHtml(team.team)}</h1>
          <div class="team-hero-meta">
            <span class="team-hero-league">${leagueFlag} ${escapeHtml(leagueName)}</span>
            ${teamBirthday ? `<span class="team-hero-founded">${t('founded')} ${(() => {
              const bd = teamBirthday;
              if (bd.day && bd.month && bd.year) {
                const dateStr = new Date(bd.year, bd.month - 1, bd.day).toLocaleDateString(currentLocale(), { day: 'numeric', month: 'long', year: 'numeric' });
                const today = new Date();
                const isBirthday = today.getDate() === bd.day && (today.getMonth() + 1) === bd.month;
                return dateStr + (isBirthday ? ' \u{1F382}' : '');
              }
              return bd.year || '';
            })()}</span>` : (teamFounded ? `<span class="team-hero-founded">${t('founded')} ${teamFounded}</span>` : "")}
          </div>
          ${teamHashtags.length > 0 ? `<div class="team-hero-hashtags">${teamHashtags.map(h => escapeHtml(h)).join(" ")}</div>` : ""}
          <div class="team-hero-tier">
            <span class="tier-badge tier-${tc}">${emoji} ${escapeHtml(translateTier(team.hair_tier))}</span>
          </div>
        </div>
        ${jerseyUrl ? `<img src="${jerseyUrl}" alt="${escapeHtml(team.team)} shirt" class="team-hero-jersey">` : ''}
      </div>`;

    // --- 2. Stat cards ---
    const daysStr = formatDays(team.days_since);
    const humanDuration = daysToHuman(team.days_since);
    const position = getStandingsPosition(team, leagueCode);
    const zoneClass = position ? getPositionZone(leagueCode, position) : "";

    let streakCardContent;
    if (team.streak_found) {
      const endDate = formatDate(team.streak_end_date);
      streakCardContent = `
        <div class="stat-card-value" style="color: var(--accent)">${team.streak_length}x</div>
        <div class="stat-card-label">${t('wins_in_a_row')}</div>
        <div class="stat-card-sub">${t('last_on')} ${endDate}</div>`;
    } else {
      streakCardContent = `
        <div class="stat-card-value" style="color: var(--text-muted)">--</div>
        <div class="stat-card-label">${t('no_streak')}</div>`;
    }

    let statCardsHtml = `
      <div class="stat-cards">
        <div class="stat-card">
          <div class="stat-card-value days-${tc}">${daysStr}</div>
          <div class="stat-card-label">${t('days')}</div>
          ${humanDuration ? `<div class="stat-card-sub">${humanDuration}</div>` : ""}
        </div>
        <div class="stat-card">
          ${position
            ? `<div class="stat-card-value"><span class="position-badge ${zoneClass}" style="font-size:1.5rem;display:inline-block">#${position}</span></div>
               <div class="stat-card-label">${t('league_position')}</div>`
            : `<div class="stat-card-value" style="color: var(--text-muted)">--</div>
               <div class="stat-card-label">${t('league_position')}</div>`
          }
        </div>
        <div class="stat-card">
          ${streakCardContent}
        </div>
      </div>`;

    // --- 3. Current form + growth strip ---
    let formHtml = "";
    if (team.current_form && team.current_form.length > 0) {
      const formDots = team.current_form.slice(0, 10)
        .map(r => `<span class="form-dot ${r}" title="${r}">${r}</span>`)
        .join("");
      formHtml = `
        <div class="team-form-section">
          <h3>${t('current_form')}</h3>
          <div class="team-form-dots">${formDots}</div>
        </div>`;
    }

    let growthStripHtml = "";
    if (teamData) {
      growthStripHtml = renderGrowthStrip(teamData);
    }

    // --- 4. Streak detail ---
    let streakDetailHtml = "";
    if (teamData) {
      streakDetailHtml = renderStreakDetail(teamData);
    }

    // --- 5. Rivalries section ---
    let rivalriesHtml = "";
    if (teamRivalries.length > 0) {
      const rivalryCards = teamRivalries.map(riv => {
        const oppLogo = getLogoUrl(riv.opponent);
        const oppSlug = slugify(riv.opponent);
        const oppUrl = teamUrl(leagueCode, oppSlug);
        const rivHashtags = riv.hashtags ? riv.hashtags.map(h => escapeHtml(h)).join(" ") : "";
        return `
          <div class="rivalry-card">
            ${oppLogo ? `<img src="${oppLogo}" class="rivalry-logo" alt="" onerror="this.style.display='none'">` : ""}
            <div class="rivalry-info">
              <a class="rivalry-name-link" href="${oppUrl}">${escapeHtml(riv.opponent)}</a>
              ${riv.name ? `<div class="rivalry-label">${escapeHtml(riv.name)}</div>` : ""}
              ${rivHashtags ? `<div class="rivalry-hashtags">${rivHashtags}</div>` : ""}
            </div>
          </div>`;
      }).join("");

      rivalriesHtml = `
        <div class="rivalries-section">
          <h3>&#x2694;&#xFE0F; ${t('rivals')}</h3>
          <div class="rivalry-cards">${rivalryCards}</div>
        </div>`;
    }

    // --- 5b. Season stats ---
    let seasonStatsHtml = "";
    if (teamData) {
      seasonStatsHtml = renderSeasonStats(teamData);
    }

    // --- 6. Full standings table ---
    let standingsSnippetHtml = renderStandingsTable(leagueCode, team.team);

    // --- 7. Match table ---
    let matchTableHtml = "";
    if (teamData) {
      matchTableHtml = renderMatchTable(teamData);
    }

    // --- 8. Share section ---
    const shareTeamSlug = teamSlugForUrl;
    let shareHtml = `
      <div class="team-share-section">
        <button class="team-share-btn" onclick="shareTeamFromPage(this, '${escapeHtml(team.team)}', ${team.days_since ?? 'null'}, '${emoji}', '${shareTeamSlug}')">
          &#8599; ${t('share')}
        </button>
      </div>`;

    // --- Assemble ---
    container.innerHTML = `
      <div class="team-page">
        ${heroHtml}
        ${statCardsHtml}
        ${formHtml}
        ${growthStripHtml}
        ${seasonStatsHtml}
        ${streakDetailHtml}
        ${rivalriesHtml}
        ${standingsSnippetHtml}
        ${matchTableHtml}
        ${shareHtml}
      </div>`;

    // Auto-scroll growth strip to streak
    const streakEl = container.querySelector('[data-streak-start="true"]');
    if (streakEl) {
      const strip = container.querySelector(".growth-strip");
      if (strip) strip.scrollLeft = streakEl.offsetLeft - strip.offsetWidth / 2;
    }

    // Init strip tooltips
    const stripContainer = container.querySelector('.growth-strip');
    if (stripContainer) {
      initStripTooltips(stripContainer.parentElement);
    }

    // Auto-scroll standings to highlighted row
    const highlightRow = container.querySelector('.standings-full .highlight-row');
    if (highlightRow) {
      setTimeout(() => highlightRow.scrollIntoView({ behavior: 'smooth', block: 'center' }), 300);
    }
  } catch (err) {
    console.error("Failed to load team page:", err);
    container.innerHTML = `<div class="error">${t('could_not_load_team_page')}</div>`;
  }
}

// Share handler for team page share button
async function shareTeamFromPage(btn, teamName, days, emoji, teamSlug) {
  const daysStr = days !== null && days !== undefined ? days.toLocaleString(currentLocale()) : "???";
  const leagueSlug = CODE_TO_SLUG[currentLeague] || 'eredivisie';
  const leagueName = LEAGUES[currentLeague]?.name || 'Eredivisie';
  const text = `${emoji} ${t('share_text', { team: teamName, days: daysStr })} #HairLengthIndex #${leagueName.replace(/\s+/g, '')}`;
  const url = `https://wijnandb.github.io/hair-length-index/#/${leagueSlug}/${teamSlug || ''}`;

  if (navigator.share) {
    try { await navigator.share({ title: "Hair Length Index", text, url }); return; }
    catch (e) { /* user cancelled */ }
  }
  if (/Android|iPhone|iPad/i.test(navigator.userAgent)) {
    const waUrl = `https://wa.me/?text=${encodeURIComponent(text + "\n" + url)}`;
    window.open(waUrl, "_blank");
    return;
  }
  try {
    await navigator.clipboard.writeText(`${text}\n${url}`);
    btn.classList.add("copied");
    const orig = btn.innerHTML;
    btn.innerHTML = "&#x2713; Copied!";
    setTimeout(() => { btn.classList.remove("copied"); btn.innerHTML = orig; }, 1500);
  } catch (e) { /* clipboard not available */ }
}

// === Route Handler ===

function applyLanguage(leagueCode) {
  if (typeof I18N !== 'undefined') {
    I18N.setLangForLeague(leagueCode);
  }
  applyLanguageUI();
}

function applyLanguageUI() {
  // Update subtitle
  const subtitle = document.querySelector('.subtitle');
  if (subtitle) subtitle.textContent = t('subtitle');
  // Update watch heading
  const watchHeading = document.getElementById('watch-heading');
  if (watchHeading) watchHeading.textContent = t('almost_haircut');
  // Update html lang attribute
  const html = document.documentElement;
  if (html && typeof I18N !== 'undefined') html.lang = I18N.getLang();
  // Update language picker active state
  document.querySelectorAll('.lang-link').forEach(link => {
    link.classList.toggle('active', typeof I18N !== 'undefined' && link.dataset.lang === I18N.getLang());
  });
}

function handleRoute(route) {
  const leagueCode = route.league || 'DED';
  // URL language takes priority (don't persist), then auto-detect from league
  if (route.lang && typeof I18N !== 'undefined') {
    I18N.setLang(route.lang, false);
  } else if (typeof I18N !== 'undefined') {
    I18N.setLangForLeague(leagueCode);
  }
  // Update UI elements for current language
  applyLanguageUI();

  if (route.view === 'team') {
    renderTeamPage(route.league, route.teamSlug);
  } else if (route.view === 'league') {
    loadData(route.league);
    updateMeta(
      `Hair Length Index — ${LEAGUES[route.league]?.name || route.league}`,
      `${t('subtitle')} ${LEAGUES[route.league]?.name || ''}`
    );
  } else {
    // Home — default to Eredivisie
    loadData('DED');
    updateMeta("Hair Length Index", t('subtitle'));
  }
}

document.addEventListener("DOMContentLoaded", () => {
  // Language picker click handler
  document.querySelectorAll('.lang-link').forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const lang = link.dataset.lang;
      // Persist manual language choice
      if (typeof I18N !== 'undefined') I18N.setLang(lang, true);
      // Navigate to URL with language prefix
      const route = parseHash();
      const leagueSlug = route.leagueSlug || CODE_TO_SLUG[currentLeague] || 'eredivisie';
      if (route.view === 'team') {
        navigateTo(`#/${lang}/${leagueSlug}/${route.teamSlug}`);
      } else if (route.view === 'league') {
        navigateTo(`#/${lang}/${leagueSlug}`);
      } else {
        navigateTo(`#/${lang}/${leagueSlug}`);
      }
    });
  });

  initRouter(handleRoute);
});
