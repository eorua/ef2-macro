// 유물 공방(헥사 머지) n-tuple TD(0) afterstate 학습기
// hexa_engine.py 규칙 그대로 옮김. 상태 인코딩: 0 빈칸, 1 죽은 칸(lo 미만), 2.. = 등급-lo+2 (최대 8)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include <pthread.h>
#include <time.h>
#include "board.h"

#define MAXT 10
#define NV 9
static float *LUT[NB_T];
static long LSIZE[NB_T];
static int NINST = NB_T * 4;
static int AXI[16][16]; // (q+4, r+6)

typedef struct { uint64_t s; } rng_t;
static inline uint64_t rnext(rng_t *r) { uint64_t x = r->s; x ^= x << 13; x ^= x >> 7; x ^= x << 17; return r->s = x; }
static inline double runi(rng_t *r) { return (rnext(r) >> 11) * (1.0 / 9007199254740992.0); }
static inline int rint_(rng_t *r, int n) { return (int)(runi(r) * n); }

static double W_N[3] = {0.29, 0.36, 0.35};   // 1/2/3칸 (실전 75조각)
static double W_T[3] = {0.58, 0.22, 0.20};   // lo, lo+1, hi

typedef struct { int n; int off[3][2]; int t[3]; } piece_t;

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
}

