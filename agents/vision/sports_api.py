"""
Phase 39 — Football-Data.org API wrapper
Free tier: 10 req/min. Key: football-data.org/client/register
"""
import requests
import datetime
from core.throttle import throttle

BASE_URL = "https://api.football-data.org/v4"

# Common team IDs — verified against football-data.org v4 API 2026-06-08
# Full list: https://www.football-data.org/documentation/quickstart
_TEAM_IDS = {
    # ── National teams (World Cup 2026 verified IDs) ──
    "portugal": 765,
    "france": 773,
    "germany": 759,
    "spain": 760,
    "brazil": 764,
    "argentina": 762,
    "england": 770,
    "uruguay": 758,
    "paraguay": 761,
    "ghana": 763,
    "japan": 766,
    "mexico": 769,
    "united states": 771,
    "usa": 771,
    "south korea": 772,
    "south africa": 774,
    "algeria": 778,
    "australia": 779,
    "switzerland": 788,
    "sweden": 792,
    "ecuador": 791,
    "czech republic": 798,
    "czechia": 798,
    "croatia": 799,
    "saudi arabia": 801,
    "tunisia": 802,
    "turkey": 803,
    "senegal": 804,
    "belgium": 805,
    "morocco": 815,
    "austria": 816,
    "colombia": 818,
    "egypt": 825,
    "canada": 828,
    "haiti": 836,
    "iran": 840,
    "new zealand": 783,
    "netherlands": 8601,
    "norway": 8872,
    "scotland": 8873,
    "congo dr": 1934,
    "ivory coast": 1935,
    "denmark": 782,
    "ukraine": 790,
    "poland": 794,
    "serbia": 781,
    # ── Club teams (verified via Premier League API) ──
    "arsenal": 57,
    "aston villa": 58,
    "chelsea": 61,
    "everton": 62,
    "liverpool": 64,
    "manchester city": 65,
    "manchester united": 66,
    "newcastle": 67,
    "newcastle united": 67,
    "tottenham": 73,
    "tottenham hotspur": 73,
    "spurs": 73,
    "west ham": 563,
    "brighton": 397,
    "barcelona": 81,
    "real madrid": 86,
    "atletico madrid": 78,
    "athletic bilbao": 77,
    "bilbao": 77,
    "villarreal": 94,
    "valencia": 95,
    "juventus": 109,
    "inter milan": 108,
    "inter": 108,
    "ac milan": 98,
    "milan": 98,
    "napoli": 113,
    "roma": 100,
    "lazio": 110,
    "paris saint-germain": 524,
    "psg": 524,
    "marseille": 516,
    "lyon": 523,
    "monaco": 548,
    "ajax": 674,
    "porto": 503,
    "benfica": 498,
    "sporting cp": 498,
    "sporting": 498,
    "celtic": 481,
    "rangers": 1065,
    "borussia dortmund": 4,
    "bvb": 4,
    "dortmund": 4,
    "bayern munich": 5,
    "bayern": 5,
    "rb leipzig": 721,
    "sevilla": 559,
    "feyenoord": 675,
    "psv": 672,
}

# Competition codes for standings
_COMPETITION_CODES = {
    "premier league": "PL",
    "epl": "PL",
    "bundesliga": "BL1",
    "serie a": "SA",
    "la liga": "PD",
    "ligue 1": "FL1",
    "champions league": "CL",
    "ucl": "CL",
    "euros": "EC",
    "euro": "EC",
    "world cup": "WC",
    "nations league": "UNL",
}


def _headers(api_key: str) -> dict:
    return {"X-Auth-Token": api_key}


def _find_team(name: str, api_key: str) -> tuple:
    """Returns (team_id, display_name). Checks hardcoded dict first, then API search."""
    name_lower = name.lower().strip()

    # Exact match in known list
    if name_lower in _TEAM_IDS:
        return _TEAM_IDS[name_lower], name.title()

    # Word-level partial match — "man united" -> ["man","united"] both in "manchester united"
    query_words = name_lower.split()
    for known, tid in _TEAM_IDS.items():
        # All query words must appear in the known name (as substrings of words or whole words)
        known_words = known.split()
        if all(any(qw in kw for kw in known_words) for qw in query_words):
            return tid, known.title()

    # Prefix match — "port" -> "porto" or "portugal" (only if unique)
    matches = [(k, v) for k, v in _TEAM_IDS.items() if k.startswith(name_lower)]
    if len(matches) == 1:
        return matches[0][1], matches[0][0].title()

    # API search as last resort
    try:
        throttle("football")
        r = requests.get(
            f"{BASE_URL}/teams",
            params={"name": name, "limit": 5},
            headers=_headers(api_key),
            timeout=10
        )
        if r.status_code == 200:
            teams = r.json().get("teams", [])
            if teams:
                return teams[0]["id"], teams[0]["name"]
    except Exception:
        pass

    return None, None


