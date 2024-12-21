from sqlalchemy import Column, Integer, String
from database import Base

# Модель товара для взаимодействия с базой данных
class ProductDB(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(Integer, index=True)
    name = Column(String, index=True)
    price = Column(Integer)
    currency = Column(String)

    def __init__(self, code, name, price, currency):
        self.code = code
        self.name = name
        self.price = price
        self.currency = currency


    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "price": self.price,
            "currency": self.currency
        }