import numpy as np, json, sys
m=json.load(open('tuples.json'))
raw=np.fromfile(sys.argv[1],dtype=np.float32); off=0; d={}
for i,t in enumerate(m['base']):
    n=9**len(t); d['t%d'%i]=raw[off:off+n]; off+=n
assert off==len(raw)
if len(sys.argv)>3: m['reward']={'mode':sys.argv[3],'bonus':float(sys.argv[4]) if len(sys.argv)>4 else 0.002}
d['meta']=np.array(json.dumps(m))
np.savez_compressed(sys.argv[2],**d)
