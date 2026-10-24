// patch246: EXACT=1 환경변수 = 첫 무작위 단계(3수째)에서 조각을 K개 뽑지 않고 모양(회전 같은 것끼리 묶음)x등급 모든 경우를 확률 가중평균. 0 이면 search4.c 와 같음.
// patch244: DEADP/DEADG 환경변수 = 낮은 등급(1~DEADG) 칸 하나당 평가 벌점(초반에 1~3성 정리 유도). 0 이면 search3.c 와 같음.
// 유물 공방 깊은 수 읽기 (patch232). n-tuple 평가 + expectimax(D수), 멀티스레드.
// 사용: hexa_search.exe 가중치.bin  -> 표준입력 한 줄씩:
//   u  b0..b22  n (q r t)*n  m (q r t)*m  D B K only_k0 budget_ms threads seed
//   출력: OK np c0 t0 c1 t1 .. score evaluated_roots   (수 없으면 NONE)
// 가상 대전: hexa_search 가중치.bin sim 판수 D B K threads seed
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include <time.h>
#ifdef _WIN32
#include <windows.h>
typedef HANDLE th_t;
static double now_ms(void) { LARGE_INTEGER f, c; QueryPerformanceFrequency(&f); QueryPerformanceCounter(&c); return 1000.0 * c.QuadPart / f.QuadPart; }
static long atomic_inc(volatile long *p) { return InterlockedIncrement(p) - 1; }
#else
#include <pthread.h>
typedef pthread_t th_t;
static double now_ms(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec * 1000.0 + t.tv_nsec / 1e6; }
static long atomic_inc(volatile long *p) { return __sync_fetch_and_add(p, 1); }
#endif
#include "board2.h"
#include "core2.inc"

static int RMODE = 1; static double BONUS = 0.002;
static inline double rw(double raw) { return RMODE ? 1.0 + BONUS * raw : raw; }

typedef struct { int B, K; uint64_t seed; int Kd; } prm_t;
static int CRN = 0, K2 = 0, B2 = 0;
static double DEADP = 0; static int DEADG = 3;
// patch244: 학습 평가 - 낮은 등급 칸 벌점 (이미 죽은 칸은 모든 수에서 같아 판단에 영향 없음)
static inline double evalv(const int8_t *b, int u) {
    double v = value(b, u);
    if (DEADP > 0) { int c = 0; for (int i = 0; i < NC; i++) if (b[i] >= 1 && b[i] <= DEADG) c++; v -= DEADP * c; }
    return v;
}

static double maxnode(const int8_t *b, int u, const piece_t *p, const piece_t *nx, int d, const prm_t *P, rng_t *R);

