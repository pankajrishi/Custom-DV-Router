# 🚀 Distance Vector Router using Python & Docker

## 📌 Overview
This project implements a custom Distance Vector Routing Protocol (similar to RIP) using Python and Docker containers. Each container acts as a router and communicates with neighbors using UDP sockets to dynamically compute the shortest path between networks using the Bellman-Ford algorithm.

## 🎯 Features
- Distance Vector Routing (Bellman-Ford)
- Dynamic routing table updates
- UDP-based router communication
- Docker-based network simulation
- Multi-hop routing support
- Fault tolerance (node failure handling)
- Clean and readable logs

## 🧠 Concepts Used
- Distance Vector Routing Protocol
- Bellman-Ford Algorithm
- UDP Socket Programming
- Docker Networking
- Routing Tables & Subnetting

## 🏗️ Network Topology
Triangle topology with 3 routers:

        (10.0.3.0/24)
        A -------- C
         \        /
          \      /
           \    /
        (10.0.1.0/24)
             B
        (10.0.2.0/24)

Router Connections:
- Router A → 10.0.1.0/24, 10.0.3.0/24
- Router B → 10.0.1.0/24, 10.0.2.0/24
- Router C → 10.0.2.0/24, 10.0.3.0/24

## ⚙️ Setup Instructions

### 1. Build Docker Image
```bash
docker build -t my-router .
```

### 2. Create Networks
```bash
docker network create --subnet=10.0.1.0/24 net_ab
docker network create --subnet=10.0.2.0/24 net_bc
docker network create --subnet=10.0.3.0/24 net_ac
```

### 3. Run Routers

#### Router A
```bash
docker run -d --name router_a --privileged --network net_ab --ip 10.0.1.2 -e MY_IP=10.0.1.2 -e NEIGHBORS=10.0.1.3,10.0.3.2 my-router
docker network connect net_ac router_a --ip 10.0.3.3
```

#### Router B
```bash
docker run -d --name router_b --privileged --network net_ab --ip 10.0.1.3 -e MY_IP=10.0.1.3 -e NEIGHBORS=10.0.1.2,10.0.2.2 my-router
docker network connect net_bc router_b --ip 10.0.2.3
```

#### Router C
```bash
docker run -d --name router_c --privileged --network net_bc --ip 10.0.2.2 -e MY_IP=10.0.2.2 -e NEIGHBORS=10.0.2.3,10.0.3.3 my-router
docker network connect net_ac router_c --ip 10.0.3.2
```

## 📊 How It Works

### Initialization
Each router adds:
- Its own network → distance 0
- Neighbor networks → distance 1

### Communication
- Routers send updates every 5 seconds
- Uses UDP on port 5000

### Route Update Logic
new_distance = neighbor_distance + 1

Update happens if:
- Route is new
- OR shorter path is found

## 🛠️ Key Improvements
- Own Network Protection (router never updates its own network)
- Correct Neighbor Handling (direct neighbor distance = 1)
- Clean Logging (only initial and updated tables printed)
- Stable updates (no unnecessary recalculations)

## 📈 Example Output

Initial Routing Table (Router A):
10.0.1.0/24 -> Distance: 0, Next Hop: 0.0.0.0
10.0.3.0/24 -> Distance: 1, Next Hop: 10.0.3.2

After Convergence:
10.0.2.0/24 -> Distance: 2, Next Hop: 10.0.1.3

## 🧪 Failure Testing

Stop Router C:
```bash
docker stop router_c
```

Result:
- Routers remain stable
- No crashes
- Routes remain consistent

## 📷 Suggested Screenshots
- docker ps
- Initial routing tables
- Updated routing tables
- Failure scenario

## ⚠️ Limitations
- No full Split Horizon implementation
- No route timeout mechanism

## 📚 Future Improvements
- Add Split Horizon
- Add route timeout
- Improve logging
- Add CLI for debugging

## 👨‍💻 Author
Pankaj Rishi

## 📌 Note
This project is part of an academic assignment on Distance Vector Routing Protocol using Docker.
