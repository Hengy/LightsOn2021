from flask import Flask, render_template, request, session, url_for, redirect
from flask_socketio import SocketIO, emit
from flask_socketio import send as sendio
from flask import send_from_directory

import os
import subprocess

import time
import datetime

import zmq
from zmq.eventloop.ioloop import ZMQIOLoop
from zmq.eventloop.zmqstream import ZMQStream

import json

import uuid

import pickle

from apscheduler.schedulers.background import BackgroundScheduler

import env_config

import math

# -----------------------------------------------------
# FLASK CONFIG
# -----------------------------------------------------
app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SECRET_KEY'] = b'6hc/_gsh,./;2ZZx3c6_s,1//'
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
socketio = SocketIO(app,cors_allowed_origins="*")

# -----------------------------------------------------
# USER QUEUE
# -----------------------------------------------------
user_queue = []

# -----------------------------------------------------
# USER CLASS
# -----------------------------------------------------
class Controller():
  _controller = False
  _IP = None
  _position = None
  _UUID = None
  _time_start = None
  _time_end = None
  
  # -----------------------------------------------------
  # class init
  # -----------------------------------------------------
  def __init__(self, IP, pos, ctrl):
    self._controller = ctrl
    self._IP = IP
    self._position = pos
    self._UUID = uuid.uuid4()
    self._time_start = time.time()

  # returns user IP address
  def get_IP(self):
    return self._IP

  # returns user position in queue
  def get_position(self):
    return self._position

  # set user position in queue
  def set_position(self, pos):
    self._position = pos

  # decrement user position in queue
  def decr_position(self):
    self._position -= 1

  # returns if user is current LED controller
  def get_ctrl(self):
    return self._controller

  # set user LED controller status
  def set_ctrl(self, ctrl):
    self._controller = ctrl

  # return user UUID
  def get_uuid(self):
    return self._UUID

  # return time user was created (added to queue)
  def get_time_start(self):
    return self._time_start

  # return time user was created (added to queue)
  def set_time_start(self, t):
    self._time_start = t

  # return user end of session time
  def get_time_end(self):
    return self._time_end

  # set user end of session time
  def set_time_end(self, t):
    self._time_end = t

  # modify uuid for controlling all displays
  def mod_uuid(self):
    print("modifying UUID")
    uuid_str = str(self._UUID)
    new_uuid = (env_config.UUID_MODIFIER + uuid_str[8:45])
    print(new_uuid)
    self._UUID = uuid.UUID(new_uuid)

# -----------------------------------------------------
# ZMQ global context
# -----------------------------------------------------
ws_context = zmq.Context()


# -----------------------------------------------------
# Database add record
# -----------------------------------------------------
def database_add_rec(rec):

  if rec["type"] == "effect":
    print("recording effect to db")

    try:
      with sql.connect("database.db") as con:
        cur = con.cursor()
        cur.execute( "INSERT INTO use_effect (timestamp,UUID,queue_pos,window,window_ip) VALUES (NOW(),?,?,?)", (rec["uuid"], rec["queue_pos"], rec["window"], rec["ip"]) )
        con.commit()

    except:

      con.rollback()
      print("Database insert error")

    finally:
      
      con.close()

  elif rec["type"] == "window":
    print("recording window to db")

  else:
    print("unknown record type")


# -----------------------------------------------------
# Check if it is within Lights On time
# returns True if it is between TIME_ON and TIME_OFF
# -----------------------------------------------------
def check_in_time():
  in_time = False
  hour_now = datetime.datetime.now().hour
  if hour_now >= env_config.TIME_ON_HOUR:
    if hour_now <= env_config.TIME_OFF_HOUR:
      in_time = True

  return in_time

# -----------------------------------------------------
# Check if current controller time has elapsed
# -----------------------------------------------------
def controllercheck():

  popped = False

  if len(user_queue) > 0:
    if user_queue[0].get_time_end() < time.time(): # if controller time had expired
      print("new controller!")

      # send_zmq_msg("IDLE", None, None)

      send_zmq_msg("Stop Controller", None, None)
      user_queue.pop(0)
      popped = True

      if len(user_queue) > 0:
        print("next!")
        for i in range(len(user_queue)):
          user_queue[i].decr_position()
        
        user_queue[0].set_ctrl(True)
        user_queue[0].set_time_end(time.time() + env_config.QUEUE_MAX_TIME)
        time.sleep(0.2)
        send_zmq_msg("New Controller", str(user_queue[0].get_uuid()), str(user_queue[0].get_IP()))
      
  return popped