// patch246: 3칸 모양을 회전으로 같은 것끼리 묶기 (gen_moves 가 6방향을 다 두어 보므로 대표 하나면 충분)
static int EXACT = 0, NCL = 0, CLREP[NSH3]; static double CLW[NSH3];
static void norm3(int c[3][2]) {      // 칸 순서 정렬 후 첫 칸 기준으로 옮김
    for (int i = 0; i < 3; i++) for (int j = i + 1; j < 3; j++)
        if (c[j][0] < c[i][0] || (c[j][0] == c[i][0] && c[j][1] < c[i][1])) { int t0 = c[i][0], t1 = c[i][1]; c[i][0] = c[j][0]; c[i][1] = c[j][1]; c[j][0] = t0; c[j][1] = t1; }
    int q0 = c[0][0], r0 = c[0][1];
    for (int i = 0; i < 3; i++) { c[i][0] -= q0; c[i][1] -= r0; }
}
static void init_classes(void) {
    int key[NSH3][3][2]; int cls[NSH3];
    for (int s = 0; s < NSH3; s++) {          // 6방향 중 사전순 최소 = 모양 열쇠
        int best[3][2]; int have = 0;
        for (int k = 0; k < 6; k++) {
            int c[3][2]; for (int j = 0; j < 3; j++) { int q = SH3[s][j][0], r = SH3[s][j][1]; rot1(&q, &r, k); c[j][0] = q; c[j][1] = r; }
            norm3(c);
            if (!have || memcmp(c, best, sizeof c) < 0) { memcpy(best, c, sizeof c); have = 1; }
        }
        memcpy(key[s], best, sizeof best);
        cls[s] = -1;
        for (int t = 0; t < NCL; t++) if (!memcmp(key[CLREP[t]], key[s], sizeof best)) { cls[s] = t; break; }
        if (cls[s] < 0) { CLREP[NCL] = s; CLW[NCL] = 0; cls[s] = NCL++; }
        CLW[cls[s]] += 1.0 / NSH3;
    }
}
// patch246: 기회 노드 - 나올 수 있는 조각 전부(모양 대표 x 등급) 확률 가중평균
static double chance_exact(const int8_t *b, int u, int d, const prm_t *P, rng_t *R) {
    int hi = spawn_hi(u), lo = lo_of(u), ng = hi - lo + 1;
    double pt[3];
    for (int i = 0; i < ng; i++) pt[i] = (hi - lo == 2) ? W_T[i] : 1.0 / ng;
    double acc = 0; piece_t q;
    q.n = 1; q.off[0][0] = 0; q.off[0][1] = 0;
    for (int a = 0; a < ng; a++) { q.t[0] = lo + a; acc += W_N[0] * pt[a] * maxnode(b, u, &q, NULL, d, P, R); }
    q.n = 2; q.off[1][0] = 1; q.off[1][1] = 0;            // 두 칸은 180도 돌리면 칸이 바뀌므로 a<=c 만 (a!=c 는 두 배)
    for (int a = 0; a < ng; a++) for (int c = a; c < ng; c++) {
        q.t[0] = lo + a; q.t[1] = lo + c;
        acc += W_N[1] * pt[a] * pt[c] * (a == c ? 1 : 2) * maxnode(b, u, &q, NULL, d, P, R);
    }
    q.n = 3;
    for (int k = 0; k < NCL; k++) {
        int s = CLREP[k];
        for (int j = 0; j < 3; j++) { q.off[j][0] = SH3[s][j][0]; q.off[j][1] = SH3[s][j][1]; }
        for (int a = 0; a < ng; a++) for (int c = 0; c < ng; c++) for (int e = 0; e < ng; e++) {
            q.t[0] = lo + a; q.t[1] = lo + c; q.t[2] = lo + e;
            acc += W_N[2] * CLW[k] * pt[a] * pt[c] * pt[e] * maxnode(b, u, &q, NULL, d, P, R);
        }
    }
    return acc;
}

// 기회 노드: 무작위 조각 K개 평균
static double chance(const int8_t *b, int u, int d, const prm_t *P, rng_t *R) {
    if (d <= 0) return evalv(b, u);
    if (EXACT && d >= P->Kd) return chance_exact(b, u, d, P, R);     // patch246: 첫 무작위 단계만 전부
    double acc = 0;
    int K = (K2 && d < P->Kd) ? K2 : P->K;
    if (CRN) { rng_t Q = {(P->seed ^ (0x9E3779B97F4A7C15ULL * (uint64_t)(d + 1))) | 1};
        for (int s = 0; s < K; s++) { piece_t q; gen_piece(u, &Q, &q); acc += maxnode(b, u, &q, NULL, d, P, R); } }
    else for (int s = 0; s < K; s++) { piece_t q; gen_piece(u, R, &q); acc += maxnode(b, u, &q, NULL, d, P, R); }
    return acc / K;
}

// 1수 빠른 평가 (갈림 평균 r + V)
static double quick(const int8_t *b, int u, const piece_t *p, const mv_t *m) {
    double tot = 0; int nbr = 1;
    for (int ch = 0; ch < nbr; ch++) {
        int8_t nb[NC]; memcpy(nb, b, NC);
        for (int j = 0; j < m->n; j++) nb[m->c[j]] = p->t[j];
        int u2 = u, mm = 0, br;
        double r = rw(resolve(nb, m->c, m->n, ch, &br, &u2, &mm)); nbr = br;
        tot += r + evalv(nb, u2);
    }
    return tot / nbr;
}

