import simpy
def waitfewtimes(env):
    for i in range(1, 5):
        env.process(mywait(env, 10))
        env.process(mywait(env, 5))
        print(f'now (loop): {env.now}')

def mywait(env,t):
    yield env.timeout(t)



env = simpy.Environment()
waitfewtimes(env)
env.run()

