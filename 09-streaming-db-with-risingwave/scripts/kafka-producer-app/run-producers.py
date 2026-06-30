import subprocess
import os

current_directory = os.path.dirname(os.path.realpath(__file__))

process1 = subprocess.Popen(['python3', os.path.join(current_directory, 'energy-consumed.py')])
process2 = subprocess.Popen(['python3', os.path.join(current_directory, 'energy-produced.py')])

process1.wait()
process2.wait()
