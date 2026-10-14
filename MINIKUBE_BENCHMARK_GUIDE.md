# MiniSWG Kubernetes Deployment & Benchmark Guide

This guide details how to deploy **MiniSWG** to a local Kubernetes cluster (**Minikube**) and run industry-standard performance benchmarks using **Google's `hey`** load generator against a production **NGINX** origin server.

---

## 1. Prerequisites
- **Docker Desktop** installed and running
- **Minikube** installed (`minikube version`)
- **kubectl** installed (`kubectl version --client`)

---

## 2. Start Minikube
In PowerShell:
```powershell
minikube start --driver=docker
```
Verify cluster readiness:
```powershell
kubectl get nodes
```

---

## 3. Build Container Image
Build the `miniswg:latest` image directly inside Minikube's container runtime:
```powershell
minikube image build -t miniswg:latest .
```

---

## 4. Deploy Services
Apply the Kubernetes manifests for the NGINX origin server and MiniSWG gateway:
```powershell
kubectl apply -f k8s/origin.yaml
kubectl apply -f k8s/miniswg.yaml
```

Verify that both pods are running:
```powershell
kubectl get pods
```
*(Wait until both `miniswg-deployment` and `origin-deployment` show `STATUS: Running` and `READY: 1/1`)*.

---

## 5. Run Industry-Standard In-Cluster Benchmark (`hey`)

Run Google's `hey` load generator directly inside the cluster as a transient Pod to eliminate host port-forwarding overhead:

```powershell
# 5,000 requests at 50 concurrency through MiniSWG
kubectl run hey-bench --image=williamyeh/hey --rm -it --restart=Never -- -n 5000 -c 50 -x http://miniswg-service:8080 http://origin-service:8000/
```

### High-Concurrency Stress Test (200 Concurrent Connections)
```powershell
kubectl run hey-stress --image=williamyeh/hey --rm -it --restart=Never -- -n 5000 -c 200 -x http://miniswg-service:8080 http://origin-service:8000/
```

### Direct Baseline Test (Origin Without Gateway)
```powershell
kubectl run hey-baseline --image=williamyeh/hey --rm -it --restart=Never -- -n 5000 -c 50 http://origin-service:8000/
```

---

## 6. View Results
Benchmark reports and full percentile distributions (p50, p90, p95, p99) are documented in:
- [bench/results.md](bench/results.md)
