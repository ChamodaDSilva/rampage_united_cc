from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from bson.objectid import ObjectId
import os

app = Flask(__name__)
app.secret_key = 'rampage_united_secret_key'  # Change this in production

# MongoDB Connection
# MongoDB Connection (Atlas)
client = MongoClient(
    'mongodb+srv://chamodadsilva_db_user:OLvzB1R2tPmUWwK6@cluster0.y6xyc8l.mongodb.net/?retryWrites=true&w=majority'
)

db = client['rampage_united_cc']


# Collections
users_collection = db['users']
players_collection = db['players']
matches_collection = db['matches']

def overs_to_balls(overs):
    full_overs = int(overs)
    balls = int(round((overs - full_overs) * 10))
    if balls >= 6:
        raise ValueError("Invalid overs input: decimal part must be < 0.6")
    return full_overs * 6 + balls

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # Simple hardcoded check for demonstration, or check against DB
        # For now, let's just allow any login or a specific admin
        if username == 'admin' and password == 'admin':
            session['username'] = username
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/players')
def list_players():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    search_query = request.args.get('search', '')
    if search_query:
        # Case-insensitive search
        players = list(players_collection.find({'name': {'$regex': search_query, '$options': 'i'}}))
    else:
        players = list(players_collection.find())
        
    return render_template('players.html', players=players, search_query=search_query)

@app.route('/players/add', methods=['POST'])
def add_player():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    player_data = {
        'name': request.form['name'],
        'role': request.form['role'],
        'batting_style': request.form['batting_style'],
        'bowling_style': request.form['bowling_style'],
        'fees_pending': int(request.form.get('fees_pending', 0)),
        'stats': {
            'matches': 0,
            'runs': 0,
            'wickets': 0,
            'balls_faced': 0,
            'runs_conceded': 0,
            'overs': 0.0,
            'balls_bowled': 0,
            'innings_batted': 0,
            'innings_bowled': 0,
            'not_outs': 0
        }
    }
    players_collection.insert_one(player_data)
    flash('Player added successfully!')
    return redirect(url_for('list_players'))


