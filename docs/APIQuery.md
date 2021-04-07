## APIQuery breakdown
This file was made to define objects to hold data and make API calls to collect this data.  These methods and objects are used by other files and these objects and methods are a vital part of our project.
#### Placeable class:
This is a super class that represents an object on a floorplan.  It stores the associated floorplan with that object, location data and its variance.  It also had a function that sets a mask override.  This is used to mark the boundaries of where an object could be.  It is used by the FOV implementation of the cameras.

#### Client class:
This class extends the Placeable class, and has the added attributes of a mac address and the mac address of the nearest access point.  This class is used to represent devices, such as phones etc.

#### Person class:
This class extends the Placeable class, and is used to represent people on the floorplans that have been observed by a camera

#### Floorplan class:
This class is used to store the data of a floorplan.  It stores its id, name, centre and dimensions.  It contains functions to return the image of the floorplan and a function to verify the floorplan.  The m_rel_from_coords function is used to get the x and y co-ordinates of the centre of the floorplan from its latitude and longitude.

#### Functions m_p_d_lat and m_p_d_lng:
These functions convert degrees to metres, and are used in getting x and y co-ordinates from latitudes and longitudes, specifically for the floorplan and cameras.


#### Class AP:
This class is used to represent an access point, and contains data about its name, associated floorplan, mac address and location.

#### Class camera:
This class is used to represent a camera and contains data about its mac address and serial number, location data, associated floorplan and mask.  The mask is a set of co-ordinates that the camera can see, and is used to represent the cameras field of view.  This class contains functions to test if the camera has a FOV and a setter and getter for the FOV.

#### Class APIQuery:
This class contains methods that query the meraki API for a given network.  Its constructor makes the network dashboard object, using the meraki API key that is stored as an environment variable (MERAKI_DASHBOARD_API_KEY).  It has methods to get floorplan objects, access points, cameras and take a photo with a given camera.  updateCmaeraMVSenseData?
It also has methods to get a set of person objects detected by MVSense and get a JSON of camera observations, which our app will then use to populate the data model.

#### main method:
This method contains a demonstration of some of the functions in the file that were used for testing purposes.