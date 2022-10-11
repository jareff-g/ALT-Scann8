# Alternative T-Scann 8 User Interface

This application is a derivative of 'T-Scann8-UserInterface v2.1' by Torulf Holmström, from his project [T-Scann 8](http://tscann8.torulf.com/index.html), licensed under a [Creative Commons Attribution-NonCommercial 4.0 International License](http://creativecommons.org/licenses/by-nc/4.0/). ALT-Scann8-UI is licensed under a MIT License by Juan Remirez de Esparza.

The original intention of this derivative was to adapt the original code by Torulf Holmström to use the PiCamera2 library, but at the end it resulted in some major changes, including code refactoring and a few additional features. 

The application us the user interface for [T-Scann 8](http://tscann8.torulf.com/index.html), the Super8/Regular8 film scanner designed by Torulf Holmström. 

Some of the changes done over original version:
- Major code refactoring
- Reorganization of UI widgets
- Support of PiCamera2 (backward compatible with PiCamera legacy)
- Implement 'post-view' to replace standard preview mode in PiCamera2, too slow and inaccurate compared to PiCamera legacy, not really usable for this kind of project.
- Support for automatic exposure, with optional adjustable adaptation delay
- Support for automatic white balance, with optional adjustable adaptation delay
- Expert mode flag to hide advanced features during normal usage
- Fast-forward added, plus protection blocking FF/Rwnd if film present in filmgate
