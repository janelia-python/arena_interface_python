- [About](#org5777b24)
- [Example Usage](#orga9243ec)
- [Installation](#org83d1ff7)
- [Development](#orgabcdda2)

    <!-- This file is generated automatically from metadata -->
    <!-- File edits may be overwritten! -->


<a id="org5777b24"></a>

# About

```markdown
- Python Package Name: panels_controller_client
- Description: Python client interface to the Reiser lab PanelsController.
- Version: 0.1.0
- Python Version: 3.10
- Release Date: 2023-10-18
- Creation Date: 2023-10-17
- License: BSD-3-Clause
- URL: https://github.com/janelia-pypi/panels_controller_client_python
- Author: Peter Polidoro
- Email: peter@polidoro.io
- Copyright: 2023 Howard Hughes Medical Institute
- References:
  - https://github.com/janelia-arduino/PanelsController
- Dependencies:
  - pyserial
  - click
```


<a id="orga9243ec"></a>

# Example Usage


## Python

```python
from panels_controller_client import PanelsControllerClient
```


## Command Line


### help

```sh
panels --help
# Usage: panels [OPTIONS]

#   Command line interface for panels controller client.

# Options:
#   -p, --port TEXT          Device name (e.g. /dev/ttyACM0 on GNU/Linux or COM3
#                            on Windows)
#   --debug                  Print debugging information.
#   -h, --help               Show this message and exit.
```


<a id="org83d1ff7"></a>

# Installation

<https://github.com/janelia-pypi/python_setup>


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
    python3 -m venv ~/venvs/panels_controller_client
    source ~/venvs/panels_controller_client/bin/activate
    pip install panels_controller_client
    ```

2.  guix

    Setup guix-janelia channel:
    
    <https://github.com/guix-janelia/guix-janelia>
    
    ```sh
    guix install python-panels-controller-client
    ```


## Windows


### Python Code

The Python code in this library may be installed in any number of ways, chose one.

1.  pip

    ```sh
    python3 -m venv C:\venvs\panels_controller_client
    C:\venvs\panels_controller_client\Scripts\activate
    pip install panels_controller_client
    ```


<a id="orgabcdda2"></a>

# Development


## Clone Repository

```sh
git clone git@github.com:janelia-pypi/panels_controller_client_python.git
cd panels_controller_client_python
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
import panels_controller_client
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
import panels_controller_client
exit
```


### Test Python package installation

```sh
make -f .metadata/Makefile docker-container
exit
```