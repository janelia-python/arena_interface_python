- [About](#org07082ef)
- [Example Usage](#orge519745)
- [Installation](#org0faadf0)
- [Development](#org48628f4)

    <!-- This file is generated automatically from metadata -->
    <!-- File edits may be overwritten! -->


<a id="org07082ef"></a>

# About

```markdown
- Python Package Name: arena_interface
- Description: Python interface to the Reiser lab ArenaController.
- Version: 3.0.0
- Python Version: 3.11
- Release Date: 2025-09-09
- Creation Date: 2023-10-17
- License: BSD-3-Clause
- URL: https://github.com/janelia-python/arena_interface_python
- Author: Peter Polidoro
- Email: peter@polidoro.io
- Copyright: 2025 Howard Hughes Medical Institute
- References:
  - https://github.com/janelia-arduino/ArenaController
- Dependencies:
  - click
  - schedule
  - pyserial
```


<a id="orge519745"></a>

# Example Usage


## Python

```python
from arena_interface import ArenaInterface

ai = ArenaInterface(debug=True)
ai.set_ethernet_mode()
# or
ai.set_serial_mode(port='/dev/ttyACM0', baudrate=115200)
ai.all_on()
ai.all_off()
ai.stream_frame(path='./patterns/pat0004.pat', frame_index=0)
ai.stream_frames(path='./patterns/pat0004.pat', frame_rate=20, runtime_duration=50)
ai.trial_params(pattern_id=3, frame_rate=20, runtime_duration=50)
ai.trial_params(pattern_id=3, frame_rate=-20, runtime_duration=50)
```


## Command Line


### help

```sh
arena-interface --help
# Usage: arena-interface [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  all-off
  all-on
  display-reset
  set-refresh-rate
  stream-frame
  trial-params
```

```sh
arena-interface stream-frame --help
# Usage: arena-interface [OPTIONS] PATH FRAME_INDEX

Options:
  --help  Show this message and exit.
```

1.  example commands

    ```sh
    arena-interface all-on
    ```
    
    ```sh
    $FRAME_INDEX=0
    arena-interface stream-frame ./patterns/pat0004.pat $FRAME_INDEX
    arena-interface stream-frame ./patterns/pat0004.pat 0
    ```
    
    ```sh
    FRAME_RATE=2
    RUNTIME_DURATION=50 # 50 * 100ms = 5000ms = 5s
    arena-interface stream-frames ./patterns/pat0004.pat $FRAME_RATE $RUNTIME_DURATION
    arena-interface stream-frames ./patterns/pat0004.pat 2 50
    ```
    
    ```sh
    PATTERN_ID=3
    FRAME_RATE=20
    RUNTIME_DURATION=50 # 50 * 100ms = 5000ms = 5s
    arena-interface trial-params -- $PATTERN_ID $FRAME_RATE $RUNTIME_DURATION
    arena-interface trial-params -- 3 20 50
    ```
    
    ```sh
    PATTERN_ID=3
    FRAME_RATE=-20
    RUNTIME_DURATION=50 # 50 * 100ms = 5000ms = 5s
    arena-interface trial-params -- $PATTERN_ID $FRAME_RATE $RUNTIME_DURATION
    arena-interface trial-params -- 3 -20 50
    ```
    
    ```sh
    arena-interface all-off
    ```

2.  advanced commands

    ```sh
    arena-interface set-refresh-rate 175
    ```
    
    ```sh
    arena-interface switch-grayscale 0 # 0=binary, 1=grayscale
    ```


<a id="org0faadf0"></a>

# Installation

<https://github.com/janelia-python/python_setup>


## GNU/Linux


### Ethernet

C-x C-f /sudo::/etc/network/interfaces

```sh
auto eth1

iface eth1 inet static

    address 192.168.10.2

    netmask 255.255.255.0

    gateway 192.168.10.1

    dns-nameserver 8.8.8.8 8.8.4.4
```

```sh
nmap -sn 192.168.10.0/24
nmap -p 62222 192.168.10.62
nmap -sV -p 62222 192.168.10.0/24
```

```sh
sudo -E guix shell nmap
sudo -E guix shell wireshark -- wireshark
```

```sh
make guix-container
```


### Serial

1.  Drivers

    GNU/Linux computers usually have all of the necessary drivers already installed, but users need the appropriate permissions to open the device and communicate with it.
    
    Udev is the GNU/Linux subsystem that detects when things are plugged into your computer.
    
    Udev may be used to detect when a device is plugged into the computer and automatically give permission to open that device.
    
    If you plug a sensor into your computer and attempt to open it and get an error such as: "FATAL: cannot open /dev/ttyACM0: Permission denied", then you need to install udev rules to give permission to open that device.
    
    Udev rules may be downloaded as a file and placed in the appropriate directory using these instructions:
    
    [99-platformio-udev.rules](https://docs.platformio.org/en/stable/core/installation/udev-rules.html)

2.  Download rules into the correct directory

    ```sh
    curl -fsSL https://raw.githubusercontent.com/platformio/platformio-core/master/scripts/99-platformio-udev.rules | sudo tee /etc/udev/rules.d/99-platformio-udev.rules
    ```

3.  Restart udev management tool

    ```sh
    sudo service udev restart
    ```

4.  Ubuntu/Debian users may need to add own “username” to the “dialout” group

    ```sh
    sudo usermod -a -G dialout $USER
    sudo usermod -a -G plugdev $USER
    ```

5.  After setting up rules and groups

    You will need to log out and log back in again (or reboot) for the user group changes to take effect.
    
    After this file is installed, physically unplug and reconnect your board.


## Python Code

The Python code in this library may be installed in any number of ways, chose one.

1.  pip

    ```sh
    python3 -m venv ~/venvs/arena_interface
    source ~/venvs/arena_interface/bin/activate
    pip install arena_interface
    ```

2.  guix

    Setup guix-janelia channel:
    
    <https://github.com/guix-janelia/guix-janelia>
    
    ```sh
    guix install python-arena-interface
    ```


## Windows


### Python Code

The Python code in this library may be installed in any number of ways, chose one.

1.  pip

    ```sh
    python3 -m venv C:\venvs\arena_interface
    C:\venvs\arena_interface\Scripts\activate
    pip install arena_interface
    ```


<a id="org48628f4"></a>

# Development


## Clone Repository

```sh
git clone git@github.com:janelia-python/arena_interface_python.git
cd arena_interface_python
```


## Guix


### Install Guix

[Install Guix](https://guix.gnu.org/manual/en/html_node/Binary-Installation.html)


### Edit metadata.org

```sh
make metadata-edits
```


### Tangle metadata.org

```sh
make metadata
```


### Develop Python package

```sh
make guix-dev-container
exit
```


### Test Python package using ipython shell

```sh
make guix-dev-container-ipython
import arena_interface
exit
```


### Test Python package installation

```sh
make guix-container
exit
```


### Upload Python package to pypi

```sh
make upload
```


### Test direct device interaction using serial terminal

```sh
make guix-dev-container-port-serial # PORT=/dev/ttyACM0
# make PORT=/dev/ttyACM1 guix-dev-container-port-serial
? # help
[C-a][C-x] # to exit
```


## Docker


### Install Docker Engine

<https://docs.docker.com/engine/>


### Develop Python package

```sh
make docker-dev-container
exit
```


### Test Python package using ipython shell

```sh
make docker-dev-container-ipython
import arena_interface
exit
```


### Test Python package installation

```sh
make docker-container
exit
```
