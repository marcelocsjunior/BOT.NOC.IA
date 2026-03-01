#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from noc_bot.main import main

if __name__ == "__main__":
    main()