// 한 수 깊게: 갈림 평균 r + (다음 조각 앎 ? maxnode : chance)
static double deep(const int8_t *b, int u, const piece_t *p, const mv_t *m, const piece_t *nx, int d, const prm_t *P, rng_t *R) {
    double tot = 0; int nbr = 1;
    for (int ch = 0; ch < nbr; ch++) {
        int8_t nb[NC]; memcpy(nb, b, NC);
        for (int j = 0; j < m->n; j++) nb[m->c[j]] = p->t[j];
        int u2 = u, mm = 0, br;
        double r = rw(resolve(nb, m->c, m->n, ch, &br, &u2, &mm)); nbr = br;
        double f = nx ? maxnode(nb, u2, nx, NULL, d - 1, P, R) : chance(nb, u2, d - 1, P, R);
        tot += r + f;
    }
    return tot / nbr;
}

static void order(const int8_t *b, int u, const piece_t *p, mv_t *ms, int n, double *sc, int *ord) {
    for (int k = 0; k < n; k++) { sc[k] = quick(b, u, p, &ms[k]); ord[k] = k; }
    for (int i = 1; i < n; i++) { int x = ord[i], j = i; while (j > 0 && sc[ord[j - 1]] < sc[x]) { ord[j] = ord[j - 1]; j--; } ord[j] = x; }
}

// d = 남은 조각 수(이 조각 포함). 놓을 곳 없으면 0(끝)
static double maxnode(const int8_t *b, int u, const piece_t *p, const piece_t *nx, int d, const prm_t *P, rng_t *R) {
    mv_t ms[256]; int n = gen_moves(b, p, ms);
    if (!n) return 0;
    double sc[256]; int ord[256];
    if (d <= 1) { double best = -1e18; for (int k = 0; k < n; k++) { double v = quick(b, u, p, &ms[k]); if (v > best) best = v; } return best; }
    order(b, u, p, ms, n, sc, ord);
    int Bn = (B2 && d < P->Kd) ? B2 : P->B;
    int lim = n < Bn ? n : Bn;
    double best = -1e18;
    for (int q = 0; q < lim; q++) { double v = deep(b, u, p, &ms[ord[q]], nx, d, P, R); if (v > best) best = v; }
    return best;
}

// ---------- 뿌리: 스레드가 뿌리 후보를 하나씩 가져감 ----------
typedef struct {
    const int8_t *b; int u; const piece_t *p, *nx; int D; prm_t P;
    mv_t ms[256]; int ord[256], n, lim; double val[256]; int done[256];
    volatile long next; double deadline; uint64_t seed;
} root_t;

#ifdef _WIN32
static DWORD WINAPI root_worker(LPVOID a)
#else
static void *root_worker(void *a)
#endif
{
    root_t *T = (root_t *)a;
    for (;;) {
        long i = atomic_inc(&T->next);
        if (i >= T->lim) break;
        if (i >= 2 && now_ms() > T->deadline) break;
        rng_t R = {T->seed * 0x9E3779B97F4A7C15ULL + 7}; // 뿌리 후보마다 같은 무작위 조각(공정 비교)
        T->val[i] = deep(T->b, T->u, T->p, &T->ms[T->ord[i]], T->nx, T->D, &T->P, &R);
        T->done[i] = 1;
    }
    return 0;
}

// 반환: 고른 수 번호(ms 안), -1 이면 없음
static int search_root(root_t *T, int k0, int threads, double budget_ms) {
    T->n = gen_moves_k(T->b, T->p, T->ms, k0);
    if (!T->n) return -1;
    double sc[256];
    order(T->b, T->u, T->p, T->ms, T->n, sc, T->ord);
    if (T->D <= 1) return T->ord[0];
    int B1 = T->P.B * 2; // 뿌리는 두 배 넓게
    T->lim = T->n < B1 ? T->n : B1;
    T->next = 0; memset(T->done, 0, sizeof T->done);
    T->deadline = now_ms() + budget_ms;
    if (threads <= 1) root_worker(T);
    else {
        th_t th[64]; if (threads > 64) threads = 64;
#ifdef _WIN32
        for (int i = 0; i < threads; i++) th[i] = CreateThread(NULL, 0, root_worker, T, 0, NULL);
        WaitForMultipleObjects(threads, th, TRUE, INFINITE);
        for (int i = 0; i < threads; i++) CloseHandle(th[i]);
#else
        for (int i = 0; i < threads; i++) pthread_create(&th[i], NULL, root_worker, T);
        for (int i = 0; i < threads; i++) pthread_join(th[i], NULL);
#endif
    }
    int bi = -1; double bv = -1e18; int cnt = 0;
    for (int i = 0; i < T->lim; i++) if (T->done[i]) { cnt++; if (T->val[i] > bv) { bv = T->val[i]; bi = i; } }
    T->val[255] = bv; T->done[255] = cnt;
    return T->ord[bi];
}

