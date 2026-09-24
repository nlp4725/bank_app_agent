"""The Discovery Run: the one package where a model is in the loop.

`propose_contract` turns a goal in words into a Contract and a Role for a Reviewer to
confirm; `discover` then drives the app one policy-checked action per turn and hands a
successful run to the Recorder. Nothing in `cua.replay` can reach this package.
"""

from .propose import ProposalError, propose_contract, spec_from_proposal
from .request import DiscoveryRequest, DiscoveryResult
from .model import MODEL, Model, ToolCall, Turn
from .run import discover, observation

__all__ = ["MODEL", "DiscoveryRequest", "DiscoveryResult", "Model", "ProposalError", "ToolCall",
           "Turn", "discover", "observation", "propose_contract", "spec_from_proposal"]
