import requests
from bs4 import BeautifulSoup
import re
import math
import pandas as pd

# Parameters (Modify these as needed)
a_params = {
    "match_played": 4,
    "runs": 1,
    "wickets": 25,
    "catches": 8,
    "run_outs_stumpings": 6,
    "fours": 1,
    "sixes": 2,
    "maidens": 10,
    "dots_per_4": 1,
    "duck": -4,
    "no_balls_bowled": -2,
    "not_out": 5,
    "fifty": 8,
    "hundred": 8,
    "four_wickets": 10,
    "player_of_match": 0
}

def f(economy_rate):
    x=economy_rate
    if x<4:
        return 16
    elif x<5:
        return 12
    elif x<6:
        return 10
    elif x<7:
        return 6
    elif x<8:
        return 2
    elif x<9:
        return 0
    elif x<10:
        return -4
    elif x<11:
        return -6
    elif x<12:
        return -10
    else:
        return -14

def g(strike_rate):
    x=strike_rate
    if x<70 and x>0:
        return -10
    elif x<80:
        return -10
    elif x<100:
        return -8
    elif x<110:
        return -6
    elif x<120:
        return -4
    elif x<130:
        return -2
    elif x<140:
        return 0
    elif x<150:
        return 2
    elif x<160:
        return 4
    elif x<180:
        return 6
    elif x<200:
        return 8
    elif x<240:
        return 10
    else:
        return 16

# ---------------------------
# Helper to split names into first and last.
def split_name(name):
    parts = name.split()
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    else:
        return "", name

# ---------------------------
# Helper to clean player names.
def clean_player_name(name):
    # Normalize apostrophes so that both ’ and ' become the same
    name = name.replace("’", "'")
    name = name.strip()
    # Remove any trailing parentheses and their contents (e.g., " (c)", " (sub ...)", " (wk)")
    name = re.sub(r'\s*\(.*?\)\s*$', '', name)
    # Remove any leading special characters (like "†") and trailing non-alphanumeric symbols.
    name = re.sub(r'^[^A-Za-z0-9]+', '', name)
    name = re.sub(r'[^A-Za-z0-9 \']+$', '', name)
    return name

# ---------------------------
# Global aggregated stats across all games.
# Keys are the canonical full names.
player_stats = {}

def init_player(player):
    if player not in player_stats:
        first, last = split_name(player)
        player_stats[player] = {
            'first_name': first,
            'last_name': last,
            'matches': 0,
            'score': 0,
            'runs': 0,
            'fours': 0,
            'sixes': 0,
            'wickets': 0,
            'maidens': 0,
            'dot_balls': 0,
            'catches': 0,
            'stumpings': 0,
            'run_outs': 0,
            'contributions': {
                'batting': [],
                'bowling': [],
                'fielding': []
            }
        }
    else:
        first, last = split_name(player)
        if not player_stats[player].get('first_name'):
            player_stats[player]['first_name'] = first
        if not player_stats[player].get('last_name'):
            player_stats[player]['last_name'] = last

# ---------------------------
# Helper to resolve a player name (case-insensitive) for full names.
def resolve_player_name(name):
    cleaned = clean_player_name(name)
    normalized = cleaned.lower()
    for key in player_stats.keys():
        if key.lower() == normalized:
            return key
    # Try matching by surname:
    candidates = []
    for key in player_stats.keys():
        _, last = split_name(key)
        if last.lower() == normalized:
            candidates.append(key)
    if len(candidates) == 1:
        return candidates[0]
    elif len(candidates) > 1:
        print(f"Ambiguity detected: '{name}' could refer to any of {', '.join(candidates)}. Using first candidate.")
        return candidates[0]
    else:
        return cleaned.title()

# ---------------------------
# Helper to parse a fielder's name from dismissal text.
def parse_fielder_name(dismissal_text, player_list):
    # Normalize apostrophes
    dismissal_text = dismissal_text.replace("’", "'")
    # Remove wicketkeeper symbols (like †)
    dismissal_text = dismissal_text.replace('†', '').strip()
    sub_pattern = re.compile(r'c\s+sub\s*\((.*?)\)\s+b\s+', re.IGNORECASE)
    match = sub_pattern.search(dismissal_text)
    if match:
        return match.group(1).strip()
    
    caught_pattern = re.compile(r'c\s+(.*?)\s+b\s+', re.IGNORECASE)
    match = caught_pattern.search(dismissal_text)
    if match:
        fielder = match.group(1).strip()
        return fielder  # May be full name or surname
    return None

