import struct, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

def load_stl(path):
    with open(path,"rb") as f:
        f.read(80); n=struct.unpack("<I",f.read(4))[0]
        data=np.frombuffer(f.read(n*50),dtype=np.uint8).reshape(n,50)
    floats=data[:,:48].copy().view("<f4").reshape(n,12)
    tris=floats[:,3:].reshape(n,3,3)
    return tris

def shade(tris, base):
    v=tris; n=np.cross(v[:,1]-v[:,0], v[:,2]-v[:,0])
    ln=np.linalg.norm(n,axis=1,keepdims=True); ln[ln==0]=1; n=n/ln
    light=np.array([0.3,0.4,0.85]); b=0.45+0.55*np.clip(n@light,0,1)
    return np.clip(np.array(base)[None,:]*b[:,None],0,1)

fig=plt.figure(figsize=(11,5)); ax=fig.add_subplot(111,projection="3d")
allpts=[]
for path,col,a in [("front.stl",(0.62,0.64,0.68),1.0),
                   ("lens_right.stl",(0.4,0.6,0.95),0.55),
                   ("lens_left.stl",(0.4,0.6,0.95),0.55)]:
    t=load_stl(path); allpts.append(t.reshape(-1,3))
    pc=Poly3DCollection(t,facecolors=shade(t,col),edgecolors="none",alpha=a)
    ax.add_collection3d(pc)
P=np.concatenate(allpts); c=(P.min(0)+P.max(0))/2; r=(P.max(0)-P.min(0)).max()/2
ax.set_xlim(c[0]-r,c[0]+r); ax.set_ylim(c[1]-r,c[1]+r); ax.set_zlim(c[2]-r,c[2]+r)
ax.set_box_aspect((1,1,1)); ax.view_init(elev=22,azim=-72); ax.set_axis_off()
plt.tight_layout(); plt.savefig("iso.png",dpi=130,bbox_inches="tight"); print("wrote iso.png")
