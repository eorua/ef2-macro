// patch269: search11.c = search10.c + core5.inc (resolve 처리 순서만 다름). 나머지 동작·환경변수 동일
// patch262: HUB/HUB7 환경변수 = ★8(★7) 2+2 쌍이 빈 칸 하나를 둘러싼 '허브' 구조 보너스(5개 합치기 → +2등급 = ★10/★9 직행). 기본 0 이면 search9.c 와 같음.
// patch260: 기본값 TENB=0 CLUST=0 으로 복귀(환경변수로만 켬). patch259(★10 올인): TENB 180 + CLUST(필드에 ★8·★9 출현 시 인접 결합 가중치 기본 1.0) 반영.
// patch251(0단계 진단): CALIB=1 환경변수 = sim 에서 매 수 afterstate 평가값 V 와 실제 이후 보상합 G(=남은 수 + 0.002x합성점수) 비교, u별·진행 수별 오차 표 출력. 수 선택은 바뀌지 않음(평가 호출만 추가) -> SIM 줄은 search8.c 와 같음.
// patch250: TENB 환경변수 = ★10 을 만들 때마다 보상에 더하는 보너스(단위 ≈ 수). 0 이면 search7.c 와 같음. sim 에 TEN 통계(★10 경로: 8성 5개 / 9성 3개). core4.inc = core3.inc + ★10 경로 세기.
// patch249: FIVEB 환경변수 = 5개 이상 합치기(+2등급) 한 번마다 보상에 더하는 보너스(단위 = 대략 '수'). 0 이면 search6.c 와 같음. sim 에 FIVE 통계 줄. core3.inc = core2.inc + 합치기 횟수 세기.
// patch248: GATEP 환경변수 = '진짜 죽은 칸'(등급 < 지금 나오는 최저 등급) 하나당 평가 벌점. 이미 죽은 칸은 모든 수에서 같으므로 실제로는 '단계를 넘기며 새로 죽이는 칸'에만 작용(1~3성을 먼저 지우고 넘어가게). 큰 값(1000)이면 사실상 금지. sim 은 둘째 줄에 DEAD 통계 출력.
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
static _Thread_local int G3 = 0, G5 = 0, G10A = 0, G10B = 0;   // patch249: 합치기 횟수 / 그중 5개 이상
#include "core6.inc"   // patch299b: 합성점 확정 합성 반영 (core6.inc)

// patch299b: 비상 망치 파괴 대상 칸 선택 (둘 곳 없을 때 현재 조각을 둘 수 있게 해주는 최저티어 칸)
static int pick_hammer_target(const int8_t *b, const piece_t *p) {
    int best_cell = -1;
    int best_tier = 99;
    for (int k = 0; k < 6; k++) {
        int ro[3][2];
        for (int j = 0; j < p->n; j++) {
            int q = p->off[j][0], r = p->off[j][1];
            rot1(&q, &r, k);
            ro[j][0] = q; ro[j][1] = r;
        }
        for (int a = 0; a < NC; a++) {
            int blocked_cell = -1;
            int blocked_count = 0;
            int ok = 1;
            for (int j = 0; j < p->n; j++) {
                int q = AXQ[a] + ro[j][0] - ro[0][0], r = AXR[a] + ro[j][1] - ro[0][1];
                if (q < -4 || q > 11 || r < -6 || r > 9) { ok = 0; break; }
                int c = AXI[q + 4][r + 6];
                if (c < 0) { ok = 0; break; }
                if (b[c] > 0) {
                    blocked_cell = c;
                    blocked_count++;
                }
            }
            if (ok && blocked_count == 1) {
                int tier = b[blocked_cell];
                if (tier < best_tier) {
                    best_tier = tier;
                    best_cell = blocked_cell;
                }
            }
        }
    }
    if (best_cell >= 0) return best_cell;
    for (int i = 0; i < NC; i++) {
        if (b[i] > 0 && b[i] < best_tier) {
            best_tier = b[i];
            best_cell = i;
        }
    }
    return best_cell;
}

static int RMODE = 1; static double BONUS = 0.002;
static inline double rw(double raw) { return RMODE ? 1.0 + BONUS * raw : raw; }

typedef struct { int B, K; uint64_t seed; int Kd; } prm_t;
static int CRN = 0, K2 = 0, B2 = 0;
static double DEADP = 0; static int DEADG = 3;
// patch244: 학습 평가 - 낮은 등급 칸 벌점 (이미 죽은 칸은 모든 수에서 같아 판단에 영향 없음)
// patch259: ★10 확정 달성 올인 모드 - TENB 기본 180 상향 + CLUST(필드에 ★8·★9 출현 시 인접 결합 가중치)
static double GATEP = 0; static double FIVEB = 0; static double TENB = 0; static double CLUST = 0;   /* patch260: 기본 0 (search8 호환), 켜려면 환경변수 TENB/CLUST */
static inline int dead_cnt(const int8_t *b, int u) { int lo = lo_of(u), c = 0; for (int i = 0; i < NC; i++) if (b[i] > 0 && b[i] < lo) c++; return c; }

