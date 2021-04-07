# Purpose/ Overview

Defines classes and functionality for the creation and modification of a Model object. A Model stores data corresponding to each floorplan in the network and the data layers produced from each data source. Model class has functionality for spike detection. Module also deals with storage and usage of historical average data.

The flask app will create a Model object to to display and modify busyness data through the GUI.

# Design
## Floor
Wrapper class for a floorplan object from APIQuery module.
  - stores additional model data relating to corresponding data overlay
  - functions for setting bounds masks and rendering a heatmap of the floorplan

## Overlay
Represents a data overlay for a single data source for a single floorplan.
- data overlay is a numpy array with location data
- has functions for adding, verifying and updating data in the overlay
- unfixed observations are seperated from fixed as they are not useful for relative busyness

## Layer
A series of Overlays for all floorplans corresponding to a single data source.
- overlays stored in dictionary with floorplan id keys
- functions for adding, verifying and updating data in all overlays corresponding to layer

## Model
A complete representation of the current busyness across all floorplans on the network, using all layers.
- Model initialised by creating an APIQuery object to pull API data and reading the configuration data from file
- functions pull, update and manipulate APIQuery data (floorplans, access points, cameras, scanning api data)
- stores Layer objects in a dictionary with layer ids as keys

Current Model is associated with only one network on the dashboard.
- changing network requires reading relevant data from API and from config file

Functionality for historical TimeSlotAvg data
- loads in current TimeSlotAvg object to Model from file
- compares current model data with TimeSlotAvg data to get relative data
- updates the average data for current TimeSlotAvg object with current data

Functionality for configuration storage
- update the current model object with new configuration data
- serialize data to be stroed in config file
- read from / write to the config file


Spike detection functionality
- when current busyness data updated, checks all areas for floorplan for busyness above a set threshold
- if theshold passed, finds the nearest camera and sends snapshot to list of stored webhook addresses

## TimeSlotAvg
Class to hold historical average data for hour of each day of the week.
- stores the day, hour of timeslot it corresponds to
- holds series of data layers as in Model with average data for it's timeslot
- a historical data file for each is stored
- functionality to check the TimeSlotAvg object being used is the current time when modifying data

