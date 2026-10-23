"""fastcam.py - scrcpy 서버와 직접 통신해서 게임 화면을 실시간(최대 60장/초)으로 받고, 터치를 바로 보냄.
창도 마우스도 쓰지 않음. scrcpy 4.1 의 서버 파일(C:\\scrcpy\\scrcpy-win64-v4.1\\scrcpy-server)을 사용.

  cam = FastCam(); cam.start()
  img, t, n = cam.latest()      # 가장 최근 화면(720x1280 BGR), 받은 시각(perf_counter), 몇 번째 화면인지
  cam.tap(360, 900)             # 손가락 터치
  cam.stop()
"""
import os, socket, struct, subprocess, threading, time, collections

ADB_EXE = r"C:\platform-tools\adb.exe"
SERIAL = __import__("adbport").DEV
SERVER = r"C:\scrcpy\scrcpy-win64-v4.1\scrcpy-server"
VERSION = "4.1"
REMOTE = "/data/local/tmp/scrcpy-server-macro.jar"
SCID = "0e2f0a01"                       # 우리 전용 이름 (scrcpy 창 프로그램과 겹치지 않게)
PORT = 27199
LOG = r"C:\macro\shots\fastcam_server.txt"
FINGER = -2                             # scrcpy 의 '일반 손가락' 포인터 번호
TOUCH = 2                               # 제어 메시지 종류: 터치
DOWN, UP, MOVE = 0, 1, 2


def _adb(*a, timeout=15):
    return subprocess.run([ADB_EXE, "-s", SERIAL, *a], capture_output=True, timeout=timeout)


def _recv_exact(s, n):
    buf = bytearray()
    while len(buf) < n:
        c = s.recv(n - len(buf))
        if not c:
            raise ConnectionError("영상 연결이 끊김")
        buf += c
    return bytes(buf)