// patch259: 필드에 ★8·★9 가 떠 있을 때 공간 확보보다 이들을 인접시켜 ★10 합각을 만드는 결합 가중치
static inline double cluster_eval(const int8_t *b) {
    int n8 = 0, n9 = 0;
    for (int i = 0; i < NC; i++) {
        if (b[i] == 8) n8++;
        else if (b[i] == 9) n9++;
    }
    if (!n8 && !n9) return 0.0;
    int adj99 = 0, adj98 = 0, adj88 = 0, adj87 = 0;
    int bridge99 = 0, bridge98 = 0;
    int iso8 = 0, trap9 = 0;
    for (int i = 0; i < NC; i++) {
        int ti = b[i];
        if (ti == 9) {
            int open9 = 0;
            for (int k = 0; k < NBN[i]; k++) {
                int j = NBL[i][k], tj = b[j];
                if (tj == 9 && j > i) adj99++;
                else if (tj == 8) { adj98++; open9++; }
                else if (tj == 0 || tj == 7) open9++;
            }
            if (open9 == 0) trap9 += 2;
            else if (open9 == 1) trap9 += 1;
        } else if (ti == 8) {
            int conn = 0;
            for (int k = 0; k < NBN[i]; k++) {
                int j = NBL[i][k], tj = b[j];
                if (tj == 8) { conn = 1; if (j > i) adj88++; }
                else if (tj == 9) conn = 1;
                else if (tj == 7) adj87++;
            }
            if (!conn && (n8 + n9) >= 2) iso8++;
        }
        // 두 ★9 를 동시에 이웃으로 두는 브릿지(합각) 칸 점검
        if (n9 >= 2 && ti != 9) {
            int c9 = 0;
            for (int k = 0; k < NBN[i]; k++) if (b[NBL[i][k]] == 9) c9++;
            if (c9 >= 2) {
                if (ti == 8) bridge98++;
                else if (ti == 0 || ti == 7) bridge99++;
            }
        }
    }
    double sc = 18.0 * n9 + 2.5 * n8;
    sc += 28.0 * adj99 + 9.0 * adj98 + 5.0 * adj88 + 2.0 * adj87;
    sc += 18.0 * bridge98 + 10.0 * bridge99;
    sc -= 4.0 * trap9 + 2.5 * iso8;
    if (n9 >= 2 && adj99 == 0 && bridge99 == 0 && bridge98 == 0)
        sc -= 16.0 * (n9 - 1);   // ★9 가 서로 멀리 고립되는 배치 강력 억제
    return sc;
}

// patch262: 허브 구조 - 빈 칸 h 주위에 등급 T 덩어리(크기 1~2)가 둘 이상 붙어 합계 4칸 이상이면 1.0, 3칸이면 0.3.
//   h 에서 T 가 새로 생기면 5개(또는 4개) 합치기 -> T+2(★8 이면 ★10). 가장 좋은 허브 하나만 셈.
static double HUB = 0, HUB7 = 0;
static inline double hub_tier(const int8_t *b, int T) {
    int cnt = 0; for (int i = 0; i < NC; i++) if (b[i] == T) cnt++;
    if (cnt < 3) return 0.0;
    int comp[NC], csz[NC], nc = 0;
    for (int i = 0; i < NC; i++) comp[i] = -1;
    for (int i = 0; i < NC; i++) if (b[i] == T && comp[i] < 0) {
        int g[NC]; int gn = group(b, i, g);
        for (int j = 0; j < gn; j++) comp[g[j]] = nc;
        csz[nc++] = gn;
    }
    double best = 0.0;
    for (int h = 0; h < NC; h++) {
        if (b[h]) continue;
        int seen[6], ns = 0, s = 0;
        for (int k = 0; k < NBN[h]; k++) {
            int c = comp[NBL[h][k]]; if (c < 0) continue;
            int dup = 0; for (int x = 0; x < ns; x++) if (seen[x] == c) dup = 1;
            if (!dup) { seen[ns++] = c; s += csz[c]; }
        }
        if (ns < 2) continue;
        double v = s >= 4 ? 1.0 : (s == 3 ? 0.3 : 0.0);
        if (v > best) best = v;
        if (best >= 1.0) break;
    }
    return best;
}

