/**
 * Hair Length Index — Frontend
 *
 * Loads hair-index.json and renders the ranking table.
 * Clicking a team loads per-team match data and shows the "hair growth strip."
 */

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

const TIER_EMOJI = {
  "Fresh cut": "\u{1F487}",
  "Growing back": "\u2702\uFE0F",
  "Getting shaggy": "\u{1F488}",
  "Long & wild": "\u{1F981}",
  "Caveman": "\u{1F9D4}",
  "Sasquatch": "\u{1F9CC}",
  "Lost in time": "\u2753",
};

const TIER_AVATAR = {
  "Fresh cut":      { top: "shortFlat",           facialHair: "",              mouth: "smile",      eyes: "happy" },
  "Growing back":   { top: "shortCurly",          facialHair: "beardLight",    mouth: "default",    eyes: "default" },
  "Getting shaggy": { top: "shaggyMullet",        facialHair: "beardMedium",   mouth: "serious",    eyes: "squint" },
  "Long & wild":    { top: "longButNotTooLong",   facialHair: "beardMajestic", mouth: "serious",    eyes: "side" },
  "Caveman":        { top: "bigHair",             facialHair: "beardMajestic", mouth: "grimace",    eyes: "xDizzy" },
  "Sasquatch":      { top: "dreads",              facialHair: "beardMajestic", mouth: "screamOpen", eyes: "surprised", accessories: "prescription02" },
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
  "Sasquatch": "sasquatch",
  "Lost in time": "lost",
};

function tierClass(tier) {
  return TIER_CLASS[tier] || "lost";
}

