#define MAXT 10
#define NV 9
static float *LUT[MAXTUP];
static long LSIZE[MAXTUP];
static int NINST = 13 * 4;
static int AXI[16][16]; // (q+4, r+6)

typedef struct { uint64_t s; } rng_t;
static inline uint64_t rnext(rng_t *r) { uint64_t x = r->s; x ^= x << 13; x ^= x >> 7; x ^= x << 17; return r->s = x; }
static inline double runi(rng_t *r) { return (rnext(r) >> 11) * (1.0 / 9007199254740992.0); }
static inline int rint_(rng_t *r, int n) { return (int)(runi(r) * n); }

static double W_N[3] = {0.29, 0.36, 0.35};   // 1/2/3칸 (실전 75조각)
static double W_T[3] = {0.58, 0.22, 0.20};   // lo, lo+1, hi

typedef struct { int n; int off[3][2]; int t[3]; int dot; } piece_t;

static inline int spawn_hi(int u) { int h = u - 1; if (h > 6) h = 6; if (h < 2) h = 2; return h; }
static inline int lo_of(int u) { int l = spawn_hi(u) - 2; return l < 1 ? 1 : l; }

static void rot1(int *q, int *r, int k) {
    int x = *q, z = *r, y = -x - z;
    for (int i = 0; i < k % 6; i++) { int nx = -z, ny = -x, nz = -y; x = nx; y = ny; z = nz; }
    *q = x; *r = z;
}

static void gen_piece(int u, rng_t *R, piece_t *p) {
    int hi = spawn_hi(u), lo = lo_of(u);
    double x = runi(R);
    int n = x < W_N[0] ? 1 : (x < W_N[0] + W_N[1] ? 2 : 3);
    p->n = n;
    if (n == 1) { p->off[0][0] = 0; p->off[0][1] = 0; }
    else if (n == 2) { int k = rint_(R, 6); p->off[0][0] = 0; p->off[0][1] = 0; int q = 1, r = 0; rot1(&q, &r, k); p->off[1][0] = q; p->off[1][1] = r; }
    else { int s = rint_(R, NSH3); int k = rint_(R, 6); for (int j = 0; j < 3; j++) { int q = SH3[s][j][0], r = SH3[s][j][1]; rot1(&q, &r, k); p->off[j][0] = q; p->off[j][1] = r; } }
    for (int j = 0; j < n; j++) {
        if (hi - lo == 2) { double y = runi(R); p->t[j] = y < W_T[0] ? lo : (y < W_T[0] + W_T[1] ? lo + 1 : hi); }
        else p->t[j] = lo + rint_(R, hi - lo + 1);
    }
    // patch283/patch299: 10/26 업데이트 반영 - 점(●) 위치 결정
    if (n == 1) {
        p->dot = 0;
    } else if (n == 2) {
        p->dot = rint_(R, 2);
    } else {
        if (p->t[0] == p->t[1]) p->dot = rint_(R, 2) ? 0 : 1;
        else if (p->t[1] == p->t[2]) p->dot = rint_(R, 2) ? 1 : 2;
        else if (p->t[0] == p->t[2]) p->dot = rint_(R, 2) ? 0 : 2;
        else p->dot = rint_(R, 3);
    }
}

// 놓을 수 있는 수 목록: cells[m][3]
typedef struct { int n; int c[3]; } mv_t;
static int gen_moves_k(const int8_t *b, const piece_t *p, mv_t *out, int k0) {
    int cnt = 0;
    int same = 1; for (int j = 1; j < p->n; j++) if (p->t[j] != p->t[0]) same = 0;
    int kmax = (p->n == 1 || k0) ? 1 : 6;
    for (int k = 0; k < kmax; k++) {
        int ro[3][2];
        for (int j = 0; j < p->n; j++) { int q = p->off[j][0], r = p->off[j][1]; rot1(&q, &r, k); ro[j][0] = q - 0; ro[j][1] = r; }
        for (int a = 0; a < NC; a++) {
            int idx[3], ok = 1;
            for (int j = 0; j < p->n; j++) {
                int q = AXQ[a] + ro[j][0] - ro[0][0], r = AXR[a] + ro[j][1] - ro[0][1];
                if (q < -4 || q > 11 || r < -6 || r > 9) { ok = 0; break; }
                int c = AXI[q + 4][r + 6];
                if (c < 0 || b[c]) { ok = 0; break; }
                idx[j] = c;
            }
            if (!ok) continue;
            if (same) { // 같은 칸 집합이면 중복 제거
                int dup = 0;
                for (int m = 0; m < cnt && !dup; m++) {
                    int match = 1;
                    for (int j = 0; j < p->n && match; j++) { int f = 0; for (int i = 0; i < p->n; i++) if (out[m].c[i] == idx[j]) f = 1; if (!f) match = 0; }
                    if (match) dup = 1;
                }
                if (dup) continue;
            }
            out[cnt].n = p->n; for (int j = 0; j < p->n; j++) out[cnt].c[j] = idx[j];
            cnt++;
        }
    }
    return cnt;
}

