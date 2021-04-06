import math
import requests
import numpy as np
import os
import meraki
from PIL import Image
import re
import hashlib

#Note: Comments "pragma:_no_cover" (with spaces) stop coverage.py from flagging them as lacking test cover
#      Same applies for "pragma:_no_branch" 

class Placeable:
    "Interface representing an object in the floorplan space"
    def __init__(self, floorPlanId:str=None, lat=None, lng=None, x=None, y=None, variance=None):
        self.floorPlanId = floorPlanId
        self.lat = lat
        self.lng = lng
        self.x = x
        self.y = y 
        self.variance = variance

        self.has_mask_override = False
        self.mask_override = None

    def set_mask_override( self, mask:np.ndarray ):
        "Set (or unset by passing None) a mask override for the possible locations of the objects"
        self.has_mask_override = isinstance(mask,np.ndarray)
        self.mask_override = mask

class Client(Placeable):
    "Class representing a client observation on the network"
    def __init__(self, mac:str, nearestApMac:str=None, floorPlanId:str=None, lat=None, lng=None, x=None, y=None, variance=None):
        super().__init__( floorPlanId, lat, lng, x, y, variance )
        self.mac = mac
        self.nearestApMac = nearestApMac
    
class Person(Placeable):
    "Class representing a person observation by a camera"
    def __init__( self, floorPlanId:str=None, lat=None, lng=None, x=None, y=None, variance=None ):
        super().__init__( floorPlanId, lat, lng, x, y, variance )

class FloorPlan:
    "Class to represent a floor plan"

    __DEBUG_HASH_OVERRIDE = False
    MINIMAL_LENGTH = 0.5#m
    IMG_ROOT = ["static","img","floorplans"]

    class FloorPlanException( Exception ):
        pass

    def __init__(self, id:str, name:str, center:dict, height:float, width:float, tlc:dict, trc:dict, url:str, md5:str):
        if height < FloorPlan.MINIMAL_LENGTH or width < FloorPlan.MINIMAL_LENGTH:
            raise FloorPlan.FloorPlanException("Dimensions (h={:.2f}m, w={:.2f}m) of FloorPlan object {} unacceptable. Minimum is {}m".format(height,width,name,FloorPlan.MINIMAL_LENGTH) )

        self.id = id
        self.name = name
        self.center = center
        self.height = round(height, 2)
        self.width = round(width, 2)

        if trc['lng'] == tlc['lng']:
            self.rotation = 90 if tlc['lat'] < trc['lat'] else 270
        else:
            self.rotation = math.degrees(math.atan(( trc['lat'] - tlc['lat'] ) / ( trc['lng'] - tlc['lng'] ))) % 360
    
        # get floorplan image as np array, from url
        self.__manage_image(url,md5)
        self.im_width, self.im_height = self.get_image().size
        self.px_per_m_w = self.im_width / self.width
        self.px_per_m_h = self.im_height / self.height

    def __manage_image(self,url:str,md5:str)->None:
        "Download or verify existing floorplan image"
        rootpath = os.path.join(*FloorPlan.IMG_ROOT)
        if not os.path.exists(rootpath):
            os.makedirs(rootpath)

        self.filename = re.sub(r"\W", "_",  self.id) + ".png"
        self.filepath = os.path.join(rootpath,self.filename)
        if FloorPlan.__DEBUG_HASH_OVERRIDE:
            return
        md5_hash = hashlib.md5()
        try:
            with open(self.filepath,"rb") as fd:
                for byte_block in iter(lambda: fd.read(4096),b""):
                    md5_hash.update(byte_block)

            if md5_hash.hexdigest() != md5:
                os.unlink(self.filepath)
                raise FileNotFoundError
        except (IOError,FileNotFoundError):
            with requests.get(url, stream=True) as req:
                with open(self.filepath, "wb") as fd:
                    for chunk in req.iter_content(chunk_size=4096):
                        if chunk:
                            fd.write(chunk)
        
    def get_image(self)->Image.Image:
        "Retreive Image of the floor plan from the API"  
        return Image.open(self.filepath)
    
    def m_rel_from_coords(self,lat,lng)->tuple:
        # get lng, lat of floorplan center
        fpc_lng = self.center['lng']
        fpc_lat = self.center['lat']

        # get a value of x0, y0 meters relative to the center before rotation
        diff_lng = lng - fpc_lng
        x0 = diff_lng * m_p_d_lng(fpc_lng)

        diff_lat = lat - fpc_lat
        y0 = diff_lat * m_p_d_lat(fpc_lat)

        # rotate points, origin is stil the center of floorplan image
        xc = x0 * math.cos( self.rotation ) - y0 * math.sin( self.rotation )
        yc = x0 * math.sin( self.rotation ) + y0 * math.cos( self.rotation )

        # move origin to lower left corner 
        return ( round( xc + 0.5 * self.width, 2), round( yc + 0.5 * self.height, 2) )

