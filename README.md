- [About](#org1d9a066)
- [Example Usage](#org58786bc)
- [Installation](#orgd361f26)
- [Development](#org2895d01)

    <!-- This file is generated automatically from metadata -->
    <!-- File edits may be overwritten! -->


<a id="org1d9a066"></a>

# About

```markdown
- Python Package Name: panels_controller_client
- Description: Python client interface to the Reiser lab PanelsController.
- Version: 0.1.0
- Python Version: 3.10
- Release Date: 2023-10-17
- Creation Date: 2023-10-17
- License: BSD-3-Clause
- URL: https://github.com/janelia-pypi/panels_controller_client_python
- Author: Peter Polidoro
- Email: peter@polidoro.io
- Copyright: 2023 Howard Hughes Medical Institute
- References:
  - https://github.com/janelia-arduino/PanelsController
- Dependencies:
  - click
```


<a id="org58786bc"></a>

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

#   Command line interface for loadstar sensors.

# Options:
#   -p, --port TEXT          Device name (e.g. /dev/ttyUSB0 on GNU/Linux or COM3
#                            on Windows)
#   -H, --high-speed         Open serial port with high speed baudrate.
#   --debug                  Print debugging information.
#   -i, --info               Print the device info and exit
#   -T, --tare               Tare before getting sensor values.
#   -d, --duration INTEGER   Duration of sensor value measurements in seconds.
#                            [default: 10]
#   -u, --units TEXT         Sensor value units.  [default: gram]
#   -f, --units-format TEXT  Units format.  [default: .1f]
#   -h, --help               Show this message and exit.
```


<a id="orgd361f26"></a>

# Installation

<https://github.com/janelia-pypi/python_setup>


## GNU/Linux


### Python Code

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


### Drivers

Download and install Windows driver:

[Loadstar Sensors Windows Driver](https://www.loadstarsensors.com/drivers-for-usb-load-cells-and-load-cell-interfaces.html)


### Python Code

The Python code in this library may be installed in any number of ways, chose one.

1.  pip

    ```sh
    python3 -m venv C:\venvs\panels_controller_client
    C:\venvs\panels_controller_client\Scripts\activate
    pip install panels_controller_client
    ```


<a id="org2895d01"></a>

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