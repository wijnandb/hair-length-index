/**
 * Hair Length Index — Internationalization (i18n)
 *
 * Auto-switches language based on which league is being viewed.
 * Manual override via localStorage('hli-lang').
 */

const I18N = (() => {
  const LEAGUE_LANG = {
    DED: 'nl', JE: 'nl',
    PL: 'en',
    BL: 'de',
    LL: 'es',
    SA: 'it',
    L1: 'fr',
    ALL: 'en',
  };

  const LOCALES = {
    nl: 'nl-NL',
    en: 'en-GB',
    de: 'de-DE',
    es: 'es-ES',
    it: 'it-IT',
    fr: 'fr-FR',
  };

  const STRINGS = {
    days: {
      nl: 'dagen', en: 'days', de: 'Tage', es: 'días', it: 'giorni', fr: 'jours',
    },
    wins_in_a_row: {
      nl: 'winst op rij', en: 'wins in a row', de: 'Siege in Folge',
      es: 'victorias consecutivas', it: 'vittorie consecutive', fr: 'victoires consécutives',
    },
    matches: {
      nl: 'wedstrijden', en: 'matches', de: 'Spiele', es: 'partidos', it: 'partite', fr: 'matchs',
    },
    almost_haircut: {
      nl: 'Bijna bij de kapper!', en: 'Almost time for a haircut!',
      de: 'Fast Zeit für den Friseur!', es: '¡Casi hora de cortarse el pelo!',
      it: 'Quasi ora di tagliarsi i capelli!', fr: 'Bientôt chez le coiffeur!',
    },
    no_streak_found: {
      nl: 'Geen 5x winst op rij gevonden', en: 'No 5-win streak found',
      de: 'Keine 5er-Siegesserie gefunden', es: 'No se encontró racha de 5 victorias',
      it: 'Nessuna serie di 5 vittorie trovata', fr: 'Aucune série de 5 victoires trouvée',
    },
    loading: {
      nl: 'Laden...', en: 'Loading...', de: 'Laden...', es: 'Cargando...', it: 'Caricamento...', fr: 'Chargement...',
    },
    home: {
      nl: 'thuis', en: 'home', de: 'heim', es: 'casa', it: 'casa', fr: 'domicile',
    },
    away: {
      nl: 'uit', en: 'away', de: 'auswärts', es: 'fuera', it: 'trasferta', fr: 'extérieur',
    },
    updated: {
      nl: 'Bijgewerkt:', en: 'Updated:', de: 'Aktualisiert:', es: 'Actualizado:', it: 'Aggiornato:', fr: 'Mis à jour:',
    },
    in_a_row: {
      nl: 'op rij', en: 'in a row', de: 'in Folge', es: 'consecutivas', it: 'consecutive', fr: 'consécutives',
    },
    x_more_to_go: {
      nl: 'nog ${n} te gaan!', en: '${n} more to go!', de: 'noch ${n}!',
      es: '¡${n} más!', it: 'ancora ${n}!', fr: 'encore ${n}!',
    },
    active_streak: {
      nl: 'Actieve reeks!', en: 'Active streak!', de: 'Aktive Serie!',
      es: '¡Racha activa!', it: 'Serie attiva!', fr: 'Série en cours!',
    },
    all_matches_table: {
      nl: 'Alle wedstrijden als tabel', en: 'All matches as table', de: 'Alle Spiele als Tabelle',
      es: 'Todos los partidos como tabla', it: 'Tutte le partite come tabella', fr: 'Tous les matchs en tableau',
    },
    search_highlights: {
      nl: 'Zoek samenvatting', en: 'Search highlights', de: 'Highlights suchen',
      es: 'Buscar resumen', it: 'Cerca highlights', fr: 'Chercher résumé',
    },
    subtitle: {
      nl: 'Hoelang geleden won jouw club 5x op een rij?',
      en: 'How long since your club won 5 in a row?',
      de: 'Wie lange hat dein Verein nicht 5x in Folge gewonnen?',
      es: '¿Cuánto tiempo lleva tu club sin ganar 5 seguidos?',
      it: 'Da quanto tempo il tuo club non vince 5 di fila?',
      fr: 'Depuis combien de temps ton club n\'a pas gagné 5 de suite?',
    },
    share: {
      nl: 'Delen', en: 'Share', de: 'Teilen', es: 'Compartir', it: 'Condividi', fr: 'Partager',
    },
    not_found: {
      nl: 'niet gevonden', en: 'not found', de: 'nicht gefunden',
      es: 'no encontrado', it: 'non trovato', fr: 'non trouvé',
    },
    no_data_available: {
      nl: 'Geen data beschikbaar.', en: 'No data available.', de: 'Keine Daten verfügbar.',
      es: 'No hay datos disponibles.', it: 'Nessun dato disponibile.', fr: 'Aucune donnée disponible.',
    },
    no_match_data: {
      nl: 'Geen wedstrijddata beschikbaar', en: 'No match data available',
      de: 'Keine Spieldaten verfügbar', es: 'No hay datos de partidos',
      it: 'Nessun dato sulle partite', fr: 'Aucune donnée de match',
    },
    could_not_load: {
      nl: 'Kon data niet laden', en: 'Could not load data', de: 'Daten konnten nicht geladen werden',
      es: 'No se pudieron cargar los datos', it: 'Impossibile caricare i dati', fr: 'Impossible de charger les données',
    },
    could_not_load_team: {
      nl: 'Kon wedstrijddata niet laden.', en: 'Could not load match data.',
      de: 'Spieldaten konnten nicht geladen werden.', es: 'No se pudieron cargar los datos del partido.',
      it: 'Impossibile caricare i dati della partita.', fr: 'Impossible de charger les données du match.',
    },
    could_not_load_team_page: {
      nl: 'Kon team niet laden.', en: 'Could not load team.',
      de: 'Team konnte nicht geladen werden.', es: 'No se pudo cargar el equipo.',
      it: 'Impossibile caricare la squadra.', fr: 'Impossible de charger l\'équipe.',
    },
    team_not_found: {
      nl: 'Team niet gevonden.', en: 'Team not found.',
      de: 'Team nicht gefunden.', es: 'Equipo no encontrado.',
      it: 'Squadra non trovata.', fr: 'Équipe non trouvée.',
    },
    ensure_file_exists: {
      nl: 'Zorg dat', en: 'Ensure', de: 'Stelle sicher, dass',
      es: 'Asegúrate de que', it: 'Assicurati che', fr: 'Assurez-vous que',
    },
    exists: {
      nl: 'bestaat.', en: 'exists.', de: 'existiert.',
      es: 'exista.', it: 'esista.', fr: 'existe.',
    },
    matches_since: {
      nl: 'wedstrijden sinds', en: 'matches since', de: 'Spiele seit',
      es: 'partidos desde', it: 'partite dal', fr: 'matchs depuis',
    },
    streak_of_x_marked: {
      nl: 'Streak van ${n}x gemarkeerd', en: 'Streak of ${n}x marked',
      de: '${n}er-Serie markiert', es: 'Racha de ${n}x marcada',
      it: 'Serie di ${n}x segnata', fr: 'Série de ${n}x marquée',
    },
    the_streak: {
      nl: 'De streak: ${n}x winst op rij', en: 'The streak: ${n}x wins in a row',
      de: 'Die Serie: ${n}x Siege in Folge', es: 'La racha: ${n}x victorias consecutivas',
      it: 'La serie: ${n}x vittorie consecutive', fr: 'La série: ${n}x victoires consécutives',
    },
    newest_left_oldest_right: {
      nl: 'Nieuwste links, oudste rechts. Hover voor details.',
      en: 'Newest left, oldest right. Hover for details.',
      de: 'Neueste links, älteste rechts. Hover für Details.',
      es: 'Más reciente a la izquierda. Pasa el ratón para más detalles.',
      it: 'Più recenti a sinistra. Passa il mouse per i dettagli.',
      fr: 'Plus récent à gauche. Survolez pour les détails.',
    },
    last_on: {
      nl: 'laatst op', en: 'last on', de: 'zuletzt am',
      es: 'último el', it: 'ultimo il', fr: 'dernier le',
    },
    searched_until: {
      nl: 'Gezocht tot', en: 'Searched until', de: 'Gesucht bis',
      es: 'Buscado hasta', it: 'Cercato fino a', fr: 'Recherché jusqu\'au',
    },
    no_data: {
      nl: 'Geen data', en: 'No data', de: 'Keine Daten',
      es: 'Sin datos', it: 'Nessun dato', fr: 'Aucune donnée',
    },
    incl_aet_pens: {
      nl: '* incl. winst n.v./w.n.s.', en: '* incl. AET/pen wins',
      de: '* inkl. Siege n.V./Elfm.', es: '* incl. victorias prórroga/pen.',
      it: '* incl. vittorie suppl./rig.', fr: '* incl. victoires prol./t.a.b.',
    },
    cup_data_missing: {
      nl: 'Bekerdata ontbreekt', en: 'Cup data missing',
      de: 'Pokaldaten fehlen', es: 'Datos de copa ausentes',
      it: 'Dati coppa mancanti', fr: 'Données coupe manquantes',
    },
    load_more_teams: {
      nl: 'Meer teams laden', en: 'Load more teams', de: 'Mehr Teams laden',
      es: 'Cargar más equipos', it: 'Carica più squadre', fr: 'Charger plus d\'équipes',
    },
    remaining: {
      nl: 'resterend', en: 'remaining', de: 'verbleibend',
      es: 'restantes', it: 'rimanenti', fr: 'restants',
    },
    ready_for_scissors: {
      nl: 'Klaar voor de schaar!', en: 'Ready for the scissors!',
      de: 'Bereit für die Schere!', es: '¡Listo para las tijeras!',
      it: 'Pronto per le forbici!', fr: 'Prêt pour les ciseaux!',
    },
    next_match: {
      nl: 'Volgende wedstrijd bepaalt alles!', en: 'Next match decides it all!',
      de: 'Nächstes Spiel entscheidet alles!', es: '¡El próximo partido lo decide todo!',
      it: 'La prossima partita decide tutto!', fr: 'Le prochain match décide de tout!',
    },
    next_match_label: {
      nl: 'Volgende wedstrijd:', en: 'Next match:', de: 'Nächstes Spiel:',
      es: 'Próximo partido:', it: 'Prossima partita:', fr: 'Prochain match:',
    },
    the_streak_label: {
      nl: 'De streak:', en: 'The streak:', de: 'Die Serie:',
      es: 'La racha:', it: 'La serie:', fr: 'La série:',
    },
    no_details: {
      nl: 'Geen details beschikbaar', en: 'No details available',
      de: 'Keine Details verfügbar', es: 'Sin detalles disponibles',
      it: 'Nessun dettaglio disponibile', fr: 'Aucun détail disponible',
    },
    unknown: {
      nl: 'onbekend', en: 'unknown', de: 'unbekannt',
      es: 'desconocido', it: 'sconosciuto', fr: 'inconnu',
    },
    days_since_no_5_wins: {
      nl: 'dagen sinds 5x winst op rij', en: 'days since 5 wins in a row',
      de: 'Tage seit 5 Siegen in Folge', es: 'días desde 5 victorias consecutivas',
      it: 'giorni da 5 vittorie consecutive', fr: 'jours depuis 5 victoires consécutives',
    },
    share_text: {
      nl: '${team} heeft al ${days} dagen geen 5x op rij gewonnen!',
      en: '${team} hasn\'t won 5 in a row for ${days} days!',
      de: '${team} hat seit ${days} Tagen nicht 5x in Folge gewonnen!',
      es: '¡${team} lleva ${days} días sin ganar 5 seguidos!',
      it: '${team} non vince 5 di fila da ${days} giorni!',
      fr: '${team} n\'a pas gagné 5 de suite depuis ${days} jours!',
    },
    highlights: {
      nl: 'samenvatting', en: 'highlights', de: 'Highlights',
      es: 'resumen', it: 'highlights', fr: 'résumé',
    },
    date_header: {
      nl: 'Datum', en: 'Date', de: 'Datum', es: 'Fecha', it: 'Data', fr: 'Date',
    },
    opponent_header: {
      nl: 'Tegenstander', en: 'Opponent', de: 'Gegner', es: 'Rival', it: 'Avversario', fr: 'Adversaire',
    },
    score_header: {
      nl: 'Score', en: 'Score', de: 'Ergebnis', es: 'Resultado', it: 'Risultato', fr: 'Score',
    },
    competition_header: {
      nl: 'Competitie', en: 'Competition', de: 'Wettbewerb', es: 'Competición', it: 'Competizione', fr: 'Compétition',
    },
    source_header: {
      nl: 'Bron', en: 'Source', de: 'Quelle', es: 'Fuente', it: 'Fonte', fr: 'Source',
    },
    footer_inspiration: {
      nl: 'Geïnspireerd door de Manchester United-fan die zijn haar niet knipt totdat United 5x op een rij wint.',
      en: 'Inspired by the Manchester United fan who won\'t cut his hair until United win 5 in a row.',
      de: 'Inspiriert vom Manchester-United-Fan, der sich die Haare nicht schneidet, bis United 5x in Folge gewinnt.',
      es: 'Inspirado en el fan del Manchester United que no se corta el pelo hasta que el United gane 5 seguidos.',
      it: 'Ispirato dal tifoso del Manchester United che non si taglia i capelli finché lo United non vince 5 di fila.',
      fr: 'Inspiré par le fan de Manchester United qui ne se coupe pas les cheveux tant que United n\'a pas gagné 5 de suite.',
    },
    footer_note: {
      nl: 'Officieel: resultaat na 90 minuten. Verlenging/strafschoppen = gelijkspel.',
      en: 'Official: result after 90 minutes. Extra time/penalties = draw.',
      de: 'Offiziell: Ergebnis nach 90 Minuten. Verlängerung/Elfmeterschießen = Unentschieden.',
      es: 'Oficial: resultado tras 90 minutos. Prórroga/penaltis = empate.',
      it: 'Ufficiale: risultato dopo 90 minuti. Supplementari/rigori = pareggio.',
      fr: 'Officiel: résultat après 90 minutes. Prolongation/tirs au but = nul.',
    },
    data_source_updated: {
      nl: 'Data: football-data.org & API-Football. Bijgewerkt op',
      en: 'Data: football-data.org & API-Football. Updated on',
      de: 'Daten: football-data.org & API-Football. Aktualisiert am',
      es: 'Datos: football-data.org y API-Football. Actualizado el',
      it: 'Dati: football-data.org e API-Football. Aggiornato il',
      fr: 'Données: football-data.org et API-Football. Mis à jour le',
    },
    penalties_short: {
      nl: 'w.n.s.', en: 'pen.', de: 'Elfm.', es: 'pen.', it: 'rig.', fr: 't.a.b.',
    },
    extra_time_short: {
      nl: 'n.v.', en: 'AET', de: 'n.V.', es: 'pró.', it: 'suppl.', fr: 'prol.',
    },
    standings: {
      nl: 'Competitiestand', en: 'League standings', de: 'Tabelle', es: 'Clasificación', it: 'Classifica', fr: 'Classement',
    },
    matchday: {
      nl: 'speelronde', en: 'matchday', de: 'Spieltag', es: 'jornada', it: 'giornata', fr: 'journée',
    },
    team: {
      nl: 'Club', en: 'Team', de: 'Verein', es: 'Equipo', it: 'Squadra', fr: 'Équipe',
    },
    played: {
      nl: 'GS', en: 'P', de: 'Sp', es: 'PJ', it: 'PG', fr: 'MJ',
    },
    won_short: {
      nl: 'W', en: 'W', de: 'S', es: 'G', it: 'V', fr: 'V',
    },
    drawn_short: {
      nl: 'G', en: 'D', de: 'U', es: 'E', it: 'N', fr: 'N',
    },
    lost_short: {
      nl: 'V', en: 'L', de: 'N', es: 'P', it: 'P', fr: 'D',
    },
    goals: {
      nl: 'DV:DT', en: 'GF:GA', de: 'T:GT', es: 'GF:GC', it: 'GF:GS', fr: 'BP:BC',
    },
    points: {
      nl: 'Ptn', en: 'Pts', de: 'Pkt', es: 'Pts', it: 'Pti', fr: 'Pts',
    },
    // Hair tier names
    tier_fresh_cut: {
      nl: 'Vers geknipt', en: 'Fresh cut', de: 'Frisch geschnitten', es: 'Recién cortado', it: 'Appena tagliato', fr: 'Fraîchement coupé',
    },
    tier_growing_back: {
      nl: 'Groeit weer', en: 'Growing back', de: 'Wächst nach', es: 'Creciendo', it: 'Ricrescita', fr: 'Repousse',
    },
    tier_getting_shaggy: {
      nl: 'Wordt ruig', en: 'Getting shaggy', de: 'Wird struppig', es: 'Cada vez más largo', it: 'Sempre più lungo', fr: 'De plus en plus long',
    },
    tier_long_wild: {
      nl: 'Lang & wild', en: 'Long & wild', de: 'Lang & wild', es: 'Largo y salvaje', it: 'Lungo e selvaggio', fr: 'Long & sauvage',
    },
    tier_caveman: {
      nl: 'Holbewoner', en: 'Caveman', de: 'Höhlenmensch', es: 'Cavernícola', it: 'Uomo delle caverne', fr: 'Homme des cavernes',
    },
    tier_bigfoot: {
      nl: 'Bigfoot', en: 'Bigfoot', de: 'Bigfoot', es: 'Bigfoot', it: 'Bigfoot', fr: 'Bigfoot',
    },
    tier_lost_in_time: {
      nl: 'Verloren in de tijd', en: 'Lost in time', de: 'In der Zeit verloren', es: 'Perdido en el tiempo', it: 'Perso nel tempo', fr: 'Perdu dans le temps',
    },
  };

  let currentLang = 'nl';

  function setLang(lang, persist) {
    if (LOCALES[lang]) {
      currentLang = lang;
      if (persist !== false) {
        localStorage.setItem('hli-lang', lang);
      }
    }
  }

  function detectBrowserLang() {
    const nav = (navigator.language || '').slice(0, 2).toLowerCase();
    return LOCALES[nav] ? nav : 'en';
  }

  function setLangForLeague(leagueCode) {
    // Manual override takes precedence
    const override = localStorage.getItem('hli-lang');
    if (override && LOCALES[override]) {
      currentLang = override;
      return;
    }
    // League-based auto-detect, or browser language for home/unknown
    if (leagueCode && LEAGUE_LANG[leagueCode]) {
      currentLang = LEAGUE_LANG[leagueCode];
    } else {
      currentLang = detectBrowserLang();
    }
  }

  function getLang() {
    return currentLang;
  }

  function getLocale() {
    return LOCALES[currentLang] || 'en-GB';
  }

  function t(key, vars) {
    const entry = STRINGS[key];
    if (!entry) return key;
    let str = entry[currentLang] || entry['en'] || key;
    if (vars) {
      for (const [k, v] of Object.entries(vars)) {
        str = str.replace('${' + k + '}', v);
      }
    }
    return str;
  }

  function clearOverride() {
    localStorage.removeItem('hli-lang');
  }

  return { setLang, setLangForLeague, getLang, getLocale, t, clearOverride, detectBrowserLang, LOCALES };
})();