static int loadw(const char *fn) {
    FILE *f = fopen(fn, "rb"); if (!f) return 0;
    for (int t = 0; t < NB_T; t++) if (fread(LUT[t], 4, LSIZE[t], f) != (size_t)LSIZE[t]) { fclose(f); return 0; }
    fclose(f); return 1;
}

// ---------- 가상 대전 (판 단위 병렬) ----------
typedef struct { int D, B, K; uint64_t seed; int games; volatile long next; int moves[4096], best[4096]; double score[4096]; } sim_t;
#ifdef _WIN32
static DWORD WINAPI sim_worker(LPVOID a)
#else
static void *sim_worker(void *a)
#endif
{
    sim_t *S = (sim_t *)a;
    for (;;) {
        long g = atomic_inc(&S->next);
        if (g >= S->games) break;
        rng_t R = {(S->seed + g) * 0x2545F4914F6CDD1DULL + 1};
        int8_t b[NC]; memset(b, 0, NC); int u = 3;
        piece_t cur, nx; gen_piece(u, &R, &cur); gen_piece(u, &R, &nx);
        int moves = 0, best = 0; double score = 0;
        root_t *T = malloc(sizeof(root_t));
        for (;;) {
            T->b = b; T->u = u; T->p = &cur; T->nx = &nx; T->D = S->D; T->P.B = S->B; T->P.K = S->K; T->seed = rnext(&R); T->P.seed = T->seed; T->P.Kd = S->D - 2;
            int mi = search_root(T, 0, 1, 1e12);
            if (mi < 0) break;
            mv_t *m = &T->ms[mi];
            for (int j = 0; j < m->n; j++) b[m->c[j]] = cur.t[j];
            int br, mm = 0;
            score += resolve(b, m->c, m->n, rint_(&R, 6), &br, &u, &mm);
            if (mm > best) best = mm;
            moves++;
            cur = nx; gen_piece(u, &R, &nx);
            if (moves > 5000) break;
        }
        free(T);
        S->moves[g] = moves; S->best[g] = best; S->score[g] = score;
    }
    return 0;
}

static int cmpi(const void *a, const void *b) { return *(int *)a - *(int *)b; }