# functions for converting degrees to meters
def m_p_d_lat(lat):
    return 111132.92 - 559.82 * math.cos( 2 * lat ) + 1.175 * math.cos( 4 * lat ) - 0.0023 * math.cos( 6 * lat )
def m_p_d_lng(lng):
    return 111412.84  * math.cos( lng ) - 93.5 * math.cos( 3 * lng ) + 0.118 * math.cos( 5 * lng )   

class AP:
    "Class to represent an access point"

    # create access point with given data
    def __init__(self, name:str, mac:str, lat:float, lng:float, floorPlanId:str, floorplan:FloorPlan):
        self.name = name
        self.mac = mac
        self.lat = lat
        self.lng = lng
        self.floorPlanId = floorPlanId
        self.x, self.y = floorplan.m_rel_from_coords(self.lat,self.lng)
    

class Camera:
    "class to represent a camera in a floorplan"

    def __init__(self, mac, serial, lat, lng, floorplan:FloorPlan):
        self.serial = serial
        self.mac = mac
        self.lat = lat
        self.lng = lng
        self.floorPlanId = floorplan.id
        self.MVdata = None
        self.x, self.y = floorplan.m_rel_from_coords(self.lat,self.lng)

        # Camera mask override
        self.__has_FOV = False
        self.__FOV_mask = None
        self.__coordinates = set()
    
    def has_FOV(self)->bool:
        "Test if camera object has a Field of View override mask"
        return self.__has_FOV

    def set_FOV(self, mask_shape:tuple, coords:set={})->None:
        "Populate FOV mask with the given possible datamap cell locations. Must be iterable of tuples shape (n,2). Call set_FOV(None) to unset"
        self.__has_FOV = True if len(coords) > 0 else False
        if not self.__has_FOV:
            #If unsetting
            return
        self.__FOV_mask = np.zeros(mask_shape,dtype=np.bool_)
        for x,y in coords:
            self.__FOV_mask[x,y]=1
        self.__coordinates = coords
    
    def get_FOV(self)->np.ndarray:
        "Get FOV location override mask"
        return self.__FOV_mask

    def get_fov_coords(self)->set:
        "Get FOV coordiantes"
        return self.__coordinates


