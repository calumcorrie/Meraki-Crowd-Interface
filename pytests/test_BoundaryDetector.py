import os
import sys
import numpy as np

# import BoundaryDetector from lib directory 
parentddir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir))
sys.path.append(parentddir)

from lib.BoundaryDetector import BoundaryDetector

# generate expected map
expected_sym_map = np.ones((100,100),dtype=np.bool_)
expected_sym_map[ 11:89 , 11:89 ] = 0
expected_sym_map = ( expected_sym_map == 1)


def test_getBoundaryMask():

    b = BoundaryDetector(os.path.join("testing","simple_fp.png"))
    b.run()
    x = b.getBoundaryMask()
    assert ( np.array_equal( x, expected_sym_map ) )