# -----------------------------------------------------
# Check if user position in queue changes
# -----------------------------------------------------
def waitcheck(uuid):
  result = False

  for i in range(len(user_queue)):
    uuid1 = str(user_queue[i].get_uuid())
    uuid2 = str(uuid)
    if uuid1 == uuid2:
      result = user_queue[i].get_ctrl()
      break

  if result:
    print("waiting over")

  return result

# -----------------------------------------------------
# Send ZMQ message to Fadecandy Web API process
# -----------------------------------------------------
def send_zmq_msg(msg, uuid, ip):
  # set up Zero MQ connection to websocket server
  socket = ws_context.socket(zmq.PAIR)

  socket.connect(env_config.ZMQ_SOCKET_IP + ":" + env_config.ZMQ_SOCKET_PORT)

  response = {"message":msg, "uuid":uuid, "IP": ip}

  socket.send_json(response)
  socket.close()


# -----------------------------------------------------
# INDEX
# -----------------------------------------------------
@app.route("/")
def index():

  if check_in_time():
  
    queue_len = len(user_queue)
    if 'uuid' in session:
      # session in progress
      return redirect(url_for('ledctrl'), code=307)
    else:
      return render_template("index.html", queue_len=queue_len, in_progress=False, in_time=True, dmx=env_config.PI_DISPLAY_TYPE, choose_url=env_config.CHOOSE_DISPLAY_URL)

  else:

    return render_template("index.html", in_time=False, choose_url=env_config.CHOOSE_DISPLAY_URL)


# -----------------------------------------------------
# INDEX for controlling all
# -----------------------------------------------------
@app.route("/all")
def all():

  if env_config.SELF_IP in env_config.RPI_MASTER:

    print("This is master Pi. Accessing Control All web interface")

    if check_in_time():
    
      queue_len = len(user_queue)
      if 'uuid' in session:
        # session in progress
        return redirect(url_for('ledctrl'), code=307)
      else:
        return render_template("indexforall.html", queue_len=queue_len, in_progress=False, in_time=True, dmx=env_config.PI_DISPLAY_TYPE, choose_url=env_config.CHOOSE_DISPLAY_URL)

    else:

      return render_template("indexforall.html", in_time=False, choose_url=env_config.CHOOSE_DISPLAY_URL)

  else:

    print("This is NOT master Pi. Redirecting to single display")

    return redirect(url_for('.index'), code=307)


# -----------------------------------------------------
# END
# Ends session; removes controller from queue
# -----------------------------------------------------
@app.route("/end")
def end():

  user_uuid = session.get('uuid')

  if not user_uuid is None: # if uuid session variable exists
    session.pop('uuid', None)

    for i in range(len(user_queue)):
      if str(user_queue[i].get_uuid()) == str(user_uuid):
        
        user_queue.pop(i)
        
        if i == 0:
          # send_zmq_msg("IDLE", None, None)
          send_zmq_msg("Stop Controller", None, None)

          if len(user_queue) > 0:
            user_queue[0].set_ctrl(True)
            time.sleep(0.2)
            send_zmq_msg("New Controller", str(user_queue[0].get_uuid()), str(user_queue[0].get_IP()))

        for k in range(i, len(user_queue)):

          user_queue[k].decr_position()

        break

  return redirect(url_for('.index'), code=307)


# -----------------------------------------------------
# CHOOSE ANOTHER
# Ends session; removes controller from queue
# Rediects to https://stratford.library.on.ca/lightson
# -----------------------------------------------------
@app.route("/chooseanother")
def choose_antoher():

  user_uuid = session.get('uuid')

  if not user_uuid is None: # if uuid session variable exists
    session.pop('uuid', None)

    for i in range(len(user_queue)):
      if str(user_queue[i].get_uuid()) == str(user_uuid):
        
        user_queue.pop(i)
        
        if i == 0:
          # send_zmq_msg("IDLE", None, None)
          send_zmq_msg("Stop Controller", None, None)

          if len(user_queue) > 0:
            user_queue[0].set_ctrl(True)
            time.sleep(0.2)
            send_zmq_msg("New Controller", str(user_queue[0].get_uuid()), str(user_queue[0].get_IP()))

        for k in range(i, len(user_queue)):

          user_queue[k].decr_position()

        break

  return redirect(env_config.CHOOSE_DISPLAY_URL)


