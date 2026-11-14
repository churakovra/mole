from fastapi import FastAPI
from settlement import settle

app = FastAPI()


@app.post('/games/complete')
async def complete_game(payload):
    if not payload.get('verified'):
        raise ValueError('verification required')
    return settle(payload['player'], payload['score'])