int main(int argc, char **argv) {
    memset(AXI, -1, sizeof AXI);
    for (int i = 0; i < NC; i++) AXI[AXQ[i] + 4][AXR[i] + 6] = i;
    tup_default();
    if (argc >= 2) { char tf[1024]; snprintf(tf, sizeof tf, "%s.tup", argv[1]); tup_load(tf); }
    for (int t = 0; t < NB_T; t++) { LSIZE[t] = 1; for (int j = 0; j < TLEN[t]; j++) LSIZE[t] *= NV; LUT[t] = calloc(LSIZE[t], 4); if (!LUT[t]) { printf("ERR memory\n"); return 1; } }
    if (argc < 2 || !loadw(argv[1])) { printf("ERR weights\n"); return 1; }
    if (getenv("RMODE")) RMODE = atoi(getenv("RMODE"));
    if (getenv("CRN")) CRN = atoi(getenv("CRN"));
    if (getenv("K2")) K2 = atoi(getenv("K2"));
    if (getenv("B2")) B2 = atoi(getenv("B2"));
    if (getenv("DEADP")) DEADP = atof(getenv("DEADP"));
    if (getenv("DEADG")) DEADG = atoi(getenv("DEADG"));
    if (getenv("EXACT")) EXACT = atoi(getenv("EXACT"));
    init_classes();
    if (getenv("EXACT_DBG")) { fprintf(stderr, "classes %d:", NCL); for (int k = 0; k < NCL; k++) fprintf(stderr, " rep%d w%.3f", CLREP[k], CLW[k]); fprintf(stderr, "\n"); }
    if (argc > 2 && !strcmp(argv[2], "sim")) {
        sim_t *S = calloc(1, sizeof(sim_t));
        S->games = atoi(argv[3]); S->D = atoi(argv[4]); S->B = atoi(argv[5]); S->K = atoi(argv[6]);
        int th = atoi(argv[7]); S->seed = argc > 8 ? atoll(argv[8]) : 1;
        double t0 = now_ms();
        th_t h[64];
#ifdef _WIN32
        for (int i = 0; i < th; i++) h[i] = CreateThread(NULL, 0, sim_worker, S, 0, NULL);
        WaitForMultipleObjects(th, h, TRUE, INFINITE);
#else
        for (int i = 0; i < th; i++) pthread_create(&h[i], NULL, sim_worker, S);
        for (int i = 0; i < th; i++) pthread_join(h[i], NULL);
#endif
        double M = 0, Sc = 0; long B[11] = {0}; long totm = 0;
        for (int g = 0; g < S->games; g++) { M += S->moves[g]; Sc += S->score[g]; B[S->best[g]]++; totm += S->moves[g]; }
        qsort(S->moves, S->games, sizeof(int), cmpi);
        int n = S->games;
        printf("SIM D%d B%d K%d n=%d moves %.1f (p10 %d p50 %d p90 %d max %d) score %.0f best:", S->D, S->B, S->K, n, M / n,
               S->moves[n / 10], S->moves[n / 2], S->moves[n * 9 / 10], S->moves[n - 1], Sc / n);
        for (int k = 7; k <= 10; k++) printf(" %d:%ld", k, B[k]);
        printf("  %.1f ms/move\n", (now_ms() - t0) * th / (double)totm);
        return 0;
    }
    // 서버 모드
    char line[4096];
    root_t *T = malloc(sizeof(root_t));
    printf("READY\n"); fflush(stdout);
    while (fgets(line, sizeof line, stdin)) {
        char *s = line; int pos;
        int8_t b[NC]; int u, v;
        piece_t p, nx; int hasnx;
        int D, B, K, k0, th; double budget; long long seed;
#define RD(x) do { if (sscanf(s, "%d%n", &(x), &pos) != 1) goto bad; s += pos; } while (0)
        RD(u);
        for (int i = 0; i < NC; i++) { RD(v); b[i] = (int8_t)v; }
        RD(p.n); for (int j = 0; j < p.n; j++) { RD(p.off[j][0]); RD(p.off[j][1]); RD(p.t[j]); }
        RD(nx.n); for (int j = 0; j < nx.n; j++) { RD(nx.off[j][0]); RD(nx.off[j][1]); RD(nx.t[j]); }
        hasnx = nx.n > 0;
        RD(D); RD(B); RD(K); RD(k0);
        if (sscanf(s, "%lf %d %lld", &budget, &th, &seed) != 3) goto bad;
        {
            double t0 = now_ms();
            T->b = b; T->u = u; T->p = &p; T->nx = hasnx ? &nx : NULL; T->D = D; T->P.B = B; T->P.K = K; T->seed = (uint64_t)seed; T->P.seed = T->seed * 0xD1B54A32D192ED03ULL + 99; T->P.Kd = D - 2;
            int mi = search_root(T, k0, th, budget);
            if (mi < 0) { printf("NONE\n"); fflush(stdout); continue; }
            mv_t *m = &T->ms[mi];
            printf("OK %d", m->n);
            for (int j = 0; j < m->n; j++) printf(" %d %d", m->c[j], p.t[j]);
            printf(" %.4f %d %.0f\n", D > 1 ? T->val[255] : 0.0, D > 1 ? T->done[255] : 1, now_ms() - t0);
            fflush(stdout);
            continue;
        }
    bad:
        printf("ERR parse\n"); fflush(stdout);
    }
    return 0;
}
