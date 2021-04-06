import pytest
import os
import sys
import json
import numpy as np
import pickle

parentddir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir))
sys.path.append(parentddir)

from lib.Model import Model, SECRET_K
from lib.APIQuery import APIQuery

NETWORK_ID = "L_631066897785298299"
FLOORPLANS = { "g_631066897785293932":"Gs Gaff", "g_631066897785293913":"Ms gaff" }
FPIDS = [ "g_631066897785293932", "g_631066897785293913" ]
GS_CAMERA = "34:56:fe:a4:85:d7"
SECRET_V = "itsasecret"

def load_json(fn):
    with open(os.path.join("testing",fn)) as fd:
        data = json.load(fd)
    return data

TEST_JSON_FILE_WIFI = "test_w.json"
TEST_JSON_WIFI = load_json(TEST_JSON_FILE_WIFI)

TEST_JSON_FILE_BT = "test_b.json"
TEST_JSON_BT = load_json(TEST_JSON_FILE_BT)

HIST_PATH = "./historical_data"
if os.path.isdir(HIST_PATH):
    for root, dirs, files in os.walk(HIST_PATH):
        for file in files:
            os.unlink(os.path.join(root, file))

def make_config():
    conf = { Model.STORE_SELECTED: NETWORK_ID, 
            NETWORK_ID: {
                Model.STORE_SECRET      :"itsasecret",
                Model.STORE_TOKEN       :"4b6733d724fdf245f05c2a644a4e31f0091a4292",
                Model.STORE_LAYERS      : Model.LAYERS_ALL,
                Model.STORE_WEBHOOK     : ["https://example.org/thisexample"],
                Model.STORE_PASSWORD    : "belgium"
            }
    }
    with open(Model.CONFIG_PATH, "wb") as fd:
        pickle.dump(conf,fd)
    return

@pytest.fixture
def established():
    make_config()
    return Model()

@pytest.fixture(scope="module")
def reuse():
    make_config()
    return Model()

def test_environment():
    assert os.getenv("MERAKI_DASHBOARD_API_KEY") != None

def test_instantiation_normal( reuse:Model ):
    assert set(reuse.plans.keys()) == set(FPIDS)
    assert set(reuse.data_layers.keys()) == Model.LAYERS_ALL

# @pytest.mark.parametrize("network_id, layers", [
#     ("Nonsense", Model.LAYERS_ALL),
#     (NETWORK_ID, {-1}),
#     ("Nonsense", {-1})
# ])
# def test_instantiation_exceptional( network_id:str, layers:set ):
#     with pytest.raises( (APIQuery.APIException, Model.ModelException) ):
#         Model( network_id, layers )

@pytest.mark.parametrize("fpid", FPIDS)
def test_set_bounds_mask_normal(reuse:Model,fpid):
    reuse.setBoundsMask(fpid,on=True)

SFID = FPIDS[0]
@pytest.mark.parametrize("fpid, bsps, wthr, err", [
    ("Nonsense",None,None,Model.ModelException),
    (SFID,None,dict(),TypeError),
    (SFID,5,None,TypeError),
    (SFID,((1,1,2,2),(1,1,2)),None,ValueError)
])
def test_set_bounds_mask_exceptional(reuse:Model, fpid, bsps, wthr, err):
    with pytest.raises(err):
        reuse.setBoundsMask(fpid, True, bsps, wthr)

def test_floorplanid_dict(reuse:Model):
    fids = reuse.getFloorplanSummary()
    assert set(fids.keys()) == set(FPIDS)
    assert False not in [ fids[k] == v for k, v in FLOORPLANS.items() ]

def test_floorplan_by_name_normal(reuse:Model):
    tc = "Ms gaff"
    assert FLOORPLANS[reuse.findFloorplanByName(tc)] == tc

def test_floorplan_by_name_extreme(reuse:Model):
    tc = "Nonsense"
    assert reuse.findFloorplanByName(tc) == None

