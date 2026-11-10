from fastapi import APIRouter
from service import execute as run_order
from sqlalchemy.orm import Session
import aio_pika
router = APIRouter()

@router.post('/orders')
async def create_order(session: Session, exchange: aio_pika.Exchange):
    return await run_order(session, exchange)
