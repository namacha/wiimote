# -*- coding: utf-8 -*-

from new import classobj


WiimoteNotFound = classobj('WiimoteNotFound', (Exception, ), {})
WiimoteDisconnected = classobj('WiimoteDisconnected', (Exception, ), {})
