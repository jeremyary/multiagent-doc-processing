# This project was developed with assistance from AI tools.
from abc import ABC, abstractmethod
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from config import config
from models import WorkflowState


class BaseAgent(ABC):
    """Base class for all agents in the workflow."""
    
    def __init__(self, name: str, model: str | None = None):
        self.name = name
        self.model_name = model or config.OPENAI_MODEL
        self._llm: ChatOpenAI | None = None
    
    @property
    def llm(self) -> ChatOpenAI:
        """Lazy initialization of the LLM."""
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=self.model_name,
                api_key=config.OPENAI_API_KEY,
                base_url=config.OPENAI_BASE_URL,
                temperature=config.LLM_TEMPERATURE,
            )
        return self._llm
    
    @abstractmethod
    def run(self, state: WorkflowState, config: RunnableConfig) -> dict:
        """Execute the agent's main logic. config contains callbacks for tracing."""
        pass
    
    def log(self, message: str) -> None:
        """Log a message with agent context."""
        print(f"[{self.name}] {message}")
