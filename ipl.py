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
    "hundred": 16 - 8,
    "four_wickets": 10,
    "player_of_match": 0
}

def f(economy_rate):
    x=economy_rate
    if x<3:
        return 8
    elif x<4:
        return 6
    elif x<5:
        return 2
    elif x<6:
        return 0
    elif x<7:
        return 0
    elif x<8:
        return -4
    elif x<9:
        return -6
    elif x<10:
        return -10
    elif x<11:
        return -12
    elif x<12:
        return -12
    else:
        return -12

def g(strike_rate):
    x=strike_rate
    if x<70:
        return -8
    elif x<80:
        return -4
    elif x<100:
        return -2
    elif x<110:
        return 0
    elif x<120:
        return 2
    elif x<130:
        return 4
    elif x<140:
        return 6
    elif x<150:
        return 8
    elif x<160:
        return 10
    elif x<180:
        return 10
    elif x<200:
        return 12
    elif x<240:
        return 12
    else:
        return 12

player_stats = {}

def init_player(player):
    if player not in player_stats:
        player_stats[player] = {
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
            'contributions': {  # for debugging purposes (aggregated list)
                'batting': [],
                'bowling': [],
                'fielding': []
            }
        }

# ---------------------------
# Helper function to clean player names.
def clean_player_name(name):
    name = name.strip()
    # Remove any trailing parentheses and their contents, e.g., " (c)" or " (wk)"
    name = re.sub(r'\s*\(.*?\)\s*$', '', name)
    # Remove any trailing non-alphanumeric symbols (like "†")
    name = re.sub(r'[^A-Za-z0-9 ]+$', '', name)
    return name

# ---------------------------
# The scrape function returns a per-game breakdown dictionary.
def scrape_ipl_scorecard(url):
    # Local breakdown for this game.
    breakdown = {}
    
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

    # Helper to initialize breakdown for a player.
    def init_game_player(player):
        if player not in breakdown:
            breakdown[player] = {
                'batting': {'matches': 0, 'runs': 0, 'fours': 0, 'sixes': 0, 'score': 0, 'contributions': []},
                'bowling': {'matches': 0, 'wickets': 0, 'maidens': 0, 'dot_balls': 0, 'score': 0, 'contributions': []},
                'fielding': {'catches': 0, 'stumpings': 0, 'run_outs': 0}
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

            # Parse batting stats
            try:
                runs_text = cols[2].text.strip()
                runs = int(runs_text) if runs_text.isdigit() else 0
            except Exception as e:
                runs = 0
            try:
                fours_text = cols[5].text.strip()
                fours = int(fours_text) if fours_text.isdigit() else 0
            except Exception as e:
                fours = 0
            try:
                sixes_text = cols[6].text.strip()
                sixes = int(sixes_text) if sixes_text.isdigit() else 0
            except Exception as e:
                sixes = 0
            try:
                strike_rate_text = cols[7].text.strip()
                strike_rate = float(strike_rate_text) if strike_rate_text else 0
            except Exception as e:
                strike_rate = 0

            dismissal_info = cols[1].text.strip().lower()
            got_out = ('not out' not in dismissal_info)
            
            # Update global and breakdown stats for batting
            init_player(player)
            init_game_player(player)
            player_stats[player]['matches'] += 1
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
                # Check for catch (starts with "c ")
                if dismissal_info.startswith('c '):
                    m = re.search(r"c\s+([^(]+)", dismissal_info)
                    if m:
                        fielder = clean_player_name(m.group(1).strip())
                        init_player(fielder)
                        init_game_player(fielder)
                        player_stats[fielder]['catches'] += 1
                        breakdown[fielder]['fielding']['catches'] += 1
                        # Record fielding contribution
                        field_contrib = {'type': 'catch', 'from': player, 'dismissal': dismissal_info}
                        player_stats[fielder]['contributions']['fielding'].append(field_contrib)
                        breakdown[fielder]['fielding'].setdefault('contributions', []).append(field_contrib)
                # Check for stumping (starts with "st ")
                elif dismissal_info.startswith('st '):
                    m = re.search(r"st\s+([^(]+)", dismissal_info)
                    if m:
                        fielder = clean_player_name(m.group(1).strip())
                        init_player(fielder)
                        init_game_player(fielder)
                        player_stats[fielder]['stumpings'] += 1
                        breakdown[fielder]['fielding']['stumpings'] += 1
                        field_contrib = {'type': 'stumping', 'from': player, 'dismissal': dismissal_info}
                        player_stats[fielder]['contributions']['fielding'].append(field_contrib)
                        breakdown[fielder]['fielding'].setdefault('contributions', []).append(field_contrib)
                # Check for run out (if "run out" appears in the text)
                elif "run out" in dismissal_info:
                    m = re.search(r"run out\s*\(?([^)]*)\)?", dismissal_info)
                    if m:
                        fielder = clean_player_name(m.group(1).strip())
                        init_player(fielder)
                        init_game_player(fielder)
                        player_stats[fielder]['run_outs'] += 1
                        breakdown[fielder]['fielding']['run_outs'] += 1
                        field_contrib = {'type': 'run out', 'from': player, 'dismissal': dismissal_info}
                        player_stats[fielder]['contributions']['fielding'].append(field_contrib)
                        breakdown[fielder]['fielding'].setdefault('contributions', []).append(field_contrib)
    
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
            except Exception as e:
                overs = 0
            try:
                maidens = int(cols[2].text.strip())
            except Exception as e:
                maidens = 0
            # col[3] is runs conceded (ignored)
            try:
                wickets = int(cols[4].text.strip())
            except Exception as e:
                wickets = 0
            try:
                economy = float(cols[5].text.strip())
            except Exception as e:
                economy = 0
            try:
                dot_balls = int(cols[6].text.strip())
            except Exception as e:
                dot_balls = 0

            init_player(player)
            init_game_player(player)
            player_stats[player]['matches'] += 1
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

    return breakdown

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
    
    # Write results to an Excel file.
    # Sheet 1: Aggregated totals.
    totals_data = []
    for player, stats in player_stats.items():
        totals_data.append({
            "Player": player,
            "Matches": stats['matches'],
            "Score": stats['score'],
            "Runs": stats.get('runs', 0),
            "Fours": stats.get('fours', 0),
            "Sixes": stats.get('sixes', 0),
            "Wickets": stats.get('wickets', 0),
            "Maidens": stats.get('maidens', 0),
            "Dot Balls": stats.get('dot_balls', 0),
            "Catches": stats.get('catches', 0),
            "Stumpings": stats.get('stumpings', 0),
            "Run Outs": stats.get('run_outs', 0)
        })
    totals_df = pd.DataFrame(totals_data)

    # Create an Excel writer
    excel_file = "IPL_Stats.xlsx"
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        totals_df.to_excel(writer, sheet_name="Totals", index=False)
        # Create one sheet per game breakdown.
        for i, (url, breakdown) in enumerate(game_breakdowns, start=1):
            # For each game, build a DataFrame of players' game stats.
            game_data = []
            for player, data in breakdown.items():
                game_data.append({
                    "Player": player,
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
    
    print(f"Excel file '{excel_file}' has been created.")

if __name__ == '__main__':
    main()