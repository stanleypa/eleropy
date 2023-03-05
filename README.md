Python code to control elero blinds

This builds on the work of QuadCorei8085 (https://github.com/QuadCorei8085/elero_protocol) who worked out the basic message structure and the encryption of the messages

This has been tested using a RPi running rasbian and an esp32 (dual core with wifi) running micropython.
It uses the cc1101 module and the code currently uses the default spi bus of the respective platform.
 - For RPi use elero.py - preferably set up as a service. 
 - For esp32 call main.py from your boot.py after connecting to you wifi.

Both variants write the status of the blinds and the RSSI of recieved messages to an mqtt server.

e.g. "cc1101mqtt/Status/AA:AA:AA" and  "cc1101mqtt/RSSI/AA:AA:AA"

They also accept a range of commands published to the command topic and send them to the blind:

e.g. publishing "Up" to "cc1101mqtt/command/AA:AA:AA"

will send the up command to the blind with the address AA:AA:AA assuming blind AA:AA:AA is defined properly in conf.py.

This allows the setup to be used with any home automation system that supports mqtt - e.g. openhab/FHEM/home assistant

It's also possible to put any "known" blind into learning mode and program blinds to to virtual (= software) remotes.
This requires adding a remote configuration with blind addresses (of the actual blinds) and channel number (1-255: you select) to conf.py and after, a program restart, following the steps via mqtt commands that you would with a physical remote:
 - Put the blind into asynchronous programming standby - "Async" command (or kill and restore power to the blind)
 - Start programming - "Prog" command to the configured blind address (the last remote which knows the address will be programmed to allow software remotes to be added to previously configured hardware remotes)
 - Set first hit with either "Pup" or "PDown" command - depending on blind direction
 - Set second hit with other "Pup" or "PDown" command - when moving in the other direction.

The deletion of a given remote channel in a blind is also supported by "Pdel"

To detect blind changes initiated by other physical remotes, the program polls the status of all known blinds at a configured frequency. If you don't need this feature just set the frequency interval really high. This is similar to how the elero USB stick behaves - at least when used in OpenHAB.

Todo: It should be possible to completely emulate a elero USB stick with the esp32 setup by accepting commands and sending status over the serial port in parallel to or instead of mqtt. The protocol is described in a pdf document "Easy Control Transmitter Stick" . Currently the serial port is used to print messages sent and received by the cc1101 which is useful to determine the remote addresses and blind addresses/channels of existing devices aswell as debugging. This would need to be moved to a different uart.

Some notes on cc1101 modules. 
 - Modules from one supplier never worked for me, a second supplier worked without a problem.
 - Using a simple 82mm dipole antenna instead of the small coil improved RSSI by 10-20.
 - I did use a slightly different frequency than QuadCorei8085 after checking the frequency of my elero remotes using SDRangel, so you might need to adjust registers 0x0E and 0x0F in the cc1101 class initialization.
