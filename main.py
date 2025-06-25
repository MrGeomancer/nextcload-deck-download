from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
import os
from dotenv import load_dotenv, find_dotenv

# Настройки
load_dotenv(find_dotenv())
NEXTCLOUD_URL = f'{os.getenv("NEXTCLOUD_URL")}'
USERNAME = f'{os.getenv("USERNAME_NXCD")}'
print(f'{USERNAME=}')
PASSWORD = f'{os.getenv("PASSWORD")}'
WORRKING_DIR = os.path.dirname(os.path.abspath(__file__))

# Настройка Chrome для скачивания
chrome_options = webdriver.ChromeOptions()
prefs = {
    "download.default_directory": WORRKING_DIR,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
}
chrome_options.add_experimental_option("prefs", prefs)

driver = webdriver.Chrome(options=chrome_options)

try:
    # Логин в Nextcloud
    driver.get(NEXTCLOUD_URL)
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