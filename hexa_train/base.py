import sys, random, time, hexa_engine as E
_orig = E.rand_piece
def rp(unlocked, rng):
    hi = E.spawn_hi(unlocked); lo = max(1, hi-2)
    n = rng.choices([1,2,3],[0.29,0.36,0.35])[0]
    if n==1: offs=[(0,0)]
    elif n==2: offs=E.rot([(0,0),(1,0)], rng.randrange(6))
    else: offs=E.rot(list(rng.choice(E.SH3)), rng.randrange(6))
    return [(o, rng.choices([lo,lo+1,hi],E.SPAWN_W)[0] if hi-lo==2 else rng.randint(lo,hi)) for o in offs]
E.rand_piece = rp
a,b = int(sys.argv[1]), int(sys.argv[2])
for s in range(a,b):
    t=time.time(); r=E.play3(1000+s, B1=24, B2=10, K=24)
    print(s, r, "%.0fs"%(time.time()-t), flush=True)
