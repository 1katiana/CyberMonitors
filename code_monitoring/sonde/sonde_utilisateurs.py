#!/usr/bin/env python3

import psutil

nombre_utilisateurs = len(psutil.users())

print(nombre_utilisateurs)
