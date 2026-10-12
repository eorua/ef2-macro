# reset_high.py - state.json 의 high_done 을 false 로 (메인을 끈 상태에서 실행)
import os
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
b = open(p, "rb").read()
n = b.count(b'"high_done": true')
if n != 1:
    print("high_done 이 true 가 아니거나 형식이 다름:", n)
else:
    open(p, "wb").write(b.replace(b'"high_done": true', b'"high_done": false').replace(b'"high_fails": 3', b'"high_fails": 0'))
    print("high_done = false 로 바꿨습니다")
