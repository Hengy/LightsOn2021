
import os

#------------------------------------------------------
# LightsOn web addresses
#------------------------------------------------------

CHOOSE_DISPLAY_URL = 'https://splsparkles.ca/'

SPECIAL_CODE = '2S5J'

#------------------------------------------------------
# LightsOn RPi IP addresses
#------------------------------------------------------

# RPI_IPS = ('192.168.1.190','192.168.1.191','192.168.1.193')   # LIBRARY ONLY

RPI_IPS = ('192.168.0.81',)     # DEBUG ONLY

RPI_MASTER = ('192.168.0.80', '192.168.1.192')
UUID_MODIFIER = '3141fade'

#------------------------------------------------------
# FLASK APP
#------------------------------------------------------

SELF_IP =  ""  # set to static IP address of Raspberry Pi
SELF_PORT = ":5000"

def get_self_ip():
    global SELF_IP
    result = os.popen("ip -4 route show default").read().split()
    if '192.168.1.190' in result:
        ip = '192.168.1.190'
    if '192.168.1.191' in result:
        ip = '192.168.1.191'
    if '192.168.1.192' in result:
        ip = '192.168.1.192'
    if '192.168.1.193' in result:
        ip = '192.168.1.193'
    if '192.168.1.194' in result:
        ip = '192.168.1.194'
    if '192.168.0.80' in result:
        ip = '192.168.0.80'
    if '192.168.0.81' in result:
        ip = '192.168.0.81'
    SELF_IP = ip
    return ip

FLASK_HOST = '0.0.0.0'  # leave as 0.0.0.0 to accept al incoming connections

#------------------------------------------------------
# ZMQ
#------------------------------------------------------

ZMQ_SOCKET_IP = "tcp://127.0.0.1"
ZMQ_SOCKET_PORT = "62830"

# ZMQ_RPI_PORTS = ["62840","62841","62842","62843","62844","62845","62846"]

#------------------------------------------------------
# TORNADO / WEBSOCKET
#------------------------------------------------------

TORNADO_PORT = 31415    # DO NOT MODIFY!!!

#------------------------------------------------------
# OPC / FADECANDY SERVER
#------------------------------------------------------

OPC_ADDR = 'localhost:7890' # MUST match fcserver.json in /usr/local/bin

#------------------------------------------------------
# QUEUE
#------------------------------------------------------

QUEUE_MAX = 3           # max number of users. This includes those waiting, and the controller; if full, user will be asked to try again later
QUEUE_MAX_TIME = 120    # time (in seconds) a user has to control LEDs before control is passed to next in queue

#------------------------------------------------------
# TIME ON/OFF
#------------------------------------------------------

TIME_ON_HOUR = 1       # hour to turn on (24 hour time) 16 = 4PM
TIME_OFF_HOUR = 23      # hour to turn off (24 hour time) 23 = 11PM

#------------------------------------------------------
# DISPLAY TYPE
#------------------------------------------------------

PI_DISPLAY_TYPE = 0     # (0) = Addressable LED strips
                        # (1) = GPIO/Relay OR DMX Lights

RELAY_LOGIC_INV = True

#------------------------------------------------------
# GPIO PINS
#------------------------------------------------------

PSU_PIN = 11

RELAY_PINS = (11, 13, 15, 16, 18, 22)

RELAY_PIN_IDLE = 24

RELAY_PIN_OFF = 26 

RELAY_PIN_MOM_TIME = 0.2 # time in seconds that the relay is in opposite pin state (momentary action)

#------------------------------------------------------
# LED SETUP
#------------------------------------------------------

#NUM_LEDS = 918          # Upper Windows LED total
#NUM_LEDS = 708          # Lower Windows LED total

NUM_LEDS = 1  #for testing ONLY

LED_POWER_LIMIT = True  # enable (True) power limit on LED effects that use all (or  most) pixels
LED_POWER_SCALE = 0.6   # factor to limit LED power; < 1 reduces LED brightness/power
LED_POWER_MIN = 0.2     # minimum power to prevent noticable flickering. setting to LED_POWER_MIN / 2 will set power to 0

FC_CAHNNELS = 3         # number of Fadecandy OPC channels - 1 OPC channel per window for easy addressing!

CHAN_1_NUM_LEDS = 236   # number of LEDs in channel

# idle LED effect
IDLE_COLOR_CHANGE_TIME = 20
IDLE_SYNC_OFFSET01 = 0.4
IDLE_MODE_CHANGE_TIME = 300

# window configuration
WIN_UPPER_PANE = False
# WIN_PANE1 = [0,236]     #[0,50]
# WIN_PANE2 = [236,472]   #[50,100]
# WIN_PANE3 = [472,708]   #[100,150]
# WIN_PANE4 = [708,918]   #[150,192]

WIN_PANE1 = [0,50]
WIN_PANE2 = [50,100]
WIN_PANE3 = [100,150]
WIN_PANE4 = [150,191]

def config_leds():
    global SELF_IP
    global WIN_PANE1
    global WIN_PANE2
    global WIN_PANE3
    global WIN_PANE4
    global WIN_UPPER_PANE
    global PI_DISPLAY_TYPE
    global NUM_LEDS

    WIN_PANE1 = [0,236]     #[0,50]
    WIN_PANE2 = [236,472]   #[50,100]
    WIN_PANE3 = [472,708]   #[100,150]
    WIN_PANE4 = [708,918]   #[150,192]

    if SELF_IP == "192.168.0.80" or SELF_IP == '192.168.0.81':
        global NUM_LEDS
        WIN_PANE1 = [0,128]
        WIN_PANE2 = [129,236]
        WIN_PANE3 = [237,290]
        WIN_PANE4 = [294,298]
        # WIN_PANE1 = [0,75]
        # WIN_PANE2 = [75,150]
        # WIN_PANE3 = [150,225]
        # WIN_PANE4 = [225,299]
        PI_DISPLAY_TYPE = 0
        WIN_UPPER_PANE = False
        NUM_LEDS = 369
        # PI_DISPLAY_TYPE = 1
    elif SELF_IP == "192.168.1.190":    # Staff room - upper
        WIN_UPPER_PANE = False
        PI_DISPLAY_TYPE = 0
        NUM_LEDS = 709
    elif SELF_IP == "192.168.1.191":    # PSL - upper
        WIN_UPPER_PANE = False
        PI_DISPLAY_TYPE = 0
        NUM_LEDS = 709
    elif SELF_IP == "192.168.1.192":    # Makerspace - lower
        WIN_UPPER_PANE = True
        PI_DISPLAY_TYPE = 0
        NUM_LEDS = 919
    elif SELF_IP == "192.168.1.193":    # Shaunas office - lower
        WIN_UPPER_PANE = True
        PI_DISPLAY_TYPE = 0
        NUM_LEDS = 919
    elif SELF_IP == "192.168.1.194":    # DMX
        PI_DISPLAY_TYPE = 1