class FastCam:
    def __init__(self, max_fps=60, bit_rate=8000000, scid=SCID, port=PORT):
        self.max_fps, self.bit_rate = max_fps, bit_rate
        self.scid, self.port = scid, port              # 여러 모듈이 동시에 쓸 때는 서로 다른 값으로
        self.proc = self.vs = self.cs = None
        self.w, self.h = 720, 1280
        self.img, self.t, self.n = None, 0.0, 0
        self.err = None
        self._lock = threading.Lock()
        self._run = False

    # ------------------------------------------------------------ 시작 / 종료
    def start(self, timeout=8.0):
        import av                                       # 여기서 실패하면 'py -m pip install av'
        self._av = av
        if not os.path.exists(SERVER):
            raise FileNotFoundError(SERVER)
        _adb("push", SERVER, REMOTE)
        _adb("forward", "--remove", f"tcp:{self.port}")
        _adb("forward", f"tcp:{self.port}", f"localabstract:scrcpy_{self.scid}")
        args = [f"scid={self.scid}", "log_level=info", "tunnel_forward=true", "audio=false", "control=true",
                "video_codec=h264", f"max_size=1280", f"max_fps={self.max_fps}",
                f"video_bit_rate={self.bit_rate}", "send_device_meta=false", "send_dummy_byte=true",
                "cleanup=true", "power_off_on_close=false", "clipboard_autosync=false"]
        cmd = f"CLASSPATH={REMOTE} app_process / com.genymobile.scrcpy.Server {VERSION} " + " ".join(args)
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        self._logf = open(LOG, "w", encoding="utf-8", errors="replace")
        self.proc = subprocess.Popen([ADB_EXE, "-s", SERIAL, "shell", cmd],
                                     stdout=self._logf, stderr=subprocess.STDOUT)
        end = time.time() + timeout
        while True:                                     # 서버가 뜰 때까지 반복 연결 (첫 1바이트가 오면 성공)
            if self.proc.poll() is not None:
                raise RuntimeError("scrcpy 서버가 바로 종료됨 -> shots\\fastcam_server.txt 확인")
            s = socket.create_connection(("127.0.0.1", self.port), timeout=2)
            try:
                if s.recv(1):
                    break
            except OSError:
                pass
            s.close()
            if time.time() > end:
                self.stop()
                raise TimeoutError("scrcpy 서버 연결 실패")
            time.sleep(0.1)
        self.vs = s
        self.vs.settimeout(None)
        self.cs = socket.create_connection(("127.0.0.1", self.port), timeout=3)
        self.cs.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        codec = _recv_exact(self.vs, 4)
        if codec != b"h264":
            raise RuntimeError(f"예상과 다른 영상 형식 {codec!r}")
        self._run = True
        threading.Thread(target=self._reader, daemon=True).start()
        end = time.time() + timeout
        while self.img is None and self.err is None and time.time() < end:
            time.sleep(0.02)
        if self.img is None:
            self.stop()
            raise TimeoutError(f"첫 화면을 받지 못함 ({self.err})")
        return self

    def stop(self):
        self._run = False
        for s in (self.vs, self.cs):
            try:
                if s:
                    s.close()
            except OSError:
                pass
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        try:
            _adb("forward", "--remove", f"tcp:{self.port}", timeout=5)
        except Exception:
            pass

    def __enter__(self):
        return self.start()

    def __exit__(self, *a):
        self.stop()

    # ------------------------------------------------------------ 화면
    def _reader(self):
        av = self._av
        try:
            ctx = av.CodecContext.create("h264", "r")
            try:
                ctx.thread_type = "SLICE"               # 프레임 단위 멀티스레드는 지연이 생기므로 사용 안 함
            except Exception:
                pass
            try:
                ctx.flags |= av.codec.context.Flags.low_delay
            except Exception:
                pass
            config = b""
            offs = collections.deque(maxlen=90)         # patch143: (받은 시각 - 기기 촬영 시각) 최근 값들
            while self._run:
                head = _recv_exact(self.vs, 12)
                if head[0] & 0x80:                      # 세션 정보 (화면 크기)
                    self.w, self.h = struct.unpack(">II", head[4:12])
                    continue
                pts_flags, size = struct.unpack(">QI", head)
                data = _recv_exact(self.vs, size)
                t_recv = time.perf_counter()
                if pts_flags & (1 << 62):               # 설정 묶음 -> 다음 화면과 합쳐서 해독
                    config = data
                    continue
                if config:
                    data, config = config + data, b""
                pts = (pts_flags & ((1 << 61) - 1)) / 1e6   # 기기에서 화면을 찍은 시각(초)
                for fr in ctx.decode(av.Packet(data)):
                    img = fr.to_ndarray(format="bgr24")
                    t_done = time.perf_counter()
                    # patch143: 화면 시각 = 기기 촬영 시각 + (가장 빨리 도착한 화면들의 지연).
                    #           받은 시각을 그대로 쓰면 화면이 몰려 올 때 시각이 틀어져 과녁 속도를 잘못 계산함
                    t_img = t_done
                    if pts > 0:
                        offs.append(t_done - pts)
                        t_img = min(t_done, pts + min(offs))
                    with self._lock:
                        self.img, self.t, self.n = img, t_img, self.n + 1
                        self.t_recv = t_recv
        except Exception as e:
            if self._run:
                self.err = repr(e)

    def latest(self):
        with self._lock:
            return self.img, self.t, self.n

    def wait_new(self, n_prev, timeout=1.0):
        """n_prev 다음 화면이 올 때까지 기다림 -> (img, t, n) 또는 None"""
        end = time.perf_counter() + timeout
        while time.perf_counter() < end:
            img, t, n = self.latest()
            if n > n_prev:
                return img, t, n
            time.sleep(0.002)
        return None

    # ------------------------------------------------------------ 터치
    def touch(self, action, x, y):
        msg = struct.pack(">BBqiiHHHii", TOUCH, action, FINGER, int(x), int(y), self.w, self.h,
                          0xFFFF if action != UP else 0, 0, 0)
        self.cs.sendall(msg)

    def tap(self, x, y, hold=0.03):
        """누른 시각(perf_counter)을 돌려줌"""
        t = time.perf_counter()
        self.touch(DOWN, x, y)
        time.sleep(hold)
        self.touch(UP, x, y)
        return t
