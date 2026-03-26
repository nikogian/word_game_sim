import socket
from fastapi import FastAPI, Request, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Set
import random
import csv

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

WORDS = []
with open("words_300.csv", encoding="utf-8") as f:
    reader = csv.reader(f)
    for row in reader:
        WORDS.append({"english": row[0], "greek": row[1]})

state = {
    "game_board": [],
    "first_team": "",
    "main_language": "english",
    "players": {"red": [], "blue": []},
    "current_team": "",
    "round_number": 1,
    "red_score": 0,
    "blue_score": 0,
    "mode": "normal",
    "overtime": False,
    "timer_duration": 150,   # seconds, configurable
    "game_over": False,
    "winner": "",
    "win_reason": "",
}

connected_clients: Set[WebSocket] = set()


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "localhost"
    return ip


def get_points_for_team(first_team, current_team, round_number):
    if current_team == first_team:
        return 2 * round_number - 1
    else:
        return 2 * round_number


def advance_turn(state):
    first_team = state["first_team"]
    second_team = "blue" if first_team == "red" else "red"
    if state["current_team"] == second_team:
        state["round_number"] += 1
        state["current_team"] = first_team
    else:
        state["current_team"] = second_team
    state["overtime"] = False


def check_game_over_normal(state):
    board = state["game_board"]
    # Assassin revealed → other team wins
    for cell in board:
        if cell["role"] == "assassin" and cell["revealed"]:
            winner = "blue" if state["current_team"] == "red" else "red"
            state["game_over"] = True
            state["winner"] = winner
            state["win_reason"] = "assassin"
            return
    # All red revealed
    red_left = sum(1 for c in board if c["role"] == "red" and not c["revealed"])
    if red_left == 0:
        state["game_over"] = True
        state["winner"] = "red"
        state["win_reason"] = "all_words_found"
        return
    # All blue revealed
    blue_left = sum(1 for c in board if c["role"] == "blue" and not c["revealed"])
    if blue_left == 0:
        state["game_over"] = True
        state["winner"] = "blue"
        state["win_reason"] = "all_words_found"
        return


def check_game_over_alternative(state):
    board = state["game_board"]
    # Black revealed → other team wins
    for cell in board:
        if cell["role"] == "black" and cell["revealed"]:
            winner = "blue" if state["current_team"] == "red" else "red"
            state["game_over"] = True
            state["winner"] = winner
            state["win_reason"] = "black_revealed"
            return
    # No white words left
    white_left = sum(1 for c in board if c["role"] == "white" and not c["revealed"])
    if white_left == 0:
        if state["red_score"] > state["blue_score"]:
            winner = "red"
        elif state["blue_score"] > state["red_score"]:
            winner = "blue"
        else:
            winner = "draw"
        state["game_over"] = True
        state["winner"] = winner
        state["win_reason"] = "all_words_found"
        return


def generate_normal_board(first_team=None):
    unique_words = list({(w['english'], w['greek']): w for w in WORDS}.values())
    if len(unique_words) < 25:
        raise ValueError("Not enough unique words!")
    selected = random.sample(unique_words, 25)
    if first_team is None:
        first_team = random.choice(["red", "blue"])
    second_team = "blue" if first_team == "red" else "red"
    roles = ([first_team]*9 + [second_team]*8 + ["neutral"]*7 + ["assassin"])
    random.shuffle(roles)
    board = [
        {
            "word_en": w["english"],
            "word_gr": w["greek"],
            "role": r,
            "revealed": False,
            "assigned_team": None,
        }
        for w, r in zip(selected, roles)
    ]
    return board, first_team


def generate_alternative_board():
    unique_words = list({(w['english'], w['greek']): w for w in WORDS}.values())
    if len(unique_words) < 25:
        raise ValueError("Not enough unique words!")
    selected = random.sample(unique_words, 25)
    roles = ["black"] * 4 + ["white"] * 21
    random.shuffle(roles)
    board = [
        {
            "word_en": w["english"],
            "word_gr": w["greek"],
            "role": r,
            "revealed": False,
            "assigned_team": None,
        }
        for w, r in zip(selected, roles)
    ]
    return board


