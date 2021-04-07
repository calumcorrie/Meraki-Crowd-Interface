# Purpose/ Overview

Creates Flask app to display and modify data in a Model object. Defines views to send and recieve data from the app and modify the Model.

# Design

Wrapper classes are defined to pass API query data to the app.
A Model object is created using the current data from the API and configuration data stored in config file.

Helper functions are defined to send images to app; check session authentificaion; to serialize data for storage in the config file.

A set of views are defined to load data into the app and render it, to take new data from the app to configure the model and also to check user authentification.


# App Flow

## Index page
- loads list of floorplans
- renders card for each with title and floorplan image
- cards link to floorplan busyness page

## Floorplan busyness page
- loads single floorplan busyness render
- every 30 seconds the model data is updated and rendered

## Configuration page
- provided with current model configuration data to create form
- recieves form data via POST on submit
- form data is used to update the current model settings
- new settings stored in config file