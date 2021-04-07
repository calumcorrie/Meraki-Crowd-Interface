## BoundaryDetector breakdown
#### Class BoundaryDetector:
  The boundary detector takes an image and returns a pixel mask of the unbounded outer region.  This is important to the project as if an observation is located outside of a building then we can discard it, as it is most likely just someone walking past etc, and will disrupt our data.  It also has the option for a user to manually add areas to exclude from the floorplan.  It contains methods that walk the provided image and create the mask.  It also has a method to display the mask, so the user can check it is correct and add in blind spots if they want.
#### main method:
This method contains a demonstration to make a mask of a floorplan by providing a file, adding a blind spot, running the algorithm and then showing the result.