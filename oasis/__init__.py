# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
# Licensed under the Apache License, Version 2.0 (the “License”);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an “AS IS” BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
__version__ = "0.2.5"

from oasis import aoasis, atherum
from oasis.aoasis import (AOASIS_EXECUTION_MODES,
                           AOASIS_SUPPORTED_PLATFORMS, AOASIS_VARIANT_NAME,
                           ATHERUM_DEFAULT_ARCHETYPES, AOasisEvidenceSummary,
                           AOasisPlatformOutput, AOasisPreparedRun,
                           AOasisRunConfig, AOasisRunResult,
                           AOasisWorkerError, AOasisWorkerService,
                           AOasisSocialAction, AOasisSocialComment,
                           AOasisSocialPost, AOasisCostEstimate,
                           AtherumAgentArchetype, AtherumPopulationStore,
                           MODEL_TOKEN_RATES_USD_PER_MILLION,
                           PersistentAgentProfile, PersistentAgentState,
                           PersistentPopulationSnapshot,
                           build_default_population,
                           build_evidence_summary,
                           build_graph_from_population,
                           build_scribe_markdown,
                           build_worker_result,
                           estimate_run_cost,
                           execute_aoasis_run,
                           extract_memory_updates_from_trace,
                           finalize_aoasis_run,
                           make_aoasis_worker_server,
                           normalize_platform_db,
                           platform_action_policy,
                           prepare_aoasis_run)
from oasis.environment.env_action import LLMAction, ManualAction
from oasis.environment.make import make
from oasis.social_agent import (generate_reddit_agent_graph,
                                generate_twitter_agent_graph)
from oasis.social_agent.agent import SocialAgent
from oasis.social_agent.agent_graph import AgentGraph
from oasis.social_platform.config import UserInfo
from oasis.social_platform.platform import Platform
from oasis.social_platform.typing import ActionType, DefaultPlatformType
from oasis.testing.show_db import print_db_contents

__all__ = [
    "make", "Platform", "ActionType", "DefaultPlatformType", "ManualAction",
    "LLMAction", "print_db_contents", "AgentGraph", "SocialAgent", "UserInfo",
    "generate_reddit_agent_graph", "generate_twitter_agent_graph",
    "AtherumPopulationStore", "PersistentAgentProfile",
    "PersistentAgentState", "PersistentPopulationSnapshot",
    "ATHERUM_DEFAULT_ARCHETYPES", "AtherumAgentArchetype",
    "AOASIS_EXECUTION_MODES", "AOASIS_SUPPORTED_PLATFORMS",
    "AOASIS_VARIANT_NAME",
    "AOasisEvidenceSummary", "AOasisPlatformOutput", "AOasisPreparedRun",
    "AOasisRunConfig", "AOasisRunResult",
    "AOasisWorkerError", "AOasisWorkerService",
    "AOasisSocialAction", "AOasisSocialComment", "AOasisSocialPost",
    "AOasisCostEstimate", "MODEL_TOKEN_RATES_USD_PER_MILLION",
    "build_default_population", "build_evidence_summary",
    "build_graph_from_population", "build_scribe_markdown", "aoasis",
    "build_worker_result",
    "atherum",
    "estimate_run_cost", "execute_aoasis_run",
    "extract_memory_updates_from_trace", "finalize_aoasis_run",
    "normalize_platform_db", "platform_action_policy", "prepare_aoasis_run",
    "make_aoasis_worker_server"
]
