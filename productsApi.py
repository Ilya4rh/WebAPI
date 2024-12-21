from fastapi import FastAPI, Depends, BackgroundTasks, WebSocket, HTTPException
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import ProductDB
from database import AsyncSessionLocal, init_db, close_db
import json
from parser import get_all_products_info
from pydantic import BaseModel
from typing import AsyncGenerator
import asyncio
import datetime
from starlette.websockets import WebSocketDisconnect
import json


class ConnectionManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)

    async def broadcast(self, data: str):
        for connect in self.connections:
            await connect.send_text(data);



manager = ConnectionManager();


# Функция выполняющаяся при запуске приложения и управляющая его жизненным циклом
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Инициализируем базу данных
    await init_db()
    # Добавляем фоновую задачу на работу парсера с временным промежутком в 2 часа
    app.state.background_task = asyncio.create_task(background_parser_async(2 * 60 * 60))

    yield

    # Закрываем базу данных, после окончания работы приложения
    await close_db()


# Создаём приложение с написанной функцией жизненного цикла
app = FastAPI(lifespan=lifespan)


# Создаём сессию для работы с базой данных
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as db:
        yield db


# фоновая задача для запуска парсера
async def background_parser_async(delay_in_second: int):
    # Создаём сессию с базой данных
    async with AsyncSessionLocal() as db:
        while True:
            # Указываем время задержки работы
            await asyncio.sleep(delay_in_second)
            print(f"Parser start. Time start: {datetime.datetime.now().time()}")
            # Запускаем парсер
            products = await parser(db)
            print(f"Parser end. Add {len(products)} products. Time end: {datetime.datetime.now().time()}")
            await manager.broadcast(f"Background parser parsed {len(products)} products")


# Асинхронная функция парсера
async def parser(db: AsyncSession):
    # Асинхронно запуска парсер и получаем результат его работы
    all_products = await asyncio.to_thread(get_all_products_info)

    # Проходимся циклом по полученным товарам
    for product in all_products:
        # Ищем по коду товар в базе данных
        existing_product = await db.execute(select(ProductDB).filter(ProductDB.code == product.code))
        existing_product = existing_product.scalar_one_or_none()

        # Если в базе данных есть товар с таким кодом, то обновляем его поля
        if existing_product:
            existing_product.name = product.name
            existing_product.price = product.price
            existing_product.currency = product.currency
        # Иначе создаем новый товар и добавляем его в базу данных
        else:
            db_product = ProductDB(
                code=product.code,
                name=product.name,
                price=product.price,
                currency=product.currency
            )
            db.add(db_product)

    await db.commit()

    return all_products;


# Модели для запросов и отетов эндпоинтов
class ProductBase(BaseModel):
    code: int
    name: str
    price: int
    currency: str

    class Config:
        from_attributes = True

class ProductCreate(ProductBase):
    pass

class Product(ProductBase):
    id: int


# Асинхронный эндпоинт для получения информации о всех товарах
@app.get("/api/products", response_model=list[Product])
async def get_products(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ProductDB))
    products = result.scalars().all()

    await manager.broadcast(f"Get Products: {json.dumps([product.to_dict() for product in products], ensure_ascii=False)}")

    return products


# Асинхронный эндпоинт для получения информации об одном товаре по Id
@app.get("/api/products/{product_id}", response_model=Product)
async def get_product_by_id(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ProductDB).filter(ProductDB.id == product_id))
    product = result.scalar_one_or_none()

    # Если товар не найден, то кидаем 404, с соответствующим сообщением
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    await manager.broadcast(f"Get Product by Id: {json.dumps(product.to_dict(), ensure_ascii=False)}")

    return product


# Асинхронный эндпоинт для добавления нового товара
@app.post("/api/products/add_product", response_model=Product)
async def add_product(product: ProductCreate, db: AsyncSession = Depends(get_db)):
    # Проверяем, существует ли уже товар с таким кодом
    existing_product = await db.execute(select(ProductDB).filter(ProductDB.code == product.code))
    existing_product = existing_product.scalar_one_or_none()

    if existing_product:
        # Если товар существует, обновляем его поля
        existing_product.name = product.name
        existing_product.price = product.price
        existing_product.currency = product.currency
        await db.commit()
        await db.refresh(existing_product)

        await manager.broadcast(f"Change Product: {json.dumps(db_product.to_dict(), ensure_ascii=False)}")

        return existing_product

    # Иначе добавляем новый товар в базу данных
    db_product = ProductDB(**product.dict())
    db.add(db_product)

    await db.commit()
    await db.refresh(db_product)

    await manager.broadcast(f"Add Product: {json.dumps(db_product.to_dict(), ensure_ascii=False)}")

    return db_product


# Асинхронный эндпоинт для запуска парсера один раз
@app.post("/api/products/run_parser_once", response_model=dict)
async def run_parser_once(db: AsyncSession = Depends(get_db)):
    # Получаем все товары с сайта, запуская парсер
    all_products = await parser(db)

    await manager.broadcast(f"Parsed {len(all_products)} products")

    return { "message": f"{len(all_products)} products have been added." }


# Асинхронный эндпоинт для изменения полей товара по Id
@app.put("/api/products/{product_id}", response_model=Product)
async def сhange_product(product_id: int, product: ProductCreate, db: AsyncSession = Depends(get_db)):
    # Ищем товар по Id
    existing_product = await db.execute(select(ProductDB).filter(ProductDB.id == product_id))
    existing_product = existing_product.scalar_one_or_none()

    # Если товар не найден, то кидаем 404, с соответствующим сообщением
    if not existing_product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Обновляем товар
    existing_product.code = product.code
    existing_product.name = product.name
    existing_product.price = product.price
    existing_product.currency = product.currency
    await db.commit()
    await db.refresh(existing_product)

    await manager.broadcast(f"Change Product: {json.dumps(existing_product.to_dict(), ensure_ascii=False)}")

    return existing_product


# Асинхронный эндпоинт для удаления товара по Id
@app.delete("/api/products/{product_id}", response_model=dict)
async def delete_product(product_id: int, db: AsyncSession = Depends(get_db)):
    existing_product = await db.execute(select(ProductDB).filter(ProductDB.id == product_id))
    existing_product = existing_product.scalar_one_or_none()

    # Если товар не найден, то кидаем 404, с соответствующим сообщением
    if not existing_product:
        raise HTTPException(status_code=404, detail="Product not found")

    await db.delete(existing_product)
    await db.commit()

    await manager.broadcast(f"Delete Product: {json.dumps(existing_product.to_dict(), ensure_ascii=False)}")

    return {"message": f"Product with Id '{product_id}' has been deleted."}


@app.websocket("/websocket")
async def websocket_endpoint(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    await manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            if data == "get_products":
                result = await db.execute(select(ProductDB))
                products = result.scalars().all()
                response = json.dumps([product.to_dict() for product in products], ensure_ascii=False)
                await websocket.send_text(response)
                continue
            await websocket.send_text(data)
    except WebSocketDisconnect:
        print(f"Client {websocket} disconnected")