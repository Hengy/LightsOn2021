import multiprocessing

import opc

import os

import sys

import time
import datetime

import json

import functools

import env_config

import RPi.GPIO as GPIO

import math

import random

import signal

numLEDs = 1
client = opc.Client(env_config.OPC_ADDR)

# converts HSV to RGB values; h = 0..359, s,v = 0..1
def HSVtoRGB(h, s, v):
    if s == 0.0: v*=255; return (v, v, v)
    i = int(h*6.) # XXX assume int() truncates!
    f = (h*6.)-i; p,q,t = int(255*(v*(1.-s))), int(255*(v*(1.-s*f))), int(255*(v*(1.-s*(1.-f)))); v*=255; i%=6
    if i == 0: return (int(v), t, p)
    if i == 1: return (int(q), v, p)
    if i == 2: return (int(p), v, t)
    if i == 3: return (int(p), q, v)
    if i == 4: return (int(t), p, v)
    if i == 5: return (int(v), p, q)

LIB_GREEN_R = 150
LIB_GREEN_G = 202
LIB_GREEN_B = 80

LIB_BLUE_R = 0
LIB_BLUE_G = 171
LIB_BLUE_B = 232

LIB_PURPLE_R = 87
LIB_PURPLE_G = 52
LIB_PURPLE_B = 148

# -----------------------------------------------------
# Check if it is within Lights On time
# returns True if it is between TIME_ON and TIME_OFF
# -----------------------------------------------------
def check_in_time():
  in_time = False
  hour_now = datetime.datetime.now().hour
  if hour_now >= env_config.TIME_ON_HOUR:
    if hour_now < env_config.TIME_OFF_HOUR:
      in_time = True

  return in_time

def signal_handler(signal, frame):
    GPIO.cleanup()
    print("exiting LEDs...")
    sys.exit(0)