static inline double evalv(const int8_t *b, int u) {
    double v = value(b, u);
    if (GATEP > 0) v -= GATEP * dead_cnt(b, u);
    if (DEADP > 0) { int c = 0; for (int i = 0; i < NC; i++) if (b[i] >= 1 && b[i] <= DEADG) c++; v -= DEADP * c; }
    if (CLUST > 0) v += CLUST * cluster_eval(b);
    // patch284: 필드에 이미 ★10 이 달성되었으면 허브 강제 보너스를 꺼서 무리한 8성 쌓기를 방지하고 최고 점수/생존 모드로 전환
    int has10 = 0;
    for (int i = 0; i < NC; i++) if (b[i] >= 10) { has10 = 1; break; }
    if (!has10) {
        if (HUB > 0) v += HUB * hub_tier(b, 8);      // patch262
        if (HUB7 > 0) v += HUB7 * hub_tier(b, 7);    // patch262
    }
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
    int dot_cell = (p && p->dot >= 0 && p->dot < m->n) ? m->c[p->dot] : -1;
    for (int ch = 0; ch < nbr; ch++) {
        int8_t nb[NC]; memcpy(nb, b, NC);
        for (int j = 0; j < m->n; j++) nb[m->c[j]] = p->t[j];
        int u2 = u, mm = 0, br;
        int g5 = G5, g10 = G10A + G10B; double r = rw(resolve(nb, m->c, m->n, dot_cell, ch, &br, &u2, &mm)); nbr = br;
        if (FIVEB > 0) r += FIVEB * (G5 - g5);
        if (TENB > 0) r += TENB * (G10A + G10B - g10);
        tot += r + evalv(nb, u2);
    }
    return tot / nbr;
}

