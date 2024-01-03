# ALT-Scann 8 User Interface

The application is an alternate user interface for [T-Scann 8](http://tscann8.torulf.com/index.html), the Super8/Regular8 film scanner designed by Torulf Holmström.  It is a fork of the original UI ('T-Scann8-UserInterface v2.1') from Torulf, licensed under a [Creative Commons Attribution-NonCommercial 4.0 International License](http://creativecommons.org/licenses/by-nc/4.0/). ALT-Scann8-UI is licensed under a MIT License by Juan Remirez de Esparza.

The original intention of this version was to adapt the original code by Torulf Holmström to use the PiCamera2 library, with the objetive of allowing its use with Bullseye 64 bit version, but afterwards some other changes were implemented, including code refactoring and a few additional features. 

Some of the changes done over original version:
- Code refactoring (use of Tkinter instead of Pygame)
- Reorganization of UI widgets
- Support of PiCamera2
- Implement 'post-view' to replace standard preview mode in PiCamera2, which proved too slow and inaccurate compared to PiCamera legacy, not really usable for this kind of project.
- Support for automatic exposure, with optional adjustable adaptation delay (enabled by default)
- Support for automatic white balance, with optional adjustable adaptation delay (disabled by default)
- Support for multi-exposure capture (4 snapshots with different exposures, automatic bracket calculation)
- Fast-forward added, plus protection blocking FF/Rwnd if film present in filmgate
- Settings saved when exiting, so that it is easier to continue from the same point if applications need to be restarted

# ALT-Scann8-Controller

This is the application handlign the Arduino board in the T-Scann 8 film scanner. It is a fork of 'Arduino to card Controll T-Scann 8 v1.61' by Torulf.

The original intention of this version was to add a specific feature to the existing software, but finally some other changes were done, including code refactoring and an extended feature set. 

Some of the changes done over original version:
Added features
- Code refactoring
- Fast forward
- Protection against FF/Rwnd when film is in film gate
- Improved FF/Rwnd function (progressive stop)
- Improved outgoing film winding algorithm

__Important notes:__ 
- Always use both ALT-Scann8 modules (UI + Arduino) toghether, do not mix with T-Scann8 original software. At this point in time (October 2023) the interface between both has changed a lot and is no longer compatible.
- ALT-Scann8 behavior in some areas is not neccesarily the same as T-Scann 8. For better performance, I reccomend to use a pich roller (details in [T-Scann 8 mods page](https://github.com/jareff-g/ALT-Scann8/wiki/T%E2%80%90Scann-8-mods) in the wiki) to help the capstan keep traction. 

## Join Our Community on Discord

[![Discord](https://img.shields.io/badge/Join%20Discord-Chat%20Now-blue.svg)](https://discord.gg/gJmNvHcQ)

Feel free to join our Discord server to discuss and get support!
