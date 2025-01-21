"""Provide a lower-level async interface to the Devtools Protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import logistro

from choreographer import protocol
from choreographer._brokers import Broker

if TYPE_CHECKING:
    from collections.abc import MutableMapping
    from typing import Any


_logger = logistro.getLogger(__name__)


class Session:
    """A session is a single conversation with a single target."""

    _broker_type = Broker
    # A list of the types that are essential to use
    # with this class

    session_id: str
    """The id of the session given by the browser."""
    message_id: int
    """All messages are counted per session and this is the current message id."""

    def __init__(self, session_id: str, broker: Broker) -> None:
        """
        Construct a session from the browser as an object.

        A session is like an open conversation with a target.
        All commands are sent on sessions.

        Args:
            broker:  a reference to the browser's broker
            session_id:  the id given by the browser

        """
        if not isinstance(session_id, str):
            raise TypeError("session_id must be a string")
        # Resources
        self._broker = broker

        # State
        self.session_id = session_id
        _logger.debug(f"New session: {session_id}")
        self.message_id = 0

    async def send_command(
        self,
        command: str,
        params: MutableMapping[str, Any] | None = None,
    ) -> Any:
        """
        Send a devtools command on the session.

        https://chromedevtools.github.io/devtools-protocol/

        Args:
            command: devtools command to send
            params: the parameters to send

        Returns:
            A message key (session, message id) tuple or None

        """
        current_id = self.message_id
        self.message_id += 1
        json_command = protocol.BrowserCommand(
            {
                "id": current_id,
                "method": command,
            },
        )

        if self.session_id:
            json_command["sessionId"] = self.session_id
        if params:
            json_command["params"] = params
        _logger.debug(
            f"Sending {command} with {params} on session {self.session_id}",
        )
        return await self._broker.write_json(json_command)


class Target:
    """A target like a browser, tab, or others. It sends commands. It has sessions."""

    _session_type = Session
    _broker_type = Broker
    """Needs to know."""

    target_id: str
    """The browser's ID of the target."""
    sessions: MutableMapping[str, Session]
    """A list of all the sessions for this target."""

    def __init__(self, target_id: str, broker: Broker):
        """
        Create a target after one ahs been created by the browser.

        Args:
            broker:  a reference to the browser's broker
            target_id:  the id given by the browser

        """
        if not isinstance(target_id, str):
            raise TypeError("target_id must be string")
        # Resources
        self._broker = broker

        # States
        self.sessions = {}
        self.target_id = target_id
        _logger.info(f"Created new target {target_id}.")

    def _add_session(self, session: Session) -> None:
        if not isinstance(session, self._session_type):
            raise TypeError("session must be a session type class")
        self.sessions[session.session_id] = session

    def _remove_session(self, session_id: str) -> None:
        if isinstance(session_id, self._session_type):
            session_id = session_id.session_id
        _ = self.sessions.pop(session_id, None)

    def get_session(self) -> Session:
        """Retrieve the first session of the target, if it exists."""
        if not self.sessions.values():
            raise RuntimeError(
                "Cannot use this method without at least one valid session",
            )
        session = next(iter(self.sessions.values()))
        return session

    async def send_command(
        self,
        command: str,
        params: MutableMapping[str, Any] | None = None,
    ) -> Any:
        """
        Send a command to the first session in a target.

        https://chromedevtools.github.io/devtools-protocol/

        Args:
            command: devtools command to send
            params: the parameters to send

        """
        if not self.sessions.values():
            raise RuntimeError("Cannot send_command without at least one valid session")
        session = self.get_session()
        _logger.debug(
            f"Sending {command} with {params} on session {session.session_id}",
        )
        return await session.send_command(command, params)

    async def create_session(self) -> Session:
        """Create a new session on this target."""
        response = await self._broker._browser.send_command(  # noqa: SLF001 yeah we need the browser :-(
            "Target.attachToTarget",
            params={"targetId": self.target_id, "flatten": True},
        )
        if "error" in response:
            raise RuntimeError(
                "Could not create session",
            ) from protocol.DevtoolsProtocolError(
                response,
            )
        session_id = response["result"]["sessionId"]
        new_session = Session(session_id, self._broker)
        self._add_session(new_session)
        return new_session

    # async only
    async def close_session(
        self,
        session_id: str,
    ) -> protocol.BrowserResponse:
        """
        Close a session by session_id.

        Args:
            session_id: the session to close

        """
        if isinstance(session_id, Session):
            session_id = session_id.session_id
        response = await self._broker._browser.send_command(  # noqa: SLF001 we need browser
            command="Target.detachFromTarget",
            params={"sessionId": session_id},
        )

        self._remove_session(session_id)
        if "error" in response:
            raise RuntimeError(
                "Could not close session",
            ) from protocol.DevtoolsProtocolError(
                response,
            )
        _logger.debug(f"The session {session_id} has been closed")
        return cast(protocol.BrowserResponse, response)
        # kinda hate, why do we need this again?