# -----------------------------------------------------
# ADD TO QUEUE
# Adds new user to queue
# -----------------------------------------------------
@app.route("/addtoqueue")
def addtoqueue():
  
  user = None
  user_uuid = session.get('uuid')
  if not user_uuid is None: # if uuid session variable exists
    controller = False
    for user in user_queue:
      if str(user_uuid) == str(user.get_uuid()):
        controller = True
        return redirect(url_for('ledctrl', uuid=user_uuid))
    
    if not controller:
      return redirect(url_for('waitqueue', uuid=user_uuid))

  else:
    if len(user_queue) == 0:
      # empty queue, give control right away

      print("Adding user. First in queue.")

      user = Controller(request.remote_addr, len(user_queue), True)
      user.set_time_end(time.time() + env_config.QUEUE_MAX_TIME)
      user_queue.append(user)

      session['uuid'] = user.get_uuid()

      time.sleep(0.1)
      send_zmq_msg("New Controller", str(user.get_uuid()), str(request.remote_addr))

      return redirect(url_for('ledctrl'), code=307)

    elif len(user_queue) < env_config.QUEUE_MAX:
      # queue not empty, add to queue

      print("Adding user to queue. Position ", len(user_queue) + 1)

      user = Controller(request.remote_addr, len(user_queue), False)
      user.set_time_end(time.time() + (len(user_queue) * env_config.QUEUE_MAX_TIME))
      user_queue.append(user)

      session['uuid'] = user.get_uuid()

      return redirect(url_for('waitqueue', uuid=user.get_uuid()))
      #return render_template("queuewait.html", queue_full=False, queue_pos=pos, max_queue=maxq)
    
    else:
      # queue is full
      return redirect(url_for('queuefull'))


# -----------------------------------------------------
# ADD TO QUEUE
# Adds new user that can controll all RPis to queue
# -----------------------------------------------------
@app.route("/addtoqueueall")
def addtoqueueall():
  
  user = None
  user_uuid = session.get('uuid')
  if not user_uuid is None: # if uuid session variable exists
    controller = False
    for user in user_queue:
      if str(user_uuid) == str(user.get_uuid()):
        controller = True
        return redirect(url_for('ledctrl', uuid=user_uuid))
    
    if not controller:
      return redirect(url_for('waitqueue', uuid=user_uuid))

  else:
    if len(user_queue) == 0:
      # empty queue, give control right away

      print("Adding user. First in queue.")

      user = Controller(request.remote_addr, len(user_queue), True)
      user.mod_uuid()
      user.set_time_end(time.time() + env_config.QUEUE_MAX_TIME)
      user_queue.append(user)

      session['uuid'] = user.get_uuid()

      time.sleep(0.1)
      send_zmq_msg("New Controller", str(user.get_uuid()), str(request.remote_addr))

      return redirect(url_for('ledctrl'), code=307)

    elif len(user_queue) < env_config.QUEUE_MAX:
      # queue not empty, add to queue

      print("Adding user to queue. Position ", len(user_queue) + 1)

      user = Controller(request.remote_addr, len(user_queue), False)
      user.mod_uuid()
      user.set_time_end(time.time() + (len(user_queue) * env_config.QUEUE_MAX_TIME))
      user_queue.append(user)

      session['uuid'] = user.get_uuid()

      return redirect(url_for('waitqueue', uuid=user.get_uuid()))
      #return render_template("queuewait.html", queue_full=False, queue_pos=pos, max_queue=maxq)
    
    else:
      # queue is full
      return redirect(url_for('queuefull'))
      

# -----------------------------------------------------
# QUEUE WAIT
# Wait for turn in queue
# -----------------------------------------------------
@app.route("/waitqueue", methods = ['GET', 'POST'])
def waitqueue():
  pos = None
  user_uuid = session.get('uuid')

  for user in user_queue:
    if str(user_uuid) == str(user.get_uuid()):
      pos = user.get_position()
      break

  maxq = env_config.QUEUE_MAX

  time_left = (user_queue[0].get_time_end() - time.time()) + ((pos-1) * env_config.QUEUE_MAX_TIME)
  time_left_ceil = math.trunc(time_left)

  return render_template("queuewait.html", queue_full=False, queue_pos=pos, max_queue=maxq-1, user_uuid=user_uuid, user_ip=request.remote_addr, time_wait=time_left_ceil)

