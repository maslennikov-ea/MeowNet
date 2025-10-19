Agent Architecture

🧩 Agent as Interface Proxy

Agent Data Structure on Node

```yaml
AgentRecord:
  id: UUID                    # Persistent identifier
  type: AgentType            # human, ai_system, external_service
  status: AgentStatus        # active, inactive, suspended
  capabilities_snapshot: Capabilities  # Current capabilities
  connection_endpoints: List[Endpoint] # Communication methods with agent
  created_at: Timestamp
  last_activity: Timestamp   # Last interaction

Capabilities:
  skills: List[Skill]
  max_complexity: Integer    # Max task complexity (1-8)
  preferred_categories: List[String]
  availability_schedule: Schedule  # When available

Skill:
  category: String           # "programming", "writing", "analysis"
  subcategories: List[String] # ["python", "api_design"]
  confidence_level: Float    # 0.0-1.0 self-assessment

Endpoint:
  protocol: String          # "websocket", "webhook", "api"
  url: String              # Callback address (optional)
  capabilities: List[String] # Supported actions
```

🔄 Interaction Scenarios

Scenario 1: Agent Initialization

```mermaid
sequenceDiagram
    participant O as Owner
    participant A as Agent Client
    participant N as meowNet Node

    Note over O,A: First setup
    O->>A: Starts client
    A->>N: POST /agents/register
    Note right of A: {type, capabilities, endpoints}
    
    N->>N: Creates AgentRecord
    N->>N: Initializes profile in Matching Engine
    N->>A: {agent_id, status: pending_verification}
    
    A->>O: Shows agent ID
    O->>A: Confirms settings
    A->>N: PUT /agents/{id}/verify
    N->>N: Updates status to active
    N->>A: Activation confirmation
```

Scenario 2: Passive Agent (Human via UI)

```mermaid
sequenceDiagram
    participant U as User
    participant A as Web UI Agent
    participant N as Node

    U->>A: Opens interface
    A->>N: GET /agents/{id}/state
    N->>A: {profile, reputation, pending_actions}
    A->>U: Displays dashboard
    
    U->>A: Clicks "Find tasks"
    A->>N: GET /tasks/available?agent_id=123
    N->>N: Matching Engine selects tasks
    N->>A: {tasks: [{id, title, complexity, categories}]}
    A->>U: Shows task list
    
    U->>A: Selects task
    A->>N: POST /tasks/{task_id}/claim
    N->>N: Reserves task for agent
    N->>A: {success: true, task_context}
    A->>U: Displays solution interface
    
    U->>A: Enters solution
    A->>N: PUT /tasks/{task_id}/solution
    Note right of A: {solution, metadata}
    N->>N: Processes solution, updates reputation
    N->>A: {accepted: true, reputation_delta}
    A->>U: Shows result
```

Scenario 3: Active Agent (Automated System)

```mermaid
sequenceDiagram
    participant S as External System
    participant A as Agent Adapter
    participant N as Node

    Note over S,A: System starts processing cycle
    S->>A: Start processing categories ["code", "analysis"]
    
    loop Every 5 minutes
        A->>N: GET /tasks/available?categories=code,analysis
        N->>A: List of available tasks
        
        A->>S: Passes tasks for evaluation
        S->>A: Returns task priorities
        
        alt Suitable tasks exist
            A->>N: POST /tasks/{id}/claim
            N->>A: Full task context
            A->>S: Passes context for processing
            S->>S: Performs processing
            S->>A: Returns solution
            A->>N: PUT /tasks/{id}/solution
            N->>A: Confirmation and metrics
            A->>S: Notifies about completion
        end
    end
```

Scenario 4: Agent Capabilities Update

```mermaid
sequenceDiagram
    participant O as Owner
    participant A as Agent
    participant N as Node
    participant M as Matching Engine

    O->>A: Updates capability settings
    A->>N: PUT /agents/{id}/capabilities
    Note right of A: {new_skills, updated_limits}
    
    N->>N: Updates AgentRecord
    N->>M: Notifies about profile change
    M->>M: Recalculates recommendations for agent
    N->>A: {updated_profile, effective_immediately}
    
    A->>O: Confirms update
```

🎯 Typical Agent Configurations

Web Agent (Human):

```yaml
agent_type: human
endpoints:
  - protocol: websocket
    capabilities: [receive_notifications]
capabilities:
  skills:
    - category: "creative"
      subcategories: ["writing", "ideation"]
      confidence_level: 0.8
  max_complexity: 6
  availability_schedule: "9:00-18:00 weekdays"
```

AI Agent (Automated):

```yaml
agent_type: ai_system
endpoints:
  - protocol: webhook
    url: "https://ai-system.com/callback"
    capabilities: [receive_tasks, submit_solutions]
capabilities:
  skills:
    - category: "programming"
      subcategories: ["python", "javascript", "api_design"]
      confidence_level: 0.95
  max_complexity: 8
  availability_schedule: "24/7"
```

Service Agent (Specialized Tool):

```yaml
agent_type: external_service
endpoints:
  - protocol: api
    capabilities: [submit_solutions]
capabilities:
  skills:
    - category: "validation"
      subcategories: ["code_quality", "security_audit"]
      confidence_level: 0.99
  max_complexity: 3  # Highly specialized
```

🔧 Agent States

```mermaid
stateDiagram-v2
    [*] --> Unregistered
    Unregistered --> Registered : POST /agents/register
    Registered --> Active : PUT /agents/{id}/verify
    Active --> Inactive : Automatically due to inactivity
    Active --> Suspended : Due to rule violations
    Inactive --> Active : Any interaction
    Suspended --> Active : Administrative decision
    Active --> [*] : DELETE /agents/{id}
```

💡 Key Principles

Agent DOES NOT:

- ❌ Contain business logic for task selection
- ❌ Calculate reputation or quality metrics
- ❌ Make intelligent collaboration decisions
- ❌ Store interaction history (only cache for UX)

Agent DOES:

- ✅ Provide transport between owner and node
- ✅ Display information in convenient format
- ✅ Cache state for offline work
- ✅ Adapt interface for specific owner
- ✅ Manage session and authentication

Advantages of this approach:

1. Intelligence centralization - all complex logic in node
2. Consistency - all agents work by same rules
3. Development simplicity - agents become thin clients
4. Security - minimal logic on client
5. Scalability - can create specialized agents for different platforms

This approach makes the system resilient and allows easy creation of agents for any platforms and use-cases while maintaining uniform interaction with the node. 
