from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
import os
from dotenv import load_dotenv, find_dotenv
import glob
from datetime import datetime
import pandas as pd
import chardet
from bot import send_message_to_chat
import asyncio

# Настройки
load_dotenv(find_dotenv())
NEXTCLOUD_URL = f'{os.getenv("NEXTCLOUD_URL")}'
USERNAME = f'{os.getenv("USERNAME_NXCD")}'
PASSWORD = f'{os.getenv("PASSWORD")}'
WORKING_DIR = os.path.dirname(os.path.abspath(__file__))

# Настройка Chrome для скачивания

def cleanup_old_files(directory, pattern="*.csv", keep=1):
    """
    Удаляет самые старые файлы, оставляя только {keep} самых новых
    """
    files = sorted(glob.glob(os.path.join(directory, pattern)),
                   key=os.path.getmtime, reverse=True)

    if len(files) > keep:
        for old_file in files[keep:]:
            os.remove(old_file)
            print(f"Удален старый файл: {old_file}")


def download_deck_file(url):
    chrome_options = webdriver.ChromeOptions()
    prefs = {
        "download.default_directory": WORKING_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
    }
    chrome_options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=chrome_options)

    try:
        # Логин в Nextcloud
        driver.get(url)
        time.sleep(1)

        # 2. Вводим логин и пароль
        username_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "user"))
        )
        username_field.send_keys(USERNAME)

        password_field = driver.find_element(By.ID, "password")
        password_field.send_keys(PASSWORD)

        # 3. Находим кнопку входа по XPath (вместо ID)
        login_button = driver.find_element(
            By.XPATH,
            '//button[@type="submit" and contains(@class, "button-vue")]'
        )
        login_button.click()
        time.sleep(2)

        # Переход на страницу доски (укажите ваш URL)
        # driver.get(f"{NEXTCLOUD_URL}apps/deck/board/37/export")  # Замените 123 на ID доски
        driver.get(f"{NEXTCLOUD_URL}apps/deck/board/37")  # Замените 123 на ID доски
        time.sleep(3)

        # Открытие меню (три точки или шестеренка)
        menu_button = driver.find_element(By.CSS_SELECTOR, "button.app-navigation-toggle")
        # menu_button = WebDriverWait(driver, 10).until(
        #     EC.presence_of_element_located((By.CSS_SELECTOR, "button.action-item__menutoggle"))
        # )
        ActionChains(driver).move_to_element(menu_button).click().perform()
        time.sleep(1)

        # Нажатие кнопки "Экспортировать доску"
        dots_button = driver.find_element(
            By.CSS_SELECTOR,
            ".app-navigation-entry__actions.action-item.action-item--default-popover.action-item--primary"
        )
        ActionChains(driver).move_to_element(dots_button).click().perform()
        time.sleep(1)
        export_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Экспортировать доску')]"))
        )
        export_button.click()
        time.sleep(5)  # Ждем скачивания

        print("Файл успешно скачан!")
    finally:
        driver.quit()


def rename_with_current_date(filepath):
    """
    Переименовывает файл, добавляя текущую дату
    """
    if not os.path.exists(filepath):
        return None

    dirname = os.path.dirname(filepath)
    filename, ext = os.path.splitext(os.path.basename(filepath))
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
    new_name = f"{date_str}{ext}"
    new_path = os.path.join(dirname, new_name)

    os.rename(filepath, new_path)
    print(f"Файл переименован: {new_path}")
    return new_path


def detect_encoding(file_path):
    """Определяем кодировку файла с помощью chardet"""
    with open(file_path, 'rb') as f:
        result = chardet.detect(f.read(10000))  # Проверяем первые 10KB для скорости
    return result['encoding']


def read_csv_to_dict(file_path):
    """Читаем CSV файл и возвращаем список словарей с уникальными идентификаторами"""
    try:
        # Определяем кодировку
        encoding = detect_encoding(file_path)
        print(f"Определена кодировка файла {os.path.basename(file_path)}: {encoding}")

        # Читаем файл
        df = pd.read_csv(file_path, sep='\t', quotechar='"', encoding=encoding,
                         on_bad_lines='warn', dtype=str, keep_default_na=False)

        # Заменяем специальные значения на None
        df = df.replace(['null', 'nan', '', 'None', 'NULL'], None)

        # Проверяем обязательные колонки
        required_cols = ['Заголовок карточки', 'Название списка']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Отсутствуют обязательные колонки: {missing_cols}")

        # Очищаем данные
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

        # Создаем уникальные идентификаторы для каждой карточки
        cards = []
        for idx, row in df.iterrows():
            # Базовый ключ
            base_key = f"{row['Заголовок карточки']}|{row['Название списка']}"

            # Если такой ключ уже есть, добавляем суффикс
            suffix = 1
            key = base_key
            while any(card['key'] == key for card in cards):
                suffix += 1
                key = f"{base_key}|{suffix}"

            card_data = {
                'key': key,
                'title': row['Заголовок карточки'],
                'list_name': row['Название списка'],
                'description': row.get('Описание'),
                'labels': row.get('Метки'),
                'due_date': row.get('Due date'),
                'created': row.get('Создано'),
                'updated': row.get('Изменено')
            }
            cards.append(card_data)

        return {card['key']: card for card in cards}

    except Exception as e:
        print(f"Ошибка при обработке файла {os.path.basename(file_path)}: {str(e)}")
        raise