function formatDate(dateStr) {
  if (!dateStr) return "niet gevonden";
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("nl-NL", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function formatDateShort(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("nl-NL", { day: "numeric", month: "short", year: "2-digit" });
}

function formatDays(days) {
  if (days === null || days === undefined) return "???";
  return days.toLocaleString("nl-NL");
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

// === Hair Growth Strip ===

function renderGrowthStrip(teamData) {
  const matches = teamData.matches;
  const streak = teamData.streak;
  if (!matches || matches.length === 0) {
    return `<p class="no-matches">Geen wedstrijddata beschikbaar</p>`;
  }

  const startIdx = streak.found ? streak.start_index : -1;
  const endIdx = streak.found ? streak.end_index : -1;

  // Matches are most-recent-first; render left-to-right = newest on left
  const blocks = matches.map((m, i) => {
    const r = m.result || "?";
    const isStreak = streak.found && i >= startIdx && i <= endIdx;
    const ha = m.home_away === "H" ? "T" : "U";
    const extra = m.decided_in === "PENALTIES" ? " (w.n.s.)" :
                  m.decided_in === "EXTRA_TIME" ? " (n.v.)" : "";
    const tip = `${m.date} | ${m.opponent} (${ha}) ${m.score}${extra} | ${m.competition} | ${m.source}`;
    const streakClass = isStreak ? " streak-highlight" : "";
    const markerAttr = isStreak && i === startIdx ? ' data-streak-start="true"' : "";
    return `<div class="strip-block ${r}${streakClass}" title="${escapeHtml(tip)}"${markerAttr}>${r}</div>`;
  }).join("");

  // Legend
  const total = matches.length;
  const wins = matches.filter(m => m.result === "W").length;
  const draws = matches.filter(m => m.result === "D").length;
  const losses = matches.filter(m => m.result === "L").length;
  const oldest = matches[matches.length - 1]?.date || "";
  const streakLabel = streak.found
    ? `Streak van ${streak.length}x gemarkeerd`
    : "Geen 5x winst op rij gevonden";

  return `
    <div class="strip-legend">
      <span>${total} wedstrijden sinds ${formatDateShort(oldest)}</span>
      <span class="strip-stats">
        <span class="form-dot W">W</span>${wins}
        <span class="form-dot D">D</span>${draws}
        <span class="form-dot L">L</span>${losses}
      </span>
      <span class="strip-streak-label">${streakLabel}</span>
    </div>
    <div class="strip-hint">Nieuwste links, oudste rechts. Hover voor details.</div>
    <div class="growth-strip">${blocks}</div>
  `;
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
    const extra = m.decided_in === "PENALTIES" ? " (w.n.s.)" :
                  m.decided_in === "EXTRA_TIME" ? " (n.v.)" : "";
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
        <a href="${ytUrl}" target="_blank" rel="noopener" class="streak-match-yt" title="Zoek samenvatting">🎬</a>
      </div>`;
  }).join("");

  // Calculate date of first and last match in streak
  const firstDate = chronological[0]?.date;
  const lastDate = chronological[chronological.length - 1]?.date;

  return `
    <div class="streak-detail">
      <div class="streak-detail-header">
        <span class="streak-detail-title">✂️ De streak: ${streak.length}x winst op rij</span>
        <span class="streak-detail-dates">${formatDateShort(firstDate)} — ${formatDateShort(lastDate)}</span>
      </div>
      <div class="streak-matches">${rows}</div>
    </div>`;
}

function youtubeSearchUrl(teamName, opponent, homeAway, date) {
  const home = homeAway === "H" ? teamName : opponent;
  const away = homeAway === "H" ? opponent : teamName;
  const query = `${home} ${away} samenvatting ${date}`;
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
    const ha = m.home_away === "H" ? "thuis" : "uit";
    const extra = m.decided_in === "PENALTIES" ? " (w.n.s.)" :
                  m.decided_in === "EXTRA_TIME" ? " (n.v.)" : "";
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
        <td class="match-yt"><a href="${ytUrl}" target="_blank" rel="noopener" class="yt-link" title="Zoek samenvatting">&#x1F3AC;</a></td>
        <td class="match-source">${escapeHtml(m.source)}</td>
      </tr>`;
  }).join("");

  return `
    <details class="match-table-toggle">
      <summary>Alle wedstrijden als tabel</summary>
      <table class="match-table">
        <thead>
          <tr><th>Datum</th><th></th><th>Tegenstander</th><th>Score</th><th>Competitie</th><th></th><th>Bron</th></tr>
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

  let streakDetail = "";
  if (team.streak_found) {
    const endDate = formatDate(team.streak_end_date);
    streakDetail = `<strong>${team.streak_length}x</strong> winst op rij \u2014 laatst op ${endDate}`;
  } else {
    const depth = team.search_depth
      ? `Gezocht tot ${formatDate(team.search_depth)}`
      : "Geen data";
    streakDetail = `Geen 5x winst op rij gevonden. ${depth}`;
  }

  let notes = [];
  if (team.includes_aet_pens) {
    notes.push(`<span class="note">* incl. winst n.v./w.n.s.</span>`);
  }
  if (!team.data_complete) {
    notes.push(`<span class="data-warning">Bekerdata ontbreekt</span>`);
  }

  return `
    <div class="team-card-wrapper" data-team-id="${team.team_id}">
      <div class="team-card" onclick="toggleDetail(this)">
        <div class="rank">${rank}</div>

        <div class="avatar">
          <img src="${getLogoUrl(team.team) || avatar}" alt="${escapeHtml(team.team)}" class="avatar-img" loading="lazy"
               onerror="this.src='${avatar}'">
        </div>

        <div class="team-info">
          <span class="team-name">${escapeHtml(team.team)}</span>
          ${team.league_flag ? `<span class="league-flag" title="${escapeHtml(team.league_name || '')}">${team.league_flag}</span>` : ""}
          <span class="tier-badge tier-${tc}">${emoji} ${escapeHtml(team.hair_tier)}</span>
        </div>

        <div class="hair-metric">
          <div class="days-number days-${tc}">${daysStr}</div>
          <div class="days-label">dagen</div>
        </div>

        <div class="team-details">
          <span class="streak-info">${streakDetail}</span>
          <div class="form">${renderFormDots(team.current_form)}</div>
          <div class="competitions">${renderCompetitions(team.competitions_in_streak)}</div>
          ${notes.join(" ")}
        </div>

        <div class="matches-since">
          ${team.matches_since > 0 ? team.matches_since + " wedstrijden" : "Actieve reeks!"}
        </div>

        <button class="share-btn" onclick="shareTeam(event, '${escapeHtml(team.team)}', ${team.days_since}, '${emoji}')" title="Delen">&#8599;</button>
      </div>
      <div class="match-detail" style="display:none">
        <div class="detail-loading">Laden...</div>
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
    container.innerHTML = `<div class="error">Geen data beschikbaar.</div>`;
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
          Meer teams laden (${teams.length - pageSize} remaining)
        </button>
      </div>`;
  }

  const genDate = data.generated_at
    ? new Date(data.generated_at).toLocaleDateString("nl-NL", {
        day: "numeric",
        month: "long",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "onbekend";

  document.getElementById("updated").textContent = `Bijgewerkt: ${genDate}`;
  const footerDate = document.getElementById("footer-date");
  if (footerDate) footerDate.textContent = genDate;

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
    renderIndex(data);
    // Update league selector active state
    document.querySelectorAll(".league-tab").forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.league === currentLeague);
    });
    // Update badge
    const badge = document.querySelector(".league-badge");
    if (badge) badge.textContent = `${config.name} 2025-26`;
  } catch (err) {
    console.error("Failed to load data:", err);
    document.getElementById("index-table").innerHTML = `
      <div class="error">
        Kon data niet laden. Zorg dat <code>${config.file}</code> bestaat.<br>
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
        // Auto-scroll to streak
        const streakEl = detail.querySelector('[data-streak-start="true"]');
        if (streakEl) {
          const strip = detail.querySelector(".growth-strip");
          if (strip) {
            strip.scrollLeft = streakEl.offsetLeft - strip.offsetWidth / 2;
          }
        }
      } else {
        detail.innerHTML = `<p class="no-matches">Kon wedstrijddata niet laden.</p>`;
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
          Meer teams laden (${remaining} remaining)
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

  const watchTeams = teams.filter((t) => {
    if (!t.current_form || t.current_form.length === 0) return false;
    if (t.days_since === null || t.days_since === undefined) return false;
    if (t.days_since <= 60) return false;
    return getConsecutiveWins(t.current_form) >= 3;
  });

  if (watchTeams.length === 0) {
    section.style.display = "none";
    return;
  }

  section.style.display = "block";
  container.innerHTML = watchTeams
    .map((t) => {
      const streak = getConsecutiveWins(t.current_form);
      const toGo = 5 - streak;
      const logo = getLogoUrl(t.team);
      const leagueFlag = t.league_flag || "";
      const daysStr = t.days_since ? t.days_since.toLocaleString("nl-NL") : "???";
      const label = toGo > 0
        ? `nog <strong>${toGo}</strong> te gaan!`
        : `<strong>Klaar voor de schaar!</strong>`;
      return `
        <div class="watch-card" onclick="toggleWatchDetail(this, ${t.team_id})">
          <div class="watch-header">
            ${logo ? `<img src="${logo}" class="watch-logo" alt="" onerror="this.style.display='none'">` : ""}
            <div>
              <div class="watch-team-name">${leagueFlag} ${escapeHtml(t.team)}</div>
              <div class="watch-days">${daysStr} dagen</div>
            </div>
          </div>
          <div class="watch-streak-badge">${streak}x <span class="watch-streak-label">op rij</span></div>
          <div class="watch-remaining">${label}</div>
          <div class="watch-detail" style="display:none">
            <div class="watch-loading">Laden...</div>
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
        let nextMatchHtml = `<span class="watch-next-label">Volgende wedstrijd bepaalt alles!</span>`;
        if (fixturesData && teamData.team) {
          const fix = fixturesData[teamData.team];
          if (fix) {
            const fixLogo = getLogoUrl(fix.opponent);
            const ha = fix.home_away === "H" ? "🏠" : "✈️";
            const fixDate = formatDateShort(fix.date);
            nextMatchHtml = `
              <span class="watch-next-label">Volgende wedstrijd:</span>
              <div class="watch-match watch-next-match">
                <span class="watch-match-date">${fixDate}</span>
                ${fixLogo ? `<img src="${fixLogo}" class="watch-match-logo" alt="" onerror="this.style.display='none'">` : ""}
                <span class="watch-match-opp">${ha} ${escapeHtml(fix.opponent)}</span>
              </div>`;
          }
        }

        detail.innerHTML = `
          <div class="watch-matches-title">De streak:</div>
          ${matchRows}
          <div class="watch-next">
            ${nextMatchHtml}
          </div>
        `;
      } else {
        detail.innerHTML = `<div class="watch-no-data">Geen details beschikbaar</div>`;
      }
    }
  }
}

// === Social Sharing ===

async function shareTeam(event, teamName, days, emoji) {
  event.stopPropagation();
  const daysStr = days !== null && days !== undefined ? days.toLocaleString("nl-NL") : "???";
  const text = `${emoji} ${teamName} heeft al ${daysStr} dagen geen 5x op rij gewonnen! #HairLengthIndex #Eredivisie`;
  const url = "https://wijnandb.github.io/hair-length-index/";

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

document.addEventListener("DOMContentLoaded", loadData);