# ---------------------------
# The scrape function returns a per-game breakdown dictionary.
def scrape_ipl_scorecard(url):
    breakdown = {}  # Local breakdown for this game.
    pending_fielding = []  # Store fielding events pending resolution.
    
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Failed to fetch webpage.")
        return breakdown
    
    soup = BeautifulSoup(response.text, 'html.parser')
    tables = soup.find_all('table', class_=re.compile(".*ds-w-full.*"))
    if not tables or len(tables) < 4:
        print("Not enough tables found. Check the HTML structure.")
        return breakdown

    def init_game_player(player):
        if player not in breakdown:
            first, last = split_name(player)
            breakdown[player] = {
                'first_name': first,
                'last_name': last,
                'batting': {'matches': 0, 'runs': 0, 'fours': 0, 'sixes': 0, 'score': 0, 'contributions': []},
                'bowling': {'matches': 0, 'wickets': 0, 'maidens': 0, 'dot_balls': 0, 'score': 0, 'contributions': []},
                'fielding': {'catches': 0, 'stumpings': 0, 'run_outs': 0, 'contributions': []}
            }
    
    # ---------------------------
    # BATTTING SECTION: Tables 1 & 3 (indices 0 and 2)
    for idx in [0, 2]:
        table = tables[idx]
        rows = table.find_all('tr')
        for row in rows[1:]:
            cols = row.find_all('td')
            if len(cols) < 8:
                continue
            raw_player = cols[0].text.strip()
            player = clean_player_name(raw_player)
            if player.lower() in ['extras', 'did not bat']:
                continue

            try:
                runs = int(cols[2].text.strip()) if cols[2].text.strip().isdigit() else 0
            except Exception:
                runs = 0
            try:
                fours = int(cols[5].text.strip()) if cols[5].text.strip().isdigit() else 0
            except Exception:
                fours = 0
            try:
                sixes = int(cols[6].text.strip()) if cols[6].text.strip().isdigit() else 0
            except Exception:
                sixes = 0
            try:
                strike_rate = float(cols[7].text.strip()) if cols[7].text.strip() else 0
            except Exception:
                strike_rate = 0

            dismissal_info = cols[1].text.strip().lower()
            got_out = ('not out' not in dismissal_info)
            
            init_player(player)
            init_game_player(player)
            # Do not increment match count here.
            player_stats[player]['runs'] += runs
            player_stats[player]['fours'] += fours
            player_stats[player]['sixes'] += sixes
            
            breakdown[player]['batting']['matches'] += 1
            breakdown[player]['batting']['runs'] += runs
            breakdown[player]['batting']['fours'] += fours
            breakdown[player]['batting']['sixes'] += sixes
            
            delta_score = (a_params['match_played'] +
                           a_params['runs'] * runs +
                           a_params['fours'] * fours +
                           a_params['sixes'] * sixes +
                           a_params['not_out'] * (0 if got_out else 1) +
                           a_params['duck'] * (1 if got_out and runs == 0 else 0) +
                           a_params['fifty'] * (1 if runs >= 50 else 0) +
                           a_params['hundred'] * (1 if runs >= 100 else 0) +
                           g(strike_rate))
            player_stats[player]['score'] += delta_score
            breakdown[player]['batting']['score'] += delta_score
            
            bat_contrib = {
                'runs': runs,
                'fours': fours,
                'sixes': sixes,
                'strike_rate': strike_rate,
                'got_out': got_out,
                'delta_score': delta_score,
                'dismissal': dismissal_info
            }
            player_stats[player]['contributions']['batting'].append(bat_contrib)
            breakdown[player]['batting']['contributions'].append(bat_contrib)
            
            # -- Fielding from batting dismissal info --
            if got_out:
                if dismissal_info.startswith('c '):
                    fielder_candidate = parse_fielder_name(dismissal_info, list(player_stats.keys()))
                    if fielder_candidate:
                        if " " in fielder_candidate:
                            resolved = resolve_player_name(fielder_candidate)
                            init_player(resolved)
                            init_game_player(resolved)
                            player_stats[resolved]['catches'] += 1
                            breakdown[resolved]['fielding']['catches'] += 1
                            field_contrib = {'type': 'catch', 'from': player, 'dismissal': dismissal_info}
                            player_stats[resolved]['contributions']['fielding'].append(field_contrib)
                            breakdown[resolved]['fielding']['contributions'].append(field_contrib)
                        else:
                            # Single word; try to resolve using surname.
                            candidate = None
                            for key in player_stats.keys():
                                _, last = split_name(key)
                                if last.lower() == fielder_candidate.lower() and key.lower() != fielder_candidate.lower():
                                    candidate = key
                                    break
                            if candidate:
                                resolved = candidate
                                init_player(resolved)
                                init_game_player(resolved)
                                player_stats[resolved]['catches'] += 1
                                breakdown[resolved]['fielding']['catches'] += 1
                                field_contrib = {'type': 'catch', 'from': player, 'dismissal': dismissal_info}
                                player_stats[resolved]['contributions']['fielding'].append(field_contrib)
                                breakdown[resolved]['fielding']['contributions'].append(field_contrib)
                            else:
                                pending_fielding.append({
                                    'type': 'catch',
                                    'from': player,
                                    'dismissal': dismissal_info,
                                    'fielder': fielder_candidate
                                })
                elif dismissal_info.startswith('st '):
                    m = re.search(r"st\s+([^(]+)", dismissal_info)
                    if m:
                        raw_field = m.group(1).strip()
                        if " " in raw_field:
                            resolved = resolve_player_name(raw_field)
                            init_player(resolved)
                            init_game_player(resolved)
                            player_stats[resolved]['stumpings'] += 1
                            breakdown[resolved]['fielding']['stumpings'] += 1
                            field_contrib = {'type': 'stumping', 'from': player, 'dismissal': dismissal_info}
                            player_stats[resolved]['contributions']['fielding'].append(field_contrib)
                            breakdown[resolved]['fielding']['contributions'].append(field_contrib)
                        else:
                            pending_fielding.append({
                                'type': 'stumping',
                                'from': player,
                                'dismissal': dismissal_info,
                                'fielder': raw_field
                            })
                elif "run out" in dismissal_info:
                    m = re.search(r"run out\s*\(?([^)]*)\)?", dismissal_info)
                    if m:
                        raw_field = m.group(1).strip()
                        if "/" in raw_field:
                            raw_field = raw_field.split("/")[0].strip()
                        if " " in raw_field:
                            resolved = resolve_player_name(raw_field)
                            init_player(resolved)
                            init_game_player(resolved)
                            player_stats[resolved]['run_outs'] += 1
                            breakdown[resolved]['fielding']['run_outs'] += 1
                            field_contrib = {'type': 'run out', 'from': player, 'dismissal': dismissal_info}
                            player_stats[resolved]['contributions']['fielding'].append(field_contrib)
                            breakdown[resolved]['fielding']['contributions'].append(field_contrib)
                        else:
                            pending_fielding.append({
                                'type': 'run out',
                                'from': player,
                                'dismissal': dismissal_info,
                                'fielder': raw_field
                            })
    
    # ---------------------------
    # BOWLING SECTION: Tables 2 & 4 (indices 1 and 3)
    for idx in [1, 3]:
        table = tables[idx]
        rows = table.find_all('tr')
        for row in rows[1:]:
            cols = row.find_all('td')
            if len(cols) < 10:
                continue
            raw_player = cols[0].text.strip()
            player = clean_player_name(raw_player)
            try:
                overs = float(cols[1].text.strip())
            except Exception:
                overs = 0
            try:
                maidens = int(cols[2].text.strip())
            except Exception:
                maidens = 0
            try:
                wickets = int(cols[4].text.strip())
            except Exception:
                wickets = 0
            try:
                economy = float(cols[5].text.strip())
            except Exception:
                economy = 0
            try:
                dot_balls = int(cols[6].text.strip())
            except Exception:
                dot_balls = 0

            init_player(player)
            init_game_player(player)
            player_stats[player]['wickets'] += wickets
            player_stats[player]['maidens'] += maidens
            player_stats[player]['dot_balls'] += dot_balls
            
            breakdown[player]['bowling']['matches'] += 1
            breakdown[player]['bowling']['wickets'] += wickets
            breakdown[player]['bowling']['maidens'] += maidens
            breakdown[player]['bowling']['dot_balls'] += dot_balls
            
            delta_score = (a_params['wickets'] * wickets +
                           a_params['maidens'] * maidens +
                           a_params['dots_per_4'] * (math.floor(dot_balls / 4)) +
                           a_params['four_wickets'] * (1 if wickets >= 4 else 0) +
                           f(economy))
            player_stats[player]['score'] += delta_score
            breakdown[player]['bowling']['score'] += delta_score
            
            bowl_contrib = {
                'overs': overs,
                'maidens': maidens,
                'wickets': wickets,
                'economy': economy,
                'dot_balls': dot_balls,
                'delta_score': delta_score
            }
            player_stats[player]['contributions']['bowling'].append(bowl_contrib)
            breakdown[player]['bowling']['contributions'].append(bowl_contrib)
    
    # --- Player of the Match ---
    potm_section = soup.find(text=re.compile("Player Of The Match", re.I))
    if potm_section:
        potm_tag = potm_section.find_next('a')
        if potm_tag:
            potm = clean_player_name(potm_tag.text.strip())
            init_player(potm)
            init_game_player(potm)
            player_stats[potm]['score'] += a_params['player_of_match']
            breakdown[potm].setdefault('potm', 0)
            breakdown[potm]['potm'] += 1
            player_stats[potm]['contributions'].setdefault('potm', 0)
            player_stats[potm]['contributions']['potm'] += 1

    # ---------------------------
    # Process pending fielding events.
    for event in pending_fielding:
        surname = event["fielder"]
        candidate = None
        for key in player_stats.keys():
            _, last = split_name(key)
            if last.lower() == surname.lower() and player_stats[key]['first_name']:
                candidate = key
                break
        if candidate:
            resolved = candidate
            init_player(resolved)
            init_game_player(resolved)
            if event["type"] == "catch":
                player_stats[resolved]['catches'] += 1
                if resolved in breakdown:
                    breakdown[resolved]['fielding']['catches'] += 1
                    field_contrib = {'type': event["type"], 'from': event["from"], 'dismissal': event["dismissal"]}
                    player_stats[resolved]['contributions']['fielding'].append(field_contrib)
                    breakdown[resolved]['fielding']['contributions'].append(field_contrib)
            elif event["type"] == "stumping":
                player_stats[resolved]['stumpings'] += 1
                if resolved in breakdown:
                    breakdown[resolved]['fielding']['stumpings'] += 1
                    field_contrib = {'type': event["type"], 'from': event["from"], 'dismissal': event["dismissal"]}
                    player_stats[resolved]['contributions']['fielding'].append(field_contrib)
                    breakdown[resolved]['fielding']['contributions'].append(field_contrib)
            elif event["type"] == "run out":
                player_stats[resolved]['run_outs'] += 1
                if resolved in breakdown:
                    breakdown[resolved]['fielding']['run_outs'] += 1
                    field_contrib = {'type': event["type"], 'from': event["from"], 'dismissal': event["dismissal"]}
                    player_stats[resolved]['contributions']['fielding'].append(field_contrib)
                    breakdown[resolved]['fielding']['contributions'].append(field_contrib)
        else:
            new_player = surname.title()
            init_player(new_player)
            init_game_player(new_player)
            if event["type"] == "catch":
                player_stats[new_player]['catches'] += 1
                breakdown[new_player]['fielding']['catches'] += 1
                field_contrib = {'type': event["type"], 'from': event["from"], 'dismissal': event["dismissal"]}
                player_stats[new_player]['contributions']['fielding'].append(field_contrib)
                breakdown[new_player]['fielding']['contributions'].append(field_contrib)
            elif event["type"] == "stumping":
                player_stats[new_player]['stumpings'] += 1
                breakdown[new_player]['fielding']['stumpings'] += 1
                field_contrib = {'type': event["type"], 'from': event["from"], 'dismissal': event["dismissal"]}
                player_stats[new_player]['contributions']['fielding'].append(field_contrib)
                breakdown[new_player]['fielding']['contributions'].append(field_contrib)
            elif event["type"] == "run out":
                player_stats[new_player]['run_outs'] += 1
                breakdown[new_player]['fielding']['run_outs'] += 1
                field_contrib = {'type': event["type"], 'from': event["from"], 'dismissal': event["dismissal"]}
                player_stats[new_player]['contributions']['fielding'].append(field_contrib)
                breakdown[new_player]['fielding']['contributions'].append(field_contrib)
    pending_fielding.clear()

    # ---------------------------
    # Mark participation: each player in the match gets 1 match credit.
    for p in breakdown:
        if not breakdown[p].get('match_count_added', False):
            player_stats[p]['matches'] += 1
            breakdown[p]['match_count_added'] = True

    return breakdown

