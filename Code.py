import network
import urequests
import time
from machine import Pin, ADC

# Replace with your Wi-Fi credentials
SSID = ''
PASSWORD = ''

# Telegram bot token and chat ID
BOT_TOKEN = ''
CHAT_ID = ''

#Setup
sensor_pin = ADC(Pin(32)) #Analog IR sensor
buzzer_pin = Pin(33, Pin.OUT) #Buzzer

#Calibration data (for distance estimation)
high_threshold = 3500 #High threshold is raw sensor reading value
low_threshold = 4095 #Low threshold is raw sensor reading value
moving_avg_window = 5
sensor_readings = [0] * moving_avg_window
reading_index = 0
buzzer_on = False

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print('Connecting to network...')
        wlan.connect(SSID, PASSWORD)
        while not wlan.isconnected():
            pass
    print('Network connected:', wlan.ifconfig())
    
connect_wifi()

# Send Telegram message
def send_telegram_message(message):
    url = "https://api.telegram.org/bot7777659170:AAG-5ewLMU0mVrynG08cYZMTgt2BN0BpSvo/sendMessage".format(BOT_TOKEN)
    payload = {
        'chat_id': CHAT_ID,
        'text': message
    }
    try:
        response = urequests.post(url, json=payload)
        print("Telegram response:", response.text)
        response.close()
    except Exception as e:
        print("Error sending Telegram message:", e)
        
def read_sensor():
    return sensor_pin.read() #Read sensor value (0-4095)

def get_smoothed_value(sensor_value): #code to remove noise from readings and avoid false readings from raw sensor value
    global reading_index
    sensor_readings[reading_index] = sensor_value
    reading_index = (reading_index + 1) % moving_avg_window
    return sum(sensor_readings) / len(sensor_readings)

#Hystresis code, to prevent false reading and better decision making
def check_threshold(smoothed_value): #code for flame detection with buzzer control
    global buzzer_on
    if smoothed_value > high_threshold and not buzzer_on:
        buzzer_on = True
        buzzer_pin.value(0) #Turn off buzzer
        time.sleep(1)
    elif smoothed_value < low_threshold and buzzer_on:
        buzzer_on = False
        buzzer_pin.value(1) #Turn on buzzer
        send_telegram_message("Fire Detected at San Pedro, Laguna! Please respond immediately!")
        time.sleep(1)
        
#Main loop
while True:
    sensor_value = read_sensor() #Read raw sensor values
    smoothed_value = get_smoothed_value(sensor_value) #Apply smoothing that remove noise from raw readings
    check_threshold(smoothed_value) #Apply thresholding with hysteresis
    
    #Show both values in the serial monitor
    print("Raw Value:", sensor_value, "| Smoothed Value:", round(smoothed_value, 2))
    time.sleep(1) #Delay in seconds
