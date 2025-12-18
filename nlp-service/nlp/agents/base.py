"""
Base ADK agent classes for health & appointment domain.
Extends google.adk.agents with nlp-service integration.

Phase 1: Foundation - ADK agents + nlp-service bridge
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
import logging
import uuid

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base agent class for all health domain agents.
    This is a local implementation that bridges to Google ADK patterns.
    """
    
    def __init__(
        self,
        name: str,
        model: str = "gemini-2.5-pro",
        description: str = "",
        instruction: str = ""
    ):
        self.id = str(uuid.uuid4())
        self.name = name
        self.model = model
        self.description = description
        self.instruction = instruction
        self.created_at = datetime.now()
        self.audit_trail: List[Dict[str, Any]] = []
        logger.info(f"Initialized {self.__class__.__name__}: {name}")
    
    def log_action(self, action_type: str, details: str = "") -> None:
        """
        Log an action to the audit trail.
        
        Args:
            action_type: Type of action being logged
            details: Additional details about the action
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action_type": action_type,
            "details": details,
            "agent": self.name
        }
        self.audit_trail.append(log_entry)
        if details:
            logger.info(f"{action_type}: {details}")
        else:
            logger.info(action_type)
    
    async def run(self, input_data: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run agent processing on input data.
        Override in subclasses for specific behavior.
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.name,
            "action": "run",
            "input_type": type(input_data).__name__
        }
        self.audit_trail.append(log_entry)
        return {"status": "success", "data": input_data}
    
    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """Return audit trail for compliance logging."""
        return self.audit_trail


class HealthAgent(BaseAgent):
    """Base health data agent with HIPAA compliance."""
    
    def __init__(self, name: str, **kwargs):
        super().__init__(
            name=name,
            model="gemini-2.5-pro",
            description="HIPAA-compliant health agent",
            instruction="""You are a healthcare assistant with the following constraints:
- ALWAYS respect HIPAA privacy requirements
- NEVER store raw sensitive data in logs
- ALWAYS verify patient identity before sharing records
- RECOMMEND professional medical consultation for serious conditions
- MAINTAIN audit trail of all health data access
- Be empathetic and supportive
- Ask clarifying questions to understand health concerns""",
            **kwargs
        )
        self.phi_access_log: List[Dict[str, Any]] = []
    
    async def process_health_data(
        self,
        data: Dict[str, Any],
        user_id: str,
        patient_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process health data with audit logging."""
        # Log access for HIPAA compliance
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "patient_id": patient_id[:8] + "..." if patient_id else None,
            "action": "process_health_data",
            "data_type": list(data.keys()),
            "phi_fields": self._identify_phi_fields(data)
        }
        self.phi_access_log.append(log_entry)
        self.audit_trail.append(log_entry)
        
        logger.info(f"Health data processed by {self.name}: {len(data)} fields")
        
        # Process through LLM simulation (will integrate with actual Gemini later)
        response = await self.run(data)
        return response
    
    def _identify_phi_fields(self, data: Dict[str, Any]) -> List[str]:
        """Identify Protected Health Information (PHI) fields."""
        phi_indicators = [
            'patient_id', 'name', 'ssn', 'medical_record_number',
            'health_condition', 'medication', 'diagnosis', 'treatment',
            'vitals', 'heart_rate', 'blood_pressure', 'temperature'
        ]
        return [k for k in data.keys() if any(phi in k.lower() for phi in phi_indicators)]
    
    def get_phi_access_log(self) -> List[Dict[str, Any]]:
        """Return PHI access log for audit purposes."""
        return self.phi_access_log


