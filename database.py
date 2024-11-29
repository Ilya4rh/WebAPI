from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import databases


# URL для подключения к базе данных
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./products.db"

# Создаем экземпляр базы данных
database = databases.Database(SQLALCHEMY_DATABASE_URL)
# Создаем асинхронный движок SQLAlchemy
engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=True, # Включение вывода логов
    future=True # Использование асинхронных функций
)
# Создаем фабрику сессий для асинхронных сессий
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession, # Используем асинхронную версию Session
    expire_on_commit=False, # Отключение автоматического сохранения изменений при коммите
    future=True # Использование асинхронных функций
)

# Определяем базовый класс модели
Base = declarative_base()

# Инициализируем базу данных
async def init_db():
    async with engine.connect() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    # закрываем соединение с базой данных
    await engine.dispose()