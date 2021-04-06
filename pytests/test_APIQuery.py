from PIL import Image
import pytest
import numpy as np
import os
import json
import random

# import objects from lib directory 
import os, sys
parentddir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir))
sys.path.append(parentddir)

from lib.APIQuery import APIQuery, FloorPlan, Camera

API_KEY = "MERAKI_DASHBOARD_API_KEY"
NETWORK_ID = "L_631066897785298299"
NETWORK_NAME = "CS09N"
FLOORPLANS = { "g_631066897785293932":"Gs Gaff", "g_631066897785293913":"Ms gaff" }
FPIDS = list(FLOORPLANS.keys())
ARB_FPID = FPIDS[0]

APS = { "2c:3f:0b:b0:17:a3", "2c:3f:0b:b0:1e:ab", "2c:3f:0b:b0:1e:b5", "2c:3f:0b:b0:57:09", "2c:3f:0b:b0:62:da", "2c:3f:0b:b0:cf:9a" }

CAMERAS = { "34:56:fe:a4:85:d7": "G Camera" }
CAM_MAC = "34:56:fe:a4:85:d7"

LOC_NW = {"lat":2,"lng":0}
LOC_NE = {"lat":2,"lng":2}
LOC_SW = {"lat":0,"lng":0}
LOC_CN = {"lat":1,"lng":1}

NOP_IMAGE = "https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png"
NOP_MD5 = "8f9327db2597fa57d2f42b4a6c5a9855"

UNDERSIZE_LEN = FloorPlan.MINIMAL_LENGTH - 0.1

CACHE_PATH = "./cache"

if os.path.isdir(CACHE_PATH):
    for root, dirs, files in os.walk(CACHE_PATH):
        for file in files:
            os.unlink(os.path.join(root, file))

@pytest.fixture
def established():
    return APIQuery(NETWORK_ID)

@pytest.fixture(scope="module")
def reuse():
    return APIQuery(NETWORK_ID)

def test_environment():
    assert os.getenv(API_KEY) != None

### Test APIQuery connection establishment
def test_connect_normal(established:APIQuery):
    assert established.dashboard.networks.getNetwork(NETWORK_ID)["name"] == NETWORK_NAME

@pytest.mark.parametrize("networkID, apikey",[ ("foobar",None), (NETWORK_ID,"foobar") ])
def test_connect_exceptional(networkID, apikey):
    with pytest.raises(APIQuery.APIException):
        APIQuery(networkID,apikey)

### Test FloorPlan instansiation
@pytest.mark.parametrize("tlc,trc,rot",[
    (LOC_SW,LOC_NW,90),
    (LOC_NW,LOC_SW,270)
])
def test_FloorPlan_init_extreme( tlc, trc, rot ):
    f = FloorPlan(
        FPIDS[0],
        "The office",
        LOC_CN,
        1.0,
        1.0,
        tlc,
        trc,
        NOP_IMAGE,
        NOP_MD5
    )
    assert f.rotation == rot

@pytest.mark.parametrize("height, width",[
    (UNDERSIZE_LEN,1.0),
    (1.0,UNDERSIZE_LEN),
    (UNDERSIZE_LEN,UNDERSIZE_LEN)
])
def test_FloorPlan_init_exceptional( height, width ):
    with pytest.raises(FloorPlan.FloorPlanException):
        FloorPlan(
            FPIDS[0],
            "The office",
            LOC_CN,
            height,
            width,
            LOC_NW,
            LOC_NE,
            NOP_IMAGE,
            NOP_MD5
        )

### Test FloorPlan pull method

def test_pullFloorPlans(reuse:APIQuery):
    established = reuse
    fps = established.pullFloorPlans()
    assert len(fps) >= 1
    assert set(FLOORPLANS.keys()) == set(fps.keys())

### Test FloorPlan get method

def test_getFloorPlan_normal(reuse:APIQuery):
    established = reuse
    established.pullFloorPlans()
    retr = established.getFloorPlan(ARB_FPID,False)
    assert retr.id == ARB_FPID
    assert retr.name == FLOORPLANS[ARB_FPID]
    assert retr.center != None and isinstance(retr.center,dict)
    assert retr.height != None and isinstance(retr.height, float)
    assert retr.width != None and isinstance(retr.width, float)
    assert 0 <= retr.rotation <= 360 and isinstance(retr.rotation, float)
    assert isinstance(retr.get_image(), Image.Image)
    
def test_getFloorPlan_extreme(established:APIQuery):
    assert established.getFloorPlan(ARB_FPID).name == FLOORPLANS[ARB_FPID]

def test_getFloorPlan_exceptional_1(established:APIQuery):
    with pytest.raises(APIQuery.APIException):
        established.getFloorPlan(ARB_FPID,False)

def test_getFloorPlan_exceptional_2(reuse:APIQuery):
    established=reuse
    established.pullFloorPlans()
    assert established.getFloorPlan("Nonsense") == None

### Test AP pull method

