import asyncio
import logging
import time
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from mud.server.manager import Mud, get_mud

logger = logging.getLogger(__name__)
app = FastAPI()

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Mud</title>
    </head>
    <body>
        <h1>Steve's Game</h1>
        <h2>Your ID: <span id="ws-id"></span></h2>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var client_id = Date.now()
            document.querySelector("#ws-id").textContent = client_id;
            var ws = new WebSocket(`ws://localhost:8000/ws/${client_id}`);
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages')
                var message = document.createElement('li')
                var content = document.createTextNode(event.data)
                message.appendChild(content)
                messages.appendChild(message)
            };
            function sendMessage(event) {
                var input = document.getElementById("messageText")
                ws.send(input.value)
                input.value = ''
                event.preventDefault()
            }
        </script>
    </body>
</html>
"""


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_text(self, websocket: WebSocket, message: str):
        try:
            await websocket.send_text(message)
        except RuntimeError:
            self.disconnect(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


class GameLoop:

    game: Mud

    def __init__(self, game):
        self.game = game
        self.time = time.time()
        self.tick = 1000  # ms

    async def run(self):
        # initial time to wait before starting to update game
        await asyncio.sleep(5)

        while True:
            t0 = time.perf_counter_ns()

            await self.game.update()

            t1 = time.perf_counter_ns()

            await asyncio.sleep((self.tick - ((t1 - t0) / 1000000)) / 1000)


manager = ConnectionManager()
game_loop = GameLoop(get_mud(manager))


@app.get("/")
async def get():
    return HTMLResponse(html)


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    await manager.connect(websocket)

    mud = get_mud(manager)
    await mud.connect(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            await mud.handler(websocket, data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        mud.disconnect(websocket)
        await manager.broadcast(f"Client #{client_id} left the chat")


@app.on_event("startup")
async def app_startup():

    # create the MUD game instance
    get_mud(manager)

    logger.info("creating game loop in background task")
    asyncio.create_task(game_loop.run())