# -----------------------------------------------------
# QUEUE FULL
# Queue is full
# -----------------------------------------------------
@app.route("/queuefull")
def queuefull():

  time_diff = (user_queue[0].get_time_end() - time.time()) + ((len(user_queue)-1) * env_config.QUEUE_MAX_TIME) + 2 # calcualte seconds until queue is not full, add 10 sec

  time_wait = math.ceil(time_diff)   # round number up

  return render_template("queuefull.html", wait_time=time_wait)


# -----------------------------------------------------
# LED CONTROL
# Allows controller to control LEDs
# -----------------------------------------------------
@app.route("/ledctrl")
def ledctrl():

  if check_in_time():
  
    if len(user_queue) > 0:

      if not session.get('uuid') is None: # if uuid session variable exists
        if user_queue[0].get_uuid() == session.get('uuid'):

          user_queue[0].set_time_start(time.time())
          time_left = user_queue[0].get_time_end() - time.time()
          time_left_ceil = math.trunc(time_left)
          dmx = env_config.PI_DISPLAY_TYPE
          ctrl_all = False

          if env_config.UUID_MODIFIER == str(session.get('uuid'))[0:8]:
            print("ctrl_all = true")
            ctrl_all = True
            send_zmq_msg("SYNCON", str(session.get('uuid')), str(request.remote_addr))

          return render_template("ledctrl.html", user_uuid=session.get('uuid'), user_ip=str(request.remote_addr), time_end=math.floor(user_queue[0].get_time_end()), time_wait=time_left_ceil, dmx=dmx, ctrl_all=ctrl_all, ip_list=json.dumps(env_config.RPI_IPS))

        else:

          print("ERROR! Should not be able to control LEDs at this time")

          return redirect(url_for('end'), code=307)
      
      else:

        print("ERROR!")

        return redirect(url_for('end'), code=307)

    else:

      print("ERROR! Should not be able to control LEDs at this time")

      return redirect(url_for('end'), code=307)

  else:

    return redirect(url_for('end'), code=307)

# -----------------------------------------------------
# Gives all templates the SELF_IP variable
# -----------------------------------------------------
@app.context_processor
def inject_selfip():
    return dict(self_ip=env_config.SELF_IP, self_port=env_config.SELF_PORT)


# -----------------------------------------------------
# ON SCIKETIO CONNECT
# -----------------------------------------------------
@socketio.on('connect')
def io_connect():
  controllercheck()
  # print("Client SocketIO connected")

# -----------------------------------------------------
# ON SCIKETIO CONNECT
# -----------------------------------------------------
@socketio.on('disconnect')
def io_disconnect():
  controllercheck()
  # print("Client SocketIO disconnected")

# -----------------------------------------------------
# ON SCIKETIO 'SWITCH CONTROL' EVENT
# -----------------------------------------------------
@socketio.on('switch control')
def switchctrl_handler(jsonmsg, methods=['POST']):
  print('Recieved JSON: ' + str(json))

# -----------------------------------------------------
# ON SCIKETIO 'CHECK' EVENT
# Replaces HTTP heartbeat; checks if controller end time
# has been reached - returns True if time has elapsed
# -----------------------------------------------------
@socketio.on('check')
def check_handler(jsonmsg, methods=['POST']):
  time_expired = controllercheck()
  if time_expired:
    print("Check handled; time expired")
  data = json.dumps({"check_result":time_expired})
  emit('check_result', data)

# -----------------------------------------------------
# ON SCIKETIO 'WAIT' EVENT
# query if user position in queue has changed
# -----------------------------------------------------
@socketio.on('wait')
def wait_handler(jsonmsg, methods=['POST']):
  gain_ctrl = waitcheck(str(jsonmsg['uuid']))
  if gain_ctrl:
    print("Wait handled; giving control to next in queue")
  data = json.dumps({"wait_result":gain_ctrl})
  emit('wait_result', data)


# -----------------------------------------------------
# LIGHTS ON FLASK APP MAIN
# -----------------------------------------------------
if __name__ == "__main__":

  print("Local IP Address: ", env_config.get_self_ip())
  print("Now env_config SELF_IP is: ", env_config.SELF_IP)

  env_config.config_leds()

  print("Upper Pane: ", env_config.WIN_UPPER_PANE)
  print("Display type (0 = LEDs, 1 = DMX/Relays): ", env_config.PI_DISPLAY_TYPE)
  print("LEDs: ", env_config.NUM_LEDS)

  print("Flask Process ID: ", os.getpid())

  # app.run(host='0.0.0.0',debug=True)
  socketio.run(app,host=env_config.FLASK_HOST,debug=True)