def test_pullAPs(reuse:APIQuery):
    established = reuse
    aps = established.pullAPs()
    for mac, ap in aps.items():
        assert mac == ap.mac
        assert len(ap.mac) == 17
        assert isinstance(ap.name,str)
        assert isinstance(ap.lat,float)
        assert isinstance(ap.lng,float)
        assert ap.floorPlanId in FPIDS
        
        rel_fp = established.getFloorPlan(ap.floorPlanId)
        assert ( 0 <= ap.x <= rel_fp.width )
        assert ( 0 <= ap.y <= rel_fp.height )

### Test AP get method

def test_getAP_normal(reuse:APIQuery):
    established = reuse
    aps = established.pullAPs()
    assert { established.getAP(mac) for mac in aps.keys() } == set(aps.values())

def test_getAP_extreme(established:APIQuery):
    mac = random.choice(list(APS))
    ap = established.getAP(mac)
    assert mac == ap.mac

def test_getAP_exceptional_1(established:APIQuery):
    with pytest.raises(APIQuery.APIException):
        established.getAP("11:11:11:11:11:11",False)

def test_getAP_exceptional_2(reuse:APIQuery):
    established=reuse
    established.pullAPs()
    assert established.getAP("Nonsense") == None

### Test SAPI observation extraction
def test_parse_SAPI_normal(reuse:APIQuery):
    established = reuse

    testfile_w = "test_w.json"
    testfile_b = "test_b.json"

    try:
        wfd = open(os.path.join("testing",testfile_w))
        bfd = open(os.path.join("testing",testfile_b))
    except FileNotFoundError:
        wfd = open(os.path.join("..","testing",testfile_w))
        bfd = open(os.path.join("..","testing",testfile_b))
    
    w_packet = json.load(wfd)
    b_packet = json.load(bfd)
    wfd.close()
    bfd.close()

    observations = established.extract_SAPI_observations(w_packet)
    established.extract_SAPI_observations(b_packet)

    macs = ("70:c9:4e:87:08:27","bc:85:56:83:51:d3")

    assert macs[0] in observations.keys()
    assert macs[1] in observations.keys()

    cl1 = observations[macs[0]]
    cl2 = observations[macs[1]]

    assert cl1.nearestApMac == "2c:3f:0b:b0:cf:9a"
    assert FLOORPLANS[cl1.floorPlanId] == "Gs Gaff"

    FLPR = 0.01

    assert cl2.nearestApMac == "2c:3f:0b:b0:1e:ab"
    assert FLOORPLANS[cl2.floorPlanId] == "Gs Gaff"
    assert abs(cl2.lat      - 55.87118525197333     ) < FLPR
    assert abs(cl2.lng      - (-4.276087000426031)  ) < FLPR
    assert abs(cl2.x        - 3.2866255769190014    ) < FLPR
    assert abs(cl2.y        - 6.707509473557684     ) < FLPR
    assert abs(cl2.variance - 1.635999970504618     ) < FLPR

@pytest.mark.parametrize("packet",[
    {"type":"WiFi","data":{}},
    {"type":"WiFi","data":{"observations":[]}}
])
def test_parse_SAPI_extreme(reuse:APIQuery, packet):
    assert reuse.extract_SAPI_observations(packet) == {}

@pytest.mark.parametrize("packet",[
    None,
    str(),
    list(),
    dict(),
    {"type":"WiFi"},
    {"type":"WiFi","data":None}
])
def test_parse_SAPI_exceptional(reuse:APIQuery, packet):
    with pytest.raises(APIQuery.APIException):
        reuse.extract_SAPI_observations(packet)


### Test Camera pull method

def test_pullCameras(established:APIQuery):
    cams = established.pullCameras()
    assert len(cams) >= 1

### Test Camera get method

def test_getCamera_normal_1(established:APIQuery):
    established.pullCameras()
    retr = established.getCameras(CAM_MAC,False)
    assert retr.mac == CAM_MAC

def test_getCamera_normal_2(established:APIQuery):
    established.pullCameras()
    retr = established.getCameras(None,False)
    assert retr[CAM_MAC].mac == CAM_MAC

def test_getCamera_extreme_1(established:APIQuery):
    retr = established.getCameras(CAM_MAC)
    assert retr.mac == CAM_MAC

def test_getCamera_extreme_2(established:APIQuery):
    retr = established.getCameras()
    assert retr[CAM_MAC].mac == CAM_MAC

def test_getCamera_exceptional(established:APIQuery):
    with pytest.raises(APIQuery.APIException):
        established.getCameras(CAM_MAC,False)

### Test MVSense pull
def test_updateMVsenseData(established:APIQuery):
    established.pullCameras()
    cam = established.getCameras(CAM_MAC)
    established.updateCameraMVSenseData(cam)
    assert( "0" in cam.MVdata.keys())


def test_updateMVsenseData_exceptional(established:APIQuery):
    test_cam = Camera("not_a_mac", "not_a_serial", 100, 100, established.getFloorPlan(ARB_FPID))
    with pytest.raises(APIQuery.APIException):
        established.updateCameraMVSenseData(test_cam)
