# IIS + ARR server farm for JAN-DRISHTI AI

The site-level behaviour lives in [`web.config`](web.config). The **farm itself**
(which replicas exist, health test, load-balancing algorithm) lives in
`applicationHost.config` - it is a server-level section, so it cannot be set
from a site `web.config`.

## 1. Create the farm (PowerShell, as Administrator)

```powershell
Import-Module WebAdministration

# Application pool the farm children run under
New-WebAppPool -Name "jan_drishti_pool"

# The farm. loadBalanceAlgorithm options:
#   WeightedRoundRobin | LeastRequests | LeastResponseTime | WeightedTotalTraffic | RequestHash
New-WebFarm -Name "jan_drishti_farm" -Port 80

Add-WebFarmServer -WebFarm "jan_drishti_farm" -Address "127.0.0.1:8001"
Add-WebFarmServer -WebFarm "jan_drishti_farm" -Address "127.0.0.1:8002"
Add-WebFarmServer -WebFarm "jan_drishti_farm" -Address "127.0.0.1:8003"
Add-WebFarmServer -WebFarm "jan_drishti_farm" -Address "127.0.0.1:8004"

# LeastRequests matches the CPU-bound analysis pipeline best: send work to the
# replica with the fewest requests in flight.
Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' `
  -Filter "webFarms/webFarm[@name='jan_drishti_farm']" -Name "loadBalanceAlgorithm" -Value "LeastRequests"

# Active health test against the app's own probe (never rate limited or shed)
Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' `
  -Filter "webFarms/webFarm[@name='jan_drishti_farm']/applicationRequestRouting/protocol/healthCheck" `
  -Name "url" -Value "/health"
Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' `
  -Filter "webFarms/webFarm[@name='jan_drishti_farm']/applicationRequestRouting/protocol/healthCheck" `
  -Name "interval" -Value "00:00:10"
Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' `
  -Filter "webFarms/webFarm[@name='jan_drishti_farm']/applicationRequestRouting/protocol/healthCheck" `
  -Name "responseMatch" -Value "status:ok"
Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' `
  -Filter "webFarms/webFarm[@name='jan_drishti_farm']/applicationRequestRouting/protocol/healthCheck" `
  -Name "timeout" -Value "00:00:05"

# No client affinity: sessions are HMAC-signed tokens valid on every replica.
# (ClientAffinity must stay OFF, or the load spread in the dashboard will be
# skewed and a dead replica would strand its sticky clients.)
Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' `
  -Filter "webFarms/webFarm[@name='jan_drishti_farm']/applicationRequestRouting/affinity" `
  -Name "clientAffinity" -Value "None"

# Cache + proxy buffer tuning
Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' `
  -Filter "webFarms/webFarm[@name='jan_drishti_farm']/applicationRequestRouting/proxy" `
  -Name "preserveHostHeader" -Value "True"

# Enable the proxy at server level
Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' `
  -Filter "system.webServer/proxy" -Name "enabled" -Value "True"
```

## 2. Start the replicas

```bat
set JAN_DRISHTI_INSTANCE_ID=node-1
set JAN_DRISHTI_SECRET_KEY=<shared 32+ byte secret>
set JAN_DRISHTI_PROXY_LAYER=iis
set JAN_DRISHTI_CLUSTER_NODES=http://127.0.0.1:8001,http://127.0.0.1:8002,http://127.0.0.1:8003,http://127.0.0.1:8004
python -m jan_drishti.server --host 127.0.0.1 --port 8001
```

Repeat with `--port 8002`, `8003`, `8004` and a distinct
`JAN_DRISHTI_INSTANCE_ID`. The bundled helper does it in one command:

```bat
python scripts\start_cluster.py --nodes 4 --base-port 8001
```

## 3. Verify

```powershell
# Each replica answers its own health probe
1..4 | ForEach-Object { Invoke-WebRequest "http://127.0.0.1:800$($_)/health" }

# The farm spreads requests (X-Served-By shows which replica answered)
1..8 | ForEach-Object { (Invoke-WebRequest "http://localhost/" -UseBasicParsing).Headers["X-Served-By"] }
```

Then open the **Scalability** page in the dashboard - the replica table, traffic
share bars and the autoscaler recommendation are computed from the same
`/api/scalability` endpoint, so what you see there is the farm's behaviour.

## 4. Scaling out and in on IIS

* **Add capacity**: start another replica on port `8005` and
  `Add-WebFarmServer -WebFarm "jan_drishti_farm" -Address "127.0.0.1:8005"`.
  ARR picks it up immediately, no restart.
* **Drain a replica**: ARR Management console -> *Server Farms* ->
  `jan_drishti_farm` -> server -> **Make server unavailable**. In-flight
  analysis finishes; the dashboard shows its in-flight count drop to 0, then you
  can stop the process.
* **Autoscale**: `/api/metrics` exposes the exact numbers the autoscaler needs -
  `jan_drishti_cluster_p95_ms` and `jan_drishti_cluster_requests_per_sec`.
  Point Azure Monitor / a scheduled PowerShell script at those thresholds
  (`JAN_DRISHTI_TARGET_P95_MS`, `JAN_DRISHTI_RPS_PER_NODE`) and start or stop
  replicas accordingly.
