import requests
from bs4 import BeautifulSoup
import re
import json


# Класс отражающий информацию о товаре
class Product:
    def __init__(self, code, name, price, currency):
        # Код товара с сайта
        self.code = code
        # Название
        self.name = name
        # Цена
        self.price = price
        # Валюта
        self.currency = currency

    # Преобразование информации о продукте в словарь
    def to_dict(self):
        return {
            "code": self.code,
            "name": self.name,
            "price": self.price,
            "currency": self.currency
        }


# Адрес категории товаров
# Пробовал несколько разных категорий, со всеми парсер работает -> парсер универсальный?
# Ниже закомментированы некоторые из категорий, которые я проверял
url = 'https://www.maxidom.ru/catalog/tovary-dlya-poliva/'
# url = 'https://www.maxidom.ru/catalog/homuty-dlya-shlangov/'
# url = 'https://www.maxidom.ru/catalog/laminat/'
# url = 'https://www.maxidom.ru/catalog/izmeritelnyy-instrument/'

# Возвращаем информацию о количестве старниц с товарами
def get_numbers_of_page():
    response = requests.get(url)

    soup = BeautifulSoup(response.content, "lxml")

    # блок отражающий количество страниц
    page_numbers_block = soup.find('div', class_="lvl2__content-nav-numbers-number")

    # если блок отсутствует значит страница только одна
    if page_numbers_block == None:
        return 1

    # получаем элементы хранящие номера страниц
    page_numbers = page_numbers_block.find_all('a')

    # возвращем номер последней страницы
    return int(page_numbers[-1].text)


# Возвращаем информацию о всех товарах со страницы
# На вход получаем все элементы с именами товаров и все элементы с ценами товаров
def get_products_on_page(product_names, product_prices):
    products = []

    for i in range(len(product_names)):
        # Достаём название товара, ставим в верхний регистр первое слово
        name = product_names[i].find('a').text.strip().capitalize()
        # Достаём код товара
        product_code = int(product_names[i].find('div', class_="lvl1__product-body-info-code").text.split(' ')[1])
        # Достаём все цены товаров
        product_price = product_prices[i].find('div', class_="l-product__price-base").text.strip()

        # С помощью регулярного выражения разделяю цену и валюту
        price, currency = re.search(r"([\d\s]+)(\D+)", product_price).groups()
        # Цену кастую к числу
        price = int(price.replace(" ", ""))
        # У валюты убираю точку в конце
        currency = currency.strip().rstrip('.')

        # Создаю объект класса ProductDB
        product = Product(product_code, name, price, currency)
        products.append(product)

    return products


def get_all_products_info():
    # Получаю количество страниц
    number_of_pages = get_numbers_of_page()

    # Список товаров со всех страниц
    all_products = []

    # Циклом прохожу по всем страницам
    for num in range(1, number_of_pages+1):
        # Делаю запрос, указывая адрес и номер страницы
        response = requests.get(f'{url}?amount=30&PAGEN_2={num}')
        soup = BeautifulSoup(response.content, "lxml")

        # Достаю названия и цену всез товаров со страницы
        product_names = soup.find_all('div', class_="l-product__name")
        product_prices = soup.find_all('div', class_="l-product__buy")

        # Добавляю информацию о товарах в общий список
        all_products += get_products_on_page(product_names, product_prices)

    return all_products