// 한 수 깊게: 갈림 평균 r + (다음 조각 앎 ? maxnode : chance)
static double deep(const int8_t *b, int u, const piece_t *p, const mv_t *m, const piece_t *nx, int d, const prm_t *P, rng_t *R) {
    double tot = 0; int nbr = 1;
    int dot_cell = (p && p->dot >= 0 && p->dot < m->n) ? m->c[p->dot] : -1;
    for (int ch = 0; ch < nbr; ch++) {
        int8_t nb[NC]; memcpy(nb, b, NC);
        for (int j = 0; j < m->n; j++) nb[m->c[j]] = p->t[j];
        int u2 = u, mm = 0, br;
        int g5 = G5, g10 = G10A + G10B; double r = rw(resolve(nb, m->c, m->n, dot_cell, ch, &br, &u2, &mm)); nbr = br;
        if (FIVEB > 0) r += FIVEB * (G5 - g5);
        if (TENB > 0) r += TENB * (G10A + G10B - g10);
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
typedef struct { int D, B, K; uint64_t seed; int games; volatile long next; int moves[4096], best[4096]; double score[4096]; signed char dmade[4096][5]; short at7[4096]; int n3[4096], n5[4096], ta[4096], tb[4096], hammers[4096]; double cu[4096][11][8]; double cm[4096][8][8]; short first[4096][11]; } sim_t;
static int CALIB = 0;
// cu[g][u][k] / cm[g][bucket][k]: k = 0 n, 1 sumV, 2 sumG, 3 sumVV, 4 sumGG, 5 sumVG, 6 sum|V-G|, 7 sum 남은 수
static inline void cacc(double *a, double V, double G, double Rm) { a[0] += 1; a[1] += V; a[2] += G; a[3] += V * V; a[4] += G * G; a[5] += V * G; a[6] += fabs(V - G); a[7] += Rm; }

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
        int moves = 0, best = 0; double score = 0; S->n3[g] = 0; S->n5[g] = 0; S->ta[g] = 0; S->tb[g] = 0;
        int hammer_left = (getenv("NOHAMMER") && atoi(getenv("NOHAMMER"))) ? 0 : 1;
        int hammers_used = 0;
        for (int k = 0; k < 5; k++) S->dmade[g][k] = -1; S->at7[g] = -1;
        root_t *T = malloc(sizeof(root_t));
        float *cV = CALIB ? malloc(sizeof(float) * 5002) : NULL, *cR = CALIB ? malloc(sizeof(float) * 5002) : NULL; signed char *cU = CALIB ? malloc(5002) : NULL;
        for (int k = 0; k < 11; k++) S->first[g][k] = -1;
        for (;;) {
            T->b = b; T->u = u; T->p = &cur; T->nx = &nx; T->D = S->D; T->P.B = S->B; T->P.K = S->K; T->seed = rnext(&R); T->P.seed = T->seed; T->P.Kd = S->D - 2;
            int mi = search_root(T, 0, 1, 1e12);
            if (mi < 0) {
                // patch299b: 둘 곳이 없으면 비상 망치 1회 발동
                if (hammer_left > 0) {
                    int target = pick_hammer_target(b, &cur);
                    if (target >= 0) {
                        b[target] = 0;
                        hammer_left = 0;
                        hammers_used++;
                        mi = search_root(T, 0, 1, 1e12);
                    }
                }
                if (mi < 0) break;
            }
            mv_t *m = &T->ms[mi];
            for (int j = 0; j < m->n; j++) b[m->c[j]] = cur.t[j];
            int br, mm = 0; int lo0 = lo_of(u);
            int c3 = G3, c5 = G5; int ca = G10A, cb = G10B;
            int dot_cell = (cur.dot >= 0 && cur.dot < m->n) ? m->c[cur.dot] : -1;
            double rawr = resolve(b, m->c, m->n, dot_cell, rint_(&R, 6), &br, &u, &mm); score += rawr;
            if (CALIB && moves < 5001) { cV[moves] = (float)value(b, u); cR[moves] = (float)rw(rawr); cU[moves] = (signed char)u; }
            if (u <= 10 && S->first[g][u] < 0) S->first[g][u] = (short)(moves + 1);
            { int lo1 = lo_of(u);
              if (lo1 > lo0) { int c = 0; for (int i = 0; i < NC; i++) if (b[i] >= lo0 && b[i] < lo1) c++;
                  S->dmade[g][lo1] = (signed char)c; if (lo1 == 4) S->at7[g] = (short)(moves + 1); } }
            S->n3[g] += G3 - c3; S->n5[g] += G5 - c5; S->ta[g] += G10A - ca; S->tb[g] += G10B - cb;
            if (mm > best) best = mm;
            moves++;
            cur = nx; gen_piece(u, &R, &nx);
            if (moves > 5000) break;
        }
        free(T);
        if (CALIB) {   // 뒤에서부터 G_t = r_{t+1} + ... (afterstate t 이후 받은 보상)
            int nm = moves < 5001 ? moves : 5001; double G = 0;
            for (int t = nm - 1; t >= 0; t--) {
                int uu = cU[t]; if (uu > 10) uu = 10; double Rm = nm - 1 - t;
                cacc(S->cu[g][uu], cV[t], G, Rm);
                int bk = t / 40; if (bk > 7) bk = 7;
                cacc(S->cm[g][bk], cV[t], G, Rm);
                G += cR[t];
            }
            free(cV); free(cR); free(cU);
        }
        S->moves[g] = moves; S->best[g] = best; S->score[g] = score; S->hammers[g] = hammers_used;
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
    if (getenv("GATEP")) GATEP = atof(getenv("GATEP"));
    if (getenv("FIVEB")) FIVEB = atof(getenv("FIVEB"));
    if (getenv("TENB")) TENB = atof(getenv("TENB"));
    if (getenv("CLUST")) CLUST = atof(getenv("CLUST"));
    if (getenv("HUB")) HUB = atof(getenv("HUB"));       // patch262
    if (getenv("HUB7")) HUB7 = atof(getenv("HUB7"));    // patch262
    if (getenv("CALIB")) CALIB = atoi(getenv("CALIB"));
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
        { long a3 = 0, a5 = 0; for (int g = 0; g < S->games; g++) { a3 += S->n3[g]; a5 += S->n5[g]; }
          printf("FIVE merges/game %.1f, 5+ merges/game %.2f (%.1f%%)\n", (double)a3 / S->games, (double)a5 / S->games, a3 ? a5 * 100.0 / a3 : 0); }
        { long A = 0, Bt = 0, gg = 0; for (int g = 0; g < S->games; g++) { A += S->ta[g]; Bt += S->tb[g]; if (S->ta[g] + S->tb[g]) gg++; }
          printf("TEN star10/game %.3f (8x5 %ld, 9x3 %ld), games with star10 %.1f%%\n", (double)(A + Bt) / S->games, A, Bt, gg * 100.0 / S->games); }
        { long H = 0; for (int g = 0; g < S->games; g++) H += S->hammers[g];
          printf("HAMMER used %ld/%.1f%%\n", H, H * 100.0 / S->games); }
        if (getenv("DUMP")) for (int g = 0; g < S->games; g++) { int t = 0; for (int L = 2; L <= 4; L++) if (S->dmade[g][L] > 0) t += S->dmade[g][L]; fprintf(stderr, "G %d %d\n", S->moves[g], t); }
        if (CALIB) {
            static const char *nm[2] = {"u", "mv"};
            for (int kind = 0; kind < 2; kind++) {
                int nb = kind ? 8 : 11;
                printf("CALIB by %s  (V=평가값, G=실제 이후 보상합, 단위 약 '수')\n", kind ? "move(40수 묶음)" : "u(해금 최고등급)");
                printf("CALIB %-7s %7s %6s %8s %8s %8s %8s %8s %8s %6s %6s %6s\n", nm[kind], "n", "share", "meanV", "meanG", "bias", "MAE", "RMSE", "sdG", "corr", "slope", "R2");
                double tot = 0; for (int g = 0; g < S->games; g++) for (int k = 0; k < nb; k++) tot += kind ? S->cm[g][k][0] : S->cu[g][k][0];
                for (int k = 0; k < nb; k++) {
                    double a[8] = {0};
                    for (int g = 0; g < S->games; g++) for (int j = 0; j < 8; j++) a[j] += kind ? S->cm[g][k][j] : S->cu[g][k][j];
                    if (a[0] < 1) continue;
                    double n = a[0], mV = a[1] / n, mG = a[2] / n;
                    double vV = a[3] / n - mV * mV, vG = a[4] / n - mG * mG, cov = a[5] / n - mV * mG;
                    double mse = (a[3] - 2 * a[5] + a[4]) / n;
                    double corr = (vV > 0 && vG > 0) ? cov / sqrt(vV * vG) : 0, slope = vV > 0 ? cov / vV : 0;
                    double r2 = vG > 0 ? 1 - mse / vG : 0;
                    char lab[16]; if (kind) snprintf(lab, sizeof lab, "%d-%d", k * 40, k == 7 ? 9999 : k * 40 + 39); else snprintf(lab, sizeof lab, "%d", k);
                    printf("CALIB %-7s %7.0f %5.1f%% %8.1f %8.1f %+8.1f %8.1f %8.1f %8.1f %6.3f %6.3f %6.3f\n", lab, n, n * 100 / tot, mV, mG, mV - mG, a[6] / n, sqrt(mse), sqrt(vG > 0 ? vG : 0), corr, slope, r2);
                }
            }
            printf("CALIB first move reaching u:");
            for (int k = 5; k <= 10; k++) { long s1 = 0, c = 0; for (int g = 0; g < S->games; g++) if (S->first[g][k] > 0) { s1 += S->first[g][k]; c++; }
                printf(" u%d %.0f (%ld%%)", k, c ? (double)s1 / c : 0, c * 100 / S->games); }
            printf("\n");
        }
        qsort(S->moves, S->games, sizeof(int), cmpi);
        int n = S->games;
        printf("SIM D%d B%d K%d n=%d moves %.1f (p10 %d p50 %d p90 %d max %d) score %.0f best:", S->D, S->B, S->K, n, M / n,
               S->moves[n / 10], S->moves[n / 2], S->moves[n * 9 / 10], S->moves[n - 1], Sc / n);
        for (int k = 7; k <= 10; k++) printf(" %d:%ld", k, B[k]);
        printf("  %.1f ms/move\n", (now_ms() - t0) * th / (double)totm);
        // patch248: 단계 넘어갈 때 새로 죽은 칸 (lo2=1성 죽음(★5) / lo3=2성(★6) / lo4=3성(★7))
        printf("DEAD");
        double tot = 0; int any = 0;
        for (int L = 2; L <= 4; L++) { long c = 0, s1 = 0, nz = 0; for (int g = 0; g < n; g++) if (S->dmade[g][L] >= 0) { c++; s1 += S->dmade[g][L]; if (S->dmade[g][L] > 0) nz++; }
            printf(" s%d %.2f (%ld%% >=1, n%ld)", L + 3, c ? (double)s1 / c : 0, c ? nz * 100 / c : 0, c); tot += c ? (double)s1 / c : 0; }
        for (int g = 0; g < n; g++) { int t = 0; for (int L = 2; L <= 4; L++) if (S->dmade[g][L] > 0) t += S->dmade[g][L]; if (t) any++; }
        long a7 = 0, c7 = 0; for (int g = 0; g < n; g++) if (S->at7[g] > 0) { a7 += S->at7[g]; c7++; }
        printf(" | sum %.2f, games with dead %d%%, star7 at move %.0f\n", tot, any * 100 / n, c7 ? (double)a7 / c7 : 0);
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
        p.dot = 0;
        RD(nx.n); for (int j = 0; j < nx.n; j++) { RD(nx.off[j][0]); RD(nx.off[j][1]); RD(nx.t[j]); }
        nx.dot = 0;
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
