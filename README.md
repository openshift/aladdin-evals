# Aladdin Evaluations

Starter evaluation configuration for testing your Aladdin API endpoint.

## Setup

### Configure the cluster

#### Install aladdin front/backend

Follow the steps in https://github.com/bparees/aladdin-install/blob/main/README.md to install aladdin front + backends on a cluster

#### Add a new user to the cluster

kubeadmin is a special user that doesn't have a token, we need a token to supply to lightspeed-evals, so we're going to setup the htpasswd identity provider and add a new user to the cluster.

```bash
htpasswd -c -B -b users.htpasswd user1 <somepassword>

oc create secret generic htpass-secret --from-file=htpasswd=users.htpasswd -n openshift-config

rm users.htpasswd

oc apply -f - <<EOF
apiVersion: config.openshift.io/v1
kind: OAuth
metadata:
  name: cluster
spec:
  identityProviders:
  - name: my_htpasswd_provider
    mappingMethod: claim
    type: HTPasswd
    htpasswd:
      fileData:
        name: htpass-secret
EOF

# grant admin access to the new user
# technically just enough permissions are needed to invoke LCORE, but this is easier.
oc adm policy add-cluster-role-to-user cluster-admin user1
```

#### Get the api token for the new user

```bash
oc login -u user1 -p <somepassword>

# get the token for the new admin user (you'll need this value later)
oc whoami -t
```

#### Expose a route for the LCORE service

This will allow the lightspeed-eval tool to make direct queries to the LCORE apis from outside the cluster.

```bash
oc apply -f - <<EOF
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  labels:
    app: lightspeed-core
  name: lightspeed-core
  namespace: openshift-aladdin
spec:
  host: lightspeed-core-openshift-aladdin.apps.<your_cluster_domain>
  port:
    targetPort: https
  tls:
    termination: passthrough
  to:
    kind: Service
    name: lightspeed-core
    weight: 100
  wildcardPolicy: None
EOF
```

### Configure lightspeed-evals

#### Set Environment Variables

```bash
# Required: Judge LLM API key (for evaluating responses)
export OPENAI_API_KEY="your-openai-key"

# from oc whoami -t
export API_KEY="your-cluster-api-key"
```

#### Configure Your API Endpoint

Edit `eval/system.yaml` and update these fields:

```yaml
api:
  api_base: "https://<lcore-route-hostname>" # Your API endpoint
  provider: "openai" # Your model provider
  model: "gpt-4o-mini" # Your model name
```

You can get the lcore route hostname (created earlier) via:

```bash
oc get route lightspeed-core -n openshift-aladdin
```

### Run Evaluation

If you have not done so previously, clone the lightspeed-eval repo: https://github.com/lightspeed-core/lightspeed-evaluation

#### Run a single scenario

From the lightspeed-evaluation repository root:

```bash
# Example: run a specific scenario file
uv run lightspeed-eval --system-config <path-to-aladdin-evals-repo>/eval/system.yaml --eval-data <path-to-aladdin-evals-repo>/eval/scenarios/monitoring/cpu_memory.yaml --output-dir <path-to-aladdin-evals-repo>/eval/output
```

#### Run multiple scenarios

Use the test runner script (see "Running Multiple Scenarios" section below).

### Files

- `eval/system.yaml` - System configuration (LLM settings, API endpoint, metrics, output)
- `eval/scenarios/` - Test scenarios organized by category

### Adding More Test Cases

Create or edit scenario files in `eval/scenarios/`:

```yaml
- conversation_group_id: my_new_test
  description: Description of what this tests
  tag: my-tag

  turns:
    - turn_id: turn_1
      query: "Your test question here"
      expected_response: "The expected answer"
      turn_metrics:
        - ragas:response_relevancy
        - custom:answer_correctness
```

---

## Running Multiple Scenarios

For running multiple test scenarios organized by category, use the test runner:

### Test Organization

Tests are organized into category folders:

```
eval/scenarios/
├── monitoring/              # CPU, memory, metrics
└── troubleshooting/         # Pod management, diagnostics
```

### Run Multiple Tests

```bash
# Run all scenarios
python3 run_scenarios.py

# Run specific category
python3 run_scenarios.py --category monitoring

# Run specific scenario
python3 run_scenarios.py --scenario cpu_memory.yaml

# Custom lightspeed-evaluation path
python3 run_scenarios.py --lightspeed-dir /path/to/lightspeed-evaluation
```

### Output Reports

**Per-Scenario Reports:**

```
eval/output/<category>/<scenario_name>_<timestamp>/
├── evaluation_<timestamp>_detailed.csv
├── evaluation_<timestamp>_summary.json
└── <scenario>_amended_<timestamp>.yaml
```

**Consolidated Reports:**

```
eval/output/
├── consolidated_<timestamp>_detailed.csv
├── consolidated_<timestamp>_summary.json
└── consolidated_<timestamp>_summary.txt
```