# ---------------------------
# Function to export global aggregated stats and game breakdowns to Excel.
def export_to_excel(player_stats, game_breakdowns, filename="IPL_Stats.xlsx"):
    totals_data = []
    for player, stats in player_stats.items():
        totals_data.append({
            "Player": player,
            "First Name": stats.get('first_name', ''),
            "Last Name": stats.get('last_name', ''),
            "Matches": stats['matches'],
            "Total Score": stats['score'],
            "Total Runs": stats.get('runs', 0),
            "Total Fours": stats.get('fours', 0),
            "Total Sixes": stats.get('sixes', 0),
            "Total Wickets": stats.get('wickets', 0),
            "Total Maidens": stats.get('maidens', 0),
            "Total Dot Balls": stats.get('dot_balls', 0),
            "Total Catches": stats.get('catches', 0),
            "Total Stumpings": stats.get('stumpings', 0),
            "Total Run Outs": stats.get('run_outs', 0)
        })
    totals_df = pd.DataFrame(totals_data)
    
    per_match_data = []
    for player, stats in player_stats.items():
        m = stats['matches'] if stats['matches'] > 0 else 1
        per_match_data.append({
            "Player": player,
            "First Name": stats.get('first_name', ''),
            "Last Name": stats.get('last_name', ''),
            "Matches": stats['matches'],
            "Average Score": stats['score'] / m,
            "Average Runs": stats.get('runs', 0) / m,
            "Average Fours": stats.get('fours', 0) / m,
            "Average Sixes": stats.get('sixes', 0) / m,
            "Average Wickets": stats.get('wickets', 0) / m,
            "Average Maidens": stats.get('maidens', 0) / m,
            "Average Dot Balls": stats.get('dot_balls', 0) / m,
            "Average Catches": stats.get('catches', 0) / m,
            "Average Stumpings": stats.get('stumpings', 0) / m,
            "Average Run Outs": stats.get('run_outs', 0) / m
        })
    per_match_df = pd.DataFrame(per_match_data)
    
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        totals_df.to_excel(writer, sheet_name="Totals", index=False)
        per_match_df.to_excel(writer, sheet_name="Per Match", index=False)
        for i, (url, breakdown) in enumerate(game_breakdowns, start=1):
            game_data = []
            for player, data in breakdown.items():
                game_data.append({
                    "Player": player,
                    "First Name": data.get('first_name', ''),
                    "Last Name": data.get('last_name', ''),
                    "Batting Matches": data['batting']['matches'],
                    "Runs": data['batting']['runs'],
                    "Fours": data['batting']['fours'],
                    "Sixes": data['batting']['sixes'],
                    "Batting Score": data['batting']['score'],
                    "Bowling Matches": data['bowling']['matches'],
                    "Wickets": data['bowling']['wickets'],
                    "Maidens": data['bowling']['maidens'],
                    "Dot Balls": data['bowling']['dot_balls'],
                    "Bowling Score": data['bowling']['score'],
                    "Catches": data['fielding'].get('catches', 0),
                    "Stumpings": data['fielding'].get('stumpings', 0),
                    "Run Outs": data['fielding'].get('run_outs', 0),
                    "POTM": data.get('potm', 0)
                })
            game_df = pd.DataFrame(game_data)
            sheet_name = f"Game_{i}"
            game_df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    print(f"Excel file '{filename}' has been created.")

# ---------------------------
# Main interactive loop.
def main():
    game_breakdowns = []
    while True:
        url = input("Enter a scorecard URL (or type 'stop' to finish): ").strip()
        if url.lower() == "stop":
            break
        if not url:
            continue
        print(f"Scraping: {url}")
        breakdown = scrape_ipl_scorecard(url)
        if breakdown:
            game_breakdowns.append((url, breakdown))
    
    export_to_excel(player_stats, game_breakdowns)

if __name__ == '__main__':
    main()
