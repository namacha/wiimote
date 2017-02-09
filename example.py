# -*- coding: utf-8 -*-

import wiimote
from wiimote.buttons import *


w = wiimote.Wiimote()


@w.onpressed(BUTTON_A)
def greet():
    print "Hi!"


if __name__ == '__main__':
    import time

    w.connect()
    while w.connected:
        time.sleep(1)
