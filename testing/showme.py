import pickle
import matplotlib.pyplot as plt
import numpy as np
import sys

filename = sys.argv[1]

print(f"Reading {filename}")

with open(filename,"rb") as fd:
    load = pickle.load(fd)

fid = 'g_631066897785293932'
gid = 'g_631066897785293913'

fig, (ax1, ax2) = plt.subplots(1, 2)
fig.suptitle("WIFI LAYER")
ax1.matshow(load[fid], cmap="inferno" )
ax2.matshow(load[gid], cmap="inferno")
plt.show()
