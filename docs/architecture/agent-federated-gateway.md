🕸️ Federated Agent: Symmetric Node Representation

🎯 Simplified Concept

A Federated Agent is a symmetric proxy that represents an entire external node as a single reactive agent in the local node. Each inter-node connection is a pair of symmetric agents.

```mermaid
graph TB
    subgraph "Node A"
        UA1[User A1] --> NA[Node A Core]
        UA2[User A2] --> NA
        NA --> FAB[Federated Agent B]
    end
    
    subgraph "Node B" 
        UB1[User B1] --> NB[Node B Core]
        UB2[User B2] --> NB
        NB --> FBA[Federated Agent A]
    end
    
    FAB <-.->|symmetric connection| FBA
    
    style FAB fill:#fff8e1
    style FBA fill:#fff8e1
```

📊 Federated Agent Structure

Federated Agent Profile

```yaml
FederatedAgent:
  id: UUID
  local_node_id: UUID          # Local node ID
  remote_node_id: UUID         # Remote node ID
  remote_node_info: NodeInfo   # Remote node information
  connection_status: ConnectionStatus
  last_sync: Timestamp

NodeInfo:
  name: String                 # Human-readable node name
  domain: String               # Thematic focus
  endpoint: String             # Base API URL
  capabilities: NodeCapabilities
  public_key: String           # For verification

NodeCapabilities:
  user_count: Integer
  skill_distribution: Map[String, Float]
  supported_categories: List[String]
  avg_response_time: Float
```

🔄 Symmetric Interaction

Scenario 1: Creating Federated Connection

```mermaid
sequenceDiagram
    participant A as Node A
    participant B as Node B
    participant FAB as Federated Agent B in A
    participant FBA as Federated Agent A in B

    A->>B: POST /federation/connect
    Note over A,B: {node_info, public_key, capabilities}
    
    B->>B: Validation and creation of federated agent A
    B->>A: 201 Created
    Note over B,A: {agent_id, node_info, federation_token}
    
    A->>A: Creation of federated agent B
    A->>B: PUT /federation/agents/{id}/ready
    B->>B: Activation of federated agent A
    
    Note over A,B: Both federated agents active
```

Scenario 2: Task Transfer via Federated Agent

```mermaid
sequenceDiagram
    participant UA as Node A User
    participant NA as Node A
    participant FAB as Federated Agent B
    participant FBA as Federated Agent A
    participant NB as Node B
    participant UB as Node B User

    UA->>NA: POST /tasks
    Note over UA,NA: Task creation
    
    NA->>NA: Local task publication
    NA->>FAB: GET /tasks/available (optional)
    FAB->>FAB: Determines task is suitable for Node B
    
    alt Direct sending
        NA->>FAB: POST /tasks (via standard agent API)
        Note over NA,FAB: {task, author: UA, context}
    else Reactive model
        FBA->>NB: Periodic polling of tasks from Node A
        NB->>FBA: Task list
        FBA->>NB: Selection and task reservation
    end
    
    FAB->>FBA: Task transfer (inter-node API)
    FBA->>NB: POST /tasks (as standard agent)
    Note over FBA,NB: {task, author: FBA, metadata: {original_node: A}}
    
    NB->>NB: Task publication for local agents
    UB->>NB: GET /tasks/available
    NB->>UB: Task from federated agent A
    UB->>NB: POST /tasks/{id}/claim
    NB->>UB: Task context
    UB->>NB: PUT /tasks/{id}/solution
    NB->>FBA: Solution delivery (via standard API)
    FBA->>FAB: Solution transfer (inter-node API)
    FAB->>NA: Solution delivery to Node A
    NA->>UA: Solution notification
```

Scenario 3: Reactive Federated Agent Operation

```mermaid
sequenceDiagram
    participant FAB as Federated Agent B in A
    participant NA as Node A
    participant FBA as Federated Agent A in B
    participant NB as Node B

    loop Every 10 minutes
        FAB->>NA: GET /tasks/available?categories=physics,research
        NA->>FAB: List of suitable tasks
        
        FAB->>FAB: Filtering by relevance for Node B
        FAB->>FBA: Transfer of filtered tasks
        FBA->>NB: Publication of tasks as from federated agent
        
        FBA->>NB: GET /tasks/available?categories=writing,creative
        NB->>FBA: List of suitable tasks
        FBA->>FBA: Filtering for Node A
        FBA->>FAB: Transfer of filtered tasks
        FAB->>NA: Publication of tasks as from federated agent
    end
```

🛠️ Technical Implementation

Federated Agent API (Standard + Extended)

```yaml
# Standard agent endpoints
POST   /tasks                   # Create task
GET    /tasks/available         # Get available tasks
POST   /tasks/{id}/claim        # Reserve task
PUT    /tasks/{id}/solution     # Submit solution

# Specific federated agent endpoints
GET    /federation/status       # Connection status
PUT    /federation/capabilities # Update capabilities
POST   /federation/sync         # Force synchronization
```

Connection Configuration

```yaml
FederationConfig:
  remote_node_endpoint: "https://node-b.meownet/api"
  sync_interval: "10m"         # Synchronization interval
  task_categories: List[String] # Categories for exchange
  max_complexity: 8            # Max complexity of exchanged tasks
  trust_level: "verified"      # Trust level
  auto_accept_tasks: Boolean   # Automatically accept tasks
```

🎯 Advantages of Symmetric Approach

Implementation Simplicity:

· Unified Model - federated agent uses same API as regular agents
· Symmetry - each node sees another node as a single agent
· Scalability - new agent created for connecting to new node

Flexibility:

· Isolation - problems with one node don't affect other connections
· Configuration - different parameters can be configured for each node pair
· Evolution - easy to add new nodes without architectural changes

Security:

· Trust Isolation - each node pair has separate trust settings
· Access Control - fine-grained control over which tasks to transfer
· Auditing - easy to track interactions between specific nodes

🔄 Alternative Scenarios

Multiple Connections to One Node:

```mermaid
graph TB
    subgraph "Node A"
        FAB1[Fed. Agent B v1] --> NA[Node A Core]
        FAB2[Fed. Agent B v2] --> NA
    end
    
    subgraph "Node B"
        FBA1[Fed. Agent A v1] --> NB[Node B Core]
        FBA2[Fed. Agent A v2] --> NB
    end
    
    FAB1 <-.-> FBA1
    FAB2 <-.-> FBA2
    
    style FAB1 fill:#e8f5e8
    style FAB2 fill:#e8f5e8
    style FBA1 fill:#e8f5e8
    style FBA2 fill:#e8f5e8
```

Applications:

· Different trust levels (public vs private tasks)
· Different thematic directions
· Redundancy and load balancing

💡 Key Principles

Federated Agent IS:

· ✅ Symmetric Proxy - represents entire remote node as unified whole
· ✅ Reactive Participant - operates by same rules as regular agents
· ✅ Isolated Connection - problems in one connection don't affect others
· ✅ Transparent Bridge - users see only original task and solution

Federated Agent IS NOT:

· ❌ Intelligent Router - doesn't make complex decisions about where to send tasks
· ❌ Decision Maker - doesn't make complex routing decisions
· ❌ Architecture Violator - doesn't break "one node - one agent" principle per connection

This approach ensures simplicity, predictability, and scalability of federated architecture while preserving all the power of decentralized collaboration between specialized communities.
