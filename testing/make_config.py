import pickle
from lib.Model import Model

conf = {
    Model.STORE_SELECTED    :"L_631066897785298299", 
    "L_631066897785298299"  :{
            Model.STORE_SECRET      :"itsasecret",
            Model.STORE_TOKEN       :"4b6733d724fdf245f05c2a644a4e31f0091a4292",
            Model.STORE_LAYERS      : Model.LAYERS_ALL,
            Model.STORE_WEBHOOK     : ["https://example.org/thisexample"],
            Model.STORE_PASSWORD    : "belgium"
    }
}

with open("model.conf","wb")  as fd:
    pickle.dump(conf,fd)