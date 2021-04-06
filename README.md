# Interfaced platform
[![coverage report](https://stgit.dcs.gla.ac.uk/tp3-2020-CS09/cs09-main/badges/master/coverage.svg)](https://stgit.dcs.gla.ac.uk/tp3-2020-CS09/cs09-main/-/commits/master)

Flask based web application, accepting Meraki Scanning API POST packets.
Performs refined layering, exposure smoothing and renders to GUI.

## Features
 
Whats new?
- Exposure for frame smoothing
- Separation of located and unlocated clients
- Ability to toggle masked and unmasked data mid-execution
- Fixed map margin bug
- Fixed NaN error from APIQuery

## Requirements

Requirements are formally specified in `requirements.txt`

You must supply a Meraki Dashboard API Key to the running environment for the program to run, see Execution.

For meaningful data:
- A Meraki Dashboard account and API key
- At least 1 floorplan
- At least 1 geoaligned AP
- At least 1 wifi device associated to the selected network

Ideally:
- `matplotlib`, `pickle` for Module demos
- External server hosting live snapshot data
- 3+ geoaligned APs spread over one floorplan

## Execution

The program requires that the Meraki dashboard API key is stored in the environment variable `MERAKI_DASHBOARD_API_KEY`

### Main demonstration
The main demonstration requires `curl` which is shipped in bash, but is not standard with Windows. For windows users, either use Git bash (shipped with Git), or run the Module Demonstration for Model (same effect).

With the WSGI application served at `<URL>`

    cd testing
    # Simulate a Scanning API POST
    curl -X POST -H "Content-Type: application/json" -d @test_w.json https://<URL>/scanningapi/

Observe changes on GUI heatmap

### Imports
Modules are designed to be imported

    from lib.APIQuery import *

### Unit tests
Unit tests are written in PyTest and aim to cover all functionality, though complete coverage is not practically possible due to the nature of the program.

    python -m pytest -v


## Specific documentation
For specific usages and method signatures, use (for example):

    from lib.Model import Model
    help(Model)