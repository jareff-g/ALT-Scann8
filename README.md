# ALT-Scann-8-Controller

This application is a derivative of 'Arduino to card Controll T-Scann 8 v1.61' by Torulf Holmström, from his project [T-Scann 8](http://tscann8.torulf.com/index.html), licensed under a [Creative Commons Attribution-NonCommercial 4.0 International License](http://creativecommons.org/licenses/by-nc/4.0/). ALT-Scann8-UI is licensed under a MIT License by Juan Remirez de Esparza.

The original intention of this derivative was to add a specific feature to the existing software, but at the end it resulted in major changes, including code refactoring and an extended feature set. 

This application handles the hardware side of [T-Scann 8](http://tscann8.torulf.com/index.html), the Super8/Regular8 film scanner designed by Torulf Holmström.

Some of the changes done over original version:
Added features
- Major code refactoring
- Fast forward
- Protection against FF/Rwnd when film is in film gate
- Improved FF/Rwnd function (progressive stop)
- Improved outgoing film collection algorithm
- Optimization of frame detection algorithm, resulting in higher scan speeds
- Normalized and improved logging
- 'Expert mode' flag to hide advanced features during standard usage
