# -*- coding: UTF-8 -*-
from PIL import Image
import base64
import requests
import json
import time
import configparser
import os
from picamera import PiCamera
import RPi.GPIO as GPIO

# Global settings
Server_URL = 'http://hyserver.hyetec.com:8680/test/upload.json'
Image_Filename = '/home/pi/Desktop/camera/tmp.jpg'
Device_Name = 'MyRaspberryPi'
Capture_Mode = 'interval'
Capture_Interval = 10
Start_Time = [8, 0]
End_Time = [18, 0]
Time_Points = []
Image_Mode = 'scale'
Resize_Scale = 1.0
Image_Size = (1920, 1080)

Interval_Counter = 0
camera = PiCamera()


# Camera configuration
def camera_config():
    global camera
    #camera.resolution(1280, 720)
    # camera.rotation = 0
    # Other configuration here
    pass


# Capture image with camera and save to 'tmp.jpg'
def capture_image():
    # Take picture
    camera.start_preview()
    time.sleep(5)
    camera.capture(Image_Filename)
    camera.stop_preview()

    # Resize and save picture
    img = Image.open(Image_Filename)
    if Image_Mode == 'scale':
        size = img.size
        img = img.resize((int(size[0] * Resize_Scale), int(size[1] * Resize_Scale)))
    else:
        img = img.resize(Image_Size)
    img.save(Image_Filename)


# Send image 'tmp.jpg' to server
def send_image():
    print('image sent')
    image_file = open(Image_Filename, 'rb')
    image_base64code = str(base64.b64encode(image_file.read()), encoding='utf-8')
    image_file.close()
    json_res = {'image': str(image_base64code),
                'timestamp': time.strftime('%Y%m%d%H%M%S'),
                'name': Device_Name}
    headers = {'Content-Type': 'application/json'}
    #_ = requests.post(Server_URL, json=json.dumps(json_res), headers=headers)
    _ = requests.post(Server_URL, json=json_res, headers=headers)


# Resolve config file 'servercfg.ini'
def read_config():
    global Server_URL
    global Image_Filename
    global Device_Name
    global Capture_Mode
    global Capture_Interval
    global Start_Time
    global End_Time
    global Time_Points
    global Image_Mode
    global Resize_Scale
    global Image_Size

    config = configparser.ConfigParser()
    config.read('/home/pi/Desktop/camera/servercfg.ini')  # Absolute direction is needed
    sections = config.sections()
    if 'Global' in sections:
        Server_URL = config.get('Global', 'url')
        Device_Name = config.get('Global', 'name')
    else:
        print('No Global item detected, which is necessary.')
        raise NameError

    if 'Capture' in sections:
        Capture_Mode = config.get('Capture', 'mode')
        if Capture_Mode == 'interval':
            Capture_Interval = int(config.get('Capture', 'interval'))
            start_time_str = config.get('Capture', 'starttime').split(':')
            end_time_str = config.get('Capture', 'endtime').split(':')
            Start_Time = [int(start_time_str[0]), int(start_time_str[1])]
            End_Time = [int(end_time_str[0]), int(end_time_str[1])]
        else:
            time_point_list = config.get('Capture', 'timepoint').split(',')
            for item in time_point_list:
                timepoint_str = item.strip().split(':')
                Time_Points.append(int(timepoint_str[0]) * 60 + int(timepoint_str[1]))

    if 'Image' in sections:
        Image_Mode = config.get('Image', 'mode')
        if Image_Mode == 'scale':
            Resize_Scale = float(config.get('Image', 'scale').strip())
        elif Image_Mode == 'size':
            image_size_str = config.get('Image', 'size').split(',')
            Image_Size = (int(image_size_str[0].strip()), int(image_size_str[1].strip()))


# Judge if a picture should be uploaded now, executed every minute
def time_step():
    if Capture_Mode == 'interval':
        global Interval_Counter
        if Interval_Counter >= Capture_Interval:
            hour = int(time.strftime('%H'))
            minute = int(time.strftime('%M'))
            if Start_Time[0] * 60 + Start_Time[1] <= hour * 60 + minute <= End_Time[0] * 60 + End_Time[1]:
                try:
                    capture_image()
                    send_image()
                except Exception as e:
                    print('Error: ', e)
                finally:
                    pass
            Interval_Counter = 0
    else:
        Interval_Counter = 0
        now = int(time.strftime('%H')) * 60 + int(time.strftime('%M'))
        if now in Time_Points:
            try:
                capture_image()
                send_image()
            except Exception as e:
                print('Error: ', e)
            finally:
                pass
			

def get_recording_direction():
    udisk = os.listdir('/media/pi')
    filename = 'rec_%s.h264' % time.strftime('%Y%m%d_%H_%M_%S')
    if udisk:
        return '/media/pi/' + udisk[0] + '/' + filename
    else:
        return '/home/pi/Desktop/camera/' + filename


if __name__ == '__main__':
    Record_Pin = 7
    Mode_Pin = 11
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(Record_Pin, GPIO.IN)
    GPIO.setup(Mode_Pin, GPIO.IN)
    read_config()
    camera_config()
    last_time = ''
    recoding_flag = False
    Seconds_Cnt = 0
    while True:
        if GPIO.input(Mode_Pin):  # Recording mode
            if GPIO.input(Record_Pin):
                if not recoding_flag:
                    print('Start recording!')
                    camera.start_preview()
                    camera.start_recording(get_recording_direction())
                    print('Save video file to ' + get_recording_direction())
                    recoding_flag = True
            else:
                if recoding_flag:
                    camera.stop_recording()
                    camera.stop_preview()
                    print('Stop recording')
                recoding_flag = False
        else:  # Photo taking
            Seconds_Cnt += 1
            if Seconds_Cnt >= 30:
                print('Step')
                current_time = time.strftime('%H:%M')
                if current_time != last_time:
                    Interval_Counter += 1
                    time_step()
                    last_time = current_time
        time.sleep(1)
