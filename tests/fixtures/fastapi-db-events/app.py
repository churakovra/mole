from fastapi import FastAPI, Depends, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session
import asyncio
import aio_pika

app = FastAPI()

@app.post('/orders')
async def create_order(session: Session, tasks: BackgroundTasks, exchange: aio_pika.Exchange):
    try:
        session.add({'order': 'candidate'})
        session.commit()
        tasks.add_task(deliver, exchange)
        return {'status': 'scheduled'}
    except Exception:
        session.rollback()
        raise

async def deliver(exchange: aio_pika.Exchange):
    await asyncio.wait_for(exchange.publish(message), timeout=3)