class AppointmentAgent(BaseAgent):
    """Base appointment management agent."""
    
    def __init__(self, name: str, **kwargs):
        super().__init__(
            name=name,
            model="gemini-2.0-flash",
            description="Medical appointment scheduling agent",
            instruction="""You are a medical appointment assistant.
- CONFIRM availability before booking
- ALWAYS send confirmation to patient
- CHECK for conflicts
- HANDLE cancellations and rescheduling
- PROVIDE appointment reminders
- Be professional and courteous
- Manage appointment workflow efficiently""",
            **kwargs
        )
        self.appointments_managed: List[Dict[str, Any]] = []
    
    async def manage_appointment(
        self,
        appointment_data: Dict[str, Any],
        action: str = "book"
    ) -> Dict[str, Any]:
        """Manage appointment workflow (book, reschedule, cancel)."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.name,
            "action": action,
            "appointment_id": appointment_data.get("appointment_id", "new"),
            "patient_id": appointment_data.get("patient_id")
        }
        self.appointments_managed.append(log_entry)
        self.audit_trail.append(log_entry)
        
        result = await self.run(appointment_data)
        return result
    
    def get_appointments_log(self) -> List[Dict[str, Any]]:
        """Return appointment management log."""
        return self.appointments_managed


class SequentialAgent(BaseAgent):
    """
    Sequential agent that runs multiple agents in order.
    Based on ADK sequential pattern (10-sequential-agent).
    """
    
    def __init__(
        self,
        name: str,
        agents: List[BaseAgent],
        description: str = ""
    ):
        super().__init__(
            name=name,
            description=description or f"Sequential orchestrator with {len(agents)} agents"
        )
        self.agents = agents
        self.execution_log: List[Dict[str, Any]] = []
    
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agents sequentially, passing output to next agent."""
        logger.info(f"Starting sequential execution: {self.name}")
        current_data = input_data
        execution_record = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.name,
            "total_agents": len(self.agents),
            "steps": []
        }
        
        try:
            for i, agent in enumerate(self.agents):
                logger.info(f"Executing step {i+1}/{len(self.agents)}: {agent.name}")
                
                step_start = datetime.now()
                current_data = await agent.run(current_data)
                step_duration = (datetime.now() - step_start).total_seconds()
                
                step_record = {
                    "step": i + 1,
                    "agent": agent.name,
                    "duration_seconds": step_duration,
                    "success": current_data.get("status") == "success"
                }
                execution_record["steps"].append(step_record)
                
                # Check for errors
                if not step_record["success"]:
                    logger.warning(f"Step {i+1} did not complete successfully")
                    break
            
            execution_record["status"] = "completed"
            self.execution_log.append(execution_record)
            self.audit_trail.append(execution_record)
            
            return {
                "status": "success",
                "orchestrator": self.name,
                "data": current_data,
                "execution": execution_record
            }
        
        except Exception as e:
            logger.error(f"Error in sequential execution: {e}")
            execution_record["status"] = "failed"
            execution_record["error"] = str(e)
            self.execution_log.append(execution_record)
            
            return {
                "status": "error",
                "orchestrator": self.name,
                "error": str(e),
                "execution": execution_record
            }
    
    def get_execution_log(self) -> List[Dict[str, Any]]:
        """Return execution log for monitoring."""
        return self.execution_log


class ParallelAgent(BaseAgent):
    """
    Parallel agent that runs multiple agents concurrently.
    Based on ADK parallel pattern (11-parallel-agent).
    """
    
    def __init__(
        self,
        name: str,
        agents: List[BaseAgent],
        description: str = ""
    ):
        super().__init__(
            name=name,
            description=description or f"Parallel orchestrator with {len(agents)} agents"
        )
        self.agents = agents
        self.execution_log: List[Dict[str, Any]] = []
    
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agents in parallel."""
        import asyncio
        
        logger.info(f"Starting parallel execution: {self.name}")
        execution_record = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.name,
            "total_agents": len(self.agents),
            "agents": []
        }
        
        try:
            # Run all agents concurrently
            tasks = [agent.run(input_data) for agent in self.agents]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            combined_results = {}
            for agent, result in zip(self.agents, results):
                if isinstance(result, Exception):
                    logger.error(f"Agent {agent.name} failed: {result}")
                    combined_results[agent.name] = {"status": "error", "error": str(result)}
                else:
                    combined_results[agent.name] = result
                    execution_record["agents"].append({
                        "agent": agent.name,
                        "status": result.get("status", "unknown")
                    })
            
            execution_record["status"] = "completed"
            self.execution_log.append(execution_record)
            self.audit_trail.append(execution_record)
            
            return {
                "status": "success",
                "orchestrator": self.name,
                "results": combined_results,
                "execution": execution_record
            }
        
        except Exception as e:
            logger.error(f"Error in parallel execution: {e}")
            execution_record["status"] = "failed"
            execution_record["error"] = str(e)
            self.execution_log.append(execution_record)
            
            return {
                "status": "error",
                "orchestrator": self.name,
                "error": str(e),
                "execution": execution_record
            }


class HealthAppointmentOrchestrator(SequentialAgent):
    """
    Orchestrate complete health data collection + appointment booking workflow.
    Multi-step process:
    1. Collect health data from user
    2. Validate health information
    3. Classify appointment type
    4. Book appointment
    5. Send confirmation
    """
    
    def __init__(self):
        # Create specialized agents for each step
        health_collector = HealthAgent(name="HealthDataCollector")
        health_validator = HealthAgent(name="HealthValidator")
        appointment_classifier = AppointmentAgent(name="AppointmentClassifier")
        appointment_booker = AppointmentAgent(name="AppointmentBooker")
        
        super().__init__(
            name="HealthAppointmentOrchestrator",
            description="Manage complete health-to-appointment workflow",
            agents=[
                health_collector,
                health_validator,
                appointment_classifier,
                appointment_booker
            ]
        )


# For type hints
from typing import Union
