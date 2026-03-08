from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

# Setup Chrome WebDriver
service = Service(ChromeDriverManager().install())
options = webdriver.ChromeOptions()
options.add_argument("--headless")  # Run in background
driver = webdriver.Chrome(service=service, options=options)

# Base URL
url = "https://www.matricresult2025.com/"

# Roll code and range of roll numbers
roll_code = "84021"
start_roll = 2500001
end_roll = 2500040

# Iterate over roll numbers
for roll_no in range(start_roll, end_roll + 1):
    driver.get(url)
    time.sleep(2)  # Wait for page load
    
    # Find and fill Roll Code and Roll Number
    driver.find_element(By.NAME, "rollcode").send_keys(roll_code)
    driver.find_element(By.NAME, "rollnumber").send_keys(str(roll_no))
    
    # Solve captcha
    captcha_text = driver.find_element(By.ID, "captcha").text  # Extract "12 + 8"
    numbers = captcha_text.split("+")
    captcha_result = int(numbers[0].strip()) + int(numbers[1].strip())

    driver.find_element(By.NAME, "captcha_answer").send_keys(str(captcha_result))

    # Submit form
    driver.find_element(By.NAME, "submit").click()
    time.sleep(2)

    # Click on print button
    try:
        driver.find_element(By.XPATH, "//button[contains(text(), 'Print')]").click()
        time.sleep(3)
        print(f"Result available for Roll No {roll_no}")
    except:
        print(f"No result found for Roll No {roll_no}")

# Close the browser
driver.quit()
