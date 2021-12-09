#!/bin/bash

echo "Updating from Github..."

cd /home/pi/LightsOn2021

git pull

echo "Done git pull..."

echo "Updating LightsOn project files..."

cd /home/pi/flask_apps/

cp -f -r lightsonapp /home/pi/BACKUP

cd /home/pi/LightsOn2021

cp -f fadecandy_ledctrl.py /home/pi/flask_apps/lightsonapp/
cp -f fadecandy_webapi.py /home/pi/flask_apps/lightsonapp/
cp -f lightsonapp.py /home/pi/flask_apps/lightsonapp/
cp -f -r static /home/pi/flask_apps/lightsonapp/
cp -f -r templates /home/pi/flask_apps/lightsonapp/

echo "Press ENTER to continue..."

read enter
