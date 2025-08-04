import random
import state
from network import send_message
from parser import build_message

WINNING_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),  # Horizontal
    (0, 3, 6), (1, 4, 7), (2, 5, 8),  # Vertical
    (0, 4, 8), (2, 4, 6)              # Diagonal
]

def print_board(board):
    print("\n-------------")
    for i in range(0, 9, 3):
        row = [cell if cell else str(i + j) for j, cell in enumerate(board[i:i+3])]
        print(f"| {row[0]} | {row[1]} | {row[2]} |")
        print("-------------")

def check_win(board, symbol):
    for line in WINNING_LINES:
        if all(board[pos] == symbol for pos in line):
            return ",".join(map(str, line))
    return None

def check_draw(board):
    return all(cell != '' for cell in board)

# --- handling game commands

def initiate_game(sock, my_id, opponent_id, verbose):
    game_id = f"g{random.randint(0, 255)}"
    my_symbol = random.choice(['X', 'O'])
    opponent_symbol = 'O' if my_symbol == 'X' else 'X'

    turn = opponent_id

    state.tictactoe_games[game_id] = {
        'board': [''] * 9,
        'players': {my_id: my_symbol, opponent_id: opponent_symbol},
        'my_symbol': my_symbol,
        'opponent': opponent_id,
        'turn': turn,
        'status': 'pending'
    }

    fields = {
        "TYPE": "TICTACTOE_INVITE", 
        "FROM": my_id, 
        "TO": opponent_id,
        "GAMEID": game_id, 
        "SYMBOL": opponent_symbol, 
        "TIMESTAMP": "9999", 
        "MESSAGE_ID": "msgidttt1"
    }
    ip = opponent_id.split('@')[1]
    send_message(sock, build_message(fields), ip, verbose)
    print(f"Tic-Tac-Toe invitation sent to {opponent_id} for game {game_id}.")
    print(f"Waiting for {opponent_id} to make the first move.")

def process_move(cmd, sock, args):
    try:
        _, game_id, pos_str = cmd.split(' ', 2)
        position = int(pos_str)
    except (ValueError, IndexError):
        print("Usage: move <game_id> <position(0-8)>")
        return
    
    if game_id not in state.tictactoe_games:
        print("Error: Invalid game ID.")
        return
    
    # error handling
    game = state.tictactoe_games[game_id]
    if game['status'] == 'finished':
        print("Error: This game is already over.")
        return
    if game['turn'] != args.id:
        print("Error: It's not your turn")
        return
    if not (0 <= position <= 8 and game['board'][position] == ''):
        print("Error: Invalid or occupied position.")
        return
    
    # update local board and game status
    game['board'][position] = game['my_symbol']
    game['status'] = 'active'

    # check win / draw
    winning_line = check_win(game['board'], game['my_symbol'])
    if winning_line:
        result_type = "TICTACTOE_RESULT"
        result_type = {
            "RESULT": "WIN", 
            "WINNING_LINE": winning_line, 
            "SYMBOL": game['my_symbol']
        }
        print("You won!")
    elif check_draw(game['board']):
        result_type = "TICTACTOE_RESULT"
        result_fields = {"RESULT": "DRAW"}
        print("It's a draw!")
    else:
        result_type = "TICTACTOE_MOVE"
        result_fields = {
            "POSITION": position, 
            "SYMBOL": game['my_symbol']
        }
        game['turn'] = game['opponent']

    # send message
    fields = {
        "TYPE": result_type, 
        "FROM": args.id, 
        "TO": game['opponent'],
        "GAMEID": game_id, **result_fields
    }
    ip = game['opponent'].split('@')[1]
    send_message(sock, build_message(fields), ip, args.verbose)
    print_board(game['board'])

# --- handle game messages

def handle_invite(msg):
    # --- Start of Changed Code ---
    game_id = msg.get("GAMEID")
    from_id = msg.get("FROM") # person who started the game
    my_id = msg.get("TO")     # person (you) who accepted the game

    # The SYMBOL field contains user's (invitee's) symnbol
    my_symbol = msg.get("SYMBOL")
    opponent_symbol = 'O' if my_symbol == 'X' else 'X'

    # invitee goes first
    turn = my_id

    state.tictactoe_games[game_id] = {
        'board': [''] * 9,
        'players': {from_id: opponent_symbol, my_id: my_symbol},
        'my_symbol': my_symbol,
        'opponent': from_id,
        'turn': turn,
        'status': 'pending'
    }
    print(f"\n{from_id} is inviting you to play Tic-Tac-Toe (Game ID: {game_id}).")
    print(f"It is your turn. You are '{my_symbol}'. To move, type: move {game_id} <0-8>")
    print(f"> ", end="", flush=True)

def handle_move(msg):
    game_id = msg.get("GAMEID")
    if game_id in state.tictactoe_games:
        game = state.tictactoe_games[game_id]
        position = int(msg.get("POSITION"))
        symbol = msg.get("SYMBOL")

        game['board'][position] = symbol
        game['turn'] = msg.get("TO")
        game['status'] = 'active'

        print(f"\nMove received for game {game_id}.")
        print_board(game['board'])
        print("It's your turn.")
        print(f"> ", end="", flush=True)

def handle_result(msg):
    game_id = msg.get("GAMEID")
    if game_id in state.tictactoe_games:
        game = state.tictactoe_games[game_id]
        result = msg.get("RESULT")

        # update board with final move if win
        if result == "WIN":
            winning_symbol = msg.get("SYMBOL")

            # find move not on board yet
            remote_board = game['board'][:]
            positions_on_line = msg.get("WINNING_LINE").split(',')
            for pos in positions_on_line:
                if remote_board[int(pos)] != winning_symbol:
                    remote_board[int(pos)] = winning_symbol
                    break
            game['board'] = remote_board

        game['status'] = 'finished'

        print(f"\nGame Over: {game_id}")
        print_board(game['board'])
        if result == "WIN":
            print("You lose.")
        elif result == "DRAW":
            print("It's a draw.")
        
        print(f"> ", end="", flush=True)