Wiimote
==================
A simple python library to interface with Nintendo Wiimote


Requirements
==================
- A Wiimote
- Pybluez(https://code.google.com/p/pybluez/) module


How to Use
=================

```
import wiimote
from wiimote.buttons import *


w = wiimote.Wiimote()
# w = wiimote.Wiimote(ADDR='XX:XX:XX:XX:XX:XX')  # you can specify wiimote address


@w.onpressed(BUTTON_A | BUTTON_B)
def a_and_b():
    print 'A and B pressed!'


@w.onreleased(BUTTON_DOWN)
def down():
    print 'down released'


if __name__ == '__main__':
    import sys
    import time

    try:
        w.connect()
    except wiimote.WiimoteNotFound:
        sys.stderr.write('Wiimote not found\n')
        sys.stderr.flush()
        sys.exit(1) 

    while w.connected:
        time.sleep(1)
```
