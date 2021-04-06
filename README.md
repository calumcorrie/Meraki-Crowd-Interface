# Interfaced platform

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
- External server hosting live snapshot data
- 3+ geoaligned APs spread over one floorplan

## Execution

The program requires that the Meraki dashboard API key is stored in the environment variable `MERAKI_DASHBOARD_API_KEY`
For instructions on setup, see `docs/index.md`.

### Imports
Modules are designed to be imported

    from lib.APIQuery import *


## Documentation
For a full documentation, see `docs/index.md`.

For specific usages and method signatures, use (for example):

    from lib.Model import Model
    help(Model)