@app.get("/", response_class=HTMLResponse)
async def main(request: Request):
    if not state["game_board"]:
        if state["mode"] == "alternative":
            board = generate_alternative_board()
            first_team = random.choice(["red", "blue"])
        else:
            board, first_team = generate_normal_board()
        state["game_board"] = board
        state["first_team"] = first_team
        state["current_team"] = first_team
        state["round_number"] = 1
        state["red_score"] = 0
        state["blue_score"] = 0
        state["overtime"] = False
        state["game_over"] = False
        state["winner"] = ""
        state["win_reason"] = ""

    current_points = get_points_for_team(
        state["first_team"], state["current_team"], state["round_number"]
    )
    red_remaining = sum(1 for c in state["game_board"] if c["role"] == "red" and not c["revealed"])
    blue_remaining = sum(1 for c in state["game_board"] if c["role"] == "blue" and not c["revealed"])

    return templates.TemplateResponse(
        "board.html",
        {
            "request": request,
            "board": state["game_board"],
            "first_team": state["first_team"],
            "current_team": state["current_team"],
            "round_number": state["round_number"],
            "current_points": current_points,
            "red_score": state["red_score"],
            "blue_score": state["blue_score"],
            "red_remaining": red_remaining,
            "blue_remaining": blue_remaining,
            "main_language": state["main_language"],
            "players": state["players"],
            "local_ip": get_local_ip(),
            "mode": state["mode"],
            "overtime": state["overtime"],
            "timer_duration": state["timer_duration"],
            "game_over": state["game_over"],
            "winner": state["winner"],
            "win_reason": state["win_reason"],
        },
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        connected_clients.remove(websocket)


async def broadcast(message: str):
    disconnected = set()
    for client in connected_clients:
        try:
            await client.send_text(message)
        except Exception:
            disconnected.add(client)
    for client in disconnected:
        connected_clients.remove(client)


@app.post("/reveal")
async def reveal(idx: int = Form(...)):
    if state["game_over"]:
        return RedirectResponse("/", status_code=303)
    cell = state["game_board"][idx]
    if not cell["revealed"]:
        cell["revealed"] = True
        # White/neutral word in normal mode → end turn
        if cell["role"] in ("neutral", "blue", "red"):
            if cell["role"] != state["current_team"]:
                advance_turn(state)
        check_game_over_normal(state)
    await broadcast("reload")
    return RedirectResponse("/", status_code=303)


@app.post("/reveal_black")
async def reveal_black(idx: int = Form(...)):
    if state["game_over"]:
        return RedirectResponse("/", status_code=303)
    cell = state["game_board"][idx]
    if cell["role"] == "black" and not cell["revealed"]:
        cell["revealed"] = True
        check_game_over_alternative(state)
    await broadcast("reload")
    return RedirectResponse("/", status_code=303)


@app.post("/reveal_white")
async def reveal_white(idx: int = Form(...)):
    if state["game_over"]:
        return RedirectResponse("/", status_code=303)
    cell = state["game_board"][idx]
    if cell["role"] == "white" and not cell["revealed"]:
        team = state["current_team"]
        cell["assigned_team"] = team
        cell["revealed"] = True
        points = get_points_for_team(
            state["first_team"], state["current_team"], state["round_number"]
        )
        if team == "red":
            state["red_score"] += points
        else:
            state["blue_score"] += points
        check_game_over_alternative(state)
    await broadcast("reload")
    return RedirectResponse("/", status_code=303)


@app.post("/end_turn")
async def end_turn():
    if not state["game_over"]:
        advance_turn(state)
    await broadcast("reload")
    return RedirectResponse("/", status_code=303)


@app.post("/timer_expired")
async def timer_expired():
    await broadcast("timer_expired")
    return {"status": "ok"}


@app.post("/keep_turn")
async def keep_turn():
    state["overtime"] = True
    await broadcast("keep_turn")
    return RedirectResponse("/", status_code=303)


@app.post("/set_timer")
async def set_timer(duration: int = Form(...)):
    if 10 <= duration <= 600:
        state["timer_duration"] = duration
    # Reset timer state by broadcasting reload
    await broadcast("reload")
    return RedirectResponse("/", status_code=303)


@app.post("/set_mode")
async def set_mode(mode: str = Form(...)):
    if mode in ("normal", "alternative"):
        state["mode"] = mode
        state["game_board"] = []
        state["first_team"] = ""
        state["current_team"] = ""
        state["round_number"] = 1
        state["red_score"] = 0
        state["blue_score"] = 0
        state["overtime"] = False
        state["game_over"] = False
        state["winner"] = ""
        state["win_reason"] = ""
    await broadcast("reload")
    return RedirectResponse("/", status_code=303)


@app.post("/reset")
async def reset():
    if state["mode"] == "alternative":
        board = generate_alternative_board()
        first_team = random.choice(["red", "blue"])
    else:
        board, first_team = generate_normal_board()
    state["game_board"] = board
    state["first_team"] = first_team
    state["current_team"] = first_team
    state["round_number"] = 1
    state["red_score"] = 0
    state["blue_score"] = 0
    state["overtime"] = False
    state["game_over"] = False
    state["winner"] = ""
    state["win_reason"] = ""
    state["players"] = {"red": [], "blue": []}
    await broadcast("reload")
    return RedirectResponse("/", status_code=303)


@app.post("/soft_reset")
async def soft_reset():
    old_first = state["first_team"]
    new_first = "blue" if old_first == "red" else "red"
    if state["mode"] == "alternative":
        board = generate_alternative_board()
    else:
        board, new_first = generate_normal_board(first_team=new_first)
    state["game_board"] = board
    state["first_team"] = new_first
    state["current_team"] = new_first
    state["round_number"] = 1
    state["red_score"] = 0
    state["blue_score"] = 0
    state["overtime"] = False
    state["game_over"] = False
    state["winner"] = ""
    state["win_reason"] = ""
    await broadcast("reload")
    return RedirectResponse("/", status_code=303)


@app.post("/set_language")
async def set_language(language: str = Form(...)):
    if language.lower() in ("english", "greek"):
        state["main_language"] = language.lower()
    await broadcast("reload")
    return RedirectResponse("/", status_code=303)


@app.post("/add_player")
async def add_player(name: str = Form(...), team: str = Form(...)):
    team = team.lower()
    if team in ("red", "blue") and name.strip():
        if name.strip() not in state["players"][team]:
            state["players"][team].append(name.strip())
    await broadcast("reload")
    return RedirectResponse("/", status_code=303)


@app.post("/randomize_players")
async def randomize_players():
    all_players = state["players"]["red"] + state["players"]["blue"]
    random.shuffle(all_players)
    half = len(all_players) // 2
    state["players"]["red"] = all_players[:half]
    state["players"]["blue"] = all_players[half:]
    await broadcast("reload")
    return RedirectResponse("/", status_code=303)


@app.post("/clear_players")
async def clear_players():
    state["players"]["red"] = []
    state["players"]["blue"] = []
    await broadcast("reload")
    return RedirectResponse("/", status_code=303)
