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
    "players": {"red": [], "blue": []}
}

connected_clients: Set[WebSocket] = set()

def generate_board():
    unique_words = list({(w['english'], w['greek']): w for w in WORDS}.values())
    if len(unique_words) < 25:
        raise ValueError("Not enough unique words to generate board!")

    selected = random.sample(unique_words, 25)
    first_team = random.choice(["red", "blue"])
    second_team = "blue" if first_team == "red" else "red"

    roles = (
        [first_team]*9 +
        [second_team]*8 +
        ["neutral"]*7 +
        ["assassin"]
    )
    random.shuffle(roles)

    board = [
        {
            "word_en": w["english"],
            "word_gr": w["greek"],
            "role": r,
            "revealed": False
        }
        for w, r in zip(selected, roles)
    ]
    return board, first_team

@app.get("/", response_class=HTMLResponse)
async def main(request: Request):
    if not state["game_board"]:
        board, first_team = generate_board()
        state["game_board"] = board
        state["first_team"] = first_team

    red_remaining = sum(1 for cell in state["game_board"] if cell["role"] == "red" and not cell["revealed"])
    blue_remaining = sum(1 for cell in state["game_board"] if cell["role"] == "blue" and not cell["revealed"])

    return templates.TemplateResponse(
        "board.html",
        {
            "request": request,
            "board": state["game_board"],
            "first_team": state["first_team"],
            "red_remaining": red_remaining,
            "blue_remaining": blue_remaining,
            "main_language": state["main_language"],
            "players": state["players"],
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

async def broadcast_reload():
    disconnected = set()
    for client in connected_clients:
        try:
            await client.send_text("reload")
        except Exception:
            disconnected.add(client)
    for client in disconnected:
        connected_clients.remove(client)

@app.post("/reveal")
async def reveal(idx: int = Form(...)):
    state["game_board"][idx]["revealed"] = True
    await broadcast_reload()
    return RedirectResponse("/", status_code=303)

@app.post("/reset")
async def reset():
    board, first_team = generate_board()
    state["game_board"] = board
    state["first_team"] = first_team
    state["players"] = {"red": [], "blue": []}
    await broadcast_reload()
    return RedirectResponse("/", status_code=303)

@app.post("/set_language")
async def set_language(language: str = Form(...)):
    if language.lower() in ("english", "greek"):
        state["main_language"] = language.lower()
    await broadcast_reload()
    return RedirectResponse("/", status_code=303)

@app.post("/add_player")
async def add_player(name: str = Form(...), team: str = Form(...)):
    team = team.lower()
    if team in ("red", "blue") and name.strip():
        if name.strip() not in state["players"][team]:
            state["players"][team].append(name.strip())
    await broadcast_reload()
    return RedirectResponse("/", status_code=303)

@app.post("/randomize_players")
async def randomize_players():
    all_players = state["players"]["red"] + state["players"]["blue"]
    random.shuffle(all_players)
    half = len(all_players) // 2
    state["players"]["red"] = all_players[:half]
    state["players"]["blue"] = all_players[half:]
    await broadcast_reload()
    return RedirectResponse("/", status_code=303)

@app.post("/clear_players")
async def clear_players():
    state["players"]["red"] = []
    state["players"]["blue"] = []
    await broadcast_reload()
    return RedirectResponse("/", status_code=303)
