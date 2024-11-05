import warnings

import pytest
import pytest_asyncio

import choreographer as choreo


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def session(browser):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", choreo.protocol.ExperimentalFeatureWarning)
        session_browser = await browser.create_session()
    yield session_browser
    await browser.close_session(session_browser)


@pytest.mark.asyncio
async def test_session_send_command(session):
    # Test int method should return error
    with pytest.raises(
        choreo.protocol.MessageTypeError,
        match="Message with key method must have type <class 'str'>, not <class 'int'>.",
    ):
        await session.send_command(command=12345)

    # Test valid request with correct command
    response = await session.send_command(command="Target.getTargets")
    assert "result" in response and "targetInfos" in response["result"]

    # Test invalid method name should return error
    response = await session.send_command(command="dkadklqwmd")
    assert "error" in response
