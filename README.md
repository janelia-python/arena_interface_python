- [About](#orgc6d9538)
- [Example Usage](#org721018a)
- [Installation](#orgc857b40)
- [Development](#org4882867)

    <!-- This file is generated automatically from metadata -->
    <!-- File edits may be overwritten! -->


<a id="orgc6d9538"></a>

# About

```markdown
- Python Package Name: arena_host
- Description: Python host interface to the Reiser lab ArenaController.
- Version: 0.1.0
- Python Version: 3.10
- Release Date: 2023-11-20
- Creation Date: 2023-10-17
- License: BSD-3-Clause
- URL: https://github.com/janelia-python/arena_host_python
- Author: Peter Polidoro
- Email: peter@polidoro.io
- Copyright: 2023 Howard Hughes Medical Institute
- References:
  - https://github.com/janelia-arduino/ArenaController
- Dependencies:
  - pyserial
  - click
```


<a id="org721018a"></a>

# Example Usage


## Python

```python
from arena_host import ArenaHost
```


## Command Line


### help

```sh
arena-host --help
# Usage: arena-host [OPTIONS]

#   Command line interface for arena host.

# Options:
#   -p, --port TEXT          Device name (e.g. /dev/ttyACM0 on GNU/Linux or COM3
#                            on Windows)
#   --debug                  Print debugging information.
#   -h, --help               Show this message and exit.
```


<a id="orgc857b40"></a>

# Installation

<https://github.com/janelia-python/python_setup>


## GNU/Linux

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
    python3 -m venv ~/venvs/arena_host
    source ~/venvs/arena_host/bin/activate
    pip install arena_host
    ```

2.  guix

    Setup guix-janelia channel:
    
    <https://github.com/guix-janelia/guix-janelia>
    
    ```sh
    guix install python-arena-host
    ```


## Windows


### Python Code

The Python code in this library may be installed in any number of ways, chose one.

1.  pip

    ```sh
    python3 -m venv C:\venvs\arena_host
    C:\venvs\arena_host\Scripts\activate
    pip install arena_host
    ```


<a id="org4882867"></a>

# Development


## Clone Repository

```sh
git clone git@github.com:janelia-python/arena_host_python.git
cd arena_host_python
```


## Guix


### Install Guix

[Install Guix](https://guix.gnu.org/manual/en/html_node/Binary-Installation.html)


### Edit metadata.org

```sh
make -f .metadata/Makefile metadata-edits
```


### Tangle metadata.org

```sh
make -f .metadata/Makefile metadata
```


### Develop Python package

```sh
make -f .metadata/Makefile guix-dev-container
exit
```


### Test Python package using ipython shell

```sh
make -f .metadata/Makefile guix-dev-container-ipython
import arena_host
exit
```


### Test Python package installation

```sh
make -f .metadata/Makefile guix-container
exit
```


### Upload Python package to pypi

```sh
make -f .metadata/Makefile upload
```


### Test direct device interaction using serial terminal

```sh
make -f .metadata/Makefile guix-dev-container-port-serial # PORT=/dev/ttyACM0
# make -f .metadata/Makefile PORT=/dev/ttyACM1 guix-dev-container-port-serial
? # help
[C-a][C-x] # to exit
```


## Docker


### Install Docker Engine

<https://docs.docker.com/engine/>


### Develop Python package

```sh
make -f .metadata/Makefile docker-dev-container
exit
```


### Test Python package using ipython shell

```sh
make -f .metadata/Makefile docker-dev-container-ipython
import arena_host
exit
```


### Test Python package installation

```sh
make -f .metadata/Makefile docker-container
exit
```
