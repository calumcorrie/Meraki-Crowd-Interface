import numpy as np
from PIL import Image
import os

class BoundaryDetector:
    "BoundaryDetector takes a PIL Image or filepath and returns a pixel mask of the unbounded outer region"
    
    OUTDOOR = 0
    INDOOR = 1
    WALL = 2
    CONSIDERED = 3
    
    AC_COMPASS = np.array([(-1,0),(-1,-1),(0,-1),(1,-1),(1,0),(1,1),(0,1),(-1,1)])
    
    def __init__(self,img,threshold:float=0.97):
        "Loads an image from filepath, PIL Image file or np array, parses walls according to (threshold * brightest pixel)"

        if isinstance(img,np.ndarray):
            if len(img.shape)<2:
                raise ValueError("Numpy array passed as image parameter not of sufficient shape: {}".format(str(img.shape)))
            raw_img = img
        else:
            if isinstance(img,str):
                img = Image.open(img)
            elif isinstance(img,Image.Image):
                pass
            else:
                raise TypeError
            
            raw_img = np.asarray(img,dtype="int32")
            img.close()

        orig_shape = raw_img.shape
        try:
            #Normalise the raw data by brightness
            raw_img = np.sum( raw_img, axis=2 )
        except np.AxisError:
            #Or not if b&w
            _range = 255
        else:
            _range = 255 * orig_shape[2]


        #Make the initial map all indoor
        self.sym_map = np.full((raw_img.shape[0],raw_img.shape[1]),BoundaryDetector.INDOOR,dtype="int32")

        self.sym_map[( raw_img < (threshold * _range) )] = BoundaryDetector.WALL

    def __get_scan_directions(curr:tuple) -> np.array:
        #Get the sequence of directions to check for walking
        for rolls, direction in enumerate(BoundaryDetector.AC_COMPASS):
            #Find reverse direction
            if(tuple(direction)==(-curr[0],-curr[1])):
                break
        else:
            raise KeyError(f"No such direction {curr} in compass")
        
        #Roll by one extra to find scanning directions
        return np.roll(BoundaryDetector.AC_COMPASS,-(rolls+1),axis=0)

    def __find_wall_from_root(self) -> tuple:
        #Seeks a wall to walk along by searching from the image root by exhaustive expanding squares
        sx, sy, dx, dy = 0, 0, 0, 0
        #For scan 'radius' r
        for r in range(min(self.sym_map.shape)):
            #For cell along square edges r
            for q in range(r):
                #Check southmost of pair
                if self.sym_map[r,q] == BoundaryDetector.WALL:
                    sx, sy= r, q
                    dx, dy = 1, 0
                #Check eastmost of pair
                elif self.sym_map[q,r] == BoundaryDetector.WALL:
                    sx, sy = q, r
                    dx, dy = 0, -1
                else:
                    continue

                #Give wall cell and probable walk direction
                return sx,sy,dx,dy

    def __run_line(self,x:int,y:int,dx:int,dy:int) -> None:
        #Draw a line of outsideness in direction dx,dy (ortho or 45deg) til a wall, considered or map bound is hit
        xx = x + dx
        yy = y + dy

        #Arrays of x and y coords for line points 
        xl,yl = np.array([]), np.array([])

        if dx<0:
            #x from xx to 0 edge
            xl = np.arange(xx,-1,dx)
        elif dx>0:
            #x from xx to max edge
            xl = np.arange(xx,self.sym_map.shape[0],dx)
        
        if dy<0:
            yl = np.arange(yy,-1,dy)
        elif dy>0:
            yl = np.arange(yy,self.sym_map.shape[1],dy)

        if dx==0:
            #Horisontal line
            xl=np.full_like(yl,x)
        elif dy==0:
            #Vertical
            yl=np.full_like(xl,y)
        else:
            #Otherwise, trim out of bounds xy pairs
            shortest = min( len(xl), len(yl) )
            xl = xl[:shortest]
            yl = yl[:shortest]

        #Cumprod of bools gives "first n trues" - dont draw outdoorness over walls or considereds
        cprod = np.cumprod( np.logical_or(
            self.sym_map[xl,yl] == BoundaryDetector.OUTDOOR,
            self.sym_map[xl,yl] == BoundaryDetector.INDOOR
        ))==1
        
        #Write the line
        self.sym_map[xl[cprod],yl[cprod]] = BoundaryDetector.OUTDOOR
    
    def generate_graphic(self,sample:int=1):
        """
        Generate a graphical representation of the internal symbol map
        Set sample to n>1 to sample every nth cell on each axis 
        """
        smallmap = self.sym_map[::sample,::sample]

        #Craft a fresh rgb image
        sm = np.empty((smallmap.shape[0],smallmap.shape[1],3),dtype="uint8")

        #Populate with sym_map data
        sm[smallmap==BoundaryDetector.OUTDOOR] =    [   0, 255,   0 ]
        sm[smallmap==BoundaryDetector.WALL] =       [   0,   0,   0 ]
        sm[smallmap==BoundaryDetector.CONSIDERED] = [ 255,   0,   0 ]
        sm[smallmap==BoundaryDetector.INDOOR] =     [ 192, 192, 192 ]

        return Image.fromarray(sm)

    def add_blindspot(self,x1,y1,x2,y2) -> None:
        "Add a zone on the floorplan to ignore wall boundaries. Add these around black non-wall entitites or other anomalies on the floor plan to let the algorithm function correctly. Accepts homogeneous parameters in pixel coords or relative floats"
        shape = self.sym_map.shape
        if 0<=x1<=1 and 0<=x2<=1 and 0<=y1<=1 and 0<=y2<=1:
            x1 = shape[0] * x1
            x2 = shape[0] * x2
            y1 = shape[1] * y1
            y2 = shape[1] * y2
        elif not ( 0<=x1<=shape[0] and 0<=x2<=shape[0] and 0<=y1<=shape[1] and 0<=y2<=shape[1] ):
            raise IndexError("Cannot add blindspot. Bounds ({:.2f},{:.2f})->({:.2f},{:.2f}) not in range [0,1] or (0,0)->({},{})".format(x1,y1,x2,y2,shape[0],shape[1]))

        self.sym_map[int(x1):int(x2),int(y1):int(y2)] = BoundaryDetector.OUTDOOR

    def showme(self) -> None: #pragme: no cover
        "For debugging only. Give visual representation of internal map"
        self.generate_graphic(1).show()
        
    def dump_symb(self) -> None: #prama: no cover
        "For debugging only. Dump raw map data into a space delimited file"
        np.savetxt("symbdump.rgb", self.sym_map, fmt="%1d", delimiter="") 
    
    def run(self) -> None:
        "Run the algorithm and return the mask, 1s for walls and inside, 0s for outside"

        #Get a wall cell, dxy the current direction to walk
        x,y,*dxy = self.__find_wall_from_root()

        #Until we wrap round
        while self.sym_map[x,y]!=BoundaryDetector.CONSIDERED:

            self.sym_map[x,y] = BoundaryDetector.CONSIDERED

            compass = BoundaryDetector.__get_scan_directions(dxy)

            for dxy in compass:
                if self.sym_map[x+dxy[0],y+dxy[1]] in [BoundaryDetector.WALL,BoundaryDetector.CONSIDERED]:
                    #We will step this way to stay in the wall
                    if not 0 in dxy:
                        #We've found a diagonal step, which needs an extra line drawn
                        supp_line_root = (0,dxy[1]) if dxy[0]==dxy[1] else (dxy[0],0)
                        #It should be in the direction of y,-x (90 cw from dxy)
                        self.__run_line(x+supp_line_root[0], y+supp_line_root[1], dxy[1], -dxy[0])
                    break
                else:
                    #Otherwise, mark a line to the map bounds of outsideness
                    self.__run_line(x,y,*dxy)

            #Make step
            x+=dxy[0]
            y+=dxy[1]
    
    def getBoundaryMask(self) -> np.array:
        "Get a boolean pixel mask of image with 1s in the bounding region"
        return ((self.sym_map==BoundaryDetector.OUTDOOR) | (self.sym_map==BoundaryDetector.CONSIDERED)).astype(np.bool_)



if __name__ == "__main__": #pragme: no cover
    b = BoundaryDetector(os.path.join("testing","testfloor.bmp"))
    b.add_blindspot(3068,1410,3349,1750)
    b.run()
    b.showme()
    input("Press [Enter] to continue...")
