

import os

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")

import asyncio
import time
import sys
from pathlib import Path
from typing import Optional, Type
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from deepeval.models import DeepEvalBaseLLM


GROQ_EVAL_MODEL = os.getenv("GROQ_EVAL_MODEL", "qwen/qwen3.8-27b")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
INTER_REQUEST_SLEEP = float(os.getenv("GROQ_EVAL_SLEEP_SECONDS", "2"))


class GroqDeepEvalModel(DeepEvalBaseLLM):
    """
    Wraps LangChain's ChatGroq so DeepEval can use Groq for metric scoring.
    """

    def __init__(
        self,
        model: str = GROQ_EVAL_MODEL,
        api_key: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ):
        self.model_name = model
        self.api_key = api_key or GROQ_API_KEY
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client: Optional[ChatGroq] = None

    def get_model_name(self) -> str:
        return self.model_name

    def load_model(self) -> ChatGroq:
        if self._client is None:
            self._client = ChatGroq(
                model=self.model_name,
                api_key=self.api_key,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        return self._client

    def generate(self, prompt: str, schema=None):
        """Synchronous text generation
        """
        client = self.load_model()

        for attempt in range(1, 4):
            try:
                if INTER_REQUEST_SLEEP > 0:
                    time.sleep(INTER_REQUEST_SLEEP)

                if schema is not None:
                    try:
                        structured_client = client.with_structured_output(schema)
                        result = structured_client.invoke(
                            [HumanMessage(content=prompt)]
                        )
                        return result
                    except (NotImplementedError, ValueError, TypeError):
                        pass
                    except Exception as struct_exc:
                        err_lower = str(struct_exc).lower()
                        if any(k in err_lower for k in ("tool", "function", "schema", "json")):
                            pass  # fall through to plain text
                        else:
                            raise
                response = client.invoke([HumanMessage(content=prompt)])
                return response.content

            except Exception as exc:
                err = str(exc).lower()
                if "429" in err or "rate limit" in err or "rate_limit" in err:
                    wait = 2 ** attempt * 10  # 20s, 40s, 80s
                    print(
                        f"  [GroqDeepEvalModel] Rate limit on attempt "
                        f"{attempt}/3. Sleeping {wait}s ..."
                    )
                    time.sleep(wait)
                else:
                    raise

        raise RuntimeError(
            f"[GroqDeepEvalModel] Groq rate limit persisted after 3 retries "
            f"for model '{self.model_name}'. "
            f"Try setting GROQ_EVAL_SLEEP_SECONDS=10 in your .env file."
        )

    async def a_generate(self, prompt: str, schema=None):
        """Async generation — runs the synchronous generate() in a thread pool
        to avoid blocking the event loop.
        """
        return await asyncio.to_thread(self.generate, prompt, schema)