def format_value(value):
    """Форматирует значение для вывода"""
    if value is None:
        return "пусто"
    if isinstance(value, str) and 'T' in value:
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')
        except ValueError:
            return value
    return str(value)


def compare_cards(file1, file2):
    """Сравнивает два файла и выводит различия"""
    try:
        print(f"\nЗагрузка файла 1: {os.path.basename(file1)}")
        data1 = read_csv_to_dict(file1)
        print(f"Загрузка файла 2: {os.path.basename(file2)}")
        data2 = read_csv_to_dict(file2)
    except Exception as e:
        print(f"Не удалось загрузить файлы: {str(e)}")
        return False

    all_keys = sorted(set(data1.keys()).union(set(data2.keys())))
    changes_found = False

    for key in all_keys:
        card1 = data1.get(key)
        card2 = data2.get(key)

        # Извлекаем основную информацию (без суффикса дубликатов)
        base_key_parts = key.split('|')[:2]
        title = base_key_parts[0]
        list_name = base_key_parts[1] if len(base_key_parts) > 1 else "Без группы"

        if card1 is None:
            # Новая карточка
            send_message(text=f"\n🆕 [Добавлено] В группе '{list_name}': '{title}'")
            print(f"\n🆕 [Добавлено] В группе '{list_name}': '{title}'")
            for field in ['description', 'labels', 'due_date', 'created', 'updated']:
                val = card2.get(field)
                if val is not None:
                    print(f"   {field}: {format_value(val)}")
            changes_found = True
            continue

        if card2 is None:
            # Удаленная карточка
            send_message(text=f"\n🗑️ [Удалено] Из группы '{list_name}': '{title}'")
            print(f"\n🗑️ [Удалено] Из группы '{list_name}': '{title}'")
            changes_found = True
            continue

        # Проверяем изменения полей
        changes = []
        fields = [
            ('description', 'Описание'),
            ('labels', 'Метки'),
            ('due_date', 'Due date'),
            ('created', 'Дата создания'),
            ('updated', 'Дата изменения')
        ]

        for field, display_name in fields:
            old_val = card1.get(field)
            new_val = card2.get(field)

            if old_val != new_val and not (pd.isna(old_val) and pd.isna(new_val)):
                changes.append(
                    f"{display_name}: было '{format_value(old_val)}', стало '{format_value(new_val)}'"
                )

        if changes:
            send_message(text=f"\n🔄 [Изменено] В группе '{list_name}': '{title}'")
            print(f"\n🔄 [Изменено] В группе '{list_name}': '{title}'")
            for change in changes:
                print(f"   - {change}")
            changes_found = True

    if not changes_found:
        print("\n✅ Файлы идентичны, различий не найдено")
    else:
        print("\nСравнение завершено")

    return True


def send_message(text: str):
    """
    Синхронная функция для отправки сообщения через бота
    :param text: Текст сообщения
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(send_message_to_chat(text))


if __name__ == "__main__":

    while True:
        # 1. Очистка старых файлов
        cleanup_old_files(WORKING_DIR, keep=1)
        # 2. Скачивание файла (ваш существующий код)
        download_deck_file(NEXTCLOUD_URL)  # Ваша функция скачивания
        files = sorted(glob.glob(os.path.join(WORKING_DIR, "*.csv")),
                       key=os.path.getmtime, reverse=True)
        if files:
            downloaded_file = files[0]

        # 3. Переименование с датой
            print(f'{downloaded_file=}')
            renamed_file = rename_with_current_date(downloaded_file)
            all_files = sorted(glob.glob(os.path.join(WORKING_DIR, "*.csv")),
                               key=os.path.getmtime)
            if len(all_files) > 1:
                old_file = all_files[-2]  # Предыдущий файл
                new_file = all_files[-1]  # Текущий файл
                compare_cards(old_file, new_file)
        else:
            print("Нет CSV файлов для обработки")

        time.sleep(300)
    #
    # all_files = sorted(glob.glob(os.path.join(WORKING_DIR, "*.csv")),
    #                    key=os.path.getmtime)
    # if len(all_files) > 1:
    #     old_file = all_files[-2]  # Предыдущий файл
    #     new_file = all_files[-1]  # Текущий файл
    #     compare_cards(old_file, new_file)







