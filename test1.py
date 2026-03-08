from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time
driver = webdriver.Chrome()
# driver.get("https://www.youtube.com")

driver.get("https://www.youtube.com")


# WebDriverWaitt(driver, 10).until(
#     EC.presence_of_element_located((By.NAME, "q"))
# )

# input_element = driver.find_element(By.NAME, "q")
# input_element.clear()
# input_element.send_keys("Python")



# Wait for the search input element to be present on the page
input_element = WebDriverWait(driver, 10).until(
    lambda driver: driver.find_element(By.NAME, "search_query")
)
input_element.send_keys("Python")
# input_element.clear()
input_element.send_keys(Keys.RETURN)

link_element = WebDriverWait(driver,5).until(
    # lambda driver: driver.find_element(By.XPATH, '//*[@id="video-title"]')
    lambda driver: driver.find_element(By.PARTIAL_LINK_TEXT, 'Python for Beginners')
)

link_elements = WebDriverWait(driver, 5).until(
    lambda driver: driver.find_elements(By.PARTIAL_LINK_TEXT, 'Python for Beginners')[element1,element2,element3]
)
# link_element.click()
link_elements[0].click()

time.sleep(200)
driver.close()








