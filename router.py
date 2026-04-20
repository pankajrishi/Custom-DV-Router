import socket
import threading
import time
import os
import json

MY_IP = os.environ.get("MY_IP")
NEIGHBORS = os.environ.get("NEIGHBORS").split(",")

PORT = 5000

routing_table = {}
last_updated = {}
lock = threading.Lock()

INFINITY = 999
TIMEOUT = 15  # seconds


def get_network(ip):
    return ".".join(ip.split(".")[:3]) + ".0/24"


def print_table(title="Routing Table"):
    print(f"\n{title}:")
    for dest in sorted(routing_table):
        dist, hop = routing_table[dest]
        if dist >= INFINITY:
            continue
        print(f"{dest} -> Distance: {dist}, Next Hop: {hop}")
    print("-" * 40)


def init_table():
    my_net = get_network(MY_IP)

    routing_table[my_net] = [0, "0.0.0.0"]
    last_updated[my_net] = time.time()

    for n in NEIGHBORS:
        net = get_network(n)
        if net != my_net:
            routing_table[net] = [1, n]
            last_updated[net] = time.time()

    print_table("Initial Routing Table")


# ✅ Split Horizon + Poison Reverse
def prepare_update_for_neighbor(neighbor):
    poisoned_table = {}

    for dest in routing_table:
        dist, hop = routing_table[dest]

        # Poison reverse: if route learned from this neighbor, advertise as infinity
        if hop == neighbor:
            poisoned_table[dest] = [INFINITY, hop]
        else:
            poisoned_table[dest] = [dist, hop]

    return poisoned_table


def send_updates():
    while True:
        time.sleep(5)

        for n in NEIGHBORS:
            try:
                table_to_send = prepare_update_for_neighbor(n)
                data = json.dumps(table_to_send)

                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.sendto(data.encode(), (n, PORT))
                s.close()
            except:
                pass


def receive_updates():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((MY_IP, PORT))

    my_net = get_network(MY_IP)

    while True:
        data, addr = s.recvfrom(4096)
        neighbor_ip = addr[0]
        neighbor_table = json.loads(data.decode())
        neighbor_net = get_network(neighbor_ip)

        updated = False

        with lock:
            for dest in neighbor_table:

                if dest == my_net:
                    continue

                neighbor_dist = neighbor_table[dest][0]

                # Ignore infinite routes
                if neighbor_dist >= INFINITY:
                    continue

                # Distance calculation
                if dest == neighbor_net:
                    new_dist = 1
                else:
                    new_dist = neighbor_dist + 1

                # Update condition
                if (dest not in routing_table) or (new_dist < routing_table[dest][0]):
                    routing_table[dest] = [new_dist, neighbor_ip]
                    # last_updated[dest] = time.time()
                    last_updated[dest] = time.time()
                    last_updated[neighbor_net] = time.time()
                    updated = True

        if updated:
            print_table("Updated Routing Table")


# ✅ Route timeout handling
def monitor_routes():
    while True:
        time.sleep(5)

        current_time = time.time()
        updated = False

        with lock:
            for dest in list(routing_table.keys()):
                if routing_table[dest][0] == 0:
                    continue  # skip own network

                if current_time - last_updated.get(dest, 0) > TIMEOUT:
                    routing_table[dest][0] = INFINITY
                    updated = True

        if updated:
            print_table("Updated Routing Table (After Timeout)")


def main():
    init_table()

    threading.Thread(target=send_updates, daemon=True).start()
    threading.Thread(target=receive_updates, daemon=True).start()
    threading.Thread(target=monitor_routes, daemon=True).start()

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()