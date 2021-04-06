import os
import sys
import numpy as np
from PIL import Image, ImageFilter
import bz2
import pickle
import datetime
import requests
import hashlib

parentddir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir))
sys.path.append(parentddir)
from lib.APIQuery import APIQuery, FloorPlan
from lib.BoundaryDetector import BoundaryDetector

# As per Scanning API v3
SECRET_K = "secret"

class Floor:
    "Wrapper class for the floorplan object including model data"
    def __init__(self,floorplan:FloorPlan):
        self.floorplan = floorplan
        # Dimentions should default to (height, width)
        self.floorplan_dimensions = (self.floorplan.height,self.floorplan.width)
        self.overlay_dimensions = (
            int(self.floorplan_dimensions[0]//Model.CELL_SIZE_M)+1,
            int(self.floorplan_dimensions[1]//Model.CELL_SIZE_M)+1
        )
        # Determine the distance between the end of the floorplan and the data overlay, in metres and px
        self.margin_m = ( 
            Model.CELL_SIZE_M - (self.floorplan_dimensions[0] % Model.CELL_SIZE_M),
            Model.CELL_SIZE_M - (self.floorplan_dimensions[1] % Model.CELL_SIZE_M)
        )
        self.margin_px = ( 
            self.margin_m[0] * self.floorplan.px_per_m_h,
            self.margin_m[1] * self.floorplan.px_per_m_w
        )

        self.mask_enabled = False
        self.pixelmask = None
        self.mask = np.ones(self.overlay_dimensions,dtype=np.bool_)
        self.aps = {}
        self.bm_boxes = []
    
    def set_bounds_mask(self,blindspots=None,wallthreshold:float=None) -> None:
        """"
        Generate a mask from BoundaryDetector for areas of the floor that people cannot possibly be or are to be ignored
         eg outside high floors.
        Blindspots should be a Numpy array, tuple or nested list of the form [[x1,x2,y1,y2],...]
        """
        self.bm_boxes = blindspots

        if wallthreshold == None:
            bd = BoundaryDetector( self.floorplan.get_image() )
        else: # pragma: no cover
            # Not covered as only parameter passing
            bd = BoundaryDetector( self.floorplan.get_image(), threshold=wallthreshold )

        if blindspots != None: 
            for spot in blindspots:
                bd.add_blindspot(*tuple(spot))

        bd.run()

        self.pixelmask = bd.getBoundaryMask()

        #Downsample from pixel level to mask level
        #Assuming cell >> pixel

        #Mask (1msq-scale, small-dims) dims
        mx = self.mask.shape[0]
        my = self.mask.shape[1]
        #Image-scale pixel mask (mini-scale, big-dims) dims
        ix = self.pixelmask.shape[0]
        iy = self.pixelmask.shape[1]
        #Image-scale chunk divisions (what coords do we get laying one mask over the other)
        # Account for margin between edge of floorplan and overlay
        ix_divs = np.floor(np.linspace( 0, ix+self.margin_px[0], mx+1 )).astype("int32")
        iy_divs = np.floor(np.linspace( 0, iy+self.margin_px[1], my+1 )).astype("int32")

        for x in range(mx):
            #Top, bottom
            it = ix_divs[x]
            ib = ix_divs[x+1]
            for y in range(my):
                #Left, right
                il = iy_divs[y]
                ir = iy_divs[y+1]
                # As array is binary, mean gives ratio of elems 1 to elems total
                self.mask[x][y] = self.pixelmask[it:ib,il:ir].mean() < Model.DOWNSAMPLE_THRESHOLD
    
    def calc_bounds_mask(self,blindspots=None,wallthreshold:float=None) -> Image.Image:
        """
        Generate a preview of a bounds mask with given parameters.
        For more info see Floor.set_bounds_mask
        """
        if wallthreshold == None:
            bd = BoundaryDetector( self.floorplan.get_image() )
        else: # pragma: no cover
            # Not covered as only parameter passing
            bd = BoundaryDetector( self.floorplan.get_image(), threshold=wallthreshold )

        if blindspots != None: 
            for spot in blindspots:
                bd.add_blindspot(*tuple(spot))

        bd.run()
        return bd.generate_graphic()

    def render_overlay(self,overlay:np.ndarray,pixelmask:bool=True):
        """
        Render overlay onto the floorplan image in heatmap form.
        If pixelmask and image has bounds mask set, will mask final image to keep
         overlay heatmap within bounds.
        """
        POS = np.array([255,0,0,180],dtype=np.uint8)
        NEG = np.array([0,255,0,180],dtype=np.uint8)
        BLUR_CELLS = 0.35

        destination = self.floorplan.get_image().convert("RGBA")

        # Overlay scaling
        absmax = max(overlay.max(), overlay.min(), key=abs)
        #m_max, m_min = absmax, -absmax

        imarr = np.zeros((destination.size[1],destination.size[0],4),dtype="uint8")

        # Account for margin between edge of floorplan and overlay
        ix_points = np.floor(np.linspace(
            0, imarr.shape[0] + self.margin_px[0], overlay.shape[0] + 1
        )).astype("int32")

        iy_points = np.floor(np.linspace(
            0,imarr.shape[1] + self.margin_px[1], overlay.shape[1] + 1
        )).astype("int32")

        for mx in range(overlay.shape[0]):
            # Top, bottom
            ixs = ix_points[mx]
            ixe = ix_points[mx+1]
            for my in range(overlay.shape[1]):
                val = overlay[mx,my]
                if val==0: continue
                #Colour by sign, scale alpha by magnitude
                pos = val > 0
                alpha = abs(val / absmax)
                #Left, right
                iys = iy_points[my]
                iye = iy_points[my+1]
                imarr[ixs:ixe,iys:iye] = POS if pos else NEG
                imarr[ixs:ixe,iys:iye,3] = ( imarr[ixs:ixe,iys:iye,3].astype(np.float64) * alpha ).astype(np.uint8)

        imarr = Image.fromarray(imarr,"RGBA").filter( ImageFilter.BoxBlur( BLUR_CELLS * destination.size[0] / overlay.shape[1] ) )

        if isinstance(self.pixelmask, np.ndarray) and pixelmask:
            # Tidy the edges
            # Make the mask an Image, mode=L
            mask = Image.fromarray(255*self.pixelmask.astype(np.uint8),"L")
            # Paste alpha on masked region
            imarr.paste((0,0,0,0),mask)
        elif pixelmask:
            print("Error: Could not filter by pixel mask as no mask exists")
            
        destination.putalpha(255)
        return Image.alpha_composite(destination,imarr)

class Layer:
    "Class representing a data layer: a series of overlays covering all floorplans with data from a single source type"
    def __init__(self,floorplans:dict,exposure:int):
        self.exposure = exposure
        self.overlays = { _id : Overlay(_id, floor.overlay_dimensions, floor.floorplan_dimensions, floor.mask, exposure) for _id,floor in floorplans.items() }
    
    def set_observations(self,observations:dict):
        "Set the layer to contain passed observations, clearing any previous. Pass floor object dictionary"
        bins = { id : dict() for id in self.overlays.keys() }

        for id, placeable in observations.items():
            bins[placeable.floorPlanId][id] = placeable
        for fid, overlay in self.overlays.items():
            overlay.roll()
            obs = bins.get(fid)
            if obs != None:
                overlay.add(obs)

    def get_deltas(self, masked:bool=True, exposure:int=0) -> dict:
        """
        Return the delta data for each overlay in the layer.
        If exposure 0 (default), will provide all available exposures squashed.
        For more info, see Overlay.get_delta
        """
        return { _id : over.get_delta(masked, exposure) for _id, over in self.overlays.items() }
    
    def get_full(self, masked:bool=True, exposure:int=0) -> dict: #pragma: no cover
        """
        Return the full data for each overlay in the layer.
        If exposure 0 (default), will provide all available exposures squashed.
        See Overlay.get_full
        """
        # Not covered as not required for current scope
        return { _id : over.get_full(masked, exposure) for _id, over in self.overlays.items() }

    def copy(self,flatten:bool=True):
        """
        Return a copy of the layer.
        Flatten squashes exposures into 1 frame
        For more info, see Overlay.copy()
        """
        ly = Layer({}, 1 if flatten else self.exposure )
        ly.overlays = { _id : over.copy(flatten) for _id, over in self.overlays.items() }
        return ly
    
    def clear(self)->None:
        "Clear all member overlays of observation data"
        for over in self.overlays.values():
            over.clear()

    def verify_and_update(self, floorplans:dict):
        """
        Ensure overlays are compatible with current floorplans (Floor objects).
        Throws ModelException in case of dimention mismatch.
        If mask is outdated, update - note this does not effect existing data, only new observations
        If an overlay missing, print info, create new
        If an overlay is extra, do nothing
        """
        for fpid in set(floorplans).difference(self.overlays.keys()):
            # A floorplan not represented in the floorplans but not in the overlays
            print("Info: Creating new overlay for FPID:{}".format(fpid))
            fp = floorplans[fpid]
            self.overlays[fpid] = Overlay(fpid, fp.overlay_dimensions, fp.floorplan_dimensions, fp.mask, self.exposure)
        
        for fpid, floor in floorplans.items():
            self.overlays[fpid].verify_and_update(floor)
       
class Overlay:
    "Represents an data overlay of a single floorplan"
    def __init__(self, floorid:str, overlay_dimensions:tuple, real_dimensions:tuple, floormask:np.ndarray, exposure:int):
        self.floorid = floorid
        #self.observations = dict()
        self.overlay_dimensions = overlay_dimensions
        self.real_dimensions = real_dimensions
        self.mask = floormask
        assert exposure > 0
        self.exposure = exposure
        # Exposure queue, shape (exp,x,y)
        self.__unfixed_observations = np.zeros(exposure)
        self.__masked_dataoverlay = np.zeros( (exposure,)+overlay_dimensions, dtype="float32" )
        self.__unmasked_dataoverlay = np.zeros( (exposure,)+overlay_dimensions, dtype="float32" )

    def set(self, unfixed_count:np.ndarray, masked_overlay:np.ndarray, unmasked_overlay:np.ndarray):
        "Sets internal observation data. Not for general use, instead use Overlay.add"
        assert len(self.__unfixed_observations.shape) == len(unfixed_count.shape)
        assert len(self.__masked_dataoverlay.shape) == len(masked_overlay.shape)
        assert len(self.__unmasked_dataoverlay.shape) == len(unmasked_overlay.shape)
        self.__unfixed_observations = unfixed_count
        self.__masked_dataoverlay = masked_overlay
        self.__unmasked_dataoverlay = unmasked_overlay

    def roll(self) -> None:
        "Roll the exposure, preparing for a new frame of data"
        self.__masked_dataoverlay = np.roll(self.__masked_dataoverlay, 1, axis=0)
        self.__unmasked_dataoverlay = np.roll(self.__unmasked_dataoverlay, 1, axis=0)
        self.__unfixed_observations = np.roll(self.__unfixed_observations, 1, axis=0)
        self.__masked_dataoverlay[0] = 0
        self.__unmasked_dataoverlay[0] = 0
        self.__unfixed_observations[0] = 0

    def clear(self) -> None:
        "Clear accumulated observation data including exposure"
        self.__unfixed_observations[:] = 0
        self.__masked_dataoverlay[:] = 0
        self.__unmasked_dataoverlay[:] = 0

    def copy(self,flatten:bool=False):
        """
        Return a copy of the overlay.
        If flatten, squash (mean) exposure window into 1 frame.
        """
        if flatten:
            cp = Overlay(self.floorid, self.overlay_dimensions, self.real_dimensions, self.mask, 1)
            cp.__unfixed_observations[0] = self.__unfixed_observations.mean(axis=0)
            cp.__masked_dataoverlay[0] = self.__masked_dataoverlay.mean(axis=0)
            cp.__unmasked_dataoverlay[0] = self.__unmasked_dataoverlay.mean(axis=0)
        else:
            cp = Overlay(self.floorid, self.overlay_dimensions, self.real_dimensions, self.mask, self.exposure)
            cp.__unfixed_observations = self.__unfixed_observations.copy()
            cp.__masked_dataoverlay = self.__masked_dataoverlay.copy()
            cp.__unmasked_dataoverlay = self.__unmasked_dataoverlay.copy()
        return cp

    def add(self,observations:dict) -> None:
        fixed = {}
        unfixed = {}

        for id, placeable in observations.items():
            if ( placeable.x != None and placeable.y != None ) or placeable.has_mask_override:
                fixed[id] = placeable
            else:
                unfixed[id] = placeable
        
        self.__add_fixed_locations(fixed)
        self.__add_unfixed_locations(unfixed)

    def __add_fixed_locations(self,fixed:dict) -> None:
        for placeable in fixed.values():
            # We store both a copy of the m(asked)_possible locations and the u(n)m(asked)_possible locations
            um_possible = np.zeros(self.overlay_dimensions, dtype=np.bool_)

            if placeable.has_mask_override:
                # Even if a floorplan mask is in place, mask override takes precident
                um_possible = placeable.mask_override
                m_possible = placeable.mask_override
            else:
                if placeable.variance < Model.VARIANCE_THRESHOLD:
                    # Calculated minimum reach
                    # Account for change of axis
                    um_possible[-int(placeable.y/Model.CELL_SIZE_M),int(placeable.x/Model.CELL_SIZE_M)] = 1
                else:
                    # Store parsed location in x,y tuple, in m, with change of axis
                    client_loc = np.array( [self.real_dimensions[0] - placeable.y, placeable.x ] )
                    for x in range(um_possible.shape[0]):
                        for y in range(um_possible.shape[1]):
                            # For each square, see if it's centre is close enough to be within variance metres
                            d = np.linalg.norm(
                                    (np.array([x,y]) + 0.5) * Model.CELL_SIZE_M - client_loc
                                )
                            um_possible[x,y] = d <= placeable.variance
            
                # m(asked)_possible is a copy of the u(n)m(asked)_possible's with the floor mask applied
                m_possible = np.logical_and( um_possible, self.mask, dtype=np.bool_ )

            # If theres a DIV0 here, the search hasn't found any near enough to call near
            # Ignore floor mask
            self.__unmasked_dataoverlay[0][um_possible] += 1.0 / um_possible.sum()
            # Include floor mask
            self.__masked_dataoverlay[0][m_possible] += 1.0 / m_possible.sum()
        
    def __add_unfixed_locations(self,unfixed:dict) -> None:
        self.__unfixed_observations[0] += len(unfixed)
    
    def get_delta(self, masked:bool=True, exposure:int=0)->np.ndarray:
        """
        Returns a copy of the delta overlay (only fixed observations).
        If masked, will select data masked at input, else unmasked data.
        Set exposure to specify mean smoothing on the first n frames of stored exposure,
         default (0) combines all available frames,
         1 gives only the latest frame (no smoothing).
        """
        window = self.exposure if exposure == 0 else exposure
        if masked:
            return self.__masked_dataoverlay[:window].mean(axis=0)
        else:
            return self.__unmasked_dataoverlay[:window].mean(axis=0)
    
    def get_unfixed_observations(self, exposure:int=0)->float:
        """
        Return how many unfixed observations were passed.
        For more details on exposure, see Overlay.get_delta
        """
        window = self.exposure if exposure == 0 else exposure
        return self.__unfixed_observations[:window].mean(axis=0)

    def get_full(self, masked:bool=True, exposure:int=0)->np.ndarray: #pragma: no cover
        """
        Returns a copy of the full client overlay (including distributed unfixed observations)
        For exposure, see Overlay.get_delta
        """
        data = self.get_delta(masked,exposure)
        window = self.exposure if exposure == 0 else exposure
        # Distribute unfixed observations evenly across the floorplan (or mask)
        mask = self.mask if masked else np.ones(self.overlay_dimensions,dtype=np.bool_)
        data[mask] += self.__unfixed_observations[:window].mean(axis=0) / mask.sum()
        return data

    def verify_and_update(self,floor:Floor)->None:
        "Verifies overlay is compatible with passed floor, updates mask"
        if self.overlay_dimensions != floor.overlay_dimensions or self.real_dimensions != floor.floorplan_dimensions:
            raise Model.ModelException("Error: Overlay and Floorplan dimension mismatch for FPID={}".format(floor.floorplan.id))

        # Update mask in case of change
        # Note this does not change existing data, only new observations
        self.mask == floor.mask

class Model:
    LAYER_SNAP_WIFI = 1
    LAYER_SNAP_BT = 2
    LAYER_MVSENSE = 3
    LAYERS_ALL = {LAYER_SNAP_WIFI, LAYER_SNAP_BT, LAYER_MVSENSE}

    CONFIG_PATH = os.path.join('model.conf')

    CELL_SIZE_M = 1
    DOWNSAMPLE_THRESHOLD = 0.5
    VARIANCE_THRESHOLD = np.hypot( *( 2*(CELL_SIZE_M / 2,) ) )
    # This means let x = cell_s_m / 2; V_T = sqrt(x^2+x^2)
    # I wish I was kidding
    # This is 0.707 iff cell_s_m = 1
    DEFAULT_EXPOSURE = 3
    DEFAULT_PASSWORD = '90d693d30a3fa06791eb43f7cc0f8a3af2687aec3c172cb0f690ae1d68382300'

    __BAD_LAYER = "Layer {} not defined. Use internally defined layer (eg Model.LAYER_*)"

    class ModelException(Exception):
        pass

    class BadRequest(Exception):
        pass

    def __init__(self,network_id:str=None,layers:set={}):
        "Initialise model. API key must be defined in enviroment variable \"MERAKI_DASHBOARD_API_KEY\""

        self.read_config_data()
        self.write_config_data()
    
    def populate(self,layers:set):
        assert isinstance(self.query_obj, APIQuery)
        self.network_id = self.query_obj.network_id
        self.plans = self.pullFloors()
        self.getAPs()
        self.query_obj.pullCameras()
        self.data_layers = dict()
        self.webhook_threshold = 0.35
        for layer in layers:
            if layer not in Model.LAYERS_ALL:
                raise Model.ModelException(Model.__BAD_LAYER.format(layer))
            self.data_layers[layer] = Layer(self.plans, Model.DEFAULT_EXPOSURE)

        self.timeslot = TimeSlotAvg.load(self.data_layers,self.plans)       
        self.webhook_addresses = []

    ### Floorplans

    def pullFloors(self) -> dict:
        "Pull floorplans from the network, construct blank floor layer for each"
        floorplans = self.query_obj.pullFloorPlans()
        self.plans = { id : Floor(fp) for id,fp in floorplans.items() }
        return self.plans

    def getFloorplanSummary(self) -> dict:
        "Get a dict of retreived floor plan IDs and names"
        return { k : v.floorplan.name for k,v in self.plans.items() }

    def findFloorplanByName(self,name) -> str:
        "Find a floorPlanId from the floor name"
        for k in self.plans:
            if self.plans[k].floorplan.name == name:
                return k
        return None

    def setBoundsMask(self,floor_id:str,on:bool,blindspots=None,wallthreshold:float=None) -> None:
        "Generate a mask from BoundaryDetector for areas that people cannot possibly be on the given floor eg outside high floors. Blindspots should be a Numpy array, tuple or nested list of the form [[x1,x2,y1,y2],...]"
        if blindspots==None:
            pass
        elif not (isinstance(blindspots,(np.ndarray,list,tuple))):
            raise TypeError("Invalid type for blindspots parameter. Should be of type np.array, list or tuple")
        elif False in [ len(spot) == 4 for spot in blindspots ]:
            raise ValueError("Invalid format for blindspots parameter. Should be of shape (n,4), got {}".format(str(blindspots)))

        if wallthreshold == None:
            pass
        elif not isinstance(wallthreshold,(int,float)):
            raise TypeError("Invalid type for wallthreshold parameter. Should be of type int or float, got {}".format(str(type(wallthreshold))))
        
        if floor_id not in self.plans.keys():
            raise Model.ModelException("No such floor: ",floor_id)


        floor = self.plans[floor_id]
        if on:
            floor.set_bounds_mask(blindspots,wallthreshold)
        else:
            floor.bm_boxes = blindspots
            floor.mask[:] = 1
        floor.mask_enabled = on
        
        self.update_layers()

    ### Layers

    def update_layers(self)->None:
        """
        Must be called when a Floor is added, removed, or altered, including by set_bounds_mask
        This will update the Overlay objects to reflect this change
        May throw error if dimensions do not equate and historical data would be invalidated
        """
        for layer in self.data_layers.values():
            layer.verify_and_update(self.plans)

    ### Access Points

    def getAPs(self) -> None:
        "Get APs and store internally in relevent floor objects"
        aps = self.query_obj.pullAPs()
        for mac,ap in aps.items():
            if ap.floorPlanId in self.plans.keys():
                self.plans[ap.floorPlanId].aps[mac] = ap

    ### Scanning API (SAPI)

    def __validate_scanning(self,SAPI_packet:dict) -> None:
        if type(SAPI_packet) != dict:
            raise TypeError("JSON parsed a {}, expected a dict".format(str(type(SAPI_packet))))
        try:
            source_net_id = SAPI_packet["data"]["networkId"]
            if SAPI_packet[SECRET_K] != self.secret:
                raise Model.BadRequest("Request has bad authentication secret - rejecting data")
        except KeyError as ke:
            raise Model.BadRequest("Request is missing data: " + str(ke) )
        if source_net_id != self.network_id:
            raise Model.BadRequest("Request has data from wrong network: expected {} got {}".format(self.network_id,source_net_id))

    def get_type(SAPI_packet:dict) -> int: 
        "Get the Model layer constant for a given SAPI packet"
        api_layer_val = APIQuery.get_SAPI_type(SAPI_packet)
        if api_layer_val == "WiFi":
            return Model.LAYER_SNAP_WIFI
        elif api_layer_val == "Bluetooth":
            return Model.LAYER_SNAP_BT
        else:
            raise Model.ModelException(Model.__BAD_LAYER.format(api_layer_val))

    def __generate_person_obs(self) -> dict:
        "Indexes observed person objects with an arbitrary key"
        obs = self.query_obj.get_camera_observations()
        # Zip [0,n) with n obs objects, converting to dictionary
        return dict(zip(range(len(obs)),obs))

    def provide_scanning(self,SAPI_packet:dict) -> None:
        "Update model with SAPI data"
        # Raise a racket if theres something wrong
        self.__validate_scanning(SAPI_packet)
        dest_layer = Model.get_type(SAPI_packet)
        observations = self.query_obj.extract_SAPI_observations(SAPI_packet)
        self.data_layers[dest_layer].set_observations(observations)
    
    ### Camera and MVSense

    def setFOVs(self,mac:str,coords:set)->None:
        """
        Set the FOV coords from given camera (by mac).
        Coords should be iterable of shape (n,2).
        Coords pertain to sqm pixels on internal datamap.
        Pass len(iterable)==0 to unset mask
        """
        #Check if Layer exists
        if Model.LAYER_MVSENSE in self.data_layers.keys():
            #Check camera with mac exists
            if mac in self.query_obj.getCameras().keys():
                #Check coords of correct shape and iterable, or of len 0 to unset
                try:
                    if len(coords) == 0 or False not in [ len(coord)==2 for coord in coords ]:
                        cam = self.query_obj.cameras[mac]
                        shape = self.plans[cam.floorPlanId].overlay_dimensions
                        cam.set_FOV(shape,coords)
                    else:
                        raise ValueError
                except (ValueError, TypeError) as err:
                    raise err.__class__("Coordinates supplied of incorrect shape or type, should be iterable shape (n,2)")
            else:
                raise Model.ModelException("Camera with mac {} not found".format(mac))
        else:
            raise Model.ModelException("Model not configured for LAYER_MVSENSE")

    def pull_mvsense_data(self):
        "Pull live MVSense data from cameras and feed into data layer"
        self.query_obj.updateCameraMVSenseData()
        observations = self.__generate_person_obs()
        self.data_layers[Model.LAYER_MVSENSE].set_observations(observations)
    
    def spike(self, layer, threshhold)->dict: #add floorplan ID into params, camera/wifi/bluetoothall into params? threshold into params?
        
        dims = ( (len(layer)//3)+1, (len(layer[0])//3)+1 ) #splits floorplan into 3m^2 areas
        
        clusters = np.zeros(dims, dtype="float32")        
            
        for x in range(len(clusters)):                   
            for y in range(len(clusters[0])):
                clusters[x,y] = layer[3*x:3*(x+1),3*y:3*(y+1)].sum()

        busiest = 0
        busiest_location=None
        for x in range(len(clusters)):
            for y in range(len(clusters[0])):
                if clusters[x][y] > busiest:
                    busiest = clusters[x][y]
                    busiest_location = (3*(x+0.5), 3*(y+0.5))                    
        
        return {'spike':busiest > threshhold, 'location':busiest_location}
                
    def nearestCameras(self, n:int, floor:Floor,spikeDict:dict)->tuple:  #returns a list of camera objects
        # They call me the comprehension king
        # Maybe after we spend 30 minutes fixing it ;)
        event = spikeDict["location"]
        event_root = tuple([ int(d) for d in event ])
        cameras = { cam for cam in self.query_obj.getCameras().values() if cam.floorPlanId == floor.floorplan.id }
        FOVcams = { cam for cam in cameras if cam.has_FOV() }
        nonFOVcams = cameras - FOVcams
        hasView = { cam for cam in FOVcams if cam.get_FOV()[event_root]==True }

        if len(hasView)>0:
            return ("Covered", list(hasView) )
        
        distances = dict()

        for cam in FOVcams:
            fov = cam.get_FOV()
            mindist = 9999999
            for x,row in enumerate(fov):
                for y, cell in enumerate(row):
                    if cell:
                        dist = np.hypot( (x+0.5)-event[0], (y+0.5)-event[1] )
                        if dist < mindist:
                            mindist = dist
            distances[cam] = mindist
        
        for cam in nonFOVcams:
            distances[cam] = np.hypot( cam.x-event[0], cam.y-event[1] )
        
        top_n = [ cam[0] for cam in sorted(distances.items(),key=lambda x: x[1])[:n] ]
        return ("Best Effort", top_n)
    
    def getCameraImage(self, camera) -> dict:
        #returns a dictionary containing a link to the image
        response = self.query_obj.getCameraSnap(camera)
        return response
        
    def snapshotWebhook(self, snapshot:dict):
        for address in self.webhook_addresses:
            response = requests.post(address, json = snapshot)
            print(response)

    def addWebhookAddress(self, webhookAddress:str):
        self.webhook_addresses.append(webhookAddress)

    ### Historical

    def put_historical(self) -> None:
        "Updates the average data for the current TimeSlotAvg object"
        self.update_timeslot() # Get the current timeslot object
        self.timeslot.update_avg_data( self.data_layers )
    
    def comp_historical(self, floorPlanId:str):
        "Get the relative busyness of a floorplan using all layers"
        self.update_timeslot() # Get the current timeslot object
        hist_fp_data = self.timeslot.get_floor_avgs(floorPlanId)
        collective = np.zeros( self.plans[floorPlanId].overlay_dimensions )
        for lid in self.data_layers.keys():
            mask_enabled = self.plans[floorPlanId].mask_enabled
            current = self.data_layers[lid].overlays[floorPlanId].get_delta(masked=mask_enabled)
            historical = hist_fp_data[lid].get_delta(masked=mask_enabled,exposure=1)
            collective += (current - historical)
        collective /= len(self.data_layers)
        return collective
    
    def update_timeslot(self):
        "Calls the factory if the current TimeSlotAvg object is not current"
        if not (self.timeslot.is_current_time()):
            self.timeslot.write()
            self.timeslot = TimeSlotAvg.load( self.data_layers, self.plans )
            self.timeslot.verify_and_update_struct( self.data_layers, self.plans )
    
    ### Providers

    def poll_layer(self,layer:int,exposure:int) -> dict:
        return self.data_layers[layer].get_full(exposure=exposure)
    
    def render_delta(self,floorPlanId:str)->Image:
        "Get the current datamap in terms of absolute delta from mean"
        datamap = self.comp_historical(floorPlanId)
        return self.plans[floorPlanId].render_overlay(datamap)
    
    def render_abs(self,floorPlanId:str)->Image:
        "Get latest frame of WiFi layer rendered on the floor plan"
        return self.plans[floorPlanId].render_overlay(self.data_layers[Model.LAYER_SNAP_WIFI].overlays[floorPlanId].get_delta(exposure=1))

    def debug_render(self,fpid)->Image:
        import datetime
        dm = self.plans[fpid]
        dims = dm.overlay_dimensions
        testarr = np.zeros(dims).ravel()
        n = (datetime.datetime.now().second / 60) * len(testarr)
        testarr[:int(n)] = 1
        return dm.render_overlay(testarr.reshape(dims))
    
    def update(self)->None:
        "Update non-webhook (non-SAPI) layers, write history"
        self.pull_mvsense_data()
        self.put_historical()
        #spike detect
        POST_data = {}
        for fpid, floor in self.plans.items():
            spikedict = self.spike(self.comp_historical(fpid), self.webhook_threshold)
            if spikedict['spike'] == True:
                idealality, cameras = self.nearestCameras(2, floor, spikedict)  #need to get relevant floor obj
                POST_data[fpid] = {"type" : "SnapshotData", "is_ideal" : idealality}
                for i, cam in enumerate(cameras):
                    response = self.getCameraImage(cam)
                    POST_data[fpid]["camera_data_" + str(i)] = response
                      
        if POST_data != {}:
            self.snapshotWebhook(POST_data)
        
    ### Configuration

    STORE_WEBHOOK = "webhooklist"
    STORE_SELECTED = "selectednet"
    STORE_LAYERS = "layers"
    STORE_FOVCOORDS = "fov_coords"
    STORE_FOVMASK = "fov_mask"
    STORE_BMBOXES = "bm_boxes"
    STORE_BDENABLED = "bd_enabled"
    STORE_SECRET = "sapisecret"
    STORE_TOKEN = "validator_token"
    STORE_PASSWORD = "authenticator"
    STORE_WHTHRESHOLD = "webhook_threshold"

    def update_model_config(self, netid, conf_dict):
        layers = conf_dict.get(Model.STORE_LAYERS,set())

        try:
            if netid != self.network_id:
                raise AttributeError
        except AttributeError:
            self.query_obj = APIQuery(netid)
            self.populate(layers)

        self.secret = conf_dict.get(Model.STORE_SECRET)
        self.validator_token = conf_dict.get(Model.STORE_TOKEN)
        self.webhook_addresses = conf_dict.get(Model.STORE_WEBHOOK,list())
        self.password = conf_dict.get(Model.STORE_PASSWORD,Model.DEFAULT_PASSWORD)
        self.webhook_threshold = conf_dict.get(Model.STORE_WHTHRESHOLD,self.webhook_threshold)
        
        for mac, coords in conf_dict.get(Model.STORE_FOVCOORDS,dict()).items():
            self.setFOVs( mac, coords )
        
        for fpid, boxes in conf_dict.get(Model.STORE_BMBOXES, dict()).items():
            on = conf_dict.get(Model.STORE_BDENABLED,{fpid:False})[fpid]
            self.setBoundsMask(fpid, on, boxes)



    def serialize(self):
        conf = dict()
        conf[Model.STORE_SECRET] = self.secret
        conf[Model.STORE_TOKEN] = self.validator_token
        conf[Model.STORE_LAYERS] = set(self.data_layers.keys())
        conf[Model.STORE_WEBHOOK] = self.webhook_addresses
        conf[Model.STORE_WHTHRESHOLD] = self.webhook_threshold
        conf[Model.STORE_PASSWORD] = self.password
        conf[Model.STORE_FOVCOORDS] = { cam.mac: cam.get_fov_coords() for cam in self.query_obj.cameras.values() }
        conf[Model.STORE_BMBOXES] = { fpid: fp.bm_boxes for fpid,fp in self.plans.items() }
        conf[Model.STORE_BDENABLED] = { fpid: fp.mask_enabled for fpid,fp in self.plans.items() }
        return conf

    def write_config_data(self):

        config_data = {Model.STORE_SELECTED:self.network_id}
        config_data[self.network_id] = self.serialize()

        with open( self.CONFIG_PATH, 'wb' ) as f:
                pickle.dump(config_data, f)

    def read_config_data(self):
        if os.path.isfile(Model.CONFIG_PATH):
            with open( Model.CONFIG_PATH, 'rb' ) as f:
                config_data = pickle.load(f)
            selected_id = config_data[Model.STORE_SELECTED]
            select_data = config_data[selected_id]
            self.update_model_config(selected_id,select_data)
        else:
            print("Warning: config file not found")
            try:
                self.update_model_config(None, {Model.STORE_LAYERS: Model.LAYERS_ALL} )
            except APIQuery.APIException:
                raise Model.ModelException("Could not get network from config file")


class TimeSlotAvg:

    class TimeSlotAvgException( Exception ):
        pass

    DATA_DIR = "historical_data"

    def __init__(self, data_layers:dict, day:int, hour:int):
        self.day = day
        self.hour = hour
        self.data_layers = dict()
        self.count = dict()

        for l_id, layer in data_layers.items():
            # Copy the layer structure but clear the transient data
            # Also we only need 1 frame to store average so flatten
            self.data_layers[l_id] = layer.copy(flatten=True)
            self.data_layers[l_id].clear()
            # Set a count for each overlay in each layer stored
            self.count[l_id] = { fpid:0 for fpid in layer.overlays.keys() }
            
    @staticmethod
    def load( data_layers:dict, floors:dict, day=None, hour=None ):
        "Static factory method; Load TimeSlotAvg object from compressed pickle file or create new"
        #TODO remove day hour params - used for unit tests
        if day==None or hour==None:
            day, hour = TimeSlotAvg.get_time()

        try:
            tsa = bz2.BZ2File(os.path.join(TimeSlotAvg.DATA_DIR,'{}_{}.pbz2'.format(day, hour)), 'rb')
            tsa = pickle.load(tsa)
        except FileNotFoundError:
            tsa = TimeSlotAvg( data_layers, day, hour )
            tsa.verify_and_update_struct(data_layers, floors)
            tsa.write()
        else:
            if __name__!="__main__": assert isinstance(tsa,TimeSlotAvg)
            tsa.verify_and_update_struct(data_layers, floors)

        return tsa

    def is_current_time(self, debug=None) -> bool:
        "Returns True iff timeslot is for current time"
        if debug != None:
            return debug
        curr_day, curr_hour = TimeSlotAvg.get_time()
        return curr_day == self.day and curr_hour == self.hour

    def update_avg_data(self, current_data:dict, debug:bool=None) -> None:
        "Updates an average model for a timeslot using the current model data, if valid time"
        if self.is_current_time(debug): # it is valid to update with the current model
            # For each layer in the new data
            for l_key, layer in current_data.items():
                # Get the respective average layer
                avg_layer = self.data_layers[l_key]
                # For each overlay in the respective new data layer
                for o_key, over in layer.overlays.items():
                    # Get masked and unmasked deltas, and unfixed count from new data
                    # Get full available exposure by default
                    new_um_overlay = over.get_delta(masked=False)
                    new_m_overlay = over.get_delta(masked=True)
                    new_unfixed_obs = over.get_unfixed_observations()

                    # Similar from averages
                    # avg layers are already flat so exposure of 1
                    avg_um_overlay = avg_layer.overlays[o_key].get_delta(masked=False,exposure=1)
                    avg_m_overlay = avg_layer.overlays[o_key].get_delta(masked=True,exposure=1)
                    avg_unfixed_obs = over.get_unfixed_observations()

                    # Count
                    c = self.count[l_key][o_key]

                    # update the average by adding current values to sum total and dividing by new count
                    upd_um_overlay = ( avg_um_overlay * c + new_um_overlay ) / (c+1)
                    upd_m_overlay = ( avg_m_overlay * c + new_m_overlay ) / (c+1)
                    upd_unfixed_obs = ( avg_unfixed_obs * c + new_unfixed_obs ) / (c+1)

                    # save the new data overlay to the timeslots model, promoting as exposure of historicals = 1
                    self.data_layers[l_key].overlays[o_key].set( upd_unfixed_obs[None,], upd_m_overlay[None,], upd_um_overlay[None,] )

                    # Update the count
                    self.count[l_key][o_key] += 1

            #self.write()
        else:
            raise TimeSlotAvg.TimeSlotAvgException(f"Cannot update with current model as it is not currently day:{self.day}, hour:{self.hour}")
    
    def write(self):
        "Save TimeSlotAvg object to a compressed file"
        filepath = os.path.join(TimeSlotAvg.DATA_DIR,'{}_{}.pbz2'.format(self.day, self.hour))
        if not os.path.exists(TimeSlotAvg.DATA_DIR):
            os.makedirs(TimeSlotAvg.DATA_DIR)
        with bz2.BZ2File(filepath, 'wb') as f: 
            pickle.dump(self, f)

    def get_floor_avgs(self, fpid:str)->dict:
        "Return the flat average Overlay object indexed by each layer stored"
        return { layer_id: layer.overlays[fpid] for layer_id, layer in self.data_layers.items() }

    @staticmethod
    def get_time()->tuple:
        "Get the current time values needed for reading and writing data files"
        curr_dt = datetime.datetime.now( datetime.timezone( offset=datetime.timedelta(hours=0) ) )
        curr_day =  curr_dt.weekday()
        curr_hour = curr_dt.hour
        return curr_day, curr_hour
    
    def verify_and_update_struct(self, data_layers:dict, floors:dict)->None:
        """
        Verifies that the data in the TimeSlotAvg is compatible with the current Model.
        If layers or overlays are not represented in TSA, those are created, infos are printed
        Throws ModelException if dimensions do not match
        """
        for l_id in set(data_layers.keys()).difference(self.data_layers.keys()):
            # For layers in data_layers not in self
            self.data_layers[l_id] = data_layers[l_id].copy()
            self.count[l_id] = dict()
            print("Info: Layer implicitly created for Layer ID {}".format(l_id))

        for l_id, layer in self.data_layers.items():
            # Add any missing overlays
            layer.verify_and_update(floors)

        for l_id in data_layers.keys():
            # Get count if exists, else set to 1
            self.count[l_id] = { ov_id:self.count[l_id].get(ov_id,1) for ov_id in data_layers[l_id].overlays.keys() }

def sha256(inpt:str) -> str:
    m = hashlib.sha256()
    m.update(inpt.encode())
    return m.hexdigest()