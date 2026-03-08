import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# Initialize the WebDriver
driver = webdriver.Chrome()

#it will keep the browser open
# # driver.implicitly_wait(10)
# options = Options()
# options.add_experimental_option("detach", True)


cookie_id = "bigCookie"
cookies_id = "cookies"
product_prefix = "product"
product_price_prefix = "productPrice"


# Navigate to the CookieCliker website
driver.get("https://orteil.dashnet.org/cookieclicker/")
# driver.maximize_window()


# Wait for the page to load
WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.XPATH, "//*[@id='langSelect-EN']"))
).click()  # for language selection


# Find and click the "Accept" button
# accept_button = WebDriverWait(driver, 10).until(
#     EC.presence_of_element_located((By.ID, cookie_id)) # faulty code.....
# )
# accept_button.click()

WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.ID, cookie_id))
)
accept_button = driver.find_element(By.ID, cookie_id)
accept_button.click()

while True:
    accept_button.click()
    cookies_count = driver.find_element(By.ID, cookies_id).text.split(" ")[0]
    cookies_count = int(cookies_count.replace(",", ""))
    # print(cookies_count)
    for i in range(4):
        product_price = driver.find_element(By.ID, product_price_prefix + str(i)).text.replace(" ", "")
        if not product_price.isdigit():
            continue
        product_price = int(product_price)
        if cookies_count >= product_price:
            driver.find_element(By.ID, product_prefix + str(i)).click()
            break


# Wait for the page to load
time.sleep(1000)



