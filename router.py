import socket
import threading
import time
import os
import json
import subprocess
import ipaddress

# Configuration constants
PORT = 5000
INFINITY = 16
UPDATE_INTERVAL = 1  # 1 second periodic update
TIMEOUT = 4          # 4 seconds route expiration

# Environment variables
MY_IP = os.environ.get("MY_IP", "0.0.0.0")
NEIGHBORS_RAW = os.environ.get("NEIGHBORS", "").split(",")
NEIGHBORS = [n.strip() for n in NEIGHBORS_RAW if n.strip()]

# Global state
routing_table = {}  # subnet -> [distance, next_hop]
last_updated = {}   # subnet -> timestamp
lock = threading.Lock()

def get_local_subnets():
    """Identifies directly connected subnets using the 'ip' command."""
    subnets = []
    try:
        # Run 'ip -o -4 addr show' to get local addresses and subnets
        output = subprocess.check_output(["ip", "-o", "-4", "addr", "show"]).decode()
        for line in output.splitlines():
            parts = line.split()
            # Format: 'index: name inet addr/mask ...'
            if len(parts) >= 4 and parts[2] == 'inet':
                addr_with_mask = parts[3]
                if not addr_with_mask.startswith("127."):  # Ignore loopback
                    subnets.append(ipaddress.ip_network(addr_with_mask, strict=False))
    except Exception as e:
        print(f"Error identifying local subnets: {e}")
    return subnets

LOCAL_SUBNETS = []

def refresh_local_config():
    """Identifies directly connected subnets and updates the routing table."""
    global LOCAL_SUBNETS
    new_subnets = get_local_subnets()
    with lock:
        for net in new_subnets:
            net_str = str(net)
            # If it's a new local subnet or was previously learned/infinite, set to distance 0
            if net_str not in routing_table or routing_table[net_str][0] != 0:
                print(f"Detected local subnet: {net_str}")
                routing_table[net_str] = [0, "0.0.0.0"]
                last_updated[net_str] = time.time()
        LOCAL_SUBNETS = new_subnets

def is_directly_connected(sender_ip):
    """Rule 1: Check if the incoming packet is from a directly connected subnet."""
    try:
        ip_obj = ipaddress.ip_address(sender_ip)
        for subnet in LOCAL_SUBNETS:
            if ip_obj in subnet:
                return True
    except:
        pass
    return False

def sync_kernel(subnet, distance, next_hop):
    """Rule 5: Mirror internal routing changes to the Linux kernel."""
    try:
        if distance >= INFINITY:
            # Delete route if it's infinity or timed out
            subprocess.run(["ip", "route", "del", subnet], capture_output=True)
            print(f"Kernel: Deleted route {subnet}")
        else:
            if next_hop != "0.0.0.0":
                # Add or replace route via neighbor
                subprocess.run(["ip", "route", "replace", subnet, "via", next_hop], capture_output=True)
                print(f"Kernel: Replaced route {subnet} via {next_hop}")
    except Exception as e:
        print(f"Error syncing kernel: {e}")

def broadcast_updates():
    """Rule 3: Periodic and Triggered updates with Poison Reverse."""
    with lock:
        # Create a snapshot for broadcasting
        table_snapshot = {k: list(v) for k, v in routing_table.items()}
    
    for neighbor in NEIGHBORS:
        try:
            update_packet = {}
            for dest, (dist, hop) in table_snapshot.items():
                # Poison Reverse: If we route to 'dest' through 'neighbor', advertise distance 16
                if hop == neighbor:
                    update_packet[dest] = [INFINITY, hop]
                else:
                    update_packet[dest] = [dist, hop]
            
            data = json.dumps(update_packet).encode()
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.sendto(data, (neighbor, PORT))
        except Exception:
            pass

def periodic_broadcast():
    """Sends routing updates every UPDATE_INTERVAL seconds."""
    while True:
        broadcast_updates()
        time.sleep(UPDATE_INTERVAL)

def listen_for_updates():
    """Listens for RIP updates and applies the Bellman-Ford algorithm."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('0.0.0.0', PORT))
        while True:
            data, addr = s.recvfrom(4096)
            sender_ip = addr[0]
            
            # Rule 1: Neighbor Validation (Prevent Ghost Updates)
            if not is_directly_connected(sender_ip):
                continue
                
            try:
                neighbor_table = json.loads(data.decode())
            except:
                continue
            
            triggered_broadcast = False
            with lock:
                for dest, (dist, _) in neighbor_table.items():
                    # Rule 4: Logic for Triggered Updates below
                    
                    # Do not update or overwrite routes to our own directly connected networks
                    is_local = False
                    for net in LOCAL_SUBNETS:
                        if dest == str(net):
                            is_local = True
                            break
                    if is_local:
                        continue
                    
                    new_dist = min(dist + 1, INFINITY)
                    
                    if dest not in routing_table:
                        # New route discovered
                        if new_dist < INFINITY:
                            routing_table[dest] = [new_dist, sender_ip]
                            last_updated[dest] = time.time()
                            sync_kernel(dest, new_dist, sender_ip)
                            triggered_broadcast = True
                    else:
                        cur_dist, cur_hop = routing_table[dest]
                        
                        # Bellman-Ford algorithm with split updates
                        if sender_ip == cur_hop:
                            # Update from current next hop - always trust it (even if distance increases)
                            if cur_dist != new_dist:
                                routing_table[dest] = [new_dist, sender_ip]
                                sync_kernel(dest, new_dist, sender_ip)
                                triggered_broadcast = True
                            last_updated[dest] = time.time()
                        elif new_dist < cur_dist:
                            # Update from a different neighbor only if it provides a shorter path
                            routing_table[dest] = [new_dist, sender_ip]
                            last_updated[dest] = time.time()
                            sync_kernel(dest, new_dist, sender_ip)
                            triggered_broadcast = True
            
            # Rule 4: Immediate broadcast on change
            if triggered_broadcast:
                broadcast_updates()

def monitor_timeouts():
    """Rule 2: Handles route expiration after TIMEOUT seconds."""
    while True:
        time.sleep(0.5)  # Fine-grained check
        now = time.time()
        timed_out = False
        
        with lock:
            for dest in list(routing_table.keys()):
                # Skip direct networks
                is_local = False
                for net in LOCAL_SUBNETS:
                    if dest == str(net):
                        is_local = True
                        break
                if is_local:
                    continue
                
                # Check for timeout
                if now - last_updated.get(dest, 0) > TIMEOUT:
                    if routing_table[dest][0] != INFINITY:
                        print(f"Route to {dest} timed out.")
                        routing_table[dest][0] = INFINITY
                        sync_kernel(dest, INFINITY, routing_table[dest][1])
                        timed_out = True
        
        if timed_out:
            broadcast_updates()

def main():
    # Wait a moment for Docker to attach all networks
    time.sleep(2)
    refresh_local_config()
    
    print(f"Router daemon started on {MY_IP}")
    with lock:
        print(f"Direct subnets detected: {[str(s) for s in LOCAL_SUBNETS]}")
    print(f"Neighbors configured: {NEIGHBORS}")
    
    # Start threads
    threading.Thread(target=periodic_broadcast, daemon=True).start()
    threading.Thread(target=listen_for_updates, daemon=True).start()
    threading.Thread(target=monitor_timeouts, daemon=True).start()
    
    # Keep main thread alive and periodically refresh local config
    while True:
        time.sleep(5)
        refresh_local_config()
if __name__ == "__main__":
    main()
