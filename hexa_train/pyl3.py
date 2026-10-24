import sys, time, random, hexa_engine as E, hexa_nt as T
for s in range(int(sys.argv[1]), int(sys.argv[2])):
    rng=random.Random(5000+s); b=[0]*E.N; u=3
    cur,nxt=T.rand_piece(u,rng),T.rand_piece(u,rng); n=0; best=0; t0=time.time()
    while True:
        mv=T.best_move3(b,u,cur,nxt,seed=n)
        if mv is None: break
        k,cells,tt,_=mv
        b,made,_=E.apply(b,cells,tt,rng.randrange(6)); u=E.new_unlocked(u,made)
        for x in made: best=max(best,x[2])
        n+=1; cur,nxt=nxt,T.rand_piece(u,rng)
    print(s, n, best, "%.0fs"%(time.time()-t0), flush=True)
