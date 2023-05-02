import random, time, sys, secrets
import numpy as np
rng = np.random.default_rng()


gP1 = lambda: random.SystemRandom().randint(1000, 9999)
#gP2 = lambda: secrets.randbelow(9000) + 1000
gP2 = lambda: rng.integers(1000, 9999)

def f_(pinT, range_):
    def force():
        for i in range(1000, 10000): yield i
    start = time.time()
    for _ in range(range_):
        pin = pinT()
        for trypin in force():
            if pin == trypin: print("Found PIN: %d" % trypin)
        end = time.time()
    return end - start

gP1_res, gP2_res = f_(gP1, int(sys.argv[1])), f_(gP2, int(sys.argv[1]))
print("sys random \t random")
print("%f\t%f" % (gP1_res, gP2_res))
print("Difference (2 - 1) : %f" % (gP1_res - gP2_res))
#difference in percent
print("Difference in percent: %f" % ((gP2_res - gP1_res) / gP1_res * 100))