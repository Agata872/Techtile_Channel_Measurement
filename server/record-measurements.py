# ****************************************************************************************** #
#                                       IMPORTS / PATHS                                      #
# ****************************************************************************************** #

# *** Includes ***
from TechtileScope import Scope
from Positioner import PositionerClient
from TechtilePlotter.TechtilePlotter import TechtilePlotter

import os
from yaml_utils import read_yaml_file
from time import sleep, time
import numpy as np
import zmq

# Get the current directory of the script
server_dir = os.path.dirname(os.path.abspath(__file__))

config = read_yaml_file("config.yml")
scope = Scope(config=config["scope"])
positioner = PositionerClient(config=config["positioning"], backend="zmq")


positioner.start()


script_started = time()

context = zmq.Context()

iq_socket = context.socket(zmq.PUB)

iq_socket.bind(f"tcp://*:{50001}")


def wait_till_go_from_server(ip="10.128.52.53"):

    global meas_id, file_open, data_file, file_name
    # Connect to the publisher's address
    print("Connecting to server %s.", ip)
    sync_socket = context.socket(zmq.SUB)
    sync_socket.connect(f"tcp://{ip}:{5557}")
    # Subscribe to topics
    sync_socket.subscribe("")

    # Receives a string format message
    print("Waiting on SYNC from server %s.", ip)

    meas_id, unique_id = sync_socket.recv_string().split(" ")

    print(meas_id)

    sync_socket.close()

    return meas_id, unique_id


TIME_TO_MEAS_PER_EXP = 5.0

counter = 0

try:
    while True:
        plt = TechtilePlotter(realtime=True)
        meas_id, unique_id = wait_till_go_from_server()
        sleep(29.0)  # wake-up 10 seconds before rover starts to move

        # start to measure for XX long
        start = time()

        positions = []
        values = []

        while time() - start < TIME_TO_MEAS_PER_EXP:

            power_dBm = scope.get_power_dBm()
            pos = positioner.get_data()

            if pos is not None:
                print(power_dBm)
                positions.append(pos)
                print(pos)
                values.append(power_dBm)
                plt.measurements_rt(pos.x, pos.y, pos.z, power_dBm)
            sleep(0.1)
        counter+= 1
        meas_name = f"gausbf-ceiling-grid-{meas_id}-{unique_id}-{counter}"
        np.save(arr=positions, file=f"../data/positions-{meas_name}")
        np.save(arr=values, file=f"../data/values-{meas_name}")
finally:
    print("Ctrl+C pressed. Exiting loop and saving...")
    meas_name = f"gausbf-ceiling-grid-{meas_id}-{unique_id}-{counter}"
    np.save(arr=positions, file=f"../data/positions-{meas_name}")
    np.save(arr=values, file=f"../data/values-{meas_name}")
    positioner.stop()
