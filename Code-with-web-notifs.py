import network
import urequests
import time
from machine import Pin, ADC, Timer

# === Wi-Fi Credentials ===
SSID = ''
PASSWORD = ''

# === Telegram Bot Info ===
BOT_TOKEN = ''
CHAT_ID = ''

# === Blynk Info ===
BLYNK_TOKEN = ""
VIRTUAL_PIN = "V0"

# === Global Blynk Text Input ===
text_input = "Unknown Location"

# === Sensor and Actuator Setup ===
sensor_pin = ADC(Pin(32))  # Analog IR sensor
buzzer_pin = Pin(33, Pin.OUT)  # Buzzer

# === Threshold and Smoothing Config ===
high_threshold = 3500
low_threshold = 4095
moving_avg_window = 5
sensor_readings = [0] * moving_avg_window
reading_index = 0
buzzer_on = False

# === Connect to Wi-Fi ===
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print('Connecting to network...')
        wlan.connect(SSID, PASSWORD)
        while not wlan.isconnected():
            pass
    print('Network connected:', wlan.ifconfig())

# === Send Telegram Message ===
def send_telegram_message(message):
    base_url = "https://api.telegram.org"
    url = f"{base_url}/bot{BOT_TOKEN}/sendMessage?chat_id={CHAT_ID}&text={message.replace(' ', '%20')}"
    try:
        response = urequests.get(url)
        print("Telegram response:", response.text)
        response.close()
    except Exception as e:
        print("Error sending Telegram message:", e)

# === Fetch Blynk Text Input ===
def get_blynk_input(timer):
    global text_input
    try:
        url = f"https://blynk.cloud/external/api/get?token={BLYNK_TOKEN}&{VIRTUAL_PIN}"
        response = urequests.get(url)
        if response.status_code == 200:
            text_input = response.text.strip('"')
            print("Received from Blynk Text Input:", text_input)
        response.close()
    except Exception as e:
        print("Error fetching Blynk input:", e)

# === Read Sensor ===
def read_sensor():
    return sensor_pin.read()

# === Smooth Readings ===
def get_smoothed_value(sensor_value):
    global reading_index
    sensor_readings[reading_index] = sensor_value
    reading_index = (reading_index + 1) % moving_avg_window
    return sum(sensor_readings) / len(sensor_readings)

# === Check Threshold ===
def check_threshold(smoothed_value):
    global buzzer_on
    if smoothed_value > high_threshold and not buzzer_on:
        buzzer_on = True
        buzzer_pin.value(0)  # Turn off buzzer
        time.sleep(1)
    elif smoothed_value < low_threshold and buzzer_on:
        buzzer_on = False
        buzzer_pin.value(1)  # Turn on buzzer

        if text_input != "Unknown Location":
            message = "Fire Detected at " + text_input + "! Please respond immediately!"
            send_telegram_message(message)
        else:
            print("Blynk input not ready   skipping Telegram alert.")
        time.sleep(1)

# === Main Program Start ===
connect_wifi()
get_blynk_input(None)  # Initial Blynk input fetch

# Timer to update Blynk input every 5 seconds
timer = Timer(-1)
timer.init(period=5000, mode=Timer.PERIODIC, callback=get_blynk_input)

# Main loop
while True:
    sensor_value = read_sensor()
    smoothed_value = get_smoothed_value(sensor_value)
    check_threshold(smoothed_value)

    print("Raw Value:", sensor_value, "| Smoothed Value:", round(smoothed_value, 2))
    time.sleep(1)
