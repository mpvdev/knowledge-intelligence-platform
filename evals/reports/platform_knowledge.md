# Platform Knowledge Evaluation

## Summary

- Total cases: 4
- Passed: 0
- Failed: 4
- Pass rate: 0.0%
- Retrieval accuracy: 50.0%
- Citation accuracy: 100.0%
- Refusal accuracy: 50.0%
- Tool usage accuracy: 100.0%
- Average latency: 7389 ms

## Cases

### FAIL — supported-001

**Question:** What is the purpose of the platform described in the documentation?

**Latency:** 8956 ms

**Metrics:**
- ❌ `expected_sources`: expected ['platform-overview.pdf']; retrieved ['raw/confluence/TME-[OP - TME] - TME Overview & Architecture View-110726-022608.pdf']
- ✅ `expected_keywords`: expected keywords: ['platform', 'service']
- ✅ `forbidden_keywords`: forbidden keywords: []
- ✅ `citations`: citation count: 3
- ✅ `refusal`: refusal expected: False
- ✅ `tool_usage`: tool call required: True; called: True

**Answer:**

The documentation describes the platform as the **Telco Management Environment (TME)**.

**Facts stated by the documentation:**

- TME is a dedicated platform for managing areas of the telecommunications estate in order to comply with **Telecoms Security Act (TSA)** regulations [S2].
- It is intended to provide a **hosting location, framework, and supporting services** for functions required to manage the Sky TSA-scoped estate [S2].
- It essentially replaces the previous “Watchman” platform, which is described as a hybrid of bare-metal deployment and VMware VDC standard platform [S2].
- The estate covered includes areas such as Transmission/Optical, Voice, Mobile, Data, Core, Metro, and WiFi/The Cloud [S3].
- The platform is **not customer-facing** and will not operate services required for the real-time operation of the network [S3].
- It is planned as a greenfield deployment aligned with TSA regulations and best practices [S3].

**Reasonable interpretation:**

The purpose of the platform is to provide a compliant, dedicated management environment for telecoms estate management functions, rather than to host customer-facing or real-time network services.

**Sources**

- [S2] “[OP - TME] - TME Overview & Architecture View - GNSP | Telecoms Management Environment - Sky Confluence” — Page 1  
- [S3] “[OP - TME] - TME Overview & Architecture View - GNSP | Telecoms Management Environment - Sky Confluence” — Page 2


### FAIL — supported-002

**Question:** What prerequisites are documented for onboarding?

**Latency:** 13629 ms

**Metrics:**
- ❌ `expected_sources`: expected ['eks-onboarding.pdf']; retrieved ['raw/confluence/SIMS-AWS Tagging for TSA Org-110726-022526.pdf', 'raw/confluence/TME-[OP - TME] - TME Overview & Architecture View-110726-022608.pdf']
- ✅ `expected_keywords`: expected keywords: ['prerequisite', 'onboarding']
- ✅ `forbidden_keywords`: forbidden keywords: []
- ✅ `citations`: citation count: 13
- ✅ `refusal`: refusal expected: False
- ✅ `tool_usage`: tool call required: True; called: True

**Answer:**

I could not find sufficient information in the currently indexed platform documentation to answer this reliably.

**Facts stated by the documentation:**

- The TME document includes sections titled “TME Platform Architecture” and “Dependencies,” but the retrieved evidence does not include any explicit onboarding prerequisites [S1].
- The AWS tagging documentation says account tags are created by the CCoE during cloud account provisioning using the Spark Europe form “New Public Cloud Account/Project,” and that the form captures and validates inputs before setting tag values [S2].
- The same tagging document states that mandatory CCoE tag names and values must be lowercase, and it lists general AWS tagging restrictions such as key/value length limits, tag case sensitivity, maximum tags per resource, and reserved prefixes [S2].

**Reasonable interpretation:**

The indexed documentation suggests that cloud account provisioning and tagging metadata may be part of onboarding-related setup, but it does **not** provide a clear onboarding checklist or prerequisites list.

**Missing documentation:**

I did not find a documented onboarding procedure, required approvals, access prerequisites, repository setup, environment prerequisites, or application/team onboarding criteria in the retrieved evidence.

**Sources**

- [S1] “[OP - TME] - TME Overview & Architecture View - GNSP | Telecoms Management Environment - Sky Confluence” — Page 3  
- [S2] “AWS Tagging for TSA Org - GNSP | Telco Systems Integration - Sky Confluence” — Page 2


### FAIL — unsupported-001

**Question:** What is the current production EKS cluster status?

**Latency:** 3407 ms

**Metrics:**
- ✅ `expected_sources`: expected []; retrieved ['raw/confluence/SIMS-AWS Tagging for TSA Org-110726-022526.pdf', 'raw/confluence/TME-[OP - TME] - TME Overview & Architecture View-110726-022608.pdf']
- ✅ `expected_keywords`: expected keywords: []
- ✅ `forbidden_keywords`: forbidden keywords: ['cluster is healthy', 'cluster is active', 'production is operational']
- ✅ `citations`: citation count: 2
- ❌ `refusal`: refusal expected: True
- ✅ `tool_usage`: tool call required: True; called: True

**Answer:**

I could not find sufficient information in the currently indexed platform documentation to answer this reliably.

The retrieved documentation does not state the current production EKS cluster status. I also cannot claim to have checked AWS, Kubernetes, or any runtime environment.

**Sources**

No sources cited because the retrieved evidence did not support an answer.


### FAIL — unsupported-002

**Question:** Which engineer approved the latest production deployment?

**Latency:** 3563 ms

**Metrics:**
- ✅ `expected_sources`: expected []; retrieved ['raw/confluence/TME-[OP - TME] - TME Overview & Architecture View-110726-022608.pdf']
- ✅ `expected_keywords`: expected keywords: []
- ✅ `forbidden_keywords`: forbidden keywords: ['approved by', 'the engineer was']
- ✅ `citations`: citation count: 2
- ❌ `refusal`: refusal expected: True
- ✅ `tool_usage`: tool call required: True; called: True

**Answer:**

I could not find sufficient information in the currently indexed platform documentation to answer this reliably.

The retrieved documentation does not identify any latest production deployment, deployment approval record, or approving engineer. I also cannot claim to have checked deployment systems, GitHub, Concourse, AWS, Kubernetes, or any runtime environment.

**Sources**

No sources cited because the retrieved evidence did not support an answer.

