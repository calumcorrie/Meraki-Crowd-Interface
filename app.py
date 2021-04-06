import os
import sys
import io
import time
from flask import Flask, request, render_template, send_file, redirect, abort, Response, session
from flask.helpers import url_for
import numpy as np
from PIL import Image
import random
import string

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from lib.Model import Model, Floor, sha256
from lib.APIQuery import Camera, FloorPlan

POST = "POST"
GET = "GET"
SESSION_AUTH = "auth"
LOGIN_ATTEMPTS_KEY = "login_attempts"
LOGIN_ATTEMPTS = 4
COOLDOWN_S = 120
ANTI_BF_S = 0.2

class FPWrapper:
    def __init__(self,FPID:str):
        self.fp = mod.plans[FPID]
        assert isinstance(self.fp,Floor)
        self._id = FPID
        self.name = self.fp.floorplan.name
        self.img = url_for("static",filename="/".join(FloorPlan.IMG_ROOT[1:]+[self.fp.floorplan.filename]))
        self.im_h = self.fp.floorplan.im_height
        self.im_w = self.fp.floorplan.im_width
        self.dims = self.fp.overlay_dimensions
        self.ar = self.fp.overlay_dimensions[0] / self.fp.overlay_dimensions[1]
        # Calculate the size of the floorplan image compared to the overlay size as a %
        self.plandims = (
            100 * self.fp.floorplan_dimensions[0] / (self.fp.floorplan_dimensions[0] + self.fp.margin_m[0]),
            100 * self.fp.floorplan_dimensions[1] / (self.fp.floorplan_dimensions[1] + self.fp.margin_m[1])
        )
        self.masked = self.fp.mask_enabled

class FPMenuOpt(FPWrapper):
    def __init__(self, FPID: str):
        super().__init__(FPID)
        self.hm_url = url_for("display",floorPlanId=FPID)

class FOVSelector:
    COUNTER = 0
    def __init__(self,camera_mac:str, debug=None):
        if debug:
            cam = Camera("my:fa:tm:ac:ad:dr","FOOBAR",0,0,mod.plans[debug].floorplan)
            sh = (mod.plans[debug].overlay_dimensions)
            cam.set_FOV(sh,{(n,n) for n in range(min(sh))})
            del sh
        else:
            cam = mod.query_obj.getCameras(camera_mac)
        assert isinstance(cam,Camera)
        self.mac=cam.mac
        self.serial = cam.serial
        self.fp = FPWrapper(cam.floorPlanId)
        self.has_FOV = cam.has_FOV()
        self.FOV = cam.get_FOV() if cam.has_FOV() else np.zeros((self.fp.dims),dtype=np.bool_)

        self._id = FOVSelector.COUNTER
        FOVSelector.COUNTER += 1

class BDInput(FPWrapper):
    def __init__(self, FPID: str):
        super().__init__(FPID)
        self.coords = self.fp.bm_boxes

mod = Model()

imagestore = dict()
prevstore = dict()

cooldown = 0

print("Model has reset")

app = Flask(__name__)
#Note this is how the CRSF tokens and sessions are generated, should be random in production
app.secret_key = b'B\xc5\x92\xac\x02\x07\xbew\xb5U\x19\x13\x8c\xfc\xa7\xb37E\xf8\x87\xb3\xe3!\xf2'

def get_Floorplan_Menu() -> list:
    return [ FPMenuOpt(fpid) for fpid in mod.plans.keys() ]

def get_BD_objs() -> list:
    return 

def send_image(img:Image.Image,transient:bool=False)->Response:
    bytestream = io.BytesIO()
    img.save(bytestream,'PNG')
    bytestream.seek(0)
    resp = send_file(bytestream,mimetype="image/png")
    if transient:
        resp.headers["Cache-Control"] = "no-cache, must-revalidate, no-store"
        #Also suggested: Cache-Control: max-age=0
    return resp

def authenticate() -> None:
    session[SESSION_AUTH] = True

def deauthenticate() -> None:
    session[SESSION_AUTH] = False

def isauth() -> bool:
    return session.get(SESSION_AUTH) == True

def require_auth() -> None:
    if not isauth():
        abort(403)

def serialize_form(form_dict) -> dict:
    conf_dict = dict()
    n_id = form_dict.get("network")
    conf_dict[Model.STORE_SELECTED] = n_id
    conf_dict[Model.STORE_SECRET] = form_dict.get("sapisecret")
    conf_dict[Model.STORE_TOKEN] = form_dict.get("validator_token")
    conf_dict[Model.STORE_WEBHOOK] = form_dict.getlist("webhook_list")
    conf_dict[Model.STORE_WHTHRESHOLD] = float(form_dict.get("webhook_thresh"))
    conf_dict[Model.STORE_PASSWORD] = sha256(form_dict.get("password"))

    conf_dict[Model.STORE_FOVCOORDS] = dict()
    for cam in mod.query_obj.cameras.values():
        mac = cam.mac
        raw_fp_coords = form_dict.getlist("input_FOV_"+mac)
        conf_dict[Model.STORE_FOVCOORDS][mac] = { (int(x[1]), int(x[0])) for x in [ s.split("_") for s in raw_fp_coords ] }
    
    conf_dict[Model.STORE_BMBOXES] = dict()

    for fpid in mod.plans.keys():
        conf_dict[Model.STORE_BMBOXES][fpid] = []
        boxes = form_dict.get("bm_box_"+fpid)
        if boxes=="":
            continue
        boxes = boxes.split("-")
        boxparams = [ tuple( int(b) for b in boxes[a:a+4]) for a in range(0,len(boxes),4) ] 

        conf_dict[Model.STORE_BMBOXES][fpid] = boxparams
    
    conf_dict[Model.STORE_BDENABLED] = {fpid:form_dict.get("enable_"+fpid,"off")=="on" for fpid in mod.plans.keys()}

    return n_id, conf_dict