@pytest.mark.parametrize("packet",[
    int(),
    set(),
    {"nothing":"useful"},
    {"data":{}},
    {"data":{"networkId":"nonsense"}},
    {"data":{"networkId":NETWORK_ID}},
    {SECRET_K:"the wrong one","data":{"networkId":NETWORK_ID}},
    {SECRET_K:SECRET_V,"data":{"networkId":"wrong"}},
])
def test_SAPI_validation_exceptional(reuse:Model,packet):
    with pytest.raises((TypeError,Model.BadRequest)):
        #Dont EVER do this normally, its called name mangling
        reuse._Model__validate_scanning(packet)

def test_integration_normal(reuse:Model):
    established = reuse

    gid = established.findFloorplanByName("Gs Gaff")
    
    established.provide_scanning(TEST_JSON_WIFI)
    l1 = established.poll_layer(Model.LAYER_SNAP_WIFI,exposure=1)[gid]

    established.provide_scanning(TEST_JSON_BT)
    l2 = established.poll_layer(Model.LAYER_SNAP_BT,exposure=1)[gid]

    #import matplotlib.pyplot as plt
    #fig, (ax1, ax2) = plt.subplots(1, 2)
    #ax1.matshow(l1, cmap="inferno" )
    #ax2.matshow(l2, cmap="inferno")
    #plt.show()

    print(l1)
    print(l1.sum())
    print(l2)
    print(l2.sum())
    assert np.allclose( l1.sum(), 2 )
    assert np.allclose( l2.sum(), 2 )

def test_integration_exceptional(established:Model):
    data = {42:"And theres this terrible pain in all the diodes down my left side"} 
    gid = established.findFloorplanByName("Gs Gaff")
    established.setBoundsMask(gid,on=True)
    with pytest.raises( (Model.ModelException, Model.BadRequest, APIQuery.APIException) ):
        established.provide_scanning(data)

@pytest.fixture
def foved(reuse:Model):
    reuse.setFOVs(GS_CAMERA,{(0,0),(1,1),(2,2),(3,3)})
    return reuse

def test_FOV_setup_normal(foved:Model):
    assert foved.query_obj.cameras[GS_CAMERA].has_FOV() == True
    assert foved.query_obj.cameras[GS_CAMERA].get_FOV().sum() == 4

@pytest.mark.parametrize( "mac,coords", [
    (GS_CAMERA, str()),
    (GS_CAMERA, set()),
    (GS_CAMERA, list()),
    (GS_CAMERA, dict())
] )
def test_FOV_setup_extreme(reuse:Model, mac:str, coords:set):
    #We shouldnt get these, but we can deal with them as calls to unset the mask
    reuse.setFOVs(mac,coords)
    assert reuse.query_obj.cameras[GS_CAMERA].has_FOV() == False

@pytest.mark.parametrize( "mac,coords", [
    ("Nonsense", { (0,0) }),
    ("Nonsense", {}),
    ("Nonsense", int()),
    ("Nonsense", str()),
    (GS_CAMERA, int()),
    (GS_CAMERA, {(0,0),(0,1,1)}),
    (GS_CAMERA, {(10000,10000)})
] )
def test_FOV_setup_exceptional(reuse:Model, mac:str, coords:set ):
    with pytest.raises((Model.ModelException,ValueError,TypeError,IndexError)):
        reuse.setFOVs(mac,coords)

def test_MVData_pull(foved:Model):
    # Simulate model.pull_mvsense_data()
    foved.query_obj.updateCameraMVSenseData()
    #Inject 2 persons per sqm FOV
    foved.query_obj.getCameras(GS_CAMERA).MVdata["0"] = 8
    observations = foved._Model__generate_person_obs()
    foved.data_layers[Model.LAYER_MVSENSE].set_observations(observations)
    got = foved.poll_layer(Model.LAYER_MVSENSE,exposure=1)
    print(got[FPIDS[0]])
    assert (got[FPIDS[0]][0:4,0:4] == 2 * np.eye(4)).all()