class APIQuery:
    "Class with methods to query the meraki dashboard API for a given network with object deserialization"

    class APIException( Exception ):
        pass

    def __init__(self, network_id:str=None, api_key:str=None):
        "Construct a network dashboard object. API key must be defined in environment variable \"MERAKI_DASHBOARD_API_KEY\""
        #TODO: Remove api_key param, added for CHAOS TESTING PURPOSES ONLY

        if os.getenv("MERAKI_DASHBOARD_API_KEY") == None and api_key == None: # pragma: no cover
            #Not covered due to test environment constraints
            raise APIQuery.APIException("Required API key not defined in environment variable \"MERAKI_DASHBOARD_API_KEY\"")

        #Get API key implicitly from ENV VAR when api_key == None
        self.dashboard = meraki.DashboardAPI(
            print_console=False,
            output_log=False,
            api_key=api_key
        )
        
        try:
            self.org_id = self.dashboard.organizations.getOrganizations()[0]['id']
        except meraki.exceptions.APIError:
            raise APIQuery.APIException("Invalid API key")

        

        self.network_list = [ { 'id': net['id'], 'name': net['name']} for net in self.dashboard.organizations.getOrganizationNetworks(self.org_id) ]

        if network_id: # if network_id provided - validate and use
            if not isinstance(network_id,str):
                raise APIQuery.APIException("Provided network_id not of correct form")
            
            self.network_id = network_id

        else: # if no network_id provided use the first net id in the list ( will see how this works )

            self.network_id = self.network_list[0]['id']

        try:
            self.dashboard.networks.getNetwork(self.network_id)
        except (meraki.APIError, APIQuery.APIException) :
            raise APIQuery.APIException("404: Network {} does not exist (retry later if newly created)".format(network_id))

    def pullFloorPlans(self) -> dict:
        "Get a list of the floor plan objects associated to the network"
        self.floorplans = {}

        raw_data = self.dashboard.networks.getNetworkFloorPlans(self.network_id)

        # store FPs in dictionary with id as key
        for fp_data in raw_data:
            self.floorplans[fp_data['floorPlanId']] =\
                FloorPlan(
                    fp_data['floorPlanId'], 
                    fp_data['name'],
                    fp_data['center'],
                    fp_data['height'],
                    fp_data['width'],
                    fp_data['topLeftCorner'],
                    fp_data['topRightCorner'],
                    fp_data['imageUrl'],
                    fp_data['imageMd5']
                )
        return self.floorplans

    def getFloorPlan(self, floorPlanId:str, pull_on_fail:bool=True) -> FloorPlan:
        "Return a floorplan object for the given floorPlanId. If needed will pull floorplans unless pull_on_fail is false"
        if hasattr(self, "floorplans"):
            return self.floorplans.get(floorPlanId)
        elif pull_on_fail:
            self.pullFloorPlans()
            return self.getFloorPlan(floorPlanId, False)
        else:
            raise APIQuery.APIException("Floorplan pull supressed or failed")


    def pullAPs(self) -> dict:                                       
        "Get a dict of Access Point objects associated to the network"
        devices = self.dashboard.networks.getNetworkDevices(self.network_id)
        
        self.accesspoints = {}
        for device in devices:
            #If model number is of an AP type
            if device["model"].startswith("MR"):
                self.accesspoints[device["mac"]] = AP(
                    device["name"],
                    device["mac"],
                    device["lat"],
                    device["lng"],
                    device["floorPlanId"],
                    self.getFloorPlan(device["floorPlanId"])
                )

        return self.accesspoints

    def getAP(self, mac:str, pull_on_fail:bool=True) -> AP:
        "Return an AP object given its mac address. If needed, will pull APs unless pull_on_fail false"
        if hasattr(self, "accesspoints"):
            return self.accesspoints.get(mac)
        elif pull_on_fail:
            self.pullAPs()
            return self.getAP(mac,False)
        else:
            raise APIQuery.APIException("AP pull supressed or failed")
    
    def pullCameras(self) -> dict:                                       
        "Get a dict of Camera objects associated to the network"
        devices = self.dashboard.networks.getNetworkDevices(self.network_id)
        
        self.cameras = {}
        for device in devices:
            #If model number is of an Camera type
            if device["model"].startswith("MV"):
                fp = self.getFloorPlan(device["floorPlanId"])
                if fp:
                    self.cameras[device["mac"]] = Camera(
                        device["mac"],
                        device["serial"],
                        device["lat"],
                        device["lng"],
                        fp
                    )
        return self.cameras

    def getCameraSnap(self,cam:Camera):
        try:
            response = self.dashboard.camera.generateDeviceCameraSnapshot(cam.serial)
        except meraki.exceptions.APIError:
            response = "error reaching camera"
        return response
            

    def updateCameraMVSenseData(self, camera:Camera=None) -> dict:
        "Update the MVsense data for given cameras. If camera is none, update all"
        if camera==None:
            for cam in self.cameras.values():
                try:
                    self.updateCameraMVSenseData(cam)
                except APIQuery.APIException as a:
                    print("Warning: ", a)
            return

        serial = camera.serial
        try:
            resp = self.dashboard.camera.getDeviceCameraAnalyticsLive(serial)
            if "error" in resp:
                raise APIQuery.APIException("Camera with serial {} could not be reached: {}".format(serial,str(resp)))
        except meraki.exceptions.APIError:
            raise APIQuery.APIException("Camera with serial {} not found".format(serial))
        
        #parse response
        zones = { zid: counts["person"] for zid, counts in resp["zones"].items() }

        camera.MVdata = zones
        return zones

    def getCameras(self, mac:str=None, pull_on_fail:bool=True):
        """
        Get camera object, all or by mac, from APIQuery object.
        If mac is None or not passed, get dict of all cameras.
        If needed, will pull APs unless pull_on_fail false
        """
        if hasattr(self, "cameras"):
            return self.cameras.copy() if mac == None else self.cameras.get(mac)
        elif pull_on_fail:
            self.pullCameras()
            return self.getCameras(mac,False)
        else:
            raise APIQuery.APIException("Camera pull supressed or failed") 

    def get_camera_observations(self)->set:
        "Returns a set of Person objects per the number of persons detected by MVSense"
        observations = set()

        for cam in self.getCameras().values():
            if cam.MVdata == None:
                continue

            #Get data from the 0th zone, the whole frame. Int not strictly necessary
            observation_count = int(cam.MVdata["0"])
            for x in range(observation_count):
                placable = Person( cam.floorPlanId )
                if cam.has_FOV():
                    placable.set_mask_override( cam.get_FOV() )
                observations.add(placable)

        return observations

    
    def get_SAPI_type(SAPI_packet:dict):
        "Extract the SAPI defined packet type from the dict structure"
        return SAPI_packet.get("type")

    def extract_SAPI_observations( self, scanning_data:dict ) -> dict:
        "Given the JSON-parsed content of a SAPI packet, retreive latest observations, indexed by mac address"
        # TODO: Check packet for useful AP position data from BT

        packet_malformed = APIQuery.APIException("Data extraction got scanning data with bad form: \"{}\"".format(str(scanning_data)))

        try:
            sapi_type = APIQuery.get_SAPI_type(scanning_data)
            packetdata = scanning_data["data"]
        except (KeyError,TypeError,AttributeError):
            raise packet_malformed

        try:
            observations = packetdata["observations"]
        except KeyError:
            return dict()
        except TypeError:
            raise packet_malformed
        
        founds = {}
        
        for client in observations:
            nearest_ap = self.getAP(client['latestRecord']['nearestApMac'])
            mac = client['clientMac']
            locations = client['locations']

            try:
                for latest_location in locations[::-1]:
                    # Location fix
                    # We only want the most live data entry
                    # And we want one without NaNs bc theyre not much use
                    lat = latest_location['lat']
                    lng = latest_location['lng']
                    var = latest_location['variance']
                    if sapi_type == "WiFi":
                        x = latest_location['x']
                        y = latest_location['y']
                        fpid = latest_location['floorPlanId']
                    elif sapi_type == "Bluetooth":
                        x = latest_location['floorPlan']['x']
                        y = latest_location['floorPlan']['y']
                        fpid = latest_location['floorPlan']['id']
                    else:#pragma: no cover #pragma: no branch
                        #Murphy's law
                        print("Warning: Unknown SAPI type: " + str(sapi_type))
                        return founds

                    if "NaN" not in [ lat, lng, var, x, y ]:
                        founds[mac] = Client( mac, nearest_ap.mac, fpid, lat, lng, x, y, var )
                        break
                    #else:
                        #print("NaN in [",lat,lng,var,x,y,"]")
                else:
                    raise ValueError
            except (TypeError,ValueError):
                # No location fix
                founds[mac] = Client(
                    mac,                    # MAC
                    nearest_ap.mac,         # Nearest AP MAC
                    nearest_ap.floorPlanId, # Floorplan ID
                )

        return founds
