#!/usr/bin/env python

import os
import sys
import time 
import yaml
import pylirc
import select
import logging
import subprocess
from socketIO_client import SocketIO

FORMAT = '%(asctime)-15s %(message)s'
logging.basicConfig(format=FORMAT)

log = logging.getLogger("CowHD")
log.setLevel(logging.INFO)

config_file = open('/etc/cowtv/cowtv.yml')
cowtv_config = yaml.load(config_file)
config_file.close()

socketIO = None

def dc_lights_update(status):
    log.info("dc_lights_update: " + str(status))
def keep_alive():
    log.debug("Received keep_alive")

socketIO = SocketIO(cowtv_config["weblights"], 8888)
socketIO.on('dc_lights', dc_lights_update)
socketIO.on("keep_alive", keep_alive)

class CowHdController(object):

    def __init__(self, cameras_config):
        self.cameras = {}
        default_number = 1
        for camera_config in cameras_config:
            camera = CameraView(**camera_config)
            if 'number' in camera_config:
                self.cameras[camera_config['number']] = camera
            else:
                while default_number in self.cameras:
                    default_number += 1
                self.cameras[default_number] = camera

    def show_all_cameras(self):
        self.stop()
        self._tile_cameras(2)

    def _tile_cameras(self, outof):
        cam_number = 1
        for v_tile in range(outof):
            for h_tile in range(outof):
                if cam_number not in self.cameras:
                    return
                self.cameras[cam_number].start_tiled(h_tile, v_tile, outof)
                cam_number += 1

    def show_camera(self, number):
        if number not in self.cameras:
            log.warn("Camera %d doesn't exist" % number)
            return
        self.stop()
        self.cameras[number].start_full()
        

    def stop(self):
        for (number, camera) in self.cameras.iteritems():
            camera.stop()
        time.sleep(1)
        os.system("killall omxplayer.bin");

class CameraView(object):
    width = 1920
    height = 1080

    def __init__(self, full_url, tile_url, number=None):
        self.full_url = full_url
        self.tile_url = tile_url

        self.player = None

    def is_playing(self):
        return self.player != None

    def start_full(self):
        self._start_player([self.full_url])

    def start_tiled(self, horz, vert, outof):
        left = horz * (self.width/outof)
        right = (horz+1) * (self.width/outof)
        top = vert * (self.height/outof)
        bottom = (vert+1) * (self.height/outof)

        self._start_player([self.tile_url,
             "--win", "%d %d %d %d" % (left, top, right, bottom)])

    def _start_player(self, arguments):
        self.player = subprocess.Popen(["omxplayer"] + arguments,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE)

    def stop(self):
        if self.player is None:
            return

        try:
            self.player.stdin.write('q')
        except IOError, e:
            log.warn(str(e))
        self.player = None

def main():
    log.info("Starting")

    controller = CowHdController(cowtv_config["cameras"])
    
#    Start wih all cameras
    controller.show_all_cameras()

    pylirc_socket = pylirc.init("cowtv", "/etc/cowtv/lircrc", False)
    while(True):
        (iready, oready, eready) = select.select([sys.stdin, pylirc_socket],[],[])
        for s in iready:
            if s == sys.stdin:
                line = sys.stdin.readline()
                line = line.strip()
                if line == 't':
                    log.info("Toggling Lights")
                    socketIO.emit("toggle_lights")
                else:
                    try:
                        cam_number = int(line)
                    except ValueError:
                        log.warn("Unreconized command: " + line)
                    else:
                        if cam_number == 0:
                            controller.show_all_cameras()
                        else:
                            controller.show_camera(cam_number)
            elif s == pylirc_socket:
                codes = pylirc.nextcode(1)
                #if not codes:
                #    log.warn("None code")
                #    continue
                log.info("Got codes: " + str(codes))
                if not codes:
                    continue
                for code in codes:
                    command = code["config"]
                    log.info("Got command: " + str(command))
                    if command == "SELECT":
                        log.info("Toggling Lights")
                        controller.show_all_cameras()
                        socketIO.emit("toggle_lights")
#                    elif command == "TOGGLE_LIGHTS":
#                        socketIO.emit("toggle_lights")
                    elif command == "CLEAR":
                        controller.stop()
                    else:
                        try:
                            cam_number = int(command)
                        except ValueError:
                            log.warn("Unreconized IR command: " + command)
                        else:
                            if cam_number == 0:
                                controller.show_all_cameras()
                            else:
                                controller.show_camera(int(command))

main()
