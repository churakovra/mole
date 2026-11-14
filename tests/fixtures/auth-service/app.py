"""Static fixture only. The engine must never execute this module."""
from fastapi import FastAPI, Depends

app = FastAPI()


def verify_jwt(token):
    if not token:
        raise ValueError('token missing')
    return {'subject': token}


@app.get('/profile')
async def profile(identity=Depends(verify_jwt)):
    return identity