@app.route("/")
def index():
    params = { 
        "title" : "Home",
        "auth" : isauth(),
        "options" : get_Floorplan_Menu()
    }
    return render_template("index.html.jinja", context=params)
    
@app.route("/show/<floorPlanId>")
def display(floorPlanId):
    if floorPlanId not in mod.plans.keys():
        return redirect(url_for("index"))

    imgloc = url_for("render_overlay", imgFPID=floorPlanId, noop=0 )
    name = mod.getFloorplanSummary().get(floorPlanId)

    params = { 
        "title" : name,
        "auth" : isauth(),
        "portal_src" : imgloc
    }
    return render_template("heatmap.html.jinja", context=params)

@app.route("/config", methods=[POST,GET])
def configuration():    
    global fpids
    global cams

    if request.method == POST:

        require_auth()
        # Clear ajax image caches, now not needed
        imagestore.clear()
        prevstore.clear()

        # Parse the form
        netid, conf = serialize_form(request.form)
        # Update model accordingly
        mod.update_model_config(netid, conf)
        # Save changes
        mod.write_config_data()
    else:
        if not isauth():
            return redirect(url_for("challenge"))

    params=dict()
    params["title"]="Configuration"
    params["auth"] = isauth()
    params["secret"] = mod.secret
    params["token"] = mod.validator_token
    params["password"] = mod.password
    params["cameraFOVs"] = [ FOVSelector(cam.mac) for cam in mod.query_obj.cameras.values()]
    params["bounds"] = [ BDInput(fpid) for fpid in mod.plans.keys() ]
    params["networks"] = mod.query_obj.network_list
    params["net_selected"] = mod.query_obj.network_id
    params["webhooks"] = mod.webhook_addresses
    params["wh_threshold"] = mod.webhook_threshold
    return render_template("config.html.jinja",context=params)


@app.route("/authentication", methods=[POST,GET])
def challenge():
    global cooldown
    locked = "Locked out. Try again later"
    time_blocked = time.time() < cooldown
    errstr = locked if time_blocked else ""

    if request.method == POST:
        password = sha256(request.form.get("pass"))
        left = session.get(LOGIN_ATTEMPTS_KEY)
        # Bruteforce protection
        time.sleep(ANTI_BF_S)
        if password == mod.password and not (left==0) and not time_blocked:
            authenticate()
            session.pop(LOGIN_ATTEMPTS_KEY,None)
            return redirect(url_for("configuration"))
        elif time_blocked:
            # Locked out for cooldown seconds
            pass
        elif left == 1:
            # Reached 0 tries, set cooldown
            cooldown = time.time() + COOLDOWN_S
            session[LOGIN_ATTEMPTS_KEY] = LOGIN_ATTEMPTS
            errstr = locked
        else:
            if left == None:
                # As in first attempt + fail
                session[LOGIN_ATTEMPTS_KEY] = LOGIN_ATTEMPTS
            session[LOGIN_ATTEMPTS_KEY] -= 1
            errstr = "Authentication failed. {} tries left".format(session.get(LOGIN_ATTEMPTS_KEY))

    params = dict()
    params["title"] = "Admin Login"
    params["error"] = errstr
    return render_template("authenticate.html.jinja", context=params)

@app.route("/signout")
def signout():
    deauthenticate()
    return redirect(url_for("index"))

@app.route('/scanningapi/', methods=[POST,GET])
def sapi():
    if request.method == GET:
        return mod.validator_token
    else:
        gotjson = request.get_json(force=True)
        
        try:
            mod.provide_scanning(gotjson)
        except Model.BadRequest:
            return "NOT OK"
        else:
            # Currently using webhook for updating, may change this
            mod.update()

            #If we don't return something, the WSGI gods will smite us
            return "OK"

@app.route("/render/<imgFPID>/<noop>")
def render_overlay(imgFPID,noop):
    if imgFPID not in mod.plans.keys():
        abort(400)

    img = mod.render_delta(imgFPID)
    return send_image(img,True)

@app.route("/ajax/<key>")
def getajax(key):
    "Get an image that was stored in imagestore"
    got = imagestore.get(key)
    if got == None:
        abort(403)
    else:
        return send_image(got)

@app.route("/maskprev/<imgFPID>")
def prime_bd(imgFPID):
    """
    Create a boundary detector preview, or direct to cached version if previously computed
    Return a URL to get image from imagestore to set img.src to
    Takes ~1.3 seconds, so use ajax
    """
    if imgFPID not in mod.plans.keys():
        abort(400)

    boxes = request.args.get("boxes",None)
    params = (imgFPID, boxes)
    if params not in prevstore.keys():
        tag = "".join([random.choice(string.ascii_letters) for _ in range(20)])
        if boxes != None:
            boxes = boxes.split("-")
            if len(boxes) % 4 != 0:
                abort(400)
            else:
                boxparams = [ ( int(b) for b in boxes[a:a+4]) for a in range(0,len(boxes),4)  ]
        else:
            boxparams = boxes
        
        prevstore[params] = tag
        imagestore[tag] = mod.plans[imgFPID].calc_bounds_mask(boxparams)
    else:
        tag = prevstore[params]

    return url_for("getajax",key=tag)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
