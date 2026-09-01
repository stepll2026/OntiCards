#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from environs import Env


env = Env()
env.read_env()

def get(key, default = None):
    return env.str(key) if env.str(key) else default

if __name__ == '__main__':
    pass
