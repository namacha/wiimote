# -*- coding: utf-8 -*-


import threading
import functools

import bluetooth

from .buttons import (
    _BUTTON_LOWER_BYTES,
    _BUTTON_UPPER_BYTES,
    _BUTTON_UNUSED1,
    _BUTTON_UNUSED2,
)
from .exceptions import (
    WiimoteNotFound,
    WiimoteDisconnected,
)
from .command_data import (
    SET_REPORT,
    DATA_REPORT,
    CONTINUOUS_REPORTING,
    REPORT_COREBUTTONS_ACC,
    COMMAND_RUMBLE,
    COMMAND_SET_LED,
    COMMAND_REPORT_STATUS
)


COMMAND_REPORTING = SET_REPORT + DATA_REPORT + CONTINUOUS_REPORTING + REPORT_COREBUTTONS_ACC
COMMAND_STATUS = SET_REPORT + COMMAND_REPORT_STATUS
COMMAND_RUMBLE = SET_REPORT + COMMAND_RUMBLE
COMMAND_LED = SET_REPORT + COMMAND_SET_LED


DEVICE_NAME = 'Nintendo RVL-CNT-01'


class Processor(object):

    def __init__(self):
        self.connected = []
        self.released = {}
        self.pushed = {}
        self.disconnected = {}

    def onpressed(self, buttons):
        def receive_processor(processor):
            @functools.wraps(processor)
            def wrapper(*args, **kwargs):
                return processor(*args, **kwargs)
            if self.pushed.get(buttons) is None:
                self.pushed[buttons] = [wrapper]
            else:
                self.pushed[buttons].append(wrapper)
            return wrapper
        return receive_processor

    def onreleased(self, buttons):
        def receive_processor(processor):
            @functools.wraps(processor)
            def wrapper(*args, **kwargs):
                return processor(*args, **kwargs)
            if self.released.get(buttons) is None:
                self.released[buttons] = [wrapper]
            else:
                self.released[buttons].append(wrapper)
            return wrapper
        return receive_processor


class Buttons(object):

    def __init__(self, processor):
        self.processors = processor
        self.raw_pressed = (0, 0)
        self.pressed = 0
        self.previous = 0
        self.pressed_buttons = {2 ** k[1]: False for k in
                                (_BUTTON_UPPER_BYTES + _BUTTON_LOWER_BYTES)}
        self.prev_buttons = self.pressed_buttons

    def parse_line(self, data):
        self.previous = self.pressed
        self.prev_buttons = self.pressed_buttons
        try:
            upper_byte = int(data[2].encode('hex'), 16)
            lower_byte = int(data[3].encode('hex'), 16)
        except IndexError:
            raise WiimoteDisconnected
        pressed_upper = 0
        pressed_lower = 0
        for i, p in _BUTTON_UPPER_BYTES[::-1]:
            if upper_byte - i >= 0:
                if i not in (_BUTTON_UNUSED1, _BUTTON_UNUSED2):
                    pressed_upper += 2 ** p
                self.pressed_buttons[2 ** p] = True
                upper_byte -= i
            else:
                self.pressed_buttons[2 ** p] = False
        for i, p in _BUTTON_LOWER_BYTES[::-1]:
            if lower_byte - i >= 0:
                if i not in (_BUTTON_UNUSED1, _BUTTON_UNUSED2):
                    pressed_lower += 2 ** p
                self.pressed_buttons[2 ** p] = True
                lower_byte -= i
            else:
                self.pressed_buttons[2 ** p] = False
        self.raw_pressed = (pressed_upper, pressed_lower)
        self.pressed = sum(self.raw_pressed)

    def pushed(self):
        # if self.previous == 0:
        if self.pressed > self.previous:
            p = self.pressed
            funcs = self.processors.pushed.get(p, [lambda: None])
            map(lambda f: f(), funcs)

    def released(self):
        # if self.previous != 0 and self.pressed == 0:
        if self.pressed < self.previous:
            p = self.previous
            funcs = self.processors.released.get(p, [lambda: None])
            map(lambda f: f(), funcs)

    def handle(self, data):
        self.parse_line(data)
        self.pushed()
        self.released()


class Wiimote(object):

    def __repr__(self):
        return "<Wiimote: %s at %s>" % (self.ADDR, hex(id(self)))

    def __init__(self, ADDR=None):
        self.ADDR = ADDR
        self.batt = -1
        self.ledstate = 0
        self.__connected = False
        self.last_received = ''
        self.initial_data = []
        self.processor = Processor()
        self.buttons = Buttons(self.processor)
        self._pressed = self.buttons.pressed
        self.onpressed = self.processor.onpressed
        self.onreleased = self.processor.onreleased
        self.t = threading.Thread(target=self.worker)
        self.t.setDaemon(True)

    def ispressed(self, button):
        return self.buttons.pressed_buttons.get(button)

    def connected(self):
        return self.__connected

    @property
    def pressed_buttons(self):
        return self._pressed

    @pressed_buttons.getter
    def pressed_buttons(self):
        self.buttons.handle(self.last_received)
        return self.buttons.pressed

    def connect(self):
        if self.ADDR is None:
            addr = self.discover()
            if addr is None:
                raise WiimoteNotFound
            self.ADDR = addr
        self.recv_sock = bluetooth.BluetoothSocket(bluetooth.L2CAP)
        self.send_sock = bluetooth.BluetoothSocket(bluetooth.L2CAP)
        try:
            self.recv_sock.connect((self.ADDR, 0x13))
            self.send_sock.connect((self.ADDR, 0x11))
        except bluetooth.btcommon.BluetoothError:
            raise WiimoteNotFound
        self.__connected = True
        self.initialize()
        self.t.start()
        map(lambda f: f(), self.processor.connected)

    def initialize(self):
        if self.connected():
            self.send(COMMAND_STATUS)
            self.send(COMMAND_REPORTING)
            self.initial_data = [self.receive() for i in range(10)]
            for data in self.initial_data:
                intype = data.encode('hex')[2:4]
                if intype == str('20'):
                    self.set_batt_level(data)

    def disconnect(self):
        if self.connected():
            self.__connected = False
            self.recv_sock.close()
            self.send_sock.close()
            self.t = threading.Thread(target=self.worker)

    def discover(self):
        addr = None
        device_list = bluetooth.discover_devices(duration=2, lookup_names=True)
        for device in device_list:
            if device[1] == DEVICE_NAME:
                addr = device[0]
        return addr

    def send(self, value):
        self.send_sock.send(value.decode('hex'))

    def receive(self):
        try:
            return self.recv_sock.recv(25)
        except bluetooth.BluetoothError:
            raise WiimoteDisconnected

    def set_led(self, value):
        if not isinstance(value, int):
            return False
        if value > 15:
            return False
        self.ledstate = value
        self.send(COMMAND_LED % value)
        return True

    def enable_rumble(self):
        self.send(COMMAND_RUMBLE % self.ledstate)

    def disable_rumble(self):
        self.send(COMMAND_LED % self.ledstate)

    def set_batt_level(self, data):
        d = data.encode('hex')
        self.batt = d[-2:]
        self.send(COMMAND_REPORTING)
        return False

    def worker(self):
        while self.connected():
            self.last_received = self.receive()
            self.buttons.handle(self.last_received)