@app.route('/players/edit/<player_id>', methods=['GET', 'POST'])
def edit_player(player_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        updated_data = {
            'name': request.form['name'],
            'role': request.form['role'],
            'batting_style': request.form['batting_style'],
            'bowling_style': request.form['bowling_style'],
            'fees_pending': int(request.form.get('fees_pending', 0))
        }
        players_collection.update_one({'_id': ObjectId(player_id)}, {'$set': updated_data})
        flash('Player updated successfully!')
        return redirect(url_for('list_players'))
        
    player = players_collection.find_one({'_id': ObjectId(player_id)})
    return render_template('edit_player.html', player=player)

@app.route('/matches')
def list_matches():
    if 'username' not in session:
        return redirect(url_for('login'))
    matches = list(matches_collection.find())
    return render_template('matches.html', matches=matches)

@app.route('/matches/add', methods=['POST'])
def add_match():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    match_data = {
        'date': request.form['date'],
        'opponent': request.form['opponent'],
        'venue': request.form['venue'],
        'result': request.form['result'],
        'performances': []
    }
    matches_collection.insert_one(match_data)
    flash('Match added successfully!')
    return redirect(url_for('list_matches'))

def revert_match_stats(match):
    """Helper function to revert stats for all players in a match."""
    if match and 'performances' in match:
        for old_perf in match['performances']:
            try:
                # Safely calculate balls for revert, handling potential bad legacy data
                old_overs = old_perf.get('overs', 0.0)
                try:
                    old_balls = overs_to_balls(old_overs)
                except ValueError:
                    # Fallback for bad data (e.g. 1.7) -> treat as 1*6 + 7
                    full = int(old_overs)
                    dec = int(round((old_overs - full) * 10))
                    old_balls = full * 6 + dec

                # Innings logic for revert
                innings_batted_dec = 0
                if int(old_perf.get('balls_faced', 0)) > 0 or int(old_perf.get('runs', 0)) > 0 or old_perf.get('is_not_out', False):
                    innings_batted_dec = -1
                
                innings_bowled_dec = 0
                if old_balls > 0:
                    innings_bowled_dec = -1
                
                not_out_dec = 0
                if old_perf.get('is_not_out', False):
                    not_out_dec = -1

                players_collection.update_one(
                    {'_id': ObjectId(old_perf['player_id'])},
                    {
                        '$inc': {
                            'stats.matches': -1,
                            'stats.runs': -int(old_perf.get('runs', 0)),
                            'stats.balls_faced': -int(old_perf.get('balls_faced', 0)),
                            'stats.wickets': -int(old_perf.get('wickets', 0)),
                            'stats.runs_conceded': -int(old_perf.get('runs_conceded', 0)),
                            'stats.balls_bowled': -old_balls,
                            'stats.innings_batted': innings_batted_dec,
                            'stats.innings_bowled': innings_bowled_dec,
                            'stats.not_outs': not_out_dec
                        }
                    }
                )
            except Exception as e:
                print(f"Error reverting stats for player {old_perf.get('player_id')}: {e}")

@app.route('/matches/delete/<match_id>', methods=['POST'])
def delete_match(match_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    match = matches_collection.find_one({'_id': ObjectId(match_id)})
    if match:
        revert_match_stats(match)
        matches_collection.delete_one({'_id': ObjectId(match_id)})
        flash('Match deleted and stats reverted successfully!')
    else:
        flash('Match not found.')
        
    return redirect(url_for('list_matches'))

@app.route('/players/delete/<player_id>', methods=['POST'])
def delete_player(player_id):
    if 'username' not in session:
        return redirect(url_for('login'))
        
    players_collection.delete_one({'_id': ObjectId(player_id)})
    flash('Player deleted successfully!')
    return redirect(url_for('list_players'))

@app.route('/matches/<match_id>/performance', methods=['GET', 'POST'])
def match_performance(match_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    match = matches_collection.find_one({'_id': ObjectId(match_id)})
    players = list(players_collection.find())
    
    if request.method == 'POST':
        total_players = int(request.form.get('total_players', 0))
        new_performances = []
        
        # Revert existing stats for this match from players
        revert_match_stats(match)

        # Clear existing performances for this match to avoid duplicates if re-submitting
        matches_collection.update_one(
            {'_id': ObjectId(match_id)},
            {'$set': {'performances': []}}
        )
        
        for i in range(1, total_players + 1):
            played_val = request.form.get(f'played_{i}')
            if played_val:
                player_id = request.form.get(f'player_id_{i}')
                player_name = request.form.get(f'player_name_{i}')
                
                runs = int(request.form.get(f'runs_{i}', 0))
                balls_faced = int(request.form.get(f'balls_faced_{i}', 0))
                overs = float(request.form.get(f'overs_{i}', 0))
                maidens = int(request.form.get(f'maidens_{i}', 0))
                runs_conceded = int(request.form.get(f'runs_conceded_{i}', 0))
                wickets = int(request.form.get(f'wickets_{i}', 0))
                catches = int(request.form.get(f'catches_{i}', 0))
                is_not_out = True if request.form.get(f'not_out_{i}') else False
                
                try:
                    balls_bowled = overs_to_balls(overs)
                except ValueError as e:
                    flash(f'Error for {player_name}: {str(e)}')
                    # In a real app we should revert the revert here! But for MVP...
                    return redirect(url_for('match_performance', match_id=match_id))

                perf_data = {
                    'player_id': player_id,
                    'player_name': player_name,
                    'runs': runs,
                    'balls_faced': balls_faced,
                    'overs': overs,
                    'maidens': maidens,
                    'runs_conceded': runs_conceded,
                    'wickets': wickets,
                    'catches': catches,
                    'is_not_out': is_not_out
                }
                
                new_performances.append(perf_data)
                
                # Innings logic for add
                innings_batted_inc = 0
                if balls_faced > 0 or runs > 0 or is_not_out:
                    innings_batted_inc = 1
                
                innings_bowled_inc = 0
                if balls_bowled > 0:
                    innings_bowled_inc = 1
                
                not_out_inc = 0
                if is_not_out:
                    not_out_inc = 1
                
                # Update player stats
                players_collection.update_one(
                    {'_id': ObjectId(player_id)},
                    {
                        '$inc': {
                            'stats.matches': 1,
                            'stats.runs': runs,
                            'stats.balls_faced': balls_faced,
                            'stats.wickets': wickets,
                            'stats.runs_conceded': runs_conceded,
                            'stats.balls_bowled': balls_bowled,
                            'stats.innings_batted': innings_batted_inc,
                            'stats.innings_bowled': innings_bowled_inc,
                            'stats.not_outs': not_out_inc
                        }
                    }
                )

        if new_performances:
            matches_collection.update_one(
                {'_id': ObjectId(match_id)},
                {'$push': {'performances': {'$each': new_performances}}}
            )
            flash(f'Performances recorded for {len(new_performances)} players!')
        else:
            flash('No players selected.')
            
        return redirect(url_for('match_performance', match_id=match_id))
        
    # Create a map of existing performances for easy lookup in the template
    performances_map = {}
    if match and 'performances' in match:
        for perf in match['performances']:
            performances_map[str(perf['player_id'])] = perf
            
    return render_template('match_performance.html', match=match, players=players, performances_map=performances_map)

if __name__ == "__main__":
    app.run(host="0.0.0.0" , debug=True)

