#!/usr/bin/env python
"""
RollingAverage - Class to calculate rolling average on most recent values

Used to calculate averages while scanning, to display on the UI

Licensed under a MIT LICENSE.

More info in README.md file
"""

__author__ = 'Juan Remirez de Esparza'
__copyright__ = "Copyright 2022¡4, Juan Remirez de Esparza"
__credits__ = ["Juan Remirez de Esparza"]
__license__ = "MIT"
__module__ = "RollingAverage"
__version__ = "1.0.7"
__date__ = "2025-03-10"
__version_highlight__ = "Bug fix: Allow window size < 25"
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
        # If the deque is full, subtract the element that will be dropped
        if len(self.window) == self.window_size:
            # Access the leftmost element before it's overwritten
            self.sum -= self.window[0]  # Peek at the oldest value
        self.window.append(value)  # Append new value, oldest is auto-removed by maxlen
        self.sum += value


    def get_average(self):
        if len(self.window) <= 0:  # Return averages as soon as possible
            return None
        return self.sum / len(self.window)


    def get_min(self):
        return min(self.window) if len(self.window) > 0 else 0


    def get_max(self):
        return max(self.window) if len(self.window) > 0 else 0


    def clear(self):
        self.window.clear()
        self.sum = 0