from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import random
import csv

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

WORDS = []
with open("words_300.csv", encoding="utf-8") as f:
    reader = csv.reader(f)
    for row in reader:
        # Assuming no headers, just English,Greek columns
        WORDS.append({"english": row[0], "greek": row[1]})

state = {
    "game_board": [],
    "first_team": "",
    "map_visible": False,
    "main_language": "english",  # 'english' or 'greek'
}

def generate_board():
    # Remove duplicates by english+greek keys
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
        state["map_visible"] = False

    red_remaining = sum(1 for cell in state["game_board"] if cell["role"] == "red" and not cell["revealed"])
    blue_remaining = sum(1 for cell in state["game_board"] if cell["role"] == "blue" and not cell["revealed"])

    return templates.TemplateResponse(
        "board.html",
        {
            "request": request,
            "board": state["game_board"],
            "first_team": state["first_team"],
            "map_visible": state["map_visible"],
            "red_remaining": red_remaining,
            "blue_remaining": blue_remaining,
            "main_language": state["main_language"],
        },
    )

@app.post("/reveal")
async def reveal(idx: int = Form(...)):
    state["game_board"][idx]["revealed"] = True
    return RedirectResponse("/", status_code=303)

@app.post("/reset")
async def reset():
    board, first_team = generate_board()
    state["game_board"] = board
    state["first_team"] = first_team
    state["map_visible"] = False
    return RedirectResponse("/", status_code=303)

@app.post("/toggle_map")
async def toggle_map():
    state["map_visible"] = not state["map_visible"]
    return RedirectResponse("/", status_code=303)

@app.post("/set_language")
async def set_language(language: str = Form(...)):
    if language.lower() in ("english", "greek"):
        state["main_language"] = language.lower()
    return RedirectResponse("/", status_code=303)