class LEDController():
    def __init__(self):

        global numLEDs

        print("Local IP Address: ", env_config.get_self_ip())

        print("Now env_config SELF_IP is: ", env_config.SELF_IP)

        env_config.config_leds()

        numLEDs = env_config.NUM_LEDS

        print("Upper Pane: ", env_config.WIN_UPPER_PANE)
        print("Display type (0 = LEDs, 1 = DMX/Relays): ", env_config.PI_DISPLAY_TYPE)
        print("LEDs: ", env_config.NUM_LEDS)

        print("Initializing new fadecandy LED controller")

        signal.signal(signal.SIGINT, signal_handler)

        random.seed(time.time())

        GPIO.setmode(GPIO.BOARD)

        self.power_pin =env_config.PSU_PIN
        self.last_power_toggle_time = time.time()

        GPIO.setup(self.power_pin, GPIO.OUT)
        GPIO.output(self.power_pin, GPIO.HIGH)

        # pixel buffer
        self.pixels = [(0,0,0)] * numLEDs

        # state machine variables
        # ----------------------------------------------------------------------
        # state: 0 = IDLE; 1 = BLANK; 2 = STREAMING; > 3 = LED Effect modes
        self._state = 0
        
        # message polling
        self.poll_period = 10 # polling period in ms

        # effect delay time
        self.effect_delay = 20 # ms
        # self.effect_delay = 20 # ms

        # idle
        self.idle_mode_max = 6
        self.idle_mode = random.randint(0,self.idle_mode_max)
        self.idle_mode_time = 0
        self.idle_change_time = 0
        self.idle_color = 0
        self.idle_brightness = 0.7
        self.idle_step = 0.0002
        self.idle_build_dir = True
        self.idle_build_array = []
        self.idle_build_array2 = []
        self.idle_build_max_delay = 1500
        self.idle_build_chunk_min = 10
        self.idle_build_chunk_max = 18
        self.idle_build_speed = 0.87

        # Rainbow Fade In
        self.state3_color = 0
        self.state3_brightness = 0
        self.state3_step = 1

        # Rainbow
        self.state4_color = 0
        self.state4_step = 0.003

        # Chase
        self.state5_position = 0
        self.state5_color = 0
        self.state5_step = 0.05
        self.state5_speed = 2

        # theatre chase
        self.state6_position = 9
        self.state6_brightness = 1
        self.state6_color = 0

        # Dual Chase
        self.state7_position = 0
        self.state7_position2 = int(numLEDs/2) + 12
        self.state7_color = 0
        self.state7_color2 = 0

        # Triple Chase
        self.state8_position = 0
        self.state8_position2 = int(numLEDs/3) + 8
        self.state8_position3 = int((numLEDs/3) * 2) + 16
        self.state8_color = self.state5_step
        self.state8_color2 = 0
        self.state8_color3 = 0

        # build up/down
        self.state9_dir = True
        self.state9_array = []
        self.state9_array2 = []
        self.state9_max_delay = 1500
        self.state9_min_delay = 120
        self.state9_chunk_min = 10
        self.state9_chunk_max = 18
        self.state9_speed = 0.9
        self.state9_color = 0
        self.state9_step = 0.055

        # spread
        self.state10_index = 120
        self.state10_paneSize = env_config.WIN_PANE1[1]
        self.state10_posDistance = math.floor(env_config.WIN_PANE1[1]/4)
        self.state10_paneStart = [env_config.WIN_PANE1[0], env_config.WIN_PANE2[0], env_config.WIN_PANE3[0]]
        self.state10_pos1 = [0, 0, 0, 0]
        self.state10_pos2 = [0, 0, 0, 0]
        self.state10_color = 0
        self.state10_colorchoices = [0, 0.07, 0.11, 0.28, 0.47, 0.66, 0.75, 0.88]
        self.state10_centerBrightness = 0.7
        self.state10_otherBrightness = 0.45
        
        # sparkle
        self.state11_timer = 10
        self.state11_activeArray = [0] * numLEDs
        self.state11_depthArray = [0] * numLEDs
        self.state11_brightnessIndex = [0.027, 0.035, 0.047, 0.058, 0.07, 0.086, 0.105, 0.125, 0.15, 0.172, 0.2, 0.227, 0.262, 0.3, 0.34, 0.376, 0.423, 0.47, 0.525, 0.58, 0.64, 0.7, 0.772, 0.847, 0.92, 1]
        self.state11_rateMin = 2
        self.state11_rateMax = 6
        self.state11_prevNewIndex = 0
        self.state11_H = 0
        self.state11_S = 0

        # dual sparkle
        self.state12_timer = 10
        self.state12_activeArray = [0] * numLEDs
        self.state12_depthArray = [0] * numLEDs
        self.state12_brightnessIndex = [0.027, 0.035, 0.047, 0.058, 0.07, 0.086, 0.105, 0.125, 0.15, 0.172, 0.2, 0.227, 0.262, 0.3, 0.34, 0.376, 0.423, 0.47, 0.525, 0.58, 0.64, 0.7, 0.772, 0.847, 0.92, 1]
        self.state12_rateMin = 2
        self.state12_rateMax = 6
        self.state12_prevNewIndex = 0
        self.state12_H1 = 0.0
        self.state12_S1 = 1.0
        self.state12_H2 = 0.32
        self.state12_S2 = 1.0
        # ----------------------------------------------------------------------

        print("LED Controller initialized")

    def adj_brightness(self):
        if env_config.LED_POWER_LIMIT:
            for i in range(len(self.pixels)):
                new_pixel = (self.pixels[i][0]*env_config.LED_POWER_SCALE,self.pixels[i][1]*env_config.LED_POWER_SCALE,self.pixels[i][2]*env_config.LED_POWER_SCALE)
                self.pixels[i] = new_pixel

    # led controller state machine
    def run(self, conn):
        print("Fadecandy Process ID: ", os.getpid())

        msg = {"CMD":None}

        time_now = int(round(time.time() * 1000)) # time now
        time_prev_poll = 0

        time_prev_pixel_update = 0

        while msg["CMD"] != "END":
        # state machine beginning -------------------------------------------------------
            time_now = int(round(time.time() * 1000)) # time now

            if time_now - time_prev_poll >= self.poll_period:

                in_time = check_in_time()
                if in_time and (time_now - self.last_power_toggle_time) > 30:
                    GPIO.output(self.power_pin, GPIO.LOW)
                    self.last_power_toggle_time = time.time()
                else:
                    GPIO.output(self.power_pin, GPIO.HIGH)
                    self.last_power_toggle_time = time.time()

                time_prev_poll = int(round(time.time() * 1000))
                if conn.poll():
                    jsonmsg = conn.recv()
                    msg = json.loads(jsonmsg)
                    if msg["CMD"] == "FADEIN":
                        self.effect_delay = 20
                        self.state3_color = random.randint(0,6)
                        self._state = 3
                    elif msg["CMD"] == "RAINBOW":
                        self.effect_delay = 80
                        self._state = 4
                    elif msg["CMD"] == "CHASE":
                        self.effect_delay = 25
                        self._state = 5
                    elif msg["CMD"] == "THEATRE":
                        self.effect_delay = 40
                        self._state = 6
                    elif msg["CMD"] == "DUALCHASE":
                        self.effect_delay = 25
                        self._state = 7
                    elif msg["CMD"] == "TRIPLECHASE":
                        self.effect_delay = 25
                        self._state = 8
                    elif msg["CMD"] == "BUILDUPDOWN":
                        self.pixels = [(0,0,0)] * numLEDs
                        self.effect_delay = self.state9_max_delay

                        self.state9_array = []

                        # build random 'chunk' list
                        done = False
                        pos = 0
                        while not done:
                            end = pos + random.randint(self.state9_chunk_min,self.state9_chunk_max)
                            if end >= numLEDs:
                                end = numLEDs - 1
                            self.state9_array.append((pos, end))
                            if end != numLEDs - 1:
                                pos = end
                            else:
                                done = True

                        self._state = 9
                    elif msg["CMD"] == "SPREAD":
                        self.effect_delay = 25
                        self._state = 10
                    elif msg["CMD"] == "SPARKLE":
                        self.pixels = [(0,0,0)] * numLEDs
                        self.effect_delay = 35
                        self._state = 11
                    elif msg["CMD"] == "DUALSPARKLE":
                        self.pixels = [(0,0,0)] * numLEDs
                        self.effect_delay = 35
                        self._state = 12
                    # elif msg["CMD"] == "COMET":
                    #     self.effect_delay = 40
                    #     self._state = 11
                    elif msg["CMD"] == "DARK":
                        self.effect_delay = 20
                        print("turning off LEDs...")
                        self._state = 1
                    elif msg["CMD"] == "STREAM":
                        if env_config.LED_POWER_LIMIT:
                            color_val = msg["Data"][2]/100*env_config.LED_POWER_SCALE
                        else:
                            color_val = msg["Data"][2]/100

                        if color_val < env_config.LED_POWER_MIN:
                            if color_val < env_config.LED_POWER_MIN and color_val >= env_config.LED_POWER_MIN/2:
                                color_val = env_config.LED_POWER_MIN
                            else:
                                color_val = 0
                        print("new value: ", color_val)
                        new_color = HSVtoRGB(msg["Data"][0]/360, msg["Data"][1]/100, color_val)
                        self.pixels = [new_color] * numLEDs
                        self._state = 2
                    elif msg["CMD"] == "IDLE":
                        self.pixels = [(0,0,0)] * numLEDs
                        self.effect_delay = 20
                        print("idling LEDs...")
                        self._state = 0
                    elif msg["CMD"] == "CLRCHNG":
                        if self._state == 5: #chase
                            self.state5_color = msg["Colour"][0]/360
                        if self._state == 6: #theatre
                            self.state6_color = msg["Colour"][0]/360
                        if self._state == 7: #dualchase
                            self.state7_color = msg["Colour"][0]/360
                            self.state7_color2 = msg["Colour"][0]/360
                        if self._state == 8: #triplechase
                            self.state8_color = msg["Colour"][0]/360
                            self.state8_color2 = msg["Colour"][0]/360
                            self.state8_color3 = msg["Colour"][0]/360
                        if self._state == 11: # sparkle
                            self.state11_H = msg["Colour"][0]/360
                            self.state11_S = msg["Colour"][1]/100
                        if self._state == 12: # dualsparkle
                            self.state12_H1 = msg["Colour"][0]/360
                            self.state12_S1 = msg["Colour"][1]/100
                            self.state12_H2 = (msg["Colour"][0] + 115)/360
                            if self.state12_H2 > 1:
                                self.state12_H2 = self.state12_H2 - 1
                            self.state12_S2 = msg["Colour"][1]/100
                        if self._state == 9: #build
                            self.state9_color = msg["Colour"][0]/360
                            for i in range(numLEDs):
                                if self.pixels[i] != (0,0,0):
                                    if env_config.LED_POWER_LIMIT:
                                        new_color = HSVtoRGB(self.state9_color,1,0.8*env_config.LED_POWER_SCALE)
                                    else:
                                        new_color = HSVtoRGB(self.state9_color,1,0.75)
                                    self.pixels[i] = new_color
                    elif msg["CMD"] == "SPDCHNG":
                        if self._state == 4: # rainbow
                            self.effect_delay = msg["Speed"]
                        if self._state == 5 or self._state == 7 or self._state == 8: # chase / dualchase / triplechase
                            self.effect_delay = msg["Speed"]
                        if self._state == 3: # fadein
                            self.effect_delay = msg["Speed"]
                        if self._state == 9: # build
                            self.state9_speed = msg["Speed"]
                        if self._state == 6: # theatre
                            self.effect_delay = msg["Speed"]
                        if self._state == 10: # spread
                            self.effect_delay = msg["Speed"]
                        if self._state == 11: # sparkle
                            self.effect_delay = msg["Speed"]
                        if self._state == 12: # dualsparkle
                            self.effect_delay = msg["Speed"]
                    elif msg["CMD"] == "CHNKCHNG":
                        if self._state == 9:
                            size = msg["Block"]
                            if size <= 8:
                                dev = math.floor(size/2)
                                self.state9_min_delay = 60
                            elif size > 18:
                                dev = math.floor(size/4)
                                self.state9_min_delay = 150
                            else:
                                dev = 5
                                self.state9_min_delay = 120
                            self.state9_chunk_min = size - dev
                            self.state9_chunk_max = size + dev

                            self.state9_array = []
                            self.state9_array2 = []

                            # build random 'chunk' list
                            done = False
                            pos = 0
                            while not done:
                                end = pos + random.randint(self.state9_chunk_min,self.state9_chunk_max)
                                if end >= numLEDs:
                                    end = numLEDs - 1
                                self.state9_array.append((pos, end))
                                if end != numLEDs - 1:
                                    pos = end
                                else:
                                    done = True

                            self.state9_dir = True

                            self.pixels = [(0,0,0)] * numLEDs

                    else:
                        self.pixels = [(0,0,0)] * numLEDs
                        self.effect_delay = 20
                        print("idling LEDs...")
                        self._state = 0

            if time_now - time_prev_pixel_update >= self.effect_delay:
                time_prev_pixel_update = int(round(time.time() * 1000)) # time now
                if self._state == 0:
                    self.idle_leds()
                elif self._state == 2:
                    pass  
                elif self._state == 1:
                    self.blank_leds()
                elif self._state == 3:
                    self.rainbowfadein()
                    self.adj_brightness()
                elif self._state == 4:
                    self.rainbow()
                    self.adj_brightness()
                elif self._state == 5:
                    self.chase()
                elif self._state == 6:
                    self.theatre_chase()
                elif self._state == 7:
                    self.dualchase()
                elif self._state == 8:
                    self.triplechase()
                elif self._state == 9:
                    self.build_up_down()
                elif self._state == 10: # spread
                    self.connect()
                elif self._state == 11: # sparkle
                    self.sparkle()
                elif self._state == 12: # dual sparkle
                    self.dualsparkle()
                else:
                    self.idle_leds()

            if not check_in_time(): # if it is NOT time to display
                self.pixels = [(0,0,0)] * numLEDs
            client.put_pixels(self.pixels)

        # state machine end ------------------------------------------------------------
        self.blank_leds()
        print("Ending child...")
        exit()

    # idle LED routines
    def idle_leds(self):

        if self.idle_change_time == 0:
            self.idle_change_time = time.time() + env_config.IDLE_COLOR_CHANGE_TIME + random.randint(0,10) - 5
            self.idle_mode_time = time.time() + env_config.IDLE_MODE_CHANGE_TIME
            self.idle_color = random.randint(0,2)
            self.idle_brightness = random.randint(65,80)/100

            if self.idle_mode == 4:
                self.effect_delay = self.idle_build_max_delay
                self.idle_color = random.choice([86/360,196/360,280/360,86/360,196/360,280/360])
                self.idle_build_array = []

                # build random 'chunk' list
                done = False
                pos = 0
                while not done:
                    end = pos + random.randint(self.idle_build_chunk_min,self.idle_build_chunk_max)
                    if end >= numLEDs:
                        end = numLEDs - 1
                    self.idle_build_array.append((pos, end))
                    if end != numLEDs - 1:
                        pos = end
                    else:
                        done = True

            if self.idle_mode == 2:
                self.pixels = [(0,0,0)] * numLEDs

        if self.idle_mode_time <= time.time():
            self.idle_mode_time = time.time() + env_config.IDLE_MODE_CHANGE_TIME
            self.idle_mode += 1
            
            if self.idle_mode > self.idle_mode_max:
                self.idle_mode = 1
            # print("MODE: ", self.idle_mode)

            if self.idle_mode == 1:
                self.idle_mode_time = time.time() + env_config.IDLE_MODE_CHANGE_TIME
            if  self.idle_mode == 2:
                self.pixels = [(0,0,0)] * numLEDs
            elif self.idle_mode == 4:

                self.pixels = [(0,0,0)] * numLEDs
                self.effect_delay = self.idle_build_max_delay
                self.idle_color = random.choice([86/360,196/360,280/360,86/360,196/360,280/360,-1])

                self.idle_build_array = []

                # build random 'chunk' list
                done = False
                pos = 0
                while not done:
                    end = pos + random.randint(self.idle_build_chunk_min,self.idle_build_chunk_max)
                    if end >= numLEDs:
                        end = numLEDs - 1
                    self.idle_build_array.append((pos, end))
                    if end != numLEDs - 1:
                        pos = end
                    else:
                        done = True

            elif self.idle_mode == 3:
                self.idle_color = env_config.IDLE_SYNC_OFFSET01
            elif self.idle_mode == 6:
                self.pixels = [(0,0,0)] * numLEDs
                self.effect_delay = 35
        
        if self.idle_mode == 1:
            self.idle_static()
        elif self.idle_mode == 2:
            self.effect_delay = random.choice([2000,2500,3000])
            self.idle_rotate()
        elif self.idle_mode == 3:
            self.idle_rainbow()
            self.adj_brightness()
        elif self.idle_mode == 4:
            self.idle_build()
        # elif self.idle_mode == 5:
        #     self.idle_breath()
        #     self.adj_brightness()
        elif self.idle_mode == 5:
            self.idle_connect()
        elif self.idle_mode == 6:
            self.idle_sparkle()
        else:
            self.pixels = [(100,31,143)] * numLEDs

        
    def idle_static(self):
        
        if self.idle_change_time <= time.time():

            new_color = math.trunc(random.randint(0,299) / 100)
            while new_color == self.idle_color:
                new_color = math.trunc(random.randint(0,299) / 100)

            self.idle_color = new_color

            if self.idle_color == 2:
                self.idle_brightness = random.randint(65,85)/100
            else:
                self.idle_brightness = random.randint(55,75)/100

            self.idle_change_time = time.time() + env_config.IDLE_COLOR_CHANGE_TIME + random.randint(0,10) - 5

        if self.idle_color == 0:
            new_color = (LIB_BLUE_R*self.idle_brightness,LIB_BLUE_G*self.idle_brightness,LIB_BLUE_B*self.idle_brightness)
            self.pixels = [new_color] * numLEDs
        elif self.idle_color == 1:
            new_color = (LIB_GREEN_R*self.idle_brightness,LIB_GREEN_G*self.idle_brightness,LIB_GREEN_B*self.idle_brightness)
            self.pixels = [new_color] * numLEDs
        else:
            new_color = (LIB_PURPLE_R*self.idle_brightness,LIB_PURPLE_G*self.idle_brightness,LIB_PURPLE_B*self.idle_brightness)
            self.pixels = [new_color] * numLEDs

    def idle_rotate(self):
        if env_config.WIN_UPPER_PANE:
            pane = random.randint(0,3)
        else:
            pane = random.randint(0,2)
        new_color_index = random.choice([-1,86/360,196/360,280/360,-1,86/360,196/360,280/360])
        if new_color_index != -1:
            if env_config.LED_POWER_LIMIT:
                new_color = HSVtoRGB(new_color_index,1,0.8*env_config.LED_POWER_SCALE)
            else:
                new_color = HSVtoRGB(new_color_index,1,0.75)
        else:
            new_color = (0,0,0)

        if pane == 0:
            for i in range(env_config.WIN_PANE1[0],env_config.WIN_PANE1[1]):
                self.pixels[i] = new_color
        elif pane == 1:
            for i in range(env_config.WIN_PANE2[0],env_config.WIN_PANE2[1]):
                self.pixels[i] = new_color
        elif pane == 2:
            for i in range(env_config.WIN_PANE3[0],env_config.WIN_PANE3[1]):
                self.pixels[i] = new_color
        else:
            for i in range(env_config.WIN_PANE4[0],env_config.WIN_PANE4[1]):
                self.pixels[i] = new_color

    def idle_rainbow(self):
        new_color = HSVtoRGB(self.idle_color,1,1)

        self.idle_color += self.idle_step
        if(self.idle_color >= 1.0):
            self.idle_color = 0

        self.pixels = [new_color] * numLEDs

    def idle_build(self):
        if env_config.LED_POWER_LIMIT:
            new_color = HSVtoRGB(self.idle_color,1,0.8*env_config.LED_POWER_SCALE)
        else:
            new_color = HSVtoRGB(self.idle_color,1,0.75)

        if self.idle_build_dir:
            pick = random.randint(0, len(self.idle_build_array)-1)
            if len(self.idle_build_array) > 0:
                section = self.idle_build_array.pop(pick)
                self.idle_build_array2.append(section)
                for i in range(section[0],section[1]):
                    self.pixels[i] = new_color
            if self.effect_delay > 120:
                self.effect_delay = self.effect_delay*self.idle_build_speed
        else:
            pick = random.randint(0, len(self.idle_build_array2)-1)
            if len(self.idle_build_array2) > 0:
                section = self.idle_build_array2.pop(pick)
                self.idle_build_array.append(section)
                for i in range(section[0],section[1]):
                    self.pixels[i] = (0,0,0)
            if self.effect_delay > 120:
                self.effect_delay = self.effect_delay*self.idle_build_speed

        if len(self.idle_build_array) == 0:
            self.idle_build_dir = False
            self.effect_delay = self.idle_build_max_delay
        if len(self.idle_build_array2) == 0:
            self.idle_build_dir = True
            self.effect_delay = self.idle_build_max_delay

            self.idle_build_array = []
            self.idle_color = random.choice([86/360,196/360,280/360,86/360,196/360,280/360])

            # build random 'chunk' list
            done = False
            pos = 0
            while not done:
                end = pos + random.randint(self.idle_build_chunk_min,self.idle_build_chunk_max)
                if end >= numLEDs:
                    end = numLEDs - 1
                self.idle_build_array.append((pos, end))
                if end != numLEDs - 1:
                    pos = end
                else:
                    done = True

    def idle_connect(self):
        if self.state10_index < 100:
            self.state10_index = self.state10_index + 1

            offset = self.state10_posDistance * self.state10_index/100
            offsetRemain = offset % 1

            # print(offset)

            for pane in range(3):

                newpixel = self.state10_pos1[pane] + math.floor(offset)
                # print("pos1+ ", newpixel)
                if newpixel > self.state10_paneStart[pane] + self.state10_paneSize:
                    newpixel = newpixel - self.state10_paneSize - 1
                # print("newIndex: ", newpixel)
                self.pixels[newpixel] = HSVtoRGB(self.state10_colorchoices[self.state10_color],1,self.state10_otherBrightness)

                newpixel = self.state10_pos1[pane] - math.floor(offset)
                # print("pos1+ ", newpixel)
                if newpixel < self.state10_paneStart[pane]:
                    newpixel = newpixel + self.state10_paneSize + 1
                # print("newIndex: ", newpixel)
                self.pixels[newpixel] = HSVtoRGB(self.state10_colorchoices[self.state10_color],1,self.state10_otherBrightness)

                newpixel = self.state10_pos2[pane] + math.floor(offset)
                # print("pos1+ ", newpixel)
                if newpixel > self.state10_paneStart[pane] + self.state10_paneSize:
                    newpixel = newpixel - self.state10_paneSize - 1
                # print("newIndex: ", newpixel)
                self.pixels[newpixel] = HSVtoRGB(self.state10_colorchoices[self.state10_color],1,self.state10_otherBrightness)

                newpixel = self.state10_pos2[pane] - math.floor(offset)
                # print("pos1+ ", newpixel)
                if newpixel < self.state10_paneStart[pane]:
                    newpixel = newpixel + self.state10_paneSize + 1
                # print("newIndex: ", newpixel)
                self.pixels[newpixel] = HSVtoRGB(self.state10_colorchoices[self.state10_color],1,self.state10_otherBrightness)


        elif self.state10_index >= 100 and self.state10_index < 130:
            self.state10_index = self.state10_index + 1

            nop = 0

            for i in range(49999):
                nop = nop + 1

        else:
            self.state10_index = 4

            # print("pane size: ", self.state10_paneSize)
            # print("starts: ", self.state10_paneStart)

            oldcolor1 = self.state10_color
            oldcolor2 = self.state10_color - 1
            oldcolor3 = self.state10_color + 1
            if self.state10_color == 0:
                oldcolor2 = len(self.state10_colorchoices)
                oldcolor3 = self.state10_color + 1
            elif self.state10_color == len(self.state10_colorchoices):
                oldcolor2 = self.state10_color - 1
                oldcolor3 = 0

            newcolor = random.randint(0, len(self.state10_colorchoices)-1)
            while newcolor == oldcolor1 or newcolor == oldcolor2 or newcolor == oldcolor3:
                newcolor = random.randint(0, len(self.state10_colorchoices)-1)
            self.state10_color = newcolor

            for pane in range(3):

                self.state10_pos1[pane] = random.randint(self.state10_paneStart[pane], math.floor(self.state10_paneSize/2) + self.state10_paneStart[pane])
                self.state10_pos2[pane] = self.state10_pos1[pane] + math.floor(self.state10_paneSize/2)
  
                # self.pixels = [(0,0,0)] * numLEDs
                if self.state10_pos1[pane]-1 >= self.state10_paneStart[pane]:
                    self.pixels[self.state10_pos1[pane]-1] = HSVtoRGB(self.state10_colorchoices[self.state10_color],1,self.state10_centerBrightness)

                self.pixels[self.state10_pos1[pane]] = HSVtoRGB(self.state10_colorchoices[self.state10_color],1,self.state10_centerBrightness)

                if self.state10_pos1[pane]+1 <= self.state10_paneStart[pane] + self.state10_paneSize:
                    self.pixels[self.state10_pos1[pane]+1] = HSVtoRGB(self.state10_colorchoices[self.state10_color],1,self.state10_centerBrightness)

                if self.state10_pos1[pane]-1 >= self.state10_paneStart[pane]:
                    self.pixels[self.state10_pos2[pane]-1] = HSVtoRGB(self.state10_colorchoices[self.state10_color],1,self.state10_centerBrightness)

                self.pixels[self.state10_pos2[pane]] = HSVtoRGB(self.state10_colorchoices[self.state10_color],1,self.state10_centerBrightness)

                if self.state10_pos1[pane]+1 <= self.state10_paneStart[pane] + self.state10_paneSize:
                    self.pixels[self.state10_pos2[pane]+1] = HSVtoRGB(self.state10_colorchoices[self.state10_color],1,self.state10_centerBrightness)


    # sparkle effect
    def idle_sparkle(self):
        if self.state11_timer > 0:
            self.state11_timer = self.state11_timer - 1
        else:
            self.state11_timer = 2
            for p in range(0, len(self.state11_depthArray)-1):
                if self.state11_depthArray[p] == 1:
                    self.state11_activeArray[p] = 0
                    self.pixels[p] = (0,0,0)
                elif self.state11_depthArray[p] > 1:
                    self.state11_depthArray[p] = self.state11_depthArray[p] - 1
                    b = self.state11_brightnessIndex[self.state11_depthArray[p]-1]
                    self.pixels[p] = HSVtoRGB(self.state11_H,self.state11_S,b)
            upperRate = random.randint(self.state11_rateMin, self.state11_rateMax)
            for x in range(self.state11_rateMin, upperRate):
                newindex = random.randint(4, numLEDs-4)
                displacement = newindex - self.state11_prevNewIndex
                # print("displacemnt: ", displacement)
                while self.state11_activeArray[newindex] == 1 or self.state11_activeArray[newindex+1] == 1 or self.state11_activeArray[newindex-1] == 1 or self.state11_activeArray[newindex+2] == 1 or self.state11_activeArray[newindex-2] == 1 and (displacement > 20 or displacement < -20):
                    newindex = random.randint(4, numLEDs-4)
                    # print("newindex: ", newindex)
                self.state11_prevNewIndex = newindex
                self.state11_activeArray[newindex] = 1
                self.state11_depthArray[newindex] = len(self.state11_brightnessIndex)
                self.state11_depthArray[newindex+1] = math.floor(len(self.state11_brightnessIndex)*0.66)
                self.state11_depthArray[newindex-1] = math.floor(len(self.state11_brightnessIndex)*0.66)
                self.pixels[newindex] = HSVtoRGB(self.state11_H,self.state11_S,self.state11_brightnessIndex[len(self.state11_brightnessIndex)-1])

    def idle_breath(self):
        self.pixels = [(0,0,0)] * numLEDs

    # blank all LEDs
    def blank_leds(self):
        self.pixels = [(0,0,0)] * numLEDs
        client.put_pixels(self.pixels)

    # fades in to color; color switches to next in rainbow
    def rainbowfadein(self):
        
        self.pixels = [(0,0,0)] * numLEDs

        k = self.state3_brightness
        if k > 255:
            k = 255

        if self.state3_color == 0:
            self.pixels = [(k,0,0)] * numLEDs
        elif self.state3_color == 1:
            self.pixels = [(k,k*0.3,0)] * numLEDs
        elif self.state3_color == 2:
            self.pixels = [(k,k*0.9,0)] * numLEDs
        elif self.state3_color == 3:
            self.pixels = [(0,k,0)] * numLEDs
        elif self.state3_color == 4:
            self.pixels = [(0,k,k)] * numLEDs
        elif self.state3_color == 5:
            self.pixels = [(0,0,k)] * numLEDs
        else:
            self.pixels = [(k,0,k)] * numLEDs


        self.state3_brightness += self.state3_step
        if self.state3_brightness >= 400:
            self.state3_brightness = 0
            self.state3_color += 1
            if self.state3_color >= 7:
                self.state3_color = 0

    # goes through rainbow
    def rainbow(self):

        new_color = HSVtoRGB(self.state4_color,1,1)
        self.state4_color += self.state4_step
        if self.state4_color > 0.9999:
            self.state4_color = 0

        self.pixels = [new_color] * numLEDs



    # 5 pixels chase entire length of strip
    def chase(self):

        self.pixels = [(0,0,0)] * numLEDs

        for i in range(20):
            pos = self.state5_position + i
            if i < 14:
                new_color = HSVtoRGB(self.state5_color,1,(i/20))
            else:
                new_color = HSVtoRGB(self.state5_color,1,1)

            if pos > 0 and pos < numLEDs:
                self.pixels[pos] = new_color

        self.state5_position += self.state5_speed
        if self.state5_position > (numLEDs + 10):
            self.state5_position = -14



    # 5 pixels chase entire length of strip
    def dualchase(self):

        self.pixels = [(0,0,0)] * numLEDs


        for i in range(12):
            pos = self.state7_position + i
            pos2 = self.state7_position2 + i

            if i < 9:
                new_color = HSVtoRGB(self.state7_color,1,(i/12))
                new_color2 = HSVtoRGB(self.state7_color2,1,(i/12))
            else:
                new_color = HSVtoRGB(self.state7_color,1,1)
                new_color2 = HSVtoRGB(self.state7_color2,1,1)
                
            if pos > 0 and pos < numLEDs:
                self.pixels[pos] = new_color

            if pos2 > 0 and pos2 < numLEDs:
                self.pixels[pos2] = new_color2

        self.state7_position += self.state5_speed
        if self.state7_position > (numLEDs + 10):
            self.state7_position = -10

        self.state7_position2 += self.state5_speed
        if self.state7_position2 > (numLEDs + 10):
            self.state7_position2 = -10



    # 5 pixels chase entire length of strip
    def triplechase(self):

        self.pixels = [(0,0,0)] * numLEDs


        for i in range(12):
            pos = self.state8_position + i
            pos2 = self.state8_position2 + i
            pos3 = self.state8_position3 + i

            if i < 9:
                new_color = HSVtoRGB(self.state8_color,1,(i/12))
                new_color2 = HSVtoRGB(self.state8_color2,1,(i/12))
                new_color3 = HSVtoRGB(self.state8_color3,1,(i/12))
            else:
                new_color = HSVtoRGB(self.state8_color,1,1)
                new_color2 = HSVtoRGB(self.state8_color2,1,1)
                new_color3 = HSVtoRGB(self.state8_color3,1,1)
                
            if pos > 0 and pos < numLEDs:
                self.pixels[pos] = new_color

            if pos2 > 0 and pos2 < numLEDs:
                self.pixels[pos2] = new_color2

            if pos3 > 0 and pos3 < numLEDs:
                self.pixels[pos3] = new_color3

        self.state8_position += self.state5_speed
        if self.state8_position > (numLEDs + 10):
            self.state8_position = -10

        self.state8_position2 += self.state5_speed
        if self.state8_position2 > (numLEDs + 10):
            self.state8_position2 = -10

        self.state8_position3 += self.state5_speed
        if self.state8_position3 > (numLEDs + 10):
            self.state8_position3 = -10

    # theatre chase
    def theatre_chase(self):

        self.pixels = [(0,0,0)] * numLEDs

        for i in range(numLEDs - 6):
            if (i+self.state6_position) % 12 == 0:
                self.pixels[i+6] = HSVtoRGB(self.state6_color,1,self.state6_brightness)
                self.pixels[i+5] = HSVtoRGB(self.state6_color,1,self.state6_brightness)
                self.pixels[i+4] = HSVtoRGB(self.state6_color,1,self.state6_brightness*0.8)
                self.pixels[i+3] = HSVtoRGB(self.state6_color,1,self.state6_brightness*0.6)
                self.pixels[i+2] = HSVtoRGB(self.state6_color,1,self.state6_brightness*0.4)
                self.pixels[i+1] = HSVtoRGB(self.state6_color,1,self.state6_brightness*0.2)
                self.pixels[i] = HSVtoRGB(self.state6_color,1,self.state6_brightness*0.1)

        self.state6_position -= 1
        if self.state6_position == 0:
            self.state6_position = 11



    # Build up/down
    def build_up_down(self):
        if env_config.LED_POWER_LIMIT:
            new_color = HSVtoRGB(self.state9_color,1,0.8*env_config.LED_POWER_SCALE)
        else:
            new_color = HSVtoRGB(self.state9_color,1,0.75)

        if self.state9_dir:
            pick = random.randint(0, len(self.state9_array)-1)
            if len(self.state9_array) > 0:
                section = self.state9_array.pop(pick)
                self.state9_array2.append(section)
                for i in range(section[0],section[1]):
                    self.pixels[i] = new_color
            if self.effect_delay > self.state9_min_delay:
                self.effect_delay = self.effect_delay*self.state9_speed
        else:
            pick = random.randint(0, len(self.state9_array2)-1)
            if len(self.state9_array2) > 0:
                section = self.state9_array2.pop(pick)
                self.state9_array.append(section)
                for i in range(section[0],section[1]):
                    self.pixels[i] = (0,0,0)
            if self.effect_delay > self.state9_min_delay:
                self.effect_delay = self.effect_delay*self.state9_speed

        if len(self.state9_array) == 0:
            self.state9_dir = False
            self.effect_delay = self.state9_max_delay
        if len(self.state9_array2) == 0:
            self.state9_dir = True
            self.effect_delay = self.state9_max_delay

            self.state9_array = []

            # build random 'chunk' list
            done = False
            pos = 0
            while not done:
                end = pos + random.randint(self.state9_chunk_min,self.state9_chunk_max)
                if end >= numLEDs:
                    end = numLEDs - 1
                self.state9_array.append((pos, end))
                if end != numLEDs - 1:
                    pos = end
                else:
                    done = True


    # connect from opposite side of window
    def connect(self):
        if self.state10_index < 100:
            self.state10_index = self.state10_index + 1

            offset = self.state10_posDistance * self.state10_index/100
            offsetRemain = offset % 1

            # print(offset)

            for pane in range(3):

                newpixel = self.state10_pos1[pane] + math.floor(offset)
                # print("pos1+ ", newpixel)
                if newpixel > self.state10_paneStart[pane] + self.state10_paneSize:
                    newpixel = newpixel - self.state10_paneSize - 1
                # print("newIndex: ", newpixel)
                self.pixels[newpixel] = HSVtoRGB(self.state10_colorchoices[self.state10_color],1,self.state10_otherBrightness)

                newpixel = self.state10_pos1[pane] - math.floor(offset)
                # print("pos1+ ", newpixel)
                if newpixel < self.state10_paneStart[pane]:
                    newpixel = newpixel + self.state10_paneSize + 1
                # print("newIndex: ", newpixel)
                self.pixels[newpixel] = HSVtoRGB(self.state10_colorchoices[self.state10_color],1,self.state10_otherBrightness)

                newpixel = self.state10_pos2[pane] + math.floor(offset)
                # print("pos1+ ", newpixel)
                if newpixel > self.state10_paneStart[pane] + self.state10_paneSize:
                    newpixel = newpixel - self.state10_paneSize - 1
                # print("newIndex: ", newpixel)
                self.pixels[newpixel] = HSVtoRGB(self.state10_colorchoices[self.state10_color],1,self.state10_otherBrightness)

                newpixel = self.state10_pos2[pane] - math.floor(offset)
                # print("pos1+ ", newpixel)
                if newpixel < self.state10_paneStart[pane]:
                    newpixel = newpixel + self.state10_paneSize + 1
                # print("newIndex: ", newpixel)
                self.pixels[newpixel] = HSVtoRGB(self.state10_colorchoices[self.state10_color],1,self.state10_otherBrightness)


        elif self.state10_index >= 100 and self.state10_index < 130:
            self.state10_index = self.state10_index + 1

            nop = 0

            for i in range(49999):
                nop = nop + 1

        else:
            self.state10_index = 4

            # print("pane size: ", self.state10_paneSize)
            # print("starts: ", self.state10_paneStart)

            oldcolor1 = self.state10_color
            oldcolor2 = self.state10_color - 1
            oldcolor3 = self.state10_color + 1
            if self.state10_color == 0:
                oldcolor2 = len(self.state10_colorchoices)
                oldcolor3 = self.state10_color + 1
            elif self.state10_color == len(self.state10_colorchoices):
                oldcolor2 = self.state10_color - 1
                oldcolor3 = 0

            newcolor = random.randint(0, len(self.state10_colorchoices)-1)
            while newcolor == oldcolor1 or newcolor == oldcolor2 or newcolor == oldcolor3:
                newcolor = random.randint(0, len(self.state10_colorchoices)-1)
            self.state10_color = newcolor

            for pane in range(3):

                self.state10_pos1[pane] = random.randint(self.state10_paneStart[pane], math.floor(self.state10_paneSize/2) + self.state10_paneStart[pane])
                self.state10_pos2[pane] = self.state10_pos1[pane] + math.floor(self.state10_paneSize/2)
  
                # self.pixels = [(0,0,0)] * numLEDs
                if self.state10_pos1[pane]-1 >= self.state10_paneStart[pane]:
                    self.pixels[self.state10_pos1[pane]-1] = HSVtoRGB(self.state10_colorchoices[self.state10_color],1,self.state10_centerBrightness)

                self.pixels[self.state10_pos1[pane]] = HSVtoRGB(self.state10_colorchoices[self.state10_color],1,self.state10_centerBrightness)

                if self.state10_pos1[pane]+1 <= self.state10_paneStart[pane] + self.state10_paneSize:
                    self.pixels[self.state10_pos1[pane]+1] = HSVtoRGB(self.state10_colorchoices[self.state10_color],1,self.state10_centerBrightness)

                if self.state10_pos1[pane]-1 >= self.state10_paneStart[pane]:
                    self.pixels[self.state10_pos2[pane]-1] = HSVtoRGB(self.state10_colorchoices[self.state10_color],1,self.state10_centerBrightness)

                self.pixels[self.state10_pos2[pane]] = HSVtoRGB(self.state10_colorchoices[self.state10_color],1,self.state10_centerBrightness)

                if self.state10_pos1[pane]+1 <= self.state10_paneStart[pane] + self.state10_paneSize:
                    self.pixels[self.state10_pos2[pane]+1] = HSVtoRGB(self.state10_colorchoices[self.state10_color],1,self.state10_centerBrightness)
            
            # for i in range(3):
            #     print("Pane: ", i, " Pos1: ", self.state10_pos1[i], " Pos2: ", self.state10_pos2[i])

    # sparkle effect
    def sparkle(self):
        if self.state11_timer > 0:
            self.state11_timer = self.state11_timer - 1
        else:
            self.state11_timer = 2
            for p in range(0, len(self.state11_depthArray)-1):
                if self.state11_depthArray[p] == 1:
                    self.state11_activeArray[p] = 0
                    self.pixels[p] = (0,0,0)
                elif self.state11_depthArray[p] > 1:
                    self.state11_depthArray[p] = self.state11_depthArray[p] - 1
                    b = self.state11_brightnessIndex[self.state11_depthArray[p]-1]
                    self.pixels[p] = HSVtoRGB(self.state11_H,self.state11_S,b)
            upperRate = random.randint(self.state11_rateMin, self.state11_rateMax)
            for x in range(self.state11_rateMin, upperRate):
                newindex = random.randint(4, numLEDs-4)
                displacement = newindex - self.state11_prevNewIndex
                # print("displacemnt: ", displacement)
                while self.state11_activeArray[newindex] == 1 or self.state11_activeArray[newindex+1] == 1 or self.state11_activeArray[newindex-1] == 1 or self.state11_activeArray[newindex+2] == 1 or self.state11_activeArray[newindex-2] == 1 and (displacement > 20 or displacement < -20):
                    newindex = random.randint(4, numLEDs-4)
                    # print("newindex: ", newindex)
                self.state11_prevNewIndex = newindex
                self.state11_activeArray[newindex] = 1
                self.state11_depthArray[newindex] = len(self.state11_brightnessIndex)
                self.state11_depthArray[newindex+1] = math.floor(len(self.state11_brightnessIndex)*0.66)
                self.state11_depthArray[newindex-1] = math.floor(len(self.state11_brightnessIndex)*0.66)
                self.pixels[newindex] = HSVtoRGB(self.state11_H,self.state11_S,self.state11_brightnessIndex[len(self.state11_brightnessIndex)-1])

    # dualsparkle effect
    def dualsparkle(self):
        if self.state12_timer > 0:
            self.state12_timer = self.state12_timer - 1
        else:
            self.state12_timer = 2
            for p in range(0, len(self.state12_depthArray)-1):
                if self.state12_depthArray[p] == 1:
                    self.state12_activeArray[p] = 0
                    self.pixels[p] = (0,0,0)
                elif self.state12_depthArray[p] > 1:
                    self.state12_depthArray[p] = self.state12_depthArray[p] - 1
                    b = self.state12_brightnessIndex[self.state12_depthArray[p]-1]
                    if self.state12_activeArray[p] == 1 or self.state12_activeArray[p+1] == 1 or self.state12_activeArray[p-1] == 1:
                        self.pixels[p] = HSVtoRGB(self.state12_H1,self.state12_S1,b)
                    else:
                        self.pixels[p] = HSVtoRGB(self.state12_H2,self.state12_S2,b)
                    
            upperRate = random.randint(self.state12_rateMin, self.state12_rateMax)
            for x in range(self.state12_rateMin, upperRate):
                newindex = random.randint(4, numLEDs-4)
                displacement = newindex - self.state12_prevNewIndex
                # print("displacemnt: ", displacement)
                while self.state12_activeArray[newindex] == 1 or self.state12_activeArray[newindex+1] == 1 or self.state12_activeArray[newindex-1] == 1 or self.state12_activeArray[newindex+2] == 1 or self.state12_activeArray[newindex-2] == 1 and (displacement > 20 or displacement < -20):
                    newindex = random.randint(4, numLEDs-4)
                    # print("newindex: ", newindex)
                self.state12_prevNewIndex = newindex
                self.state12_activeArray[newindex] = random.randint(1,2)
                self.state12_depthArray[newindex] = len(self.state12_brightnessIndex)
                self.state12_depthArray[newindex+1] = math.floor(len(self.state12_brightnessIndex)*0.66)
                self.state12_depthArray[newindex-1] = math.floor(len(self.state12_brightnessIndex)*0.66)
                if self.state12_activeArray[newindex] == 1:
                    self.pixels[newindex] = HSVtoRGB(self.state12_H1,self.state12_S1,self.state12_brightnessIndex[len(self.state12_brightnessIndex)-1])
                else:
                    self.pixels[newindex] = HSVtoRGB(self.state12_H2,self.state12_S2,self.state12_brightnessIndex[len(self.state12_brightnessIndex)-1])

    # meteor
    # def meteor(self):

    #     for i in range(numLEDs):
    #         if self.pixels[i] != (0,0,0):
    #             self.pixels[i] = (self.pixels[i][0] * 0.65, self.pixels[i][0] * 0.65, self.pixels[i][0] * 0.65)
    #             if self.pixels[i][0] < 25 or self.pixels[i][1] < 25 or self.pixels[i][2] < 25:
    #                 self.pixels[i] = (0,0,0)
    #     # self.pixels = [(0,0,0)] * numLEDs
        
    #     # create new tail color
    #     tail_color = random.choice([0,1,2,0,1,2,0,1,2,0,1,2,0,1,2])
    #     if tail_color == 0:
    #         new_color = HSVtoRGB(self.state10_color[0],self.state10_color[1],self.state10_color[2])
    #     elif tail_color == 1:
    #         new_color = HSVtoRGB(self.state10_color2[0],self.state10_color2[1],self.state10_color2[2])
    #     else:
    #         new_color = HSVtoRGB(self.state10_color3[0],self.state10_color3[1],self.state10_color3[2])

    #     # make new decay array
    #     major = random.choice([0.65,0.8,0.8,0.65,0.8,0.65,0.65,0.8,0.65,0.65,0.8,0.65,0.8,0.8,0.8,0.65,0.8,0.65,0.65,0.8,0.8,0.65,0.65,0.8,0.65,0.65])
    #     if len(self.state10_decay_array) == 0:
    #         for i in range(self.state10_tail_len + 1):
    #             self.state10_decay_array.append(round(random.uniform(self.state10_decay_rate_min, self.state10_decay_rate_max), 2) + major)
    #         self.state10_decay_array[0] = self.state10_tail_val
    #         self.state10_decay_array[self.state10_tail_len] = 0
    #     else:   # adj decay array by 1
    #         self.state10_decay_array.pop()
    #         self.state10_decay_array.insert(0, self.state10_tail_val)
    #         self.state10_decay_array[self.state10_tail_len] = 0
    #         self.state10_decay_array[1] = round(random.uniform(self.state10_decay_rate_min, self.state10_decay_rate_max), 2) + major

    #     # print("decay: ", self.state10_decay_array)

    #     # make new decay pixels
    #     if len(self.state10_decay_pixels) == 0:
    #         self.state10_decay_pixels = [(0,0,0)] * (self.state10_tail_len + 1)

    #     # take off old pixel, insert new pixel
    #     self.state10_decay_pixels.pop()
    #     self.state10_decay_pixels.insert(0, new_color)

    #     # make new meteor
    #     if len(self.state10_array) == 0:
    #         for i in range(self.state10_tail_len + self.state10_len + 1):
    #             self.state10_array.append((0,0,0))

    #     # decay
    #     for i in range(self.state10_tail_len, len(self.state10_array)):
    #         new_pixel = (self.state10_decay_pixels[i-self.state10_tail_len][0] * self.state10_decay_array[i-self.state10_tail_len],
    #                     self.state10_decay_pixels[i-self.state10_tail_len][1] * self.state10_decay_array[i-self.state10_tail_len],
    #                     self.state10_decay_pixels[i-self.state10_tail_len][2] * self.state10_decay_array[i-self.state10_tail_len]
    #                     )
    #         self.state10_decay_pixels[i-self.state10_tail_len] = ( int(new_pixel[0]), int(new_pixel[1]), int(new_pixel[2]) )

    #     # copy decay pixel to main array
    #     for i in range(len(self.state10_decay_pixels)):
    #         self.state10_array[i + self.state10_len] = self.state10_decay_pixels[i]

    #     # head
    #     new_color = HSVtoRGB(self.state10_color[0],self.state10_color[1],self.state10_color[2])
    #     self.state10_array[0] = new_color
    #     self.state10_array[1] = new_color
    #     self.state10_array[2] = new_color
    #     for i in range(3, self.state10_len):
    #         new_color = HSVtoRGB(self.state10_color[0],self.state10_color[1],self.state10_color[2] * (1-(0.08*i)))
    #         self.state10_array[i] = new_color

    #     # insert new tail color
    #     # self.state10_array[self.state10_tail_len] = new_color

    #     # print("Array: ", self.state10_array)

    #     for i in range(len(self.state10_array)):
    #         pos = i + self.state10_index
    #         if pos < numLEDs:
    #             self.pixels[pos] = self.state10_array[len(self.state10_array) - 1 - i]
    #         else:
    #             self.pixels[pos - numLEDs] = self.state10_array[len(self.state10_array) - 1 - i]

    #     self.state10_index += 1
    #     if self.state10_index >= numLEDs:
    #         self.state10_index = 0

