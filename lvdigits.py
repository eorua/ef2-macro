"""lvdigits.py - 무한랭킹전 상대 레벨 숫자 인식 (템플릿 내장)"""
import cv2, numpy as np, base64, zlib

_BLOB = "0:3:eNrdjzsRwzAQBR8Y0TAAYzAGYYgxCIABCMBhMAYJgAEEwEafyUguUqRJkat2Ru+d9iQJovosBpfZUnA9CGU4VimC3rmJ89NcZWdx7IgpDIbvOIV556d/b27NGZpze++5OjvsDTazBMlskx5whnCWhneB7CWfYdR+zLPD7Face7I631t/edcLaQ5BEw==|2:1:eNp1jqERwCAQBE9H0wNFRGMpJxYsOvqLoAeKwKJTxAV4MhGZrNq5v5t5AJwAEBF18SMsnUYG6BWRjOBphxvb8+SgdF9s5vXZV3KlnztYz5q/BQSuoUup8Nif8Krf8viqFYU/3NYSYTo=|3:7:eNrtkdENwzAIRBnGy2SGzMAMzQyeoTMwQ2Yow1AcKGCpqfodhY/onHDnewoAiM4GY1Ya+kW0ApJ0nV3kAcw8viKrjnGL6Xi/dNOLzlM0ByxfxDeLrjvuJczMz5rp7NCbHqMb0eisz7irum6u63ARZubs+qKjWyudt2SZtO0Qpfc8v3ao3WrnieWcS/bkYvyby/TRWaOCxa+ouo0/5js/MivXoZ2r95vrMlxv/51ybw==|4:6:eNrd0q9rxDAUB/C4wfSpwVyhejA39gfU1PWPmKitGiQwFTu/s4OqzlQczIy5g+rA6aq4joO67/Kzr+x6rPqeCB/S9OU98hizUQCoGfvr9JlcY9HVi5TeVxsUjHmbHDPnN8H3EvYfZ5MjWo/Wuba2maVszKqkCgEMKhTHqM419nW4ePok2/oXrIbotELTBBfQeTF5ylntyXX/Qab+9Thq5+Ftoa8e6JU6qXOVbTYxM3e6fSAL0BmOab/aQX47X29w1PYTd4dFXDnylPn9/B3hd25vCWlFsD7CZHBtSXcBwnOZPR3fS1Cd4a5Tz86cmcNs++8cHn7axPvuFdtsmr32keaQZmPm+iuLLruutAF0Jc5EEgJok/VzeKnvdXl9/QK5gD79|5:13:eNrtlK1uwzAQxw8PTVPRsKVIw5MG+gQhwZUqDYz7EabkGUKGjINLjAMGisomVTXZcFXW4psvts9O2m7VWLsecH9qLr775z6gQjYoe1wHswxsVcLJ//U8+OegV4grTWdJ/lgdOoNRrISFEMz8yLGRANJYkBpxXtuIqCVMtQ839en5y1lXBVFXCVFXDqLGY2mk7D9Cx1pTuFwEny5cyn/QRWR11cLqokjzLs9fdV1qvf5NH747e+lpWa6P9uHI2Q3Er1NB0WBhrenunMzIdTLDpjilsbMsO6hxrHxuqMZQKPdUFT3PNIfIJTHr+iH0vq70TsuFswZnk+BqdZVJvdLa7dYHdI0yXC8Hc0qJfVGeSnW6FirqqqCna8/a0IdU+iRc5FbcMn8G7wfy+dC6tT+vufMX4U7m8J4csLiPjDrhnXlm9rm1+CZpQent1h6PztkYGPYhNWpSL56XE+s12If25H3I/ZB+UjKR29Hozddd4I1hN3p3Y/w+LIH3oXyK+5DHf3++LknXdb7Oa76u9Tqven0DOtE46w==|6:22:eNrtlq1uwzAQx40Hq9CxSMNDA9EeICSs0qSgPUBopKGGjpp7qNKkshKD4oKi4ipGQwVT0R7gdmc7dpp2bRdNmrL5pKY/qffhf+58KmPaKjDfEq3WfFcAAOeceAKwU6zxhMqi2kE8smycyVJiqCkPTFPiSkcZa7ELvIRjDqqwTOdZUSmQBct1IQCZN8drov6wLsdCCMvXCbwt0TpaMOdNZLFckGdZliZDFEX0vGIAXgU+Mm2wmX9Xy+bds3vzRtdSG4iEZcJEiayboa0L22W51S96V0p1PA/5SL8mzPeo2udp6rVMfBLg8Sm9hUKHQupaKx14bg5tR3J7HsphwrH+KD46h/je3BwiO13ptP8c4mx/1SM/h/jO3RxiL/7xHJ7VhbWcLuNZJszreo6O63oFr+th3mNvtDkRl+oK+3BY/Qr7MOzDsA+Htw9P3K9++xDvl9uHeL9+63/vz+miq9fowovf1YXl8oPrz9gYYNwIW1uOUVjN+a35XSnufF0Y33qeNcIeNcOaNuvM8JiOts9yaw9NcbVn/TnB6kPGLH3RtXROdi8pl5RP7hws9Gug/Qr7cFj7MPRrKP36BAuv1yc=|7:3:eNr7/x87mAQDt25NYoAClW2rYEyG//+xsQ0n/Z/nCWWH/v8fyoCfXXnuP9yQVf//I+z5fJtSe3B46/8RGHj9+gjCboQdNz5hs49d5P+nufj9YtL5f6M1pl9Q2RfLYEz17djscTyCYAPN3ps5YvwFAACD1RE=|8:1:eNpNj1ERwCAMQyNmZtCABjQMDWiYhmqYBiYmS487yPt6R5teAEDRkdRInxEVLTjES965kNP2HVeqm+/3MuQxWcRD3UHnIqfmvnOy0c7NnXJXh3F5N+8M+8sPzSVvaw==|9:4:eNrtUEERwzAME4ZiCIdhCIZiCIYWgzEUgzEEQ4phGDQ76ZLdrnfrd3fVS6cotmQAWMkVjlm1kEWNJqUYMtMDJP017VzeHLAvg3/qWQavOOVx80W+bouI0mBzDkxh8B4P2J8ME5qfmlxa6pz524mzXmbrvUZm6yXhSuYr/MhTqth7ZfnZq+lupt/cp9kc1X7tu9c/9noBnbF6tw=="
_T = None
ROWY = [702, 825, 947]