static int group(const int8_t *b, int i, int *g) {
    int t = b[i], n = 0; uint32_t seen = 1u << i; g[n++] = i;
    for (int h = 0; h < n; h++) { int u = g[h]; for (int k = 0; k < NBN[u]; k++) { int v = NBL[u][k]; if (!(seen >> v & 1) && b[v] == t) { seen |= 1u << v; g[n++] = v; } } }
    return n;
}

// 합치기. dot_cell: 점 찍힌 카드가 놓인 보드 칸 (없거나 모르면 -1). choice: 첫 갈림에서 고를 후보. 반환 보상, *br = 갈림 수, *u 갱신
// patch269: 한 번에 한 그룹씩 - 낮은 등급 그룹 먼저(같으면 놓은 순서), 연쇄면 직전 결과 칸이 결과 칸.
// patch299: 10/26 신규 룰 - dot_cell 이 합쳐지는 후보군에 있으면 100% 확정 합성!
static double resolve(int8_t *b, const int *placed, int np, int dot_cell, int choice, int *br, int *u, int *maxmade) {
    double rew = 0; *br = 1;
    int front[3], nf = np, first_amb = 1, chain = -1;
    for (int i = 0; i < np; i++) front[i] = placed[i];
    for (;;) {
        int bt = 0, bgn = 0, bg[NC]; uint32_t bgm = 0, done = 0;
        for (int fi = 0; fi < nf; fi++) {
            int a = front[fi];
            if ((done >> a & 1) || b[a] <= 0) continue;
            int g[NC]; int gn = group(b, a, g);
            uint32_t gm = 0; for (int j = 0; j < gn; j++) gm |= 1u << g[j];
            done |= gm;
            if (gn >= 3 && b[a] < MAXT && (bgn == 0 || b[a] < bt)) {
                bt = b[a]; bgn = gn; bgm = gm;
                for (int j = 0; j < gn; j++) bg[j] = g[j];
            }
        }
        if (!bgn) break;
        int t = bt;
        int cands[3], nc = 0;
        for (int j = 0; j < nf; j++) if (bgm >> front[j] & 1) cands[nc++] = front[j];
        if (chain >= 0 && (bgm >> chain & 1)) { cands[0] = chain; nc = 1; }
        else if (dot_cell >= 0 && (bgm >> dot_cell & 1)) { cands[0] = dot_cell; nc = 1; }
        else if (nc == 3 && first_amb && np == 3) {
            int deg[3];
            for (int x = 0; x < 3; x++) { deg[x] = 0; for (int y = 0; y < 3; y++) if (y != x) for (int k = 0; k < NBN[cands[x]]; k++) if (NBL[cands[x]][k] == cands[y]) deg[x]++; }
            int s = deg[0] + deg[1] + deg[2];
            int c1 = (deg[0] == 1) + (deg[1] == 1) + (deg[2] == 1);
            if (s == 4 && c1 == 2) { int m = 0; for (int x = 0; x < 3; x++) if (deg[x] == 1) cands[m++] = cands[x]; nc = 2; }
        }
        int tgt;
        if (nc > 1 && first_amb) { first_amb = 0; *br = nc; tgt = cands[choice % nc]; }
        else tgt = cands[0];
        for (int j = 0; j < bgn; j++) b[bg[j]] = 0;
        int nt = t + (bgn >= 5 ? 2 : 1); if (nt > MAXT) nt = MAXT;
        b[tgt] = nt;
        rew += (double)(1 << nt);
        G3++; if (bgn >= 5) G5++;
        if (nt >= MAXT && t < MAXT) { if (t == 8) G10A++; else G10B++; }
        if (nt > *u) *u = nt;
        if (nt > *maxmade) *maxmade = nt;
        chain = tgt;
        int nfr[3], nn = 0; nfr[nn++] = tgt;
        for (int j = 0; j < nf; j++) if (!(bgm >> front[j] & 1) && front[j] != tgt) nfr[nn++] = front[j];
        nf = nn; for (int i = 0; i < nn; i++) front[i] = nfr[i];
    }
    return rew;
}

static inline int enc(int g, int lo) { if (!g) return 0; if (g < lo) return 1; int v = g - lo + 2; return v > 8 ? 8 : v; }

static double value(const int8_t *b, int u) {
    int lo = lo_of(u); int e[NC]; for (int i = 0; i < NC; i++) e[i] = enc(b[i], lo);
    double v = 0;
    for (int t = 0; t < NB_T; t++) for (int s = 0; s < 4; s++) {
        long idx = 0; for (int j = 0; j < TLEN[t]; j++) idx = idx * NV + e[SYM[s][TCELL[t][j]]];
        v += LUT[t][idx];
    }
    return v;
}
static void update(const int8_t *b, int u, float d) {
    int lo = lo_of(u); int e[NC]; for (int i = 0; i < NC; i++) e[i] = enc(b[i], lo);
    for (int t = 0; t < NB_T; t++) for (int s = 0; s < 4; s++) {
        long idx = 0; for (int j = 0; j < TLEN[t]; j++) idx = idx * NV + e[SYM[s][TCELL[t][j]]];
        LUT[t][idx] += d;
    }
}

#define gen_moves(b,p,o) gen_moves_k(b,p,o,0)
