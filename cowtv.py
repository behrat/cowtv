import os
import sys
import time 
import yaml
import pylirc
import select
import logging
import subprocess
import socketIO_client
import requests.exceptions

FORMAT = '%(asctime)-15s %(message)s'
logging.basicConfig(format=FORMAT)

log = logging.getLogger("CowHD")
log.setLevel(logging.DEBUG)

class LightsNamespace(socketIO_client.BaseNamespace):

    def on_connect(self):
        log.debug("Lights connected")
    
    def on_disconnect(self):
        log.debug("Lights disconnected")
    
try:
    socketIO = socketIO_client.SocketIO("172.70.22.5", 8888)
except requests.exceptions.ConnectionError:
    print "Could not connect to lights server"
    exit(0)

lightsNamespace = socketIO.define(LightsNamespace)

def dc_lights_update(status):
    log.info("dc_lights_update: " + str(status))

socketIO.on('dc_lights', dc_lights_update)

def keep_alive():
    pass
    #log.debug("Received keep_alive")

socketIO.on("keep_alive", keep_alive)


class CowHdController(object):

    def __init__(self, config):
        self.cameras = []
        for camera_config in config:
            self.cameras.append(CameraView(**camera_config))

    def show_all_cameras(self):
        self.stop()
        self._tile_cameras(2)

    def _tile_cameras(self, outof):
        cam_number = 0
        for v_tile in range(outof):
            for h_tile in range(outof):
                if cam_number >= len(self.cameras):
                    return
                self.cameras[cam_number].start_tiled(h_tile, v_tile, outof)
                cam_number += 1

    def show_camera(self, number):
        number -= 1
        if number >= len(self.cameras):
            log.warn("Camera %d doesn't exist" % number)
            return
        self.stop()
        self.cameras[number].start_full()
        

    def stop(self):
        for camera in self.cameras:
            camera.stop()
        time.sleep(1)
        os.system("killall omxplayer.bin");

class CameraView(object):
    width = 1920
    height = 1080

    def __init__(self, full_url, tile_url):
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
            self.log.warn(str(e))
        self.player = None

def main():
    log.info("Starting")
    config_file = open('cameras.yml')
    cameras_config = yaml.load(config_file)
    config_file.close()
    
    controller = CowHdController(cameras_config)
    
#    Start wih all cameras
    controller.show_all_cameras()

    pylirc_socket = pylirc.init("cowtv", "~/.lircrc", False)
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