// 놓을 수 있는 수 목록: cells[m][3]
typedef struct { int n; int c[3]; } mv_t;
static int gen_moves(const int8_t *b, const piece_t *p, mv_t *out) {
    int cnt = 0;
    int same = 1; for (int j = 1; j < p->n; j++) if (p->t[j] != p->t[0]) same = 0;
    int kmax = (p->n == 1) ? 1 : 6;
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

// 합치기. choice: 첫 갈림에서 고를 후보. 반환 보상, *br = 갈림 수, *u 갱신
static double resolve(int8_t *b, const int *placed, int np, int choice, int *br, int *u, int *maxmade) {
    double rew = 0; *br = 1;
    int front[3], nf = np, first_amb = 1;
    for (int i = 0; i < np; i++) front[i] = placed[i];
    while (nf) {
        int nxt[3], nn = 0; uint32_t done = 0;
        for (int fi = 0; fi < nf; fi++) {
            int a = front[fi];
            if ((done >> a & 1) || b[a] == 0) continue;
            int g[NC]; int gn = group(b, a, g);
            uint32_t gm = 0; for (int j = 0; j < gn; j++) gm |= 1u << g[j];
            done |= gm;
            if (gn >= 3 && b[a] < MAXT) {
                int t = b[a];
                int cands[3], nc = 0;
                for (int j = 0; j < nf; j++) if (gm >> front[j] & 1) cands[nc++] = front[j];
                if (nc == 3 && first_amb && np == 3) {
                    int deg[3];
                    for (int x = 0; x < 3; x++) { deg[x] = 0; for (int y = 0; y < 3; y++) if (y != x) for (int k = 0; k < NBN[cands[x]]; k++) if (NBL[cands[x]][k] == cands[y]) deg[x]++; }
                    int s = deg[0] + deg[1] + deg[2];
                    int c1 = (deg[0] == 1) + (deg[1] == 1) + (deg[2] == 1);
                    if (s == 4 && c1 == 2) { int m = 0; for (int x = 0; x < 3; x++) if (deg[x] == 1) cands[m++] = cands[x]; nc = 2; }
                }
                int tgt;
                if (nc > 1 && first_amb) { first_amb = 0; *br = nc; tgt = cands[choice % nc]; }
                else tgt = cands[0];
                for (int j = 0; j < gn; j++) b[g[j]] = 0;
                int nt = t + (gn >= 5 ? 2 : 1); if (nt > MAXT) nt = MAXT;
                b[tgt] = nt;
                rew += (double)(1 << nt);
                if (nt > *u) *u = nt;
                if (nt > *maxmade) *maxmade = nt;
                nxt[nn++] = tgt;
            }
        }
        nf = nn; for (int i = 0; i < nn; i++) front[i] = nxt[i];
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

static inline double rw(double raw);
// 수 평가: 갈림 평균(r + V)
static double eval_move(const int8_t *b, int u, const piece_t *p, const mv_t *m) {
    double tot = 0; int nbr = 1;
    for (int ch = 0; ch < nbr; ch++) {
        int8_t nb[NC]; memcpy(nb, b, NC);
        for (int j = 0; j < m->n; j++) nb[m->c[j]] = p->t[j];
        int u2 = u, mm = 0, br;
        double r = rw(resolve(nb, m->c, m->n, ch, &br, &u2, &mm));
        nbr = br;
        tot += r + value(nb, u2);
    }
    return tot / nbr;
}

// 2수(다음 조각 앎) 평가
static double eval_move2(const int8_t *b, int u, const piece_t *p, const mv_t *m, const piece_t *nx) {
    double tot = 0; int nbr = 1;
    mv_t ms[256];
    for (int ch = 0; ch < nbr; ch++) {
        int8_t nb[NC]; memcpy(nb, b, NC);
        for (int j = 0; j < m->n; j++) nb[m->c[j]] = p->t[j];
        int u2 = u, mm = 0, br;
        double r = rw(resolve(nb, m->c, m->n, ch, &br, &u2, &mm));
        nbr = br;
        int n2 = gen_moves(nb, nx, ms);
        double best = n2 ? -1e18 : 0;
        for (int k = 0; k < n2; k++) { double v = eval_move(nb, u2, nx, &ms[k]); if (v > best) best = v; }
        tot += r + best;
    }
    return tot / nbr;
}

// 3수: 1수(지금) -> 2수(다음 조각 앎) -> 3수는 무작위 조각 K개 평균의 최선
static int K3 = 8;
static double best1(const int8_t *b, int u, const piece_t *p) {
    mv_t ms[256]; int n = gen_moves(b, p, ms);
    if (!n) return 0;
    double best = -1e18;
    for (int k = 0; k < n; k++) { double v = eval_move(b, u, p, &ms[k]); if (v > best) best = v; }
    return best;
}
static double eval_move3(const int8_t *b, int u, const piece_t *p, const mv_t *m, const piece_t *nx, rng_t *R, int B2) {
    double tot = 0; int nbr = 1;
    mv_t ms[256];
    for (int ch = 0; ch < nbr; ch++) {
        int8_t nb[NC]; memcpy(nb, b, NC);
        for (int j = 0; j < m->n; j++) nb[m->c[j]] = p->t[j];
        int u2 = u, mm = 0, br;
        double r = rw(resolve(nb, m->c, m->n, ch, &br, &u2, &mm));
        nbr = br;
        int n2 = gen_moves(nb, nx, ms);
        if (!n2) { tot += r; continue; }
        // 2수 후보를 1수 평가로 정렬해 상위 B2만 깊게
        double sc[256]; int ord[256];
        for (int k = 0; k < n2; k++) { sc[k] = eval_move(nb, u2, nx, &ms[k]); ord[k] = k; }
        for (int i = 0; i < n2; i++) for (int j = i + 1; j < n2; j++) if (sc[ord[j]] > sc[ord[i]]) { int t = ord[i]; ord[i] = ord[j]; ord[j] = t; }
        int lim = n2 < B2 ? n2 : B2;
        double best = -1e18;
        for (int q = 0; q < lim; q++) {
            const mv_t *m2 = &ms[ord[q]];
            double t2 = 0; int nbr2 = 1;
            for (int ch2 = 0; ch2 < nbr2; ch2++) {
                int8_t nb2[NC]; memcpy(nb2, nb, NC);
                for (int j = 0; j < m2->n; j++) nb2[m2->c[j]] = nx->t[j];
                int u3 = u2, mm2 = 0, br2;
                double r2 = rw(resolve(nb2, m2->c, m2->n, ch2, &br2, &u3, &mm2));
                nbr2 = br2;
                double acc = 0;
                rng_t R2 = *R;
                for (int s = 0; s < K3; s++) { piece_t p3; gen_piece(u3, &R2, &p3); acc += best1(nb2, u3, &p3); }
                t2 += r2 + acc / K3;
            }
            t2 /= nbr2;
            if (t2 > best) best = t2;
        }
        tot += r + best;
    }
    return tot / nbr;
}

typedef struct { int moves, best; double score; } res_t;

static int MAXMV = 20000;
static double ALPHA = 0.1;
// 보상 모드: 0 = 등급 점수(2^등급), 1 = 오래 버티기(한 수마다 1 + BONUS*등급점수)
static int RMODE = 0; static double BONUS = 0.002;
static inline double rw(double raw) { return RMODE ? 1.0 + BONUS * raw : raw; }
// 긴 판 상태에서 다시 시작(late restart)
static double P_RESTART = 0.0; static int RESTART_MIN = 100;
#define BUFN 4096
typedef struct { int8_t b[NC]; int u; } st_t;
static st_t SBUF[BUFN]; static long SBUF_N = 0;
static res_t play_game(rng_t *R, int learn, int look2) {
    int8_t b[NC]; memset(b, 0, NC);
    int u = 3;
    if (learn && P_RESTART > 0 && SBUF_N > 0 && runi(R) < P_RESTART) {
        long n0 = SBUF_N < BUFN ? SBUF_N : BUFN; st_t *s0 = &SBUF[rint_(R, (int)n0)];
        memcpy(b, s0->b, NC); u = s0->u;
    }
    piece_t cur, nx; gen_piece(u, R, &cur); gen_piece(u, R, &nx);
    int8_t prev[NC]; int prevu = 0, has_prev = 0;
    res_t res = {0, 0, 0};
    mv_t ms[256];
    float a = (float)(ALPHA / NINST);
    for (;;) {
        int n = gen_moves(b, &cur, ms);
        if (!n) { if (learn && has_prev) update(prev, prevu, a * (0 - (float)value(prev, prevu))); break; }
        int bi = 0; double bv = -1e18;
        rng_t RS = {rnext(R) | 1};
        if (look2 >= 2) { // 1수 정렬 후 상위 B1 만 3수
            double sc[256]; int ord[256];
            for (int k = 0; k < n; k++) { sc[k] = eval_move2(b, u, &cur, &ms[k], &nx); ord[k] = k; }
            for (int i = 0; i < n; i++) for (int j = i + 1; j < n; j++) if (sc[ord[j]] > sc[ord[i]]) { int t = ord[i]; ord[i] = ord[j]; ord[j] = t; }
            int lim = n < 8 ? n : 8;
            for (int q = 0; q < lim; q++) { double v = eval_move3(b, u, &cur, &ms[ord[q]], &nx, &RS, 6); if (v > bv) { bv = v; bi = ord[q]; } }
        } else
        for (int k = 0; k < n; k++) { double v = look2 ? eval_move2(b, u, &cur, &ms[k], &nx) : eval_move(b, u, &cur, &ms[k]); if (v > bv) { bv = v; bi = k; } }
        for (int j = 0; j < ms[bi].n; j++) b[ms[bi].c[j]] = cur.t[j];
        int br, mm = 0;
        double raw = resolve(b, ms[bi].c, ms[bi].n, rint_(R, 6), &br, &u, &mm);
        double r = rw(raw);
        if (mm > res.best) res.best = mm;
        res.score += raw; res.moves++;
        if (learn && P_RESTART > 0 && res.moves >= RESTART_MIN && (rnext(R) & 15) == 0) {
            long k = __sync_fetch_and_add(&SBUF_N, 1) % BUFN; memcpy(SBUF[k].b, b, NC); SBUF[k].u = u;
        }
        if (learn) {
            if (has_prev) { double d = r + value(b, u) - value(prev, prevu); update(prev, prevu, (float)(a * d)); }
            memcpy(prev, b, NC); prevu = u; has_prev = 1;
        }
        cur = nx; gen_piece(u, R, &nx);
        if (res.moves > MAXMV) break;
    }
    return res;
}

static long G_GAMES; static int G_THREADS = 2; static volatile long G_DONE = 0;
static pthread_mutex_t MU = PTHREAD_MUTEX_INITIALIZER;
static double ACC_S = 0, ACC_M = 0; static long ACC_N = 0, ACC_B[11];

static void *worker(void *arg) {
    rng_t R = {(uint64_t)(uintptr_t)arg * 0x9E3779B97F4A7C15ULL + (uint64_t)time(NULL)};
    for (;;) {
        long g = __sync_fetch_and_add(&G_DONE, 1);
        if (g >= G_GAMES) break;
        res_t r = play_game(&R, 1, 0);
        pthread_mutex_lock(&MU);
        ACC_S += r.score; ACC_M += r.moves; ACC_N++; ACC_B[r.best]++;
        pthread_mutex_unlock(&MU);
    }
    return NULL;
}

static void save(const char *fn) {
    FILE *f = fopen(fn, "wb");
    for (int t = 0; t < NB_T; t++) fwrite(LUT[t], 4, LSIZE[t], f);
    fclose(f);
}
static int load(const char *fn) {
    FILE *f = fopen(fn, "rb"); if (!f) return 0;
    for (int t = 0; t < NB_T; t++) if (fread(LUT[t], 4, LSIZE[t], f) != (size_t)LSIZE[t]) { fclose(f); return 0; }
    fclose(f); return 1;
}

static void evaluate_games(int n, int look2, uint64_t seed) {
    rng_t R = {seed}; double S = 0, M = 0; long B[11] = {0}; int mv[10000];
    for (int i = 0; i < n; i++) { res_t r = play_game(&R, 0, look2); S += r.score; M += r.moves; B[r.best]++; mv[i] = r.moves; }
    for (int i = 0; i < n; i++) for (int j = i + 1; j < n; j++) if (mv[j] < mv[i]) { int t = mv[i]; mv[i] = mv[j]; mv[j] = t; }
    printf("EVAL look%d n=%d score %.0f moves %.1f (p10 %d p50 %d p90 %d max %d) best:", look2 + 1, n, S / n, M / n, mv[n/10], mv[n/2], mv[n*9/10], mv[n-1]);
    for (int k = 6; k <= 10; k++) printf(" %d:%ld", k, B[k]);
    printf("\n"); fflush(stdout);
}

int main(int argc, char **argv) {
    memset(AXI, -1, sizeof AXI);
    for (int i = 0; i < NC; i++) AXI[AXQ[i] + 4][AXR[i] + 6] = i;
    for (int t = 0; t < NB_T; t++) { LSIZE[t] = 1; for (int j = 0; j < TLEN[t]; j++) LSIZE[t] *= NV; LUT[t] = calloc(LSIZE[t], 4); }
    if (getenv("RMODE")) RMODE = atoi(getenv("RMODE"));
    if (getenv("BONUS")) BONUS = atof(getenv("BONUS"));
    if (getenv("PRESTART")) P_RESTART = atof(getenv("PRESTART"));
    if (getenv("RMIN")) RESTART_MIN = atoi(getenv("RMIN"));
    if (getenv("MAXMV")) MAXMV = atoi(getenv("MAXMV"));
    const char *mode = argc > 1 ? argv[1] : "train";
    if (!strcmp(mode, "rtest")) {
        int bb[NC], np, c[3], t[3], ch;
        while (1) {
            for (int i = 0; i < NC; i++) if (scanf("%d", &bb[i]) != 1) return 0;
            scanf("%d", &np); for (int j = 0; j < np; j++) scanf("%d %d", &c[j], &t[j]); scanf("%d", &ch);
            int8_t b[NC]; for (int i = 0; i < NC; i++) b[i] = bb[i];
            for (int j = 0; j < np; j++) b[c[j]] = t[j];
            int br, u = 3, mm = 0; resolve(b, c, np, ch, &br, &u, &mm);
            for (int i = 0; i < NC; i++) printf("%d ", b[i]); printf("%d\n", br);
        }
    }
    if (!strcmp(mode, "val")) {
        if (!load(argc > 2 ? argv[2] : "nt_weights.bin")) return 1;
        int bb[NC], u;
        while (1) { for (int i = 0; i < NC; i++) if (scanf("%d", &bb[i]) != 1) return 0; if (scanf("%d", &u) != 1) return 0;
            int8_t b[NC]; for (int i = 0; i < NC; i++) b[i] = bb[i]; printf("%.4f\n", value(b, u)); }
    }
    if (!strcmp(mode, "mtest")) { // 수 개수 비교: 판 + 조각(n, off q r t ...)
        int bb[NC], n;
        while (1) {
            for (int i = 0; i < NC; i++) if (scanf("%d", &bb[i]) != 1) return 0;
            piece_t p; scanf("%d", &n); p.n = n; for (int j = 0; j < n; j++) scanf("%d %d %d", &p.off[j][0], &p.off[j][1], &p.t[j]);
            int8_t b[NC]; for (int i = 0; i < NC; i++) b[i] = bb[i];
            mv_t ms[256]; int k = gen_moves(b, &p, ms);
            // 칸 집합+등급 정렬 문자열 대신 개수와 해시
            long h = 0; for (int m = 0; m < k; m++) { long x = 1; for (int j = 0; j < n; j++) x *= (ms[m].c[j] * 11 + p.t[j] + 7); h += x; }
            printf("%d %ld\n", k, h);
        }
    }
    const char *wf = argc > 2 ? argv[2] : "nt_weights.bin";
    if (!strcmp(mode, "eval")) {
        if (!load(wf)) { printf("no weights\n"); return 1; }
        int n = argc > 3 ? atoi(argv[3]) : 200; int l2 = argc > 4 ? atoi(argv[4]) : 0;
        evaluate_games(n, l2, 12345); return 0;
    }
    // train: nt train weights.bin total_games chunk alpha [threads]
    long total = argc > 3 ? atol(argv[3]) : 100000;
    long chunk = argc > 4 ? atol(argv[4]) : 10000;
    if (argc > 5) ALPHA = atof(argv[5]);
    if (argc > 6) G_THREADS = atoi(argv[6]);
    if (load(wf)) printf("loaded %s\n", wf);
    time_t t0 = time(NULL);
    for (long done = 0; done < total; done += chunk) {
        G_GAMES = chunk; G_DONE = 0; ACC_S = ACC_M = 0; ACC_N = 0; memset(ACC_B, 0, sizeof ACC_B);
        pthread_t th[16];
        for (int i = 0; i < G_THREADS; i++) pthread_create(&th[i], NULL, worker, (void *)(uintptr_t)(i + 1 + done));
        for (int i = 0; i < G_THREADS; i++) pthread_join(th[i], NULL);
        printf("[%lds] games %ld  alpha %.4f  score %.0f moves %.1f  best:", (long)(time(NULL) - t0), done + chunk, ALPHA, ACC_S / ACC_N, ACC_M / ACC_N);
        for (int k = 6; k <= 10; k++) printf(" %d:%.1f%%", k, 100.0 * ACC_B[k] / ACC_N);
        printf("\n"); fflush(stdout);
        save(wf);
    }
    return 0;
}