def _load():
    global _T
    if _T is None:
        _T = {}
        for part in _BLOB.split("|"):
            ch, n, b = part.split(":")
            a = np.frombuffer(zlib.decompress(base64.b64decode(b)), np.uint8)
            _T[ch] = a.reshape(int(n), 18, 12).astype(np.float32) / 255
    return _T


def _comps(img, y):
    roi = img[y - 16:y + 16, 170:560]
    mn = roi.min(axis=2)
    mask = ((roi[..., 2] > 190) & (roi[..., 1] > 150) & (mn > 110)).astype(np.uint8) * 255
    n, lab, st, cen = cv2.connectedComponentsWithStats(mask, connectivity=8)
    cs = []
    for i in range(1, n):
        x, yy, w, h, a = st[i]
        if a < 6:
            continue
        cs.append((x, yy, w, h, a, i))
    cs.sort()
    return lab, cs


def _tail_digits(img, y):
    lab, cs = _comps(img, y)
    if len(cs) < 4:
        return None
    digs = []
    for x, yy, w, h, a, i in reversed(cs[:-1]):
        if h <= 11 and w >= 7:
            break
        digs.append((x, yy, w, h, a, i))
        if len(digs) > 3:
            return None
    digs.reverse()
    out = []
    for x, yy, w, h, a, i in digs:
        g = (lab[yy:yy + h, x:x + w] == i).astype(np.uint8) * 255
        out.append((g, w, h))
    return out


def _classify(g, w, h):
    if w <= 5:
        return "1", 1.0
    x = cv2.resize(g, (12, 18), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    best = ("?", -1.0)
    for k, T in _load().items():
        for t in T:
            sc = float((x * t).sum() / (np.linalg.norm(x) * np.linalg.norm(t) + 1e-6))
            if sc > best[1]:
                best = (k, sc)
    return best


def read_level(img, y):
    """name line y 의 'Lv.NN' 숫자를 정수로. 못 읽으면 None"""
    td = _tail_digits(img, y)
    if not td or len(td) < 1:
        return None
    s = ""
    for g, w, h in td:
        c, sc = _classify(g, w, h)
        if sc < 0.6:
            return None
        s += c
    try:
        return int(s)
    except ValueError:
        return None


def read_levels(img):
    return [read_level(img, y) for y in ROWY]