def get_next_match(team_name: str, api_key: str) -> dict:
    """Next scheduled match for a team. Returns success + message string."""
    team_id, display_name = _find_team(team_name, api_key)
    if not team_id:
        return {"success": False, "message": f"Team '{team_name}' not found in football database."}

    today = datetime.date.today().isoformat()
    date_to = (datetime.date.today() + datetime.timedelta(days=120)).isoformat()

    try:
        throttle("football")
        r = requests.get(
            f"{BASE_URL}/teams/{team_id}/matches",
            params={"status": "SCHEDULED", "dateFrom": today, "dateTo": date_to, "limit": 3},
            headers=_headers(api_key),
            timeout=10
        )

        if r.status_code == 403:
            return {"success": False, "message": "Football API key missing or invalid. Set FOOTBALL_API_KEY in config."}
        if r.status_code == 429:
            return {"success": False, "message": "Football API rate limit hit (10 req/min). Try again shortly."}
        if r.status_code != 200:
            return {"success": False, "message": f"Football API error {r.status_code}."}

        matches = r.json().get("matches", [])
        if not matches:
            return {"success": False, "message": f"No upcoming matches scheduled for {display_name}."}

        m = matches[0]
        utc_date = m.get("utcDate", "")
        home = m.get("homeTeam", {}).get("shortName") or m.get("homeTeam", {}).get("name", "?")
        away = m.get("awayTeam", {}).get("shortName") or m.get("awayTeam", {}).get("name", "?")
        competition = m.get("competition", {}).get("name", "")
        matchday = m.get("matchday")

        try:
            match_dt = datetime.datetime.strptime(utc_date, "%Y-%m-%dT%H:%M:%SZ")
            date_str = match_dt.strftime("%B %d, %Y at %H:%M UTC")
        except Exception:
            date_str = utc_date

        summary = f"{home} vs {away} on {date_str}"
        if competition:
            summary += f" — {competition}"
            if matchday:
                summary += f" (Matchday {matchday})"

        return {
            "success": True,
            "message": summary,
            "data": {
                "home": home,
                "away": away,
                "date": date_str,
                "competition": competition,
                "team": display_name,
            }
        }
    except Exception as e:
        return {"success": False, "message": f"Error fetching match data: {e}"}


def get_recent_results(team_name: str, api_key: str, n: int = 3) -> dict:
    """Last N finished matches for a team."""
    team_id, display_name = _find_team(team_name, api_key)
    if not team_id:
        return {"success": False, "message": f"Team '{team_name}' not found."}

    # Explicit date range — national teams have sparse fixtures; default window misses them.
    date_from = (datetime.date.today() - datetime.timedelta(days=365)).isoformat()
    date_to = datetime.date.today().isoformat()

    try:
        throttle("football")
        r = requests.get(
            f"{BASE_URL}/teams/{team_id}/matches",
            params={"status": "FINISHED", "dateFrom": date_from, "dateTo": date_to},
            headers=_headers(api_key),
            timeout=10
        )

        if r.status_code != 200:
            return {"success": False, "message": f"Football API error {r.status_code}."}

        matches = r.json().get("matches", [])
        if not matches:
            return {"success": False, "message": f"No recent results found for {display_name}."}

        # Sort by date desc, take most recent n
        matches.sort(key=lambda x: x.get("utcDate", ""), reverse=True)

        results = []
        for m in matches[:n]:
            home = m.get("homeTeam", {}).get("shortName") or m.get("homeTeam", {}).get("name", "?")
            away = m.get("awayTeam", {}).get("shortName") or m.get("awayTeam", {}).get("name", "?")
            score = m.get("score", {}).get("fullTime", {})
            home_g = score.get("home", "?")
            away_g = score.get("away", "?")
            utc_date = m.get("utcDate", "")
            try:
                match_dt = datetime.datetime.strptime(utc_date, "%Y-%m-%dT%H:%M:%SZ")
                date_str = match_dt.strftime("%b %d")
            except Exception:
                date_str = utc_date[:10]
            results.append(f"{home} {home_g}-{away_g} {away} ({date_str})")

        return {
            "success": True,
            "message": f"Last {len(results)} results for {display_name}: " + " | ".join(results),
            "data": {"team": display_name, "results": results}
        }
    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}


def get_standings(competition_name: str, api_key: str) -> dict:
    """Top 10 standings for a competition by name."""
    code = _COMPETITION_CODES.get(competition_name.lower().strip())
    if not code:
        # Try partial match
        for k, v in _COMPETITION_CODES.items():
            if competition_name.lower() in k:
                code = v
                break
    if not code:
        return {"success": False, "message": f"Competition '{competition_name}' not recognized. Try: Premier League, Bundesliga, Serie A, La Liga, Ligue 1, Champions League."}

    try:
        throttle("football")
        r = requests.get(
            f"{BASE_URL}/competitions/{code}/standings",
            headers=_headers(api_key),
            timeout=10
        )
        if r.status_code != 200:
            return {"success": False, "message": f"Football API error {r.status_code}."}

        data = r.json()
        comp_name = data.get("competition", {}).get("name", competition_name)
        standings = data.get("standings", [])
        if not standings:
            return {"success": False, "message": "No standings available."}

        table = standings[0].get("table", [])[:10]
        rows = []
        for row in table:
            pos = row["position"]
            team = row["team"].get("shortName") or row["team"].get("name", "?")
            pts = row["points"]
            played = row["playedGames"]
            rows.append(f"{pos}. {team} {pts}pts ({played}g)")

        return {
            "success": True,
            "message": f"{comp_name} top 10: " + " | ".join(rows),
            "data": {"competition": comp_name, "table": rows}
        }
    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}
