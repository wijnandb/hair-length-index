/**
 * Hair Length Index — Frontend
 *
 * Loads hair-index.json and renders the ranking table.
 */

const DATA_URL = "../data/hair-index.json";

const TIER_EMOJI = {
  "Fresh cut": "\u{1F487}",
  "Growing back": "\u2702\uFE0F",
  "Getting shaggy": "\u{1F488}",
  "Long & wild": "\u{1F981}",
  "Caveman": "\u{1F9D4}",
  "Sasquatch": "\u{1F9CC}",
  "Lost in time": "\u2753",
};

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

function renderTeamCard(team, rank) {
  const tc = tierClass(team.hair_tier);
  const emoji = TIER_EMOJI[team.hair_tier] || "";
  const daysStr = formatDays(team.days_since);

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
  if (team.penalty_footnote) {
    notes.push(`<span class="note">* 5 op een rij met strafschoppen</span>`);
  }
  if (!team.data_complete) {
    notes.push(`<span class="data-warning">Bekerdata ontbreekt</span>`);
  }

  return `
    <div class="team-card">
      <div class="rank">${rank}</div>

      <div class="team-info">
        <span class="team-name">${escapeHtml(team.team)}</span>
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
    </div>
  `;
}

function renderIndex(data) {
  const container = document.getElementById("index-table");
  const teams = data.teams;

  if (!teams || teams.length === 0) {
    container.innerHTML = `<div class="error">Geen data beschikbaar.</div>`;
    return;
  }

  container.innerHTML = teams
    .map((team, i) => renderTeamCard(team, i + 1))
    .join("");

  // Update timestamps
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
}

async function loadData() {
  try {
    const resp = await fetch(DATA_URL);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    renderIndex(data);
  } catch (err) {
    console.error("Failed to load data:", err);
    document.getElementById("index-table").innerHTML = `
      <div class="error">
        Kon data niet laden. Zorg dat <code>data/hair-index.json</code> bestaat.<br>
        <small>${escapeHtml(err.message)}</small>
      </div>
    `;
  }
}

document.addEventListener("DOMContentLoaded", loadData);
