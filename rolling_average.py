#!/usr/bin/env python
"""
RollignAverage - Class to calculate rolling average on most recent values

Used to calculate averages while scanning, to display on the UI

Licensed under a MIT LICENSE.

More info in README.md file
"""

__author__ = 'Juan Remirez de Esparza'
__copyright__ = "Copyright 2022¡4, Juan Remirez de Esparza"
__credits__ = ["Juan Remirez de Esparza"]
__license__ = "MIT"
__module__ = "RollingAverage"
__version__ = "1.0.2"
__date__ = "2024-01-23"
__version_highlight__ = "Rolling average - First version"
__maintainer__ = "Juan Remirez de Esparza"
__email__ = "jremirez@hotmail.com"
__status__ = "Development"


from collections import deque

class RollingAverage:
    def __init__(self, window_size):
        self.window_size = window_size
        self.window = deque(maxlen=window_size)
        self.sum = 0

    def add_value(self, value):
        if len(self.window) == self.window_size:
            self.sum -= self.window.popleft()
        self.window.append(value)
        self.sum += value

    def get_average(self):
        if len(self.window) == 0:
            return None
        return self.sum / len(self.window